class Node:
    fields = ()

    def __init__(self, *args, line=None):
        for name, value in zip(self.fields, args):
            setattr(self, name, value)
        self.line = line

    def children(self):
        out = []
        for name in self.fields:
            value = getattr(self, name)
            if isinstance(value, Node):
                out.append((name, value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, Node):
                        out.append((name, item))
        return out

    def label(self):
        return type(self).__name__

    def to_json(self):
        data = {
            'type': type(self).__name__,
            'label': self.label(),
            'line': self.line,
            'children': [dict(child.to_json(), role=role) for role, child in self.children()],
        }
        if hasattr(self, 'ctype'):
            data['ctype'] = self.ctype
        return data

    def __repr__(self):
        parts = ', '.join(f"{name}={getattr(self, name)!r}" for name in self.fields)
        return f"{type(self).__name__}({parts})"


class Program(Node):
    fields = ('items',)


class Function(Node):
    fields = ('ret_type', 'name', 'params', 'body')

    def label(self):
        args = ', '.join(f"{p.type} {p.name}" for p in self.params)
        return f"{self.ret_type} {self.name}({args})"


class Param(Node):
    fields = ('type', 'name')

    def label(self):
        return f"{self.type} {self.name}"


class VarDecl(Node):
    fields = ('type', 'name', 'size', 'init')

    def label(self):
        if self.size is not None:
            return f"{self.type} {self.name}[]"
        return f"{self.type} {self.name}"


class DeclGroup(Node):
    fields = ('decls',)

    def label(self):
        return 'Decl'


class Block(Node):
    fields = ('stmts',)

    def label(self):
        return '{ }'


class If(Node):
    fields = ('cond', 'then', 'other')

    def label(self):
        return 'if'


class While(Node):
    fields = ('cond', 'body')

    def label(self):
        return 'while'


class DoWhile(Node):
    fields = ('body', 'cond')

    def label(self):
        return 'do-while'


class For(Node):
    fields = ('init', 'cond', 'step', 'body')

    def label(self):
        return 'for'


class Return(Node):
    fields = ('value',)

    def label(self):
        return 'return'


class Break(Node):
    def label(self):
        return 'break'


class Continue(Node):
    def label(self):
        return 'continue'


class ExprStmt(Node):
    fields = ('expr',)

    def label(self):
        return 'expr;'


class Cout(Node):
    fields = ('items',)

    def label(self):
        return 'cout <<'


class Cin(Node):
    fields = ('targets',)

    def label(self):
        return 'cin >>'


class Endl(Node):
    def label(self):
        return 'endl'


class Num(Node):
    fields = ('value',)

    def label(self):
        return repr(self.value)


class Str(Node):
    fields = ('value',)

    def label(self):
        return '"' + self.value.replace('\n', '\\n') + '"'


class BoolLit(Node):
    fields = ('value',)

    def label(self):
        return 'true' if self.value else 'false'


class Var(Node):
    fields = ('name',)

    def label(self):
        return self.name


class Index(Node):
    fields = ('array', 'index')

    def label(self):
        return f"{self.array}[ ]"


class BinOp(Node):
    fields = ('op', 'left', 'right')

    def label(self):
        return self.op


class UnaryOp(Node):
    fields = ('op', 'operand')

    def label(self):
        return self.op


class IncDec(Node):
    fields = ('op', 'target', 'prefix')

    def label(self):
        name = self.target.label()
        return self.op + name if self.prefix else name + self.op


class Assign(Node):
    fields = ('op', 'target', 'value')

    def label(self):
        return self.op


class Ternary(Node):
    fields = ('cond', 'yes', 'no')

    def label(self):
        return '?:'


class Call(Node):
    fields = ('name', 'args')

    def label(self):
        return self.name + '()'
