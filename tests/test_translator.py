import glob
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cpptrans import parser
from cpptrans.pipeline import compile_source


def wrap(body, before=''):
    return f'#include <iostream>\nusing namespace std;\n{before}\nint main() {{\n{body}\nreturn 0;\n}}\n'


class Both(unittest.TestCase):
    def check(self, source, expected, stdin=''):
        r = compile_source(source, stdin=stdin, run_generated=True)
        self.assertEqual(r['errors'], [], r['errors'])
        self.assertIsNone(r['run']['error'])
        self.assertEqual(r['run']['stdout'], expected)
        self.assertEqual(r['python_run']['stdout'], expected, r['python_run']['stderr'] + r['python'])

    def test_examples_agree(self):
        for path in sorted(glob.glob(os.path.join(ROOT, 'examples', '*.cpp'))):
            if path.endswith('errors.cpp'):
                continue
            with open(path, encoding='utf-8') as f:
                r = compile_source(f.read(), stdin='5', run_generated=True)
            with self.subTest(path=os.path.basename(path)):
                self.assertEqual(r['errors'], [])
                self.assertEqual(r['run']['stdout'], r['python_run']['stdout'])

    def test_integer_division_truncates(self):
        self.check(wrap('cout << 7 / 2 << " " << -7 / 2 << " " << -7 % 3 << " " << 7 % -3 << endl;'), '3 -3 -1 1\n')

    def test_double_output(self):
        self.check(wrap('double d = 1.0 / 3; cout << d << " " << 2.5 * 2 << " " << 1e10 << endl;'), '0.333333 5 1e+10\n')

    def test_bool_prints_as_number(self):
        self.check(wrap('bool b = 3 > 2; cout << b << (1 && 0) << (2 || 0) << !5 << endl;'), '1010\n')

    def test_narrowing(self):
        self.check(wrap('int x = 3.9; int y = -3.9; x += 0.5; cout << x << " " << y << endl;'), '3 -3\n')

    def test_compound_and_incdec(self):
        self.check(wrap('int a = 10; a -= 3; a *= 2; a /= 3; a %= 3; int b = a++; int c = --a;'
                        'cout << a << b << c << endl;'), '111\n')

    def test_for_continue_runs_step(self):
        self.check(wrap('for (int i = 0; i < 6; i++) { if (i % 2) continue; cout << i; } cout << endl;'), '024\n')

    def test_do_while_continue_checks_condition(self):
        self.check(wrap('int i = 0; do { i++; if (i == 2) continue; cout << i; } while (i < 4); cout << endl;'), '134\n')

    def test_nested_break(self):
        self.check(wrap('for (int i = 0; i < 3; i++) { for (int j = 0; j < 3; j++) { if (j == i) break; cout << j; } }'
                        'cout << endl;'), '001\n')

    def test_shadowing(self):
        self.check(wrap('int x = 1; { int x = 2; cout << x; } cout << x; for (int x = 5; x < 6; x++) cout << x; cout << endl;'),
                   '215\n')

    def test_globals(self):
        src = wrap('bump(); bump(); cout << counter << endl;',
                   before='int counter = 0;\nvoid bump() { counter += 1; }')
        self.check(src, '2\n')

    def test_arrays_by_reference(self):
        src = wrap('int a[3] = {1, 2}; fill(a, 3); cout << a[0] << a[1] << a[2] << endl;',
                   before='void fill(int a[], int n) { for (int i = 0; i < n; i++) a[i] += 10; }')
        self.check(src, '111210\n')

    def test_assignment_as_expression(self):
        self.check(wrap('int a, b; int arr[2]; a = b = 4; arr[1] = a + (b += 1);'
                        'cout << a << b << arr[1] << arr[0]++ << arr[0] << endl;'), '45901\n')

    def test_comparison_chains_like_c(self):
        self.check(wrap('int a = 3, b = 2, c = 1; cout << (a > b > c) << (c < b == 1) << endl;'), '01\n')

    def test_python_keywords_renamed(self):
        src = wrap('int lambda = 2; int print = len(lambda); cout << (print > 3 ? print : -1) << endl;',
                   before='int len(int x) { return x * x; }')
        self.check(src, '4\n')

    def test_cin(self):
        self.check(wrap('int n; double d; cin >> n >> d; cout << n * 2 << " " << d / 2 << endl;'), '42 1.25\n', stdin='21 2.5')

    def test_dangling_else_binds_inner(self):
        self.check(wrap('if (1) if (0) cout << "a"; else cout << "b"; cout << endl;'), 'b\n')

    def test_recursion(self):
        src = wrap('cout << fib(15) << endl;', before='int fib(int n) { return n < 2 ? n : fib(n - 1) + fib(n - 2); }')
        self.check(src, '610\n')


class Errors(unittest.TestCase):
    def error(self, source):
        r = compile_source(source, interpret=False)
        self.assertTrue(r['errors'], 'очікувалась помилка')
        return r['errors'][0]

    def test_syntax_error_position(self):
        e = self.error('int main() {\n  int x = 3\n  return x;\n}\n')
        self.assertEqual((e['stage'], e['line']), ('syntax', 3))

    def test_unexpected_eof(self):
        self.assertIn('кінець', self.error('int main() { return 0;')['message'])

    def test_undeclared(self):
        self.assertEqual(self.error(wrap('y = 3;'))['stage'], 'semantic')

    def test_redeclared(self):
        self.assertIn('вже оголошено', self.error(wrap('int a; int a;'))['message'])

    def test_arity(self):
        self.assertIn('аргумент', self.error(wrap('f(1);', before='int f(int a, int b) { return a; }'))['message'])

    def test_break_outside_loop(self):
        self.assertIn('поза циклом', self.error(wrap('break;'))['message'])

    def test_void_value(self):
        self.error(wrap('int x = g();', before='void g() { }'))

    def test_modulo_double(self):
        self.error(wrap('double d = 5.5 % 2;'))

    def test_no_main(self):
        self.error('int f() { return 1; }')

    def test_runtime_errors(self):
        r = compile_source(wrap('int a[3]; a[5] = 1;'))
        self.assertIn('поза межами', r['run']['error'])
        r = compile_source(wrap('int z = 0; cout << 1 / z;'))
        self.assertIn('нуль', r['run']['error'])
        r = compile_source(wrap('while (true) { }'))
        self.assertIn('ліміт', r['run']['error'])


class Grammar(unittest.TestCase):
    def test_conflict_counts(self):
        self.assertEqual(parser.build('full')[1], [])
        self.assertEqual(parser.build('no-else')[1], ['1 shift/reduce conflict'])
        self.assertTrue(parser.build('none')[1][0].endswith('shift/reduce conflicts'))

    def test_precedence_shapes_tree(self):
        tree = parser.parse(wrap('int x = 1 + 2 * 3 - 4;'))
        init = tree.items[0].body.stmts[0].init
        self.assertEqual((init.op, init.left.op, init.left.right.op), ('-', '+', '*'))


if __name__ == '__main__':
    unittest.main()
