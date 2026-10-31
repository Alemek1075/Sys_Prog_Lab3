import os
import sys

import ply.lex as lex
import ply.yacc as yacc

tokens = ('NUM', 'ID', 'PLUS', 'TIMES', 'SEMI')
t_PLUS = r'\+'
t_TIMES = r'\*'
t_SEMI = r';'
t_ID = r'[a-z]+'
t_ignore = ' '


def t_NUM(t):
    r'\d+'
    t.value = int(t.value)
    return t


def t_error(t):
    raise SyntaxError(t.value[0])


def reject(self, t):
    raise SyntaxError(t)


class Log:
    def __init__(self):
        self.lines = []

    def warning(self, msg, *args):
        self.lines.append(msg % args)

    debug = info = error = critical = warning


class Expr:
    tokens = tokens

    def __init__(self, precedence):
        self.precedence = precedence

    def p_e_bin(self, p):
        '''e : e PLUS e
             | e TIMES e'''
        p[0] = f'({p[1]} {p[2]} {p[3]})'

    def p_e_num(self, p):
        'e : NUM'
        p[0] = str(p[1])

    p_error = reject


class Ambiguous:
    tokens = tokens

    def p_stmt(self, p):
        '''stmt : expr SEMI
                | decl SEMI'''
        p[0] = p[1]

    def p_expr(self, p):
        'expr : ID'
        p[0] = f'expr({p[1]})'

    def p_decl(self, p):
        'decl : ID'
        p[0] = f'decl({p[1]})'

    p_error = reject


def build(module, name):
    log = Log()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
    os.makedirs(out, exist_ok=True)
    parser = yacc.yacc(module=module, write_tables=False, errorlog=log, debug=True,
                       outputdir=out, debugfile=f'{name}.out')
    conflicts = [line for line in log.lines if line.endswith(('conflict', 'conflicts'))]
    return parser, conflicts


def main():
    lexer = lex.lex(module=sys.modules[__name__])
    text = '1 + 2 * 3 + 4'

    print('1) e : e + e | e * e | NUM, без таблиці пріоритетів')
    parser, conflicts = build(Expr(()), 'expr_no_prec')
    print('   ', conflicts)
    print('   ', text, '=>', parser.parse(text, lexer=lexer))

    print('2) та сама граматика, але %left + і %left * (нижчий рядок = вищий пріоритет)')
    prec = (('left', 'PLUS'), ('left', 'TIMES'))
    parser, conflicts = build(Expr(prec), 'expr_prec')
    print('   ', conflicts or 'конфліктів немає')
    print('   ', text, '=>', parser.parse(text, lexer=lexer))

    print('3) stmt : expr ; | decl ;   expr : ID   decl : ID')
    parser, conflicts = build(Ambiguous(), 'reduce_reduce')
    print('   ', conflicts)
    print('    x; =>', parser.parse('x;', lexer=lexer), '(перемогло правило, записане раніше)')
    print('\nавтомати з поясненням конфліктів: demo/out/*.out')


if __name__ == '__main__':
    main()
