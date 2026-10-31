import json
import os
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .pipeline import compile_source

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, 'web')
EXAMPLES = os.path.join(ROOT, 'examples')


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB, **kwargs)

    def log_message(self, fmt, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/api/examples':
            items = []
            for name in sorted(os.listdir(EXAMPLES)):
                if name.endswith('.cpp'):
                    with open(os.path.join(EXAMPLES, name), encoding='utf-8') as f:
                        items.append({'name': name, 'source': f.read()})
            return self.send_json(items)
        return super().do_GET()

    def do_POST(self):
        if self.path != '/api/compile':
            return self.send_json({'error': 'not found'}, 404)
        length = int(self.headers.get('Content-Length', 0))
        try:
            req = json.loads(self.rfile.read(length).decode('utf-8'))
        except ValueError:
            return self.send_json({'error': 'bad json'}, 400)
        result = compile_source(req.get('source', ''), stdin=req.get('stdin', ''),
                                mode=req.get('mode', 'full'), run_generated=True)
        self.send_json(result)


def serve(port=8765):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = f'http://127.0.0.1:{port}/'
    print(f'веб-інтерфейс: {url}  (Ctrl+C щоб зупинити)')
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
