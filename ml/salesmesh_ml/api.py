"""Local HTTP adapter: python -m salesmesh_ml.api --model models/model.json."""
import argparse
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .engine import HybridRecommender, ValidationError


def make_handler(model, origins=(), api_key=None):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, code, data):
            body = json.dumps(data, allow_nan=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            origin = self.headers.get('Origin')
            if origin in origins:
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Vary', 'Origin')
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            if self.headers.get('Origin') not in origins:
                self.respond(403, {'error': 'origin_not_allowed'}); return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Vary', 'Origin')
            self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.send_header('Content-Length', '0')
            self.end_headers()

        def do_GET(self):
            if self.path == '/health': self.respond(200, {'status': 'ok', 'model_loaded': True})
            else: self.respond(404, {'error': 'not_found'})

        def do_POST(self):
            if self.path != '/recommend': self.respond(404, {'error': 'not_found'}); return
            origin = self.headers.get('Origin')
            if origin and origin not in origins:
                self.respond(403, {'error': 'origin_not_allowed'}); return
            if api_key and not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer '+api_key):
                self.respond(401, {'error': 'unauthorized'}); return
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                self.respond(415, {'error': 'application/json required'}); return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2_000_000:
                    self.respond(413, {'error': 'body must be between 1 byte and 2 MB'}); return
                self.connection.settimeout(10)
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict): raise ValidationError('request must be an object')
                # Current agent state is required: never silently use stale training capacity.
                if type(payload.get('include_rejected', False)) is not bool:
                    raise ValidationError('include_rejected must be boolean')
                result = model.recommend(payload['task'], payload['agents'], payload.get('top_k', 3), payload.get('include_rejected', False))
                self.respond(200, result)
            except (ValueError, KeyError, TypeError, UnicodeError) as error:
                self.respond(400, {'error': 'invalid_request', 'detail': str(error)})
            except TimeoutError:
                self.respond(408, {'error': 'request_timeout'})

        def log_message(self, format, *args):
            # Never log submitted profiles or API credentials.
            return
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='models/model.json')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--allow-origin', action='append', default=[])
    args = parser.parse_args()
    model = HybridRecommender.load(args.model)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(model, args.allow_origin, os.getenv('SALESMESH_API_KEY')))
    server.daemon_threads = True
    print(f'SalesMesh ML API: http://127.0.0.1:{args.port} (Ctrl+C to stop)', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()
