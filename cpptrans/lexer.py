import sys

import ply.lex as lex

from .errors import CompileError

reserved = {
    'int': 'INT',
    'double': 'DOUBLE',
    'bool': 'BOOL',
    'void': 'VOID',
    'if': 'IF',
    'else': 'ELSE',
    'while': 'WHILE',
    'for': 'FOR',
    'do': 'DO',
    'return': 'RETURN',
    'break': 'BREAK',
    'continue': 'CONTINUE',
    'true': 'TRUE',
    'false': 'FALSE',
    'using': 'USING',
    'namespace': 'NAMESPACE',
    'cout': 'COUT',
    'cin': 'CIN',
    'endl': 'ENDL',
    'std': 'STD',
}

tokens = [
    'ID', 'INT_LIT', 'FLOAT_LIT', 'STRING_LIT',
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'MOD',
    'ASSIGN', 'PLUSEQ', 'MINUSEQ', 'TIMESEQ', 'DIVEQ', 'MODEQ',
    'INC', 'DEC',
    'EQ', 'NE', 'LT', 'LE', 'GT', 'GE',
    'AND', 'OR', 'NOT',
    'SHL', 'SHR', 'SCOPE',
    'LPAREN', 'RPAREN', 'LBRACE', 'RBRACE', 'LBRACKET', 'RBRACKET',
    'SEMI', 'COMMA', 'QUESTION', 'COLON',
] + sorted(set(reserved.values()))

t_PLUSEQ = r'\+='
t_MINUSEQ = r'-='
t_TIMESEQ = r'\*='
t_DIVEQ = r'/='
t_MODEQ = r'%='
t_INC = r'\+\+'
t_DEC = r'--'
t_EQ = r'=='
t_NE = r'!='
t_LE = r'<='
t_GE = r'>='
t_SHL = r'<<'
t_SHR = r'>>'
t_AND = r'&&'
t_OR = r'\|\|'
t_SCOPE = r'::'
t_PLUS = r'\+'
t_MINUS = r'-'
t_TIMES = r'\*'
t_DIVIDE = r'/'
t_MOD = r'%'
t_ASSIGN = r'='
t_LT = r'<'
t_GT = r'>'
t_NOT = r'!'
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_LBRACE = r'\{'
t_RBRACE = r'\}'
t_LBRACKET = r'\['
t_RBRACKET = r'\]'
t_SEMI = r';'
t_COMMA = r','
t_QUESTION = r'\?'
t_COLON = r':'

t_ignore = ' \t\r'


def t_PREPROCESSOR(t):
    r'\#[^\n]*'
    pass


def t_COMMENT_BLOCK(t):
    r'/\*(.|\n)*?\*/'
    t.lexer.lineno += t.value.count('\n')


def t_COMMENT_LINE(t):
    r'//[^\n]*'
    pass


def t_FLOAT_LIT(t):
    r'(\d+\.\d*|\.\d+)([eE][+-]?\d+)?|\d+[eE][+-]?\d+'
    t.value = float(t.value)
    return t


def t_INT_LIT(t):
    r'\d+'
    t.value = int(t.value)
    return t


def t_STRING_LIT(t):
    r'"([^"\\\n]|\\.)*"'
    raw = t.value[1:-1]
    t.value = (raw.replace('\\n', '\n').replace('\\t', '\t')
                  .replace('\\"', '"').replace('\\\\', '\\'))
    return t


def t_ID(t):
    r'[A-Za-z_][A-Za-z_0-9]*'
    t.type = reserved.get(t.value, 'ID')
    return t


def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)


def t_error(t):
    raise CompileError(f"невідомий символ {t.value[0]!r}", t.lexer.lineno, column(t.lexer.lexdata, t.lexpos))


def column(text, pos):
    start = text.rfind('\n', 0, pos) + 1
    return pos - start + 1


def make_lexer():
    return lex.lex(module=sys.modules[__name__])


def tokenize(source):
    lexer = make_lexer()
    lexer.input(source)
    result = []
    for tok in lexer:
        result.append({
            'type': tok.type,
            'value': tok.value,
            'line': tok.lineno,
            'col': column(source, tok.lexpos),
        })
    return result
