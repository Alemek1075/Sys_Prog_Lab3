import argparse
import json
import sys

from . import parser as grammar
from .pipeline import compile_source, run_python


def draw(node, prefix='', last=True, top=True):
    role = f"{node['role']}: " if node.get('role') else ''
    if top:
        lines = [f"{node['type']}  {node['label']}"]
    else:
        lines = [prefix + ('└─ ' if last else '├─ ') + role + node['label'] + f"   [{node['type']}]"]
    kids = node['children']
    for i, child in enumerate(kids):
        extend = '' if top else ('   ' if last else '│  ')
        lines += draw(child, prefix + extend, i == len(kids) - 1, False)
    return lines


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')

    ap = argparse.ArgumentParser(prog='python -m cpptrans',
                                 description='Транслятор підмножини C++ у Python (PLY, LALR(1))')
    ap.add_argument('file', nargs='?', help='вхідний .cpp файл')
    ap.add_argument('--tokens', action='store_true', help='показати потік токенів')
    ap.add_argument('--ast', action='store_true', help='надрукувати AST деревом')
    ap.add_argument('--ast-json', metavar='FILE', help='зберегти AST у JSON')
    ap.add_argument('--py', metavar='FILE', help='зберегти згенерований Python')
    ap.add_argument('--show-py', action='store_true', help='надрукувати згенерований Python')
    ap.add_argument('--run', action='store_true', help='виконати AST інтерпретатором')
    ap.add_argument('--run-py', action='store_true', help='запустити згенерований Python')
    ap.add_argument('--stdin', default=None, help='вхідні дані для cin (інакше читається з консолі)')
    ap.add_argument('--mode', choices=['full', 'no-else', 'none'], default='full',
                    help='таблиця пріоритетів: повна, без правила для else, майже порожня')
    ap.add_argument('--grammar', metavar='DIR', help='записати parser.out з LALR-автоматом у теку')
    ap.add_argument('--serve', action='store_true', help='запустити веб-інтерфейс')
    ap.add_argument('--port', type=int, default=8765)
    args = ap.parse_args(argv)

    if args.serve:
        from .server import serve
        serve(args.port)
        return 0

    if args.grammar:
        for mode in ('full', 'no-else', 'none'):
            _, conflicts = grammar.build(mode, report_dir=args.grammar)
            print(f"{mode:8} -> {args.grammar}/parser_{mode}.out  конфлікти: {', '.join(conflicts) or 'немає'}")
        if not args.file:
            return 0

    if not args.file:
        ap.print_help()
        return 1

    with open(args.file, encoding='utf-8') as f:
        source = f.read()

    stdin = args.stdin
    if stdin is None and (args.run or args.run_py):
        stdin = '' if sys.stdin.isatty() and 'cin' not in source else None
        if stdin is None:
            print('введіть дані для cin (Ctrl+Z, Enter у Windows або Ctrl+D для завершення):', file=sys.stderr)
            stdin = sys.stdin.read()
    stdin = (stdin or '').replace('\\n', '\n')

    result = compile_source(source, stdin=stdin, mode=args.mode, interpret=args.run)

    for c in result['conflicts']:
        print(f"[yacc] {c}", file=sys.stderr)

    if args.tokens:
        for t in result['tokens']:
            print(f"{t['line']:>4}:{t['col']:<3} {t['type']:<11} {t['value']!r}")

    if result['errors']:
        for e in result['errors']:
            stage = {'syntax': 'синтаксична помилка', 'semantic': 'семантична помилка'}.get(e['stage'], e['stage'])
            where = f"рядок {e['line']}" + (f", позиція {e['col']}" if e['col'] else '') if e['line'] else ''
            print(f"{args.file}: {where}: {stage}: {e['message']}", file=sys.stderr)
        return 2

    for w in result['warnings']:
        print(f"попередження: {w}", file=sys.stderr)

    if args.ast:
        print('\n'.join(draw(result['ast'])))
    if args.ast_json:
        with open(args.ast_json, 'w', encoding='utf-8') as f:
            json.dump(result['ast'], f, ensure_ascii=False, indent=1)
    if args.py:
        with open(args.py, 'w', encoding='utf-8', newline='\n') as f:
            f.write(result['python'])
    if args.show_py:
        print(result['python'])

    if args.run:
        run = result['run']
        sys.stdout.write(run['stdout'])
        if run['error']:
            print(f"помилка виконання: {run['error']}", file=sys.stderr)
            return 3
        print(f"[інтерпретатор] main повернула {run['code']}, {run['time']*1000:.1f} мс", file=sys.stderr)

    if args.run_py:
        r = run_python(result['python'], stdin)
        sys.stdout.write(r['stdout'])
        sys.stderr.write(r['stderr'])
        print(f"[python] код виходу {r['code']}, {r['time']*1000:.1f} мс", file=sys.stderr)

    if not any([args.tokens, args.ast, args.ast_json, args.py, args.show_py, args.run, args.run_py]):
        print(result['python'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
