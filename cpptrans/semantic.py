import builtins
import keyword

from . import nodes as N
from .errors import CompileError

NUMERIC = ('int', 'double', 'bool')
PY_TAKEN = set(keyword.kwlist) | set(dir(builtins)) | {'sys', 'main'}


class Symbol:
    def __init__(self, name, type, kind, size=None, is_global=False):
        self.name = name
        self.type = type
        self.kind = kind
        self.size = size
        self.is_global = is_global
        self.pyname = name

    @property
    def is_array(self):
        return self.kind == 'array' or self.type.endswith('[]')

    @property
    def elem_type(self):
        return self.type[:-2] if self.type.endswith('[]') else self.type


class FuncInfo:
    def __init__(self, node):
        self.name = node.name
        self.ret_type = node.ret_type
        self.param_types = [p.type for p in node.params]
        self.node = node if node.body is not None else None
        self.pyname = node.name


def error(message, node):
    return CompileError(message, getattr(node, 'line', None), stage='semantic')


class Analyzer:
    def __init__(self):
        self.globals = {}
        self.funcs = {}
        self.scopes = []
        self.func = None
        self.loops = 0
        self.warnings = []
        self.used_names = set()

    def run(self, program):
        for item in program.items:
            if isinstance(item, N.Function):
                self.declare_function(item)
            else:
                for decl in self.decls_of(item):
                    self.declare_var(decl, is_global=True)
        if 'main' not in self.funcs or self.funcs['main'].node is None:
            raise CompileError("немає функції main", stage='semantic')
        for info in self.funcs.values():
            if info.node is None:
                raise error(f"функцію {info.name} оголошено, але не визначено", program)
        program.funcs = self.funcs
        program.globals = self.globals
        return self.warnings

    def decls_of(self, item):
        return item.decls if isinstance(item, N.DeclGroup) else [item]

    def declare_function(self, node):
        if node.name in self.globals:
            raise error(f"ім'я {node.name} вже зайняте змінною", node)
        info = self.funcs.get(node.name)
        if info is not None:
            same = info.ret_type == node.ret_type and info.param_types == [p.type for p in node.params]
            if not same:
                raise error(f"несумісне повторне оголошення {node.name}", node)
            if info.node is not None and node.body is not None:
                raise error(f"функцію {node.name} визначено двічі", node)
        else:
            info = FuncInfo(node)
            info.pyname = node.name if node.name not in PY_TAKEN - {'main'} else node.name + '_'
            self.funcs[node.name] = info
        if node.body is not None:
            info.node = node
            self.check_function(node, info)
        node.info = info

    def check_function(self, node, info):
        self.func = info
        self.used_names = {s.pyname for s in self.globals.values()} | {f.pyname for f in self.funcs.values()}
        node.assigned_globals = set()
        self.current = node
        self.scopes = [{}]
        for p in node.params:
            if p.type == 'void':
                raise error("параметр не може мати тип void", p)
            if p.name in self.scopes[-1]:
                raise error(f"параметр {p.name} повторюється", p)
            sym = Symbol(p.name, p.type, 'param')
            self.assign_pyname(sym)
            self.scopes[-1][p.name] = sym
            p.sym = sym
        self.block(node.body, new_scope=False)
        self.scopes = []
        self.func = None
        if info.ret_type != 'void' and info.name != 'main' and not self.always_returns(node.body):
            self.warnings.append(f"рядок {node.line}: функція {info.name} може завершитись без return")

    def always_returns(self, stmt):
        if isinstance(stmt, N.Return):
            return True
        if isinstance(stmt, N.Block):
            return any(self.always_returns(s) for s in stmt.stmts)
        if isinstance(stmt, N.If):
            return stmt.other is not None and self.always_returns(stmt.then) and self.always_returns(stmt.other)
        return False

    def assign_pyname(self, sym):
        base = sym.name if sym.name not in PY_TAKEN and not sym.name.startswith('_') else sym.name + '_'
        candidate, n = base, 2
        while candidate in self.used_names:
            candidate = f"{base}_{n}"
            n += 1
        sym.pyname = candidate
        self.used_names.add(candidate)

    def declare_var(self, decl, is_global=False):
        if decl.type == 'void':
            raise error(f"змінна {decl.name} не може мати тип void", decl)
        table = self.globals if is_global else self.scopes[-1]
        if decl.name in table:
            raise error(f"змінну {decl.name} вже оголошено в цій області видимості", decl)
        if is_global and decl.name in self.funcs:
            raise error(f"ім'я {decl.name} вже зайняте функцією", decl)
        if decl.size is not None:
            if decl.size <= 0:
                raise error("розмір масиву має бути додатним", decl)
            sym = Symbol(decl.name, decl.type, 'array', decl.size, is_global)
            if decl.init is not None:
                if len(decl.init) > decl.size:
                    raise error(f"забагато ініціалізаторів для {decl.name}[{decl.size}]", decl)
                for value in decl.init:
                    self.convertible(self.expr(value), decl.type, value)
        else:
            sym = Symbol(decl.name, decl.type, 'var', None, is_global)
            if decl.init is not None:
                self.convertible(self.expr(decl.init), decl.type, decl.init)
        if is_global:
            if decl.name in PY_TAKEN or decl.name.startswith('_'):
                sym.pyname = decl.name + '_'
        else:
            self.assign_pyname(sym)
        table[decl.name] = sym
        decl.sym = sym

    def convertible(self, src, dst, node):
        if src == 'void':
            raise error("значення типу void не можна використати", node)
        if src.endswith('[]') or dst.endswith('[]'):
            if src != dst:
                raise error(f"не можна перетворити {src} на {dst}", node)
            return
        if src == 'double' and dst in ('int', 'bool'):
            self.warnings.append(f"рядок {node.line}: звуження double до {dst}")

    def lookup(self, name, node):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        if name in self.globals:
            return self.globals[name]
        raise error(f"змінну {name} не оголошено", node)

    def block(self, block, new_scope=True):
        if new_scope:
            self.scopes.append({})
        for stmt in block.stmts:
            self.stmt(stmt)
        if new_scope:
            self.scopes.pop()

    def stmt(self, s):
        if s is None:
            return
        if isinstance(s, N.Block):
            self.block(s)
        elif isinstance(s, (N.VarDecl, N.DeclGroup)):
            for decl in self.decls_of(s):
                self.declare_var(decl)
        elif isinstance(s, N.ExprStmt):
            self.expr(s.expr)
        elif isinstance(s, N.If):
            self.condition(s.cond)
            self.scoped(s.then)
            self.scoped(s.other)
        elif isinstance(s, N.While):
            self.condition(s.cond)
            self.loop_body(s.body)
        elif isinstance(s, N.DoWhile):
            self.loop_body(s.body)
            self.condition(s.cond)
        elif isinstance(s, N.For):
            self.scopes.append({})
            self.stmt(s.init)
            if s.cond is not None:
                self.condition(s.cond)
            if s.step is not None:
                self.expr(s.step)
            self.loop_body(s.body)
            self.scopes.pop()
        elif isinstance(s, N.Return):
            self.ret(s)
        elif isinstance(s, (N.Break, N.Continue)):
            if self.loops == 0:
                raise error(f"{s.label()} поза циклом", s)
        elif isinstance(s, N.Cout):
            for item in s.items:
                if not isinstance(item, (N.Str, N.Endl)):
                    t = self.expr(item)
                    if t not in NUMERIC:
                        raise error(f"cout не вміє виводити {t}", item)
        elif isinstance(s, N.Cin):
            for target in s.targets:
                self.lvalue(target)
        else:
            raise error(f"невідома інструкція {type(s).__name__}", s)

    def scoped(self, s):
        if isinstance(s, (N.VarDecl, N.DeclGroup)):
            self.scopes.append({})
            self.stmt(s)
            self.scopes.pop()
        else:
            self.stmt(s)

    def loop_body(self, body):
        self.loops += 1
        self.scoped(body)
        self.loops -= 1

    def ret(self, s):
        want = self.func.ret_type
        if s.value is None:
            if want != 'void':
                raise error(f"функція {self.func.name} має повернути {want}", s)
            return
        got = self.expr(s.value)
        if want == 'void':
            raise error(f"void-функція {self.func.name} не може повертати значення", s)
        self.convertible(got, want, s.value)

    def condition(self, e):
        t = self.expr(e)
        if t not in NUMERIC:
            raise error(f"умова має бути числом або bool, а не {t}", e)

    def lvalue(self, e):
        if isinstance(e, N.Var):
            sym = self.lookup(e.name, e)
            if sym.is_array:
                raise error(f"масиву {e.name} не можна присвоїти значення цілком", e)
            e.sym = sym
            e.ctype = sym.type
        else:
            self.index(e)
        if e.sym.is_global and self.func is not None and isinstance(e, N.Var):
            self.current.assigned_globals.add(e.sym.pyname)
        return e.ctype

    def index(self, e):
        sym = self.lookup(e.array, e)
        if not sym.is_array:
            raise error(f"{e.array} не є масивом", e)
        t = self.expr(e.index)
        if t != 'int' and t != 'bool':
            raise error("індекс масиву має бути цілим", e.index)
        e.sym = sym
        e.ctype = sym.elem_type
        return e.ctype

    def expr(self, e):
        e.ctype = self._expr(e)
        return e.ctype

    def _expr(self, e):
        if isinstance(e, N.Num):
            return 'int' if isinstance(e.value, int) else 'double'
        if isinstance(e, N.BoolLit):
            return 'bool'
        if isinstance(e, N.Str):
            raise error("рядки дозволені лише в cout", e)
        if isinstance(e, N.Var):
            sym = self.lookup(e.name, e)
            e.sym = sym
            return sym.elem_type + '[]' if sym.is_array else sym.type
        if isinstance(e, N.Index):
            return self.index(e)
        if isinstance(e, N.Assign):
            target = self.lvalue(e.target)
            value = self.expr(e.value)
            self.arith(value, e.value)
            if e.op == '%=' and (target == 'double' or value == 'double'):
                raise error("% працює лише з цілими", e)
            self.convertible(value, target, e.value)
            return target
        if isinstance(e, N.IncDec):
            t = self.lvalue(e.target)
            self.arith(t, e.target)
            return t
        if isinstance(e, N.UnaryOp):
            t = self.expr(e.operand)
            self.arith(t, e.operand)
            if e.op == '!':
                return 'bool'
            return 'int' if t == 'bool' else t
        if isinstance(e, N.BinOp):
            lt = self.expr(e.left)
            rt = self.expr(e.right)
            self.arith(lt, e.left)
            self.arith(rt, e.right)
            if e.op in ('&&', '||', '<', '<=', '>', '>=', '==', '!='):
                return 'bool'
            if e.op == '%':
                if 'double' in (lt, rt):
                    raise error("% працює лише з цілими", e)
                return 'int'
            return 'double' if 'double' in (lt, rt) else 'int'
        if isinstance(e, N.Ternary):
            self.condition(e.cond)
            a = self.expr(e.yes)
            b = self.expr(e.no)
            self.arith(a, e.yes)
            self.arith(b, e.no)
            if a == b:
                return a
            return 'double' if 'double' in (a, b) else 'int'
        if isinstance(e, N.Call):
            return self.call(e)
        raise error(f"невідомий вираз {type(e).__name__}", e)

    def arith(self, t, node):
        if t not in NUMERIC:
            raise error(f"очікувалось число, а маємо {t}", node)

    def call(self, e):
        info = self.funcs.get(e.name)
        if info is None:
            try:
                self.lookup(e.name, e)
            except CompileError:
                raise error(f"функцію {e.name} не оголошено", e)
            raise error(f"{e.name} не є функцією", e)
        if len(e.args) != len(info.param_types):
            raise error(f"{e.name} чекає {len(info.param_types)} аргумент(и), передано {len(e.args)}", e)
        for arg, want in zip(e.args, info.param_types):
            self.convertible(self.expr(arg), want, arg)
        e.info = info
        return info.ret_type


def analyze(program):
    return Analyzer().run(program)
