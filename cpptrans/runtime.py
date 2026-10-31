import sys


def _idiv(a, b):
    if b == 0:
        raise ZeroDivisionError("ділення на нуль")
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _imod(a, b):
    return a - b * _idiv(a, b)


def _fmt(value):
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, float):
        return '%g' % value
    return str(value)


def _out(*items):
    sys.stdout.write(''.join(item if isinstance(item, str) else _fmt(item) for item in items))


_tokens = []


def _read(kind):
    while not _tokens:
        line = sys.stdin.readline()
        if not line:
            raise EOFError("вхідні дані закінчились")
        _tokens.extend(reversed(line.split()))
    word = _tokens.pop()
    if kind is bool:
        return int(word) != 0
    return kind(word)


def _set(arr, i, value):
    arr[i] = value
    return value


def _postinc(arr, i, delta):
    old = arr[i]
    arr[i] = old + delta
    return old
