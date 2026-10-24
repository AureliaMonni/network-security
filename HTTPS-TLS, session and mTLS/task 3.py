from http.server import HTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
import threading
import ssl
import json
import secrets

HOST = "0.0.0.0"

HTTPS_PORT = 8443
MTLS_PORT = 8444

BASE_DIR = Path(__file__).resolve().parent

SERVER_CERT = BASE_DIR / "server.crt"
SERVER_KEY = BASE_DIR / "server.key"
CA_CERT = BASE_DIR / "ca.crt"


sessions = {}

class HTTPSRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/":
            self.send_response(200)
            self.end_headers()
            return

        if self.path == "/me":

            cookie_header = self.headers.get("Cookie")

            if not cookie_header:
                self.send_response(401)
                self.end_headers()
                return

            cookie = SimpleCookie()
            cookie.load(cookie_header)

            if "session" not in cookie:
                self.send_response(401)
                self.end_headers()
                return

            session_id = cookie["session"].value

            user = sessions.get(session_id)

            if user is None:
                self.send_response(401)
                self.end_headers()
                return

            response = json.dumps({
                "user": user
            }).encode("utf-8")

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json"
            )
            self.send_header(
                "Content-Length",
                str(len(response))
            )
            self.end_headers()

            self.wfile.write(response)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):

        if self.path != "/login":
            self.send_response(404)
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

        if not isinstance(data, dict):
            self.send_response(400)
            self.end_headers()
            return

        user = data.get("user")
        password = data.get("password")

        if not isinstance(user, str):
            self.send_response(400)
            self.end_headers()
            return

        if password != "netsec":
            self.send_response(401)
            self.end_headers()
            return

        session_id = secrets.token_urlsafe(32)

        sessions[session_id] = user

        self.send_response(200)

        self.send_header(
            "Set-Cookie",
            f"session={session_id}; Path=/; Secure; HttpOnly"
        )

        self.end_headers()

class MTLSRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path != "/whoami":
            self.send_response(404)
            self.end_headers()
            return

        client_cert = self.connection.getpeercert()

        common_name = None

        for item in client_cert.get("subject", ()):
            for key, value in item:

                if key == "commonName":
                    common_name = value
                    break

            if common_name is not None:
                break

        if common_name is None:
            self.send_response(400)
            self.end_headers()
            return

        response = common_name.encode("utf-8")

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain"
        )
        self.send_header(
            "Content-Length",
            str(len(response))
        )
        self.end_headers()

        self.wfile.write(response)

def create_https_server():

    server = HTTPServer(
        (HOST, HTTPS_PORT),
        HTTPSRequestHandler
    )

    context = ssl.SSLContext(
        ssl.PROTOCOL_TLS_SERVER
    )

    context.load_cert_chain(
        certfile=SERVER_CERT,
        keyfile=SERVER_KEY
    )

    server.socket = context.wrap_socket(
        server.socket,
        server_side=True
    )

    return server

def create_mtls_server():

    server = HTTPServer(
        (HOST, MTLS_PORT),
        MTLSRequestHandler
    )

    context = ssl.SSLContext(
        ssl.PROTOCOL_TLS_SERVER
    )

    context.load_cert_chain(
        certfile=SERVER_CERT,
        keyfile=SERVER_KEY
    )

    context.load_verify_locations(
        cafile=CA_CERT
    )

    context.verify_mode = ssl.CERT_REQUIRED

    server.socket = context.wrap_socket(
        server.socket,
        server_side=True
    )

    return server

def main():

    https_server = create_https_server()
    mtls_server = create_mtls_server()

    https_thread = threading.Thread(
        target=https_server.serve_forever,
        name="HTTPS-8443"
    )

    mtls_thread = threading.Thread(
        target=mtls_server.serve_forever,
        name="mTLS-8444"
    )

    https_thread.start()
    mtls_thread.start()

    print(
        f"HTTPS server listening on port {HTTPS_PORT}"
    )

    print(
        f"mTLS server listening on port {MTLS_PORT}"
    )

    try:
        https_thread.join()
        mtls_thread.join()

    except KeyboardInterrupt:

        print("\nStopping servers...")

        https_server.shutdown()
        mtls_server.shutdown()

        https_thread.join()
        mtls_thread.join()

        https_server.server_close()
        mtls_server.server_close()

        print("Servers stopped.")


if __name__ == "__main__":
    main()
