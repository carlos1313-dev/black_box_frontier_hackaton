"""Capa HTTP como función pura: (método, ruta, auth, cuerpo) -> (status, cuerpo).

Sin dependencias de servidor; el adaptador (server/app.py) solo traduce.
Las referencias entre paréntesis son ids de experimentos.jsonl.
"""

import json

from . import commands
from .errors import ErrorServicio
from .state import State

# Rutas conocidas: EXACTAS, sensibles a mayúsculas, sin barra final (31-39).
RUTAS_CONOCIDAS = {("POST", "/msg"), ("POST", "/__reset"), ("GET", "/health")}
# Cuerpo de más de 8192 bytes -> 413 E101; 8192 exactos pasan (búsqueda binaria, ids 974-975).
LIMITE_CUERPO = 8192


class Store:
    """Estados por token. Solo `token_valido` pasa la autenticación."""

    def __init__(self, token_valido: str, version: int = 2):
        self.token_valido = token_valido
        self.version = version
        self.estados: dict[str, State] = {}
        self.contador_req: dict[str, int] = {}
        # Valor de X-Req de la última respuesta, o None si no lleva header.
        self.ultimo_x_req: int | None = None

    def estado(self, token: str) -> State:
        return self.estados.setdefault(token, State(self.version))

    def reiniciar(self, token: str) -> None:
        # /__reset reinicia el estado pero NO el contador X-Req (ids 40, 58).
        self.estados[token] = State(self.version)

    def contar_req(self, token: str) -> int:
        n = self.contador_req.get(token, 0) + 1
        self.contador_req[token] = n
        return n


def _error(codigo: str) -> tuple[int, dict]:
    return ErrorServicio(codigo).respuesta()


def _autorizado(store: Store, authorization: str | None) -> bool:
    # Exactamente "Bearer " + token; el prefijo es sensible a mayúsculas (24-30, 56).
    # El valor del header se recorta como en HTTP: un espacio final pasa (927), uno doble interno no (926).
    return authorization is not None and authorization.strip() == "Bearer " + store.token_valido


def _rechazar_constante(nombre: str):
    raise ValueError(f"constante no JSON: {nombre}")


def _parsear_m(cuerpo: bytes | None):
    """Devuelve (m, None) o (None, ErrorServicio)."""
    # Cuerpo ausente, vacío o no parseable como JSON -> E100 (40-43); el Content-Type da igual (53, 54).
    if not cuerpo:
        return None, ErrorServicio("E100")
    try:
        # JSON estricto: NaN/Infinity -> E100 (248); un BOM inicial también falla (251).
        datos = json.loads(cuerpo.decode("utf-8"), parse_constant=_rechazar_constante)
    except (ValueError, UnicodeDecodeError):  # SUPUESTO: bytes no UTF-8 -> E100
        return None, ErrorServicio("E100")
    # No objeto, sin clave "m" (case-sensitive, 52) o m no string -> E102 (44-50). Extras se ignoran (51).
    if not isinstance(datos, dict) or not isinstance(datos.get("m"), str):
        return None, ErrorServicio("E102")
    return datos["m"], None


def responder(
    store: Store,
    metodo: str,
    ruta: str,
    authorization: str | None,
    cuerpo: bytes | None,
) -> tuple[int, dict | str]:
    store.ultimo_x_req = None
    ruta = ruta.split("?", 1)[0]  # el query string se ignora (918, 919)
    # 1. Ruta desconocida, ANTES que la auth (36).
    if (metodo, ruta) not in RUTAS_CONOCIDAS:
        if metodo == "HEAD":
            return 404, ""  # HEAD no lleva cuerpo (921)
        return _error("E404")
    # 2. Auth en las 3 rutas conocidas, incluida /health (24), antes del parseo del cuerpo (55).
    if not _autorizado(store, authorization):
        return _error("E001")
    token = store.token_valido

    if ruta == "/health":
        return 200, {"ok": True}  # (23)
    if ruta == "/__reset":
        store.reiniciar(token)
        return 200, {"ok": True}  # (1, 22, 57)

    # POST /msg autenticado: cuenta X-Req incluso si el cuerpo es inválido (40).
    store.ultimo_x_req = store.contar_req(token)
    # 3. Tamaño después de ruta y auth (978, 979) y antes del JSON (980). Mide el cuerpo entero (977).
    # SUPUESTO: se mide en bytes y solo aplica a /msg.
    if cuerpo is not None and len(cuerpo) > LIMITE_CUERPO:
        return _error("E101")
    m, err = _parsear_m(cuerpo)
    if err is not None:
        return err.respuesta()
    return commands.handle(store.estado(token), m)
