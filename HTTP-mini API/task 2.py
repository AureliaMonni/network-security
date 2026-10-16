from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json


HOST = "0.0.0.0"
PORT = 8080

notes = {}
next_id = 1

class MyHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        global next_id

        parsed = urlparse(self.path)

        if parsed.path != "/notes":
            self.send_response(404)
            self.end_headers()
            return

        content_type = self.headers.get("Content-Type")

        if content_type != "application/json":
            self.send_response(415)
            self.end_headers()
            return

        content_length = int(
            self.headers.get("Content-Length", 0)
        )

        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_response(400)
            self.end_headers()
            return

        if (
                not isinstance(data, dict)
                or "text" not in data
                or not isinstance(data["text"], str)
        ):
            self.send_response(400)
            self.end_headers()
            return

        note_id = next_id
        notes[note_id] = data["text"]
        next_id += 1

        response = json.dumps({
            "id": note_id
        }).encode("utf-8")

        self.send_response(201)
        self.send_header(
            "Content-Type",
            "application/json"
        )
        self.end_headers()

        self.wfile.write(response)


    def do_GET(self):

        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.send_response(200)
            self.end_headers()

        elif parsed.path == "/echo":
            query = parse_qs(parsed.query)

            msg = query.get("msg", [""])[0]

            body = json.dumps({
                "msg": msg
            }).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()

server = HTTPServer((HOST, PORT), MyHandler)

server.serve_forever()