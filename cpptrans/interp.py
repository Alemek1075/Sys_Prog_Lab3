import sys

from . import nodes as N
from .errors import RuntimeFault
from .runtime import _fmt, _idiv, _imod


class BreakLoop(Exception):
    pass


class ContinueLoop(Exception):
    pass


class ReturnValue(Exception):
    def __init__(self, value):
        self.value = value


def convert(value, ctype):
    if ctype == 'int':
        return int(value)
    if ctype == 'double':
        return float(value)
    if ctype == 'bool':
        return bool(value)
    return value


def default(ctype):
    return {'int': 0, 'double': 0.0, 'bool': False}[ctype]


class Interpreter:
    def __init__(self, program, stdin='', max_steps=5_000_000):
        self.program = program
        self.funcs = program.funcs
        self.tokens = stdin.split()
        self.pos = 0
        self.out = []
        self.steps = 0
        self.max_steps = max_steps
        self.globals = {}
        self.frame = None

    def run(self):
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 20000))
        try:
            for item in self.program.items:
                if not isinstance(item, N.Function):
                    for decl in (item.decls if isinstance(item, N.DeclGroup) else [item]):
                        self.declare(decl, self.globals)
            code = self.call(self.funcs['main'], [], self.program)
        except RecursionError:
            raise RuntimeFault("переповнення стеку викликів (надто глибока рекурсія)")
        finally:
            sys.setrecursionlimit(old_limit)
        return ''.join(self.out), code

    def tick(self, node):
        self.steps += 1
        if self.steps > self.max_steps:
            raise RuntimeFault(f"перевищено ліміт у {self.max_steps} кроків, можливо, нескінченний цикл", node.line)

    def storage(self, sym):
        return self.globals if sym.is_global else self.frame

    def declare(self, decl, store):
        sym = decl.sym
        if sym.kind == 'array':
            values = [convert(self.eval(v), sym.type) for v in (decl.init or [])]
            store[sym] = values + [default(sym.type)] * (sym.size - len(values))
        else:
            value = self.eval(decl.init) if decl.init is not None else default(sym.type)
            store[sym] = convert(value, sym.type)

    def call(self, info, args, node):
        fn = info.node
        frame = {}
        for param, value in zip(fn.params, args):
            frame[param.sym] = value if param.type.endswith('[]') else convert(value, param.type)
        saved, self.frame = self.frame, frame
        try:
            self.exec(fn.body)
            result = 0 if info.name == 'main' else None
        except ReturnValue as r:
            result = r.value
        finally:
            self.frame = saved
        if info.ret_type != 'void' and result is not None:
            result = convert(result, info.ret_type)
        elif info.ret_type != 'void':
            result = default(info.ret_type)
        return result

    def exec(self, s):
        if s is None:
            return
        self.tick(s)
        method = getattr(self, 'exec_' + type(s).__name__)
        method(s)

    def exec_Block(self, s):
        for stmt in s.stmts:
            self.exec(stmt)

    def exec_VarDecl(self, s):
        self.declare(s, self.frame)

    def exec_DeclGroup(self, s):
        for decl in s.decls:
            self.declare(decl, self.frame)

    def exec_ExprStmt(self, s):
        self.eval(s.expr)

    def exec_If(self, s):
        if self.eval(s.cond):
            self.exec(s.then)
        elif s.other is not None:
            self.exec(s.other)

    def exec_While(self, s):
        while self.eval(s.cond):
            try:
                self.exec(s.body)
            except BreakLoop:
                break
            except ContinueLoop:
                pass
            self.tick(s)

    def exec_DoWhile(self, s):
        while True:
            try:
                self.exec(s.body)
            except BreakLoop:
                break
            except ContinueLoop:
                pass
            self.tick(s)
            if not self.eval(s.cond):
                break

    def exec_For(self, s):
        self.exec(s.init)
        while s.cond is None or self.eval(s.cond):
            try:
                self.exec(s.body)
            except BreakLoop:
                break
            except ContinueLoop:
                pass
            if s.step is not None:
                self.eval(s.step)
            self.tick(s)

    def exec_Return(self, s):
        raise ReturnValue(self.eval(s.value) if s.value is not None else None)

    def exec_Break(self, s):
        raise BreakLoop()

    def exec_Continue(self, s):
        raise ContinueLoop()

    def exec_Cout(self, s):
        for item in s.items:
            if isinstance(item, N.Str):
                self.out.append(item.value)
            elif isinstance(item, N.Endl):
                self.out.append('\n')
            else:
                self.out.append(_fmt(self.eval(item)))

    def exec_Cin(self, s):
        for target in s.targets:
            if self.pos >= len(self.tokens):
                raise RuntimeFault("cin: вхідні дані закінчились", s.line)
            word = self.tokens[self.pos]
            self.pos += 1
            try:
                if target.ctype == 'double':
                    value = float(word)
                else:
                    value = int(word)
            except ValueError:
                raise RuntimeFault(f"cin: {word!r} не є числом", s.line)
            self.store(target, convert(value, target.ctype))

    def element(self, e):
        arr = self.storage(e.sym)[e.sym]
        i = self.eval(e.index)
        if not 0 <= i < len(arr):
            raise RuntimeFault(f"індекс {i} поза межами масиву {e.array}[{len(arr)}]", e.line)
        return arr, i

    def load(self, target):
        if isinstance(target, N.Var):
            return self.storage(target.sym)[target.sym]
        arr, i = self.element(target)
        return arr[i]

    def store(self, target, value):
        value = convert(value, target.ctype)
        if isinstance(target, N.Var):
            self.storage(target.sym)[target.sym] = value
        else:
            arr, i = self.element(target)
            arr[i] = value
        return value

    def eval(self, e):
        return getattr(self, 'eval_' + type(e).__name__)(e)

    def eval_Num(self, e):
        return e.value

    def eval_BoolLit(self, e):
        return e.value

    def eval_Var(self, e):
        return self.storage(e.sym)[e.sym]

    def eval_Index(self, e):
        arr, i = self.element(e)
        return arr[i]

    def eval_Assign(self, e):
        if e.op == '=':
            return self.store(e.target, self.eval(e.value))
        if isinstance(e.target, N.Index):
            arr, i = self.element(e.target)
            current = arr[i]
        else:
            current = self.load(e.target)
            arr = None
        value = self.binary(e.op[0], current, self.eval(e.value), e)
        value = convert(value, e.target.ctype)
        if arr is not None:
            arr[i] = value
        else:
            self.store(e.target, value)
        return value

    def eval_IncDec(self, e):
        delta = 1 if e.op == '++' else -1
        if isinstance(e.target, N.Index):
            arr, i = self.element(e.target)
            old = arr[i]
            arr[i] = convert(old + delta, e.target.ctype)
            return arr[i] if e.prefix else old
        old = self.load(e.target)
        new = self.store(e.target, old + delta)
        return new if e.prefix else old

    def eval_UnaryOp(self, e):
        value = self.eval(e.operand)
        if e.op == '!':
            return not value
        return -value

    def eval_BinOp(self, e):
        if e.op == '&&':
            return bool(self.eval(e.left)) and bool(self.eval(e.right))
        if e.op == '||':
            return bool(self.eval(e.left)) or bool(self.eval(e.right))
        return self.binary(e.op, self.eval(e.left), self.eval(e.right), e)

    def binary(self, op, a, b, e):
        both_int = not isinstance(a, float) and not isinstance(b, float)
        if op == '+':
            return a + b
        if op == '-':
            return a - b
        if op == '*':
            return a * b
        if op in '/%':
            if b == 0:
                raise RuntimeFault("ділення на нуль", e.line)
            if op == '%':
                return _imod(a, b)
            return _idiv(a, b) if both_int else a / b
        if op == '<':
            return a < b
        if op == '<=':
            return a <= b
        if op == '>':
            return a > b
        if op == '>=':
            return a >= b
        if op == '==':
            return a == b
        if op == '!=':
            return a != b
        raise RuntimeFault(f"невідомий оператор {op}", e.line)

    def eval_Ternary(self, e):
        value = self.eval(e.yes) if self.eval(e.cond) else self.eval(e.no)
        return convert(value, e.ctype)

    def eval_Call(self, e):
        args = []
        for arg in e.args:
            if isinstance(arg, N.Var) and arg.sym.is_array:
                args.append(self.storage(arg.sym)[arg.sym])
            else:
                args.append(self.eval(arg))
        return self.call(e.info, args, e)


def run(program, stdin='', max_steps=5_000_000):
    return Interpreter(program, stdin, max_steps).run()
