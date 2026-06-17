import http.server, socketserver, webbrowser, threading, os

PORT = 8080
DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def log_message(self, fmt, *args):
        pass


webbrowser.open(f"http://localhost:{PORT}/chat.html")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Chat at http://localhost:{PORT}/chat.html")
    httpd.serve_forever()
