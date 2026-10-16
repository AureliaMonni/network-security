import socket
import threading


HOST = "0.0.0.0"
PORT = 9001

store = {}
store_lock = threading.Lock()


def process_command(line):
    if line == "PING":
        return "PONG"

    if line.startswith("ECHO "):
        return line[5:]

    if line.startswith("SET "):
        rest = line[4:]

        parts = rest.split(" ", 1)

        if len(parts) != 2:
            return "ERR"

        key, value = parts

        if key == "" or value == "":
            return "ERR"

        with store_lock:
            store[key] = value

        return "OK"

    if line.startswith("GET "):
        key = line[4:]

        if key == "" or " " in key:
            return "ERR"

        with store_lock:
            if key in store:
                return store[key]

        return "NOT_FOUND"

    return "ERR"


def handle_client(client_socket):
    buffer = b""

    while True:
        data = client_socket.recv(4096)

        if not data:
            break

        buffer += data

        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line = line.decode("ascii")

            response = process_command(line)

            client_socket.sendall(
                (response + "\n").encode("ascii")
            )

    client_socket.close()


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server_socket.bind((HOST, PORT))
server_socket.listen()


while True:
    client_socket, client_address = server_socket.accept()

    thread = threading.Thread(
        target=handle_client,
        args=(client_socket,)
    )

    thread.start()