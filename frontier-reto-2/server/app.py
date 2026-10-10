"""Adaptador HTTP con la biblioteca estándar. Toda la lógica vive en core.http.responder.

Arranque (desde frontier-reto-2/): TEAM_TOKEN=<token> PORT=8000 python3 -m server.app
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core import Store, responder


def crear_servidor(token_valido: str, host: str = "0.0.0.0", port: int = 8000) -> ThreadingHTTPServer:
    store = Store(token_valido)  # estado en memoria, un solo proceso
    lock = threading.Lock()  # responder muta estado: se serializa

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _atender(self):
            largo = self.headers.get("Content-Length")
            cuerpo = None
            if largo is not None:
                try:
                    cuerpo = self.rfile.read(max(0, int(largo)))
                except ValueError:
                    cuerpo = b""
            ruta = self.path.split("?", 1)[0]  # SUPUESTO: el query string se ignora
            with lock:
                status, contenido = responder(
                    store, self.command, ruta, self.headers.get("Authorization"), cuerpo
                )
                x_req = store.ultimo_x_req
            if isinstance(contenido, str):
                datos, tipo = contenido.encode("utf-8"), "text/plain; charset=utf-8"
            else:
                datos = json.dumps(contenido, ensure_ascii=False).encode("utf-8")
                tipo = "application/json; charset=utf-8"
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            if x_req is not None:  # X-Req: no se compara, pero el original lo manda
                self.send_header("X-Req", str(x_req))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(datos)

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _atender

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def main():
    token = os.environ.get("TEAM_TOKEN")
    if not token:
        raise SystemExit("falta la variable de entorno TEAM_TOKEN")
    port = int(os.environ.get("PORT", "8000"))
    servidor = crear_servidor(token, "0.0.0.0", port)
    print(f"escuchando en 0.0.0.0:{port}", flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
