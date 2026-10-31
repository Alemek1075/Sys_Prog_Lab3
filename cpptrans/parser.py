import os

import ply.yacc as yacc

from . import lexer as lexmod
from . import nodes as N
from .errors import CompileError

ASSIGN_OPS = {
    'ASSIGN': '=', 'PLUSEQ': '+=', 'MINUSEQ': '-=',
    'TIMESEQ': '*=', 'DIVEQ': '/=', 'MODEQ': '%=',
}

PRECEDENCE = (
    ('nonassoc', 'IFX'),
    ('nonassoc', 'ELSE'),
    ('right', 'ASSIGN', 'PLUSEQ', 'MINUSEQ', 'TIMESEQ', 'DIVEQ', 'MODEQ'),
    ('right', 'QUESTION', 'COLON'),
    ('left', 'OR'),
    ('left', 'AND'),
    ('left', 'EQ', 'NE'),
    ('left', 'LT', 'LE', 'GT', 'GE'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE', 'MOD'),
    ('right', 'UMINUS', 'NOT', 'INC', 'DEC'),
)


class Grammar:
    tokens = lexmod.tokens

    def __init__(self, precedence=PRECEDENCE):
        self.precedence = precedence

    def p_program(self, p):
        'program : items'
        p[0] = N.Program(p[1], line=1)

    def p_items(self, p):
        '''items : items item
                 | empty'''
        if len(p) == 2:
            p[0] = []
        else:
            p[0] = p[1] + ([p[2]] if p[2] is not None else [])

    def p_item(self, p):
        '''item : function
                | declaration'''
        p[0] = p[1]

    def p_item_using(self, p):
        'item : USING NAMESPACE STD SEMI'
        p[0] = None

    def p_function(self, p):
        'function : type ID LPAREN params RPAREN block'
        p[0] = N.Function(p[1], p[2], p[4], p[6], line=p.lineno(2))

    def p_function_proto(self, p):
        'function : type ID LPAREN params RPAREN SEMI'
        p[0] = N.Function(p[1], p[2], p[4], None, line=p.lineno(2))

    def p_type(self, p):
        '''type : INT
                | DOUBLE
                | BOOL
                | VOID'''
        p[0] = p[1]

    def p_params(self, p):
        '''params : param_list
                  | VOID
                  | empty'''
        p[0] = p[1] if isinstance(p[1], list) else []

    def p_param_list(self, p):
        '''param_list : param_list COMMA param
                      | param'''
        p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]

    def p_param(self, p):
        'param : type ID'
        p[0] = N.Param(p[1], p[2], line=p.lineno(2))

    def p_param_array(self, p):
        'param : type ID LBRACKET RBRACKET'
        p[0] = N.Param(p[1] + '[]', p[2], line=p.lineno(2))

    def p_declaration(self, p):
        'declaration : type init_list SEMI'
        decls = []
        for name, size, init, line in p[2]:
            decls.append(N.VarDecl(p[1], name, size, init, line=line))
        p[0] = decls[0] if len(decls) == 1 else N.DeclGroup(decls, line=decls[0].line)

    def p_init_list(self, p):
        '''init_list : init_list COMMA init_decl
                     | init_decl'''
        p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]

    def p_init_decl(self, p):
        '''init_decl : ID
                     | ID ASSIGN expr'''
        p[0] = (p[1], None, p[3] if len(p) == 4 else None, p.lineno(1))

    def p_init_decl_array(self, p):
        '''init_decl : ID LBRACKET INT_LIT RBRACKET
                     | ID LBRACKET INT_LIT RBRACKET ASSIGN LBRACE arg_list RBRACE'''
        p[0] = (p[1], p[3], p[7] if len(p) == 9 else None, p.lineno(1))

    def p_block(self, p):
        'block : LBRACE stmts RBRACE'
        p[0] = N.Block(p[2], line=p.lineno(1))

    def p_stmts(self, p):
        '''stmts : stmts stmt
                 | empty'''
        if len(p) == 2:
            p[0] = []
        else:
            p[0] = p[1] + ([p[2]] if p[2] is not None else [])

    def p_stmt(self, p):
        '''stmt : block
                | declaration
                | if_stmt
                | while_stmt
                | do_stmt
                | for_stmt
                | jump_stmt
                | io_stmt'''
        p[0] = p[1]

    def p_stmt_expr(self, p):
        'stmt : expr SEMI'
        p[0] = N.ExprStmt(p[1], line=p[1].line)

    def p_stmt_empty(self, p):
        'stmt : SEMI'
        p[0] = None

    def p_if(self, p):
        'if_stmt : IF LPAREN expr RPAREN stmt %prec IFX'
        p[0] = N.If(p[3], p[5], None, line=p.lineno(1))

    def p_if_else(self, p):
        'if_stmt : IF LPAREN expr RPAREN stmt ELSE stmt'
        p[0] = N.If(p[3], p[5], p[7], line=p.lineno(1))

    def p_while(self, p):
        'while_stmt : WHILE LPAREN expr RPAREN stmt'
        p[0] = N.While(p[3], p[5], line=p.lineno(1))

    def p_do(self, p):
        'do_stmt : DO stmt WHILE LPAREN expr RPAREN SEMI'
        p[0] = N.DoWhile(p[2], p[5], line=p.lineno(1))

    def p_for(self, p):
        'for_stmt : FOR LPAREN for_init opt_expr SEMI opt_expr RPAREN stmt'
        p[0] = N.For(p[3], p[4], p[6], p[8], line=p.lineno(1))

    def p_for_init(self, p):
        '''for_init : declaration
                    | expr SEMI
                    | SEMI'''
        if p.slice[1].type == 'SEMI':
            p[0] = None
        elif len(p) == 3:
            p[0] = N.ExprStmt(p[1], line=p[1].line)
        else:
            p[0] = p[1]

    def p_opt_expr(self, p):
        '''opt_expr : expr
                    | empty'''
        p[0] = p[1]

    def p_jump_return(self, p):
        '''jump_stmt : RETURN expr SEMI
                     | RETURN SEMI'''
        p[0] = N.Return(p[2] if len(p) == 4 else None, line=p.lineno(1))

    def p_jump_break(self, p):
        'jump_stmt : BREAK SEMI'
        p[0] = N.Break(line=p.lineno(1))

    def p_jump_continue(self, p):
        'jump_stmt : CONTINUE SEMI'
        p[0] = N.Continue(line=p.lineno(1))

    def p_io_cout(self, p):
        'io_stmt : cout_chain SEMI'
        p[0] = N.Cout(p[1][1], line=p[1][0])

    def p_cout_chain(self, p):
        '''cout_chain : cout_name SHL out_item
                      | cout_chain SHL out_item'''
        if isinstance(p[1], tuple):
            p[0] = (p[1][0], p[1][1] + [p[3]])
        else:
            p[0] = (p[1], [p[3]])

    def p_cout_name(self, p):
        '''cout_name : COUT
                     | STD SCOPE COUT'''
        p[0] = p.lineno(1)

    def p_out_item(self, p):
        'out_item : expr'
        p[0] = p[1]

    def p_out_item_str(self, p):
        'out_item : STRING_LIT'
        p[0] = N.Str(p[1], line=p.lineno(1))

    def p_out_item_endl(self, p):
        '''out_item : ENDL
                    | STD SCOPE ENDL'''
        p[0] = N.Endl(line=p.lineno(1))

    def p_io_cin(self, p):
        'io_stmt : cin_chain SEMI'
        p[0] = N.Cin(p[1][1], line=p[1][0])

    def p_cin_chain(self, p):
        '''cin_chain : cin_name SHR lvalue
                     | cin_chain SHR lvalue'''
        if isinstance(p[1], tuple):
            p[0] = (p[1][0], p[1][1] + [p[3]])
        else:
            p[0] = (p[1], [p[3]])

    def p_cin_name(self, p):
        '''cin_name : CIN
                    | STD SCOPE CIN'''
        p[0] = p.lineno(1)

    def p_expr_binop(self, p):
        '''expr : expr PLUS expr
                | expr MINUS expr
                | expr TIMES expr
                | expr DIVIDE expr
                | expr MOD expr
                | expr LT expr
                | expr LE expr
                | expr GT expr
                | expr GE expr
                | expr EQ expr
                | expr NE expr
                | expr AND expr
                | expr OR expr'''
        p[0] = N.BinOp(p[2], p[1], p[3], line=p[1].line)

    def p_expr_ternary(self, p):
        'expr : expr QUESTION expr COLON expr'
        p[0] = N.Ternary(p[1], p[3], p[5], line=p[1].line)

    def p_expr_assign(self, p):
        '''expr : lvalue ASSIGN expr
                | lvalue PLUSEQ expr
                | lvalue MINUSEQ expr
                | lvalue TIMESEQ expr
                | lvalue DIVEQ expr
                | lvalue MODEQ expr'''
        p[0] = N.Assign(p[2], p[1], p[3], line=p[1].line)

    def p_expr_unary(self, p):
        '''expr : MINUS expr %prec UMINUS
                | NOT expr'''
        p[0] = N.UnaryOp(p[1], p[2], line=p.lineno(1))

    def p_expr_plus(self, p):
        'expr : PLUS expr %prec UMINUS'
        p[0] = p[2]

    def p_expr_prefix(self, p):
        '''expr : INC lvalue
                | DEC lvalue'''
        p[0] = N.IncDec(p[1], p[2], True, line=p.lineno(1))

    def p_expr_postfix(self, p):
        '''expr : lvalue INC
                | lvalue DEC'''
        p[0] = N.IncDec(p[2], p[1], False, line=p[1].line)

    def p_expr_group(self, p):
        'expr : LPAREN expr RPAREN'
        p[0] = p[2]

    def p_expr_number(self, p):
        '''expr : INT_LIT
                | FLOAT_LIT'''
        p[0] = N.Num(p[1], line=p.lineno(1))

    def p_expr_bool(self, p):
        '''expr : TRUE
                | FALSE'''
        p[0] = N.BoolLit(p[1] == 'true', line=p.lineno(1))

    def p_expr_lvalue(self, p):
        'expr : lvalue'
        p[0] = p[1]

    def p_expr_call(self, p):
        'expr : ID LPAREN args RPAREN'
        p[0] = N.Call(p[1], p[3], line=p.lineno(1))

    def p_args(self, p):
        '''args : arg_list
                | empty'''
        p[0] = p[1] or []

    def p_arg_list(self, p):
        '''arg_list : arg_list COMMA expr
                    | expr'''
        p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]

    def p_lvalue_var(self, p):
        'lvalue : ID'
        p[0] = N.Var(p[1], line=p.lineno(1))

    def p_lvalue_index(self, p):
        'lvalue : ID LBRACKET expr RBRACKET'
        p[0] = N.Index(p[1], p[3], line=p.lineno(1))

    def p_empty(self, p):
        'empty :'
        p[0] = None

    def p_error(self, t):
        if t is None:
            raise CompileError("неочікуваний кінець файлу")
        value = t.value if t.type != 'STRING_LIT' else '"' + t.value + '"'
        raise CompileError(f"неочікуваний токен {t.type} ({value!r})", t.lineno,
                           lexmod.column(t.lexer.lexdata, t.lexpos))


class PlainIfGrammar(Grammar):
    def p_if(self, p):
        'if_stmt : IF LPAREN expr RPAREN stmt'
        p[0] = N.If(p[3], p[5], None, line=p.lineno(1))


class Collector:
    def __init__(self):
        self.lines = []

    def _add(self, msg, *args, **kwargs):
        self.lines.append(msg % args if args else msg)

    debug = info = warning = error = critical = _add


MODES = {
    'full': (Grammar, PRECEDENCE),
    'no-else': (PlainIfGrammar, PRECEDENCE[2:]),
    'none': (PlainIfGrammar, (('right', 'UMINUS'),)),
}

_cache = {}


def build(mode='full', report_dir=None):
    if report_dir is None and mode in _cache:
        return _cache[mode]
    log = Collector()
    kwargs = dict(module=MODES[mode][0](MODES[mode][1]), write_tables=False, errorlog=log,
                  debug=True, debuglog=yacc.NullLogger())
    if report_dir:
        os.makedirs(report_dir, exist_ok=True)
        del kwargs['debuglog']
        kwargs.update(outputdir=report_dir, debugfile=f'parser_{mode}.out')
    parser = yacc.yacc(**kwargs)
    result = (parser, [line for line in log.lines if 'conflict' in line])
    if report_dir is None:
        _cache[mode] = result
    return result


def parse(source, mode='full'):
    parser, _ = build(mode)
    return parser.parse(source, lexer=lexmod.make_lexer())
