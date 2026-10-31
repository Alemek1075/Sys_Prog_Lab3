import os
import subprocess
import sys
import tempfile
import time

from . import codegen, interp, lexer, parser, semantic
from .errors import CompileError, RuntimeFault


def run_python(code, stdin='', timeout=10):
    fd, path = tempfile.mkstemp(suffix='.py')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(code)
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    try:
        started = time.perf_counter()
        proc = subprocess.run([sys.executable, path], input=stdin, capture_output=True,
                              text=True, encoding='utf-8', timeout=timeout, env=env)
        elapsed = time.perf_counter() - started
        return {'stdout': proc.stdout, 'stderr': proc.stderr, 'code': proc.returncode, 'time': elapsed}
    except subprocess.TimeoutExpired:
        return {'stdout': '', 'stderr': f'перевищено {timeout} с', 'code': None, 'time': timeout}
    finally:
        os.remove(path)


def compile_source(source, stdin='', mode='full', interpret=True, run_generated=False):
    result = {'tokens': [], 'ast': None, 'python': None, 'warnings': [], 'errors': [],
              'conflicts': parser.build(mode)[1], 'run': None, 'python_run': None}
    try:
        result['tokens'] = lexer.tokenize(source)
        tree = parser.parse(source, mode)
        result['ast'] = tree.to_json()
        result['warnings'] = semantic.analyze(tree)
        result['ast'] = tree.to_json()
        result['python'] = codegen.generate(tree)
    except CompileError as e:
        result['errors'].append(e.to_dict())
        return result
    if interpret:
        started = time.perf_counter()
        machine = interp.Interpreter(tree, stdin)
        try:
            out, code = machine.run()
            result['run'] = {'stdout': out, 'code': code, 'error': None}
        except RuntimeFault as e:
            result['run'] = {'stdout': ''.join(machine.out), 'code': None, 'error': str(e)}
        result['run']['time'] = time.perf_counter() - started
    if run_generated:
        result['python_run'] = run_python(result['python'], stdin)
    return result
