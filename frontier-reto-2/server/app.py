"""Adaptador HTTP (Starlette + uvicorn). Toda la lógica vive en core.http.responder.

Una sola ruta comodín: ASGI crudo con las clases Request/Response de Starlette, sin enrutado ni
validación automática (sus 404/405/422 no coinciden con el original).
Arranque: uvicorn server.app:app --host 0.0.0.0 --port $PORT --workers 1
"""

import json
import os

from starlette.requests import Request
from starlette.responses import Response

from core import Store, responder


def crear_app(token_valido: str):
    store = Store(token_valido)  # estado en memoria, un solo proceso

    async def manejar(request: Request) -> Response:
        cuerpo = await request.body()
        status, contenido = responder(
            store,
            request.method,
            request.scope["path"],  # SUPUESTO: el query string se ignora
            request.headers.get("authorization"),
            cuerpo,
        )
        if isinstance(contenido, str):
            datos, tipo = contenido.encode("utf-8"), "text/plain; charset=utf-8"
        else:
            datos = json.dumps(contenido, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            tipo = "application/json; charset=utf-8"
        headers = {}
        if store.ultimo_x_req is not None:  # X-Req: no se compara, pero el original lo manda
            headers["X-Req"] = str(store.ultimo_x_req)
        return Response(datos, status_code=status, media_type=tipo, headers=headers)

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                msg = await receive()
                if msg["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif msg["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        elif scope["type"] == "http":
            request = Request(scope, receive)
            response = await manejar(request)
            await response(scope, receive, send)

    return app


def _app_desde_entorno():
    token = os.environ.get("TEAM_TOKEN")
    if not token:
        raise RuntimeError("falta la variable de entorno TEAM_TOKEN")
    return crear_app(token)


app = _app_desde_entorno()
