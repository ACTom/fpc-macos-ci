"""Disposable loopback fixture for the real ssockets peer regression."""
import socket
import subprocess
import sys
import threading
listener = socket.socket()
listener.bind(('127.0.0.1', 0))
listener.listen(1)
listener.settimeout(5)
port = listener.getsockname()[1]
errors = []
def serve():
    try:
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(3)
            data = b''
            while b'\r\n\r\n' not in data:
                part = connection.recv(4096)
                if not part:
                    raise RuntimeError('Incomplete fixture request')
                data += part
            connection.sendall(b'HTTP/1.0 200 OK\r\nContent-Length: 3\r\n\r\nabc')
    except Exception as exc:
        errors.append(str(exc))
    finally:
        listener.close()
worker = threading.Thread(target=serve)
worker.start()
run = subprocess.run([sys.argv[1], '127.0.0.1', str(port)], timeout=10)
worker.join(5)
assert not worker.is_alive() and not errors, errors
raise SystemExit(run.returncode)
