from http.server import HTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
import threading
import ssl
import json
import secrets


# ============================================================
# CONFIGURATION
# ============================================================

HOST = "0.0.0.0"

HTTPS_PORT = 8443
MTLS_PORT = 8444

# Directory containing this Python script.
# This avoids problems if the program is launched
# from a different working directory.
BASE_DIR = Path(__file__).resolve().parent

SERVER_CERT = BASE_DIR / "server.crt"
SERVER_KEY = BASE_DIR / "server.key"
CA_CERT = BASE_DIR / "ca.crt"


# In-memory session store:
# session_id -> username
sessions = {}


# ============================================================
# HTTPS SERVER - PORT 8443
# ============================================================

class HTTPSRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        # ----------------------------------------------------
        # GET /
        # ----------------------------------------------------
        if self.path == "/":
            self.send_response(200)
            self.end_headers()
            return

        # ----------------------------------------------------
        # GET /me
        # ----------------------------------------------------
        if self.path == "/me":

            cookie_header = self.headers.get("Cookie")

            # No cookie -> unauthorized
            if not cookie_header:
                self.send_response(401)
                self.end_headers()
                return

            cookie = SimpleCookie()
            cookie.load(cookie_header)

            # No session cookie -> unauthorized
            if "session" not in cookie:
                self.send_response(401)
                self.end_headers()
                return

            session_id = cookie["session"].value

            # Look up the session
            user = sessions.get(session_id)

            # Invalid session -> unauthorized
            if user is None:
                self.send_response(401)
                self.end_headers()
                return

            # Valid session
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

        # ----------------------------------------------------
        # Unknown resource
        # ----------------------------------------------------
        self.send_response(404)
        self.end_headers()

    def do_POST(self):

        # ----------------------------------------------------
        # Only POST /login is supported
        # ----------------------------------------------------
        if self.path != "/login":
            self.send_response(404)
            self.end_headers()
            return

        # Get the length of the JSON body
        content_length = int(
            self.headers.get("Content-Length", 0)
        )

        # Read request body
        body = self.rfile.read(content_length)

        # Parse JSON
        try:
            data = json.loads(body)

        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_response(400)
            self.end_headers()
            return

        # JSON must be an object
        if not isinstance(data, dict):
            self.send_response(400)
            self.end_headers()
            return

        user = data.get("user")
        password = data.get("password")

        # Validate username
        if not isinstance(user, str):
            self.send_response(400)
            self.end_headers()
            return

        # ----------------------------------------------------
        # Wrong password
        # ----------------------------------------------------
        if password != "netsec":
            self.send_response(401)
            self.end_headers()
            return

        # ----------------------------------------------------
        # Correct password -> create session
        # ----------------------------------------------------

        # Generate cryptographically secure session ID
        session_id = secrets.token_urlsafe(32)

        # Associate session with username
        sessions[session_id] = user

        self.send_response(200)

        # Session cookie:
        # Secure   -> sent only through HTTPS
        # HttpOnly -> inaccessible from JavaScript
        self.send_header(
            "Set-Cookie",
            f"session={session_id}; Path=/; Secure; HttpOnly"
        )

        self.end_headers()


# ============================================================
# mTLS SERVER - PORT 8444
# ============================================================

class MTLSRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        # ----------------------------------------------------
        # Only GET /whoami is supported
        # ----------------------------------------------------
        if self.path != "/whoami":
            self.send_response(404)
            self.end_headers()
            return

        # Retrieve the certificate presented by the client.
        #
        # Because ssl.CERT_REQUIRED is enabled below,
        # clients without a valid certificate are rejected
        # during the TLS handshake before reaching this code.
        client_cert = self.connection.getpeercert()

        # ----------------------------------------------------
        # Extract Common Name (CN)
        # ----------------------------------------------------
        common_name = None

        for item in client_cert.get("subject", ()):
            for key, value in item:

                if key == "commonName":
                    common_name = value
                    break

            if common_name is not None:
                break

        # Certificate has no CN
        if common_name is None:
            self.send_response(400)
            self.end_headers()
            return

        # Plain-text response
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


# ============================================================
# CREATE HTTPS SERVER - PORT 8443
# ============================================================

def create_https_server():

    server = HTTPServer(
        (HOST, HTTPS_PORT),
        HTTPSRequestHandler
    )

    context = ssl.SSLContext(
        ssl.PROTOCOL_TLS_SERVER
    )

    # Load server certificate and private key
    context.load_cert_chain(
        certfile=SERVER_CERT,
        keyfile=SERVER_KEY
    )

    # Enable TLS on the server socket
    server.socket = context.wrap_socket(
        server.socket,
        server_side=True
    )

    return server


# ============================================================
# CREATE mTLS SERVER - PORT 8444
# ============================================================

def create_mtls_server():

    server = HTTPServer(
        (HOST, MTLS_PORT),
        MTLSRequestHandler
    )

    context = ssl.SSLContext(
        ssl.PROTOCOL_TLS_SERVER
    )

    # Same server certificate used by port 8443
    context.load_cert_chain(
        certfile=SERVER_CERT,
        keyfile=SERVER_KEY
    )

    # Trust the course Certification Authority
    context.load_verify_locations(
        cafile=CA_CERT
    )

    # Client certificate is mandatory.
    #
    # No certificate -> TLS handshake rejected
    # Wrong CA       -> TLS handshake rejected
    context.verify_mode = ssl.CERT_REQUIRED

    # Enable TLS
    server.socket = context.wrap_socket(
        server.socket,
        server_side=True
    )

    return server


# ============================================================
# MAIN
# ============================================================

def main():

    https_server = create_https_server()
    mtls_server = create_mtls_server()

    # Thread for HTTPS server on port 8443
    https_thread = threading.Thread(
        target=https_server.serve_forever,
        name="HTTPS-8443"
    )

    # Thread for mTLS server on port 8444
    mtls_thread = threading.Thread(
        target=mtls_server.serve_forever,
        name="mTLS-8444"
    )

    # Start both servers
    https_thread.start()
    mtls_thread.start()

    print(
        f"HTTPS server listening on port {HTTPS_PORT}"
    )

    print(
        f"mTLS server listening on port {MTLS_PORT}"
    )

    try:
        # Keep main thread alive while servers are running
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
