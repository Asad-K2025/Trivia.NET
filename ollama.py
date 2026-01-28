# This file was created by a staff member for INFO1112 at the University of Sydney, and is not the work of the repository owner.

from http.server import HTTPServer, BaseHTTPRequestHandler
import json

BODY = json.dumps(
    {
        "model": "llama3.2",
        "created_at": "2023-12-12T14:13:43.416799Z",
        "message": {"role": "assistant", "content": "Hello! How are you today?"},
        "done": True,
        "total_duration": 5191566416,
        "load_duration": 2154458,
        "prompt_eval_count": 26,
        "prompt_eval_duration": 383809000,
        "eval_count": 298,
        "eval_duration": 4799921000,
    }
).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def _send(self):
        if self.path == "/api/chat":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(BODY)

    def do_GET(self):
        self._send()

    def do_POST(self):
        self._send()


HTTPServer(("", 8000), Handler).serve_forever()
