import inspect
import json

from . import nodes as N
from . import runtime
from .errors import CompileError

TERNARY, OR, AND, NOT, CMP, ADD, MUL, UNARY, ATOM = range(1, 10)

BINARY = {
    '||': ('or', OR), '&&': ('and', AND),
    '<': ('<', CMP), '<=': ('<=', CMP), '>': ('>', CMP), '>=': ('>=', CMP),
    '==': ('==', CMP), '!=': ('!=', CMP),
    '+': ('+', ADD), '-': ('-', ADD),
    '*': ('*', MUL), '/': ('/', MUL), '%': ('%', MUL),
}

DEFAULTS = {'int': '0', 'double': '0.0', 'bool': 'False'}
READ_KIND = {'int': 'int', 'double': 'float', 'bool': 'bool'}
HELPER_DEPS = {'_imod': ['_idiv'], '_out': ['_fmt'], '_read': ['_tokens']}
HELPER_ORDER = ['_idiv', '_imod', '_fmt', '_out', '_tokens', '_read', '_set', '_postinc']


class PyGen:
    def __init__(self, program):
        self.program = program
        self.lines = []
        self.depth = 0
        self.helpers = set()
        self.loops = []

    def emit(self, text):
        self.lines.append('    ' * self.depth + text)

    def generate(self):
        body_start = len(self.lines)
        for item in self.program.items:
            if isinstance(item, N.Function):
                if item.body is not None:
                    self.function(item)
            else:
                for decl in (item.decls if isinstance(item, N.DeclGroup) else [item]):
                    self.declaration(decl)
        body = self.lines[body_start:]
        self.lines = []
        main = self.program.funcs['main']
        tail = ['', '', 'if __name__ == "__main__":',
                f'    sys.exit({main.pyname}())' if main.ret_type == 'int' else f'    {main.pyname}()']
        return '\n'.join(['import sys', '', ''] + self.helper_source() + self.spaced(body) + tail) + '\n'

    def spaced(self, body):
        out = []
        for line in body:
            if line.startswith('def ') and out:
                out += ['', '']
            elif not line.startswith(' ') and out and out[-1].startswith(' '):
                out += ['', '']
            out.append(line)
        return out

    def helper_source(self):
        needed = set()
        stack = list(self.helpers)
        while stack:
            name = stack.pop()
            if name not in needed:
                needed.add(name)
                stack.extend(HELPER_DEPS.get(name, []))
        out = []
        for name in HELPER_ORDER:
            if name not in needed:
                continue
            if name == '_tokens':
                out += ['_tokens = []', '']
                continue
            out += inspect.getsource(getattr(runtime, name)).rstrip().split('\n') + ['', '']
        return out

    def use(self, name):
        self.helpers.add(name)
        return name

    def function(self, fn):
        self.current = fn
        params = ', '.join(p.sym.pyname for p in fn.params)
        self.emit(f'def {fn.info.pyname}({params}):')
        self.depth += 1
        if fn.assigned_globals:
            self.emit('global ' + ', '.join(sorted(fn.assigned_globals)))
        start = len(self.lines)
        self.block(fn.body.stmts)
        if len(self.lines) == start:
            self.emit('pass')
        if fn.info.name == 'main' and not (fn.body.stmts and isinstance(fn.body.stmts[-1], N.Return)):
            self.emit('return 0')
        self.depth -= 1

    def block(self, stmts):
        for s in stmts:
            self.stmt(s)

    def body(self, s):
        self.depth += 1
        start = len(self.lines)
        if isinstance(s, N.Block):
            self.block(s.stmts)
        else:
            self.stmt(s)
        if len(self.lines) == start:
            self.emit('pass')
        self.depth -= 1

    def declaration(self, decl):
        sym = decl.sym
        if sym.kind == 'array':
            values = [self.cast(v, sym.type) for v in (decl.init or [])]
            rest = sym.size - len(values)
            if values and rest:
                self.emit(f"{sym.pyname} = [{', '.join(values)}] + [{DEFAULTS[sym.type]}] * {rest}")
            elif values:
                self.emit(f"{sym.pyname} = [{', '.join(values)}]")
            else:
                self.emit(f"{sym.pyname} = [{DEFAULTS[sym.type]}] * {sym.size}")
        elif decl.init is not None:
            self.emit(f"{sym.pyname} = {self.cast(decl.init, sym.type)}")
        else:
            self.emit(f"{sym.pyname} = {DEFAULTS[sym.type]}")

    def cast(self, e, ctype):
        code = self.code(e)
        if ctype == 'int' and e.ctype == 'double':
            return f'int({code})'
        if ctype == 'bool' and e.ctype != 'bool':
            return f'bool({code})'
        return code

    def stmt(self, s):
        if s is None:
            return
        if isinstance(s, N.Block):
            self.block(s.stmts)
        elif isinstance(s, N.VarDecl):
            self.declaration(s)
        elif isinstance(s, N.DeclGroup):
            for decl in s.decls:
                self.declaration(decl)
        elif isinstance(s, N.ExprStmt):
            self.expr_stmt(s.expr)
        elif isinstance(s, N.If):
            self.if_chain(s)
        elif isinstance(s, N.While):
            self.emit(f'while {self.cond(s.cond)}:')
            self.loops.append([])
            self.body(s.body)
            self.loops.pop()
        elif isinstance(s, N.DoWhile):
            self.emit('while True:')
            check = f'if not {self.wrap(s.cond, NOT + 1, cond=True)}:'
            self.loops.append([check, '    break'])
            self.depth += 1
            self.stmt(s.body) if not isinstance(s.body, N.Block) else self.block(s.body.stmts)
            self.emit(check)
            self.emit('    break')
            self.depth -= 1
            self.loops.pop()
        elif isinstance(s, N.For):
            self.for_loop(s)
        elif isinstance(s, N.Return):
            if s.value is None:
                self.emit('return')
            else:
                self.emit('return ' + self.cast(s.value, self.current.ret_type))
        elif isinstance(s, N.Break):
            self.emit('break')
        elif isinstance(s, N.Continue):
            for line in self.loops[-1]:
                self.emit(line)
            self.emit('continue')
        elif isinstance(s, N.Cout):
            parts = []
            for item in s.items:
                if isinstance(item, N.Str):
                    parts.append(json.dumps(item.value, ensure_ascii=False))
                elif isinstance(item, N.Endl):
                    parts.append('"\\n"')
                else:
                    parts.append(self.code(item))
            merged = []
            for part in parts:
                if merged and merged[-1].startswith('"') and part.startswith('"') and merged[-1].endswith('"') and part.endswith('"'):
                    merged[-1] = merged[-1][:-1] + part[1:]
                else:
                    merged.append(part)
            self.emit(f"{self.use('_out')}({', '.join(merged)})")
        elif isinstance(s, N.Cin):
            for target in s.targets:
                self.emit(f"{self.target(target)} = {self.use('_read')}({READ_KIND[target.ctype]})")
        else:
            raise CompileError(f"генератор не знає {type(s).__name__}", s.line, stage='codegen')

    def if_chain(self, s, keyword='if'):
        self.emit(f'{keyword} {self.cond(s.cond)}:')
        self.body(s.then)
        if s.other is None:
            return
        if isinstance(s.other, N.If):
            self.if_chain(s.other, 'elif')
        else:
            self.emit('else:')
            self.body(s.other)

    def for_loop(self, s):
        self.stmt(s.init)
        cond = self.cond(s.cond) if s.cond is not None else 'True'
        step = self.step_lines(s.step) if s.step is not None else []
        self.emit(f'while {cond}:')
        self.loops.append(step)
        self.depth += 1
        start = len(self.lines)
        if isinstance(s.body, N.Block):
            self.block(s.body.stmts)
        else:
            self.stmt(s.body)
        for line in step:
            self.emit(line)
        if len(self.lines) == start:
            self.emit('pass')
        self.depth -= 1
        self.loops.pop()

    def step_lines(self, e):
        saved, self.lines = self.lines, []
        depth, self.depth = self.depth, 0
        self.expr_stmt(e)
        out, self.lines, self.depth = self.lines, saved, depth
        return out

    def expr_stmt(self, e):
        if isinstance(e, N.Assign):
            self.emit(self.assign_stmt(e))
        elif isinstance(e, N.IncDec):
            op = '+=' if e.op == '++' else '-='
            self.emit(f'{self.target(e.target)} {op} 1')
        else:
            self.emit(self.code(e))

    def assign_stmt(self, e):
        target = self.target(e.target)
        if e.op == '=':
            return f'{target} = {self.cast(e.value, e.target.ctype)}'
        op = e.op[0]
        int_target = e.target.ctype == 'int'
        if op == '/' and int_target and e.value.ctype != 'double':
            return f"{target} = {self.use('_idiv')}({target}, {self.code(e.value)})"
        if op == '%':
            return f"{target} = {self.use('_imod')}({target}, {self.code(e.value)})"
        if int_target and e.value.ctype == 'double':
            return f'{target} = int({target} {op} {self.wrap(e.value, MUL + 1)})'
        return f'{target} {e.op} {self.code(e.value)}'

    def target(self, t):
        if isinstance(t, N.Var):
            return t.sym.pyname
        return f'{t.sym.pyname}[{self.code(t.index)}]'

    def cond(self, e):
        code, _ = self.expr(e, cond=True)
        return code

    def code(self, e):
        return self.expr(e)[0]

    def wrap(self, e, need, cond=False):
        code, prec = self.expr(e, cond)
        return f'({code})' if prec < need else code

    def expr(self, e, cond=False):
        if isinstance(e, N.Num):
            return repr(e.value), ATOM
        if isinstance(e, N.BoolLit):
            return ('True' if e.value else 'False'), ATOM
        if isinstance(e, (N.Var, N.Index)):
            return self.target(e), ATOM
        if isinstance(e, N.Call):
            args = []
            for arg, want in zip(e.args, e.info.param_types):
                args.append(self.cast(arg, want) if not want.endswith('[]') else self.code(arg))
            return f"{e.info.pyname}({', '.join(args)})", ATOM
        if isinstance(e, N.UnaryOp):
            if e.op == '!':
                return f'not {self.wrap(e.operand, NOT, cond=True)}', NOT
            return f'-{self.wrap(e.operand, UNARY)}', UNARY
        if isinstance(e, N.BinOp):
            return self.binop(e, cond)
        if isinstance(e, N.Ternary):
            yes = self.cast(e.yes, e.ctype) if e.ctype == 'int' else self.code(e.yes)
            no = self.cast(e.no, e.ctype) if e.ctype == 'int' else self.code(e.no)
            return f'({yes} if {self.cond(e.cond)} else {no})', ATOM
        if isinstance(e, N.Assign):
            return self.assign_expr(e), ATOM
        if isinstance(e, N.IncDec):
            return self.incdec_expr(e), ATOM
        raise CompileError(f"генератор не знає {type(e).__name__}", e.line, stage='codegen')

    def binop(self, e, cond):
        op, prec = BINARY[e.op]
        if e.op in ('&&', '||'):
            left = self.wrap(e.left, prec, cond=True)
            right = self.wrap(e.right, prec + 1, cond=True)
            code = f'{left} {op} {right}'
            if cond:
                return code, prec
            return f'bool({code})', ATOM
        both_int = e.left.ctype != 'double' and e.right.ctype != 'double'
        if e.op == '/' and both_int:
            return f"{self.use('_idiv')}({self.code(e.left)}, {self.code(e.right)})", ATOM
        if e.op == '%':
            return f"{self.use('_imod')}({self.code(e.left)}, {self.code(e.right)})", ATOM
        need_left = prec + 1 if prec == CMP else prec
        return f'{self.wrap(e.left, need_left)} {op} {self.wrap(e.right, prec + 1)}', prec

    def assign_expr(self, e):
        if e.op == '=':
            value = self.cast(e.value, e.target.ctype)
        else:
            fake = N.BinOp(e.op[0], e.target, e.value, line=e.line)
            fake.ctype = 'double' if 'double' in (e.target.ctype, e.value.ctype) else 'int'
            value = self.cast(fake, e.target.ctype)
        if isinstance(e.target, N.Var):
            return f'({e.target.sym.pyname} := {value})'
        return f"{self.use('_set')}({e.target.sym.pyname}, {self.code(e.target.index)}, {value})"

    def incdec_expr(self, e):
        sign = '+' if e.op == '++' else '-'
        if isinstance(e.target, N.Var):
            name = e.target.sym.pyname
            if e.prefix:
                return f'({name} := {name} {sign} 1)'
            back = '-' if sign == '+' else '+'
            return f'(({name} := {name} {sign} 1) {back} 1)'
        arr = e.target.sym.pyname
        index = self.code(e.target.index)
        delta = '1' if sign == '+' else '-1'
        if e.prefix:
            return f"{self.use('_set')}({arr}, {index}, {arr}[{index}] {sign} 1)"
        return f"{self.use('_postinc')}({arr}, {index}, {delta})"


def generate(program):
    return PyGen(program).generate()
