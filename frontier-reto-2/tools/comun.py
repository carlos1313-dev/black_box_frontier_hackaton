"""Piezas compartidas por fuzz.py y canary.py: harness falso, comparación y formato de diferencias.

La comparación reutiliza `tools.replay` (iguales + reconstruir), sin duplicar sus reglas.
"""

import json
from dataclasses import dataclass

from core import Store, responder

from .harness import Respuesta, Secuencia
from .replay import TOKEN_PROPIO, iguales, reconstruir


class HarnessFalso:
    """Sustituye a `Harness` sin red ni log: responde con su propio `responder`.

    Construye la request desde los argumentos originales (no desde la línea del log), de modo que
    también ejercita `reconstruir`. Interfaz compatible: `.secuencia()` y `.http()`.
    """

    def __init__(self):
        self.store = Store(TOKEN_PROPIO)
        self.lineas: list[dict] = []
        self.n_requests = 0
        self._siguiente_id = 1

    def secuencia(self, etiqueta: str, hipotesis: str) -> Secuencia:
        seq = f"dry-{etiqueta}"
        self.http(seq, f"reset · {hipotesis}", metodo="POST", ruta="/__reset")
        return Secuencia(self, seq)

    def http(self, seq, hipotesis, metodo="POST", ruta="/msg", body=None, raw=None,
             auth="propio", content_type="application/json"):
        if auth == "propio":
            authorization = "Bearer " + TOKEN_PROPIO
        elif auth == "ninguno":
            authorization = None
        else:
            authorization = auth
        if raw is not None:
            datos, enviado = raw.encode("utf-8"), raw
        elif body is not None:
            datos, enviado = json.dumps(body, ensure_ascii=False).encode("utf-8"), body
        else:
            datos, enviado = None, None
        status, cuerpo = responder(self.store, metodo, ruta, authorization, datos)
        self.n_requests += 1
        linea = {
            "id": self._siguiente_id, "seq": seq, "x_req": self.store.ultimo_x_req,
            "hipotesis": hipotesis, "request": enviado, "status": status,
            "response": json.loads(json.dumps(cuerpo)),
        }
        if (metodo, ruta) != ("POST", "/msg"):
            linea["metodo"], linea["ruta"] = metodo, ruta
        if auth != "propio":
            linea["auth"] = auth
        if raw is not None:
            linea["raw"] = True
        self._siguiente_id += 1
        self.lineas.append(linea)
        return Respuesta(linea)


@dataclass
class Diferencia:
    id: int
    seq: str
    request: str
    real: str
    clon: str
    hipotesis: str = ""

    def como_dict(self) -> dict:
        return {"id": self.id, "seq": self.seq, "request": self.request,
                "real": self.real, "clon": self.clon, "hipotesis": self.hipotesis}

    def texto(self) -> str:
        h = f"\n  hipótesis: {self.hipotesis}" if self.hipotesis else ""
        return (f"DIFF id={self.id} seq={self.seq}{h}\n  request: {self.request}\n"
                f"  real:    {self.real}\n  clon:    {self.clon}")


def describir_request(linea: dict) -> str:
    metodo = linea.get("metodo") or "POST"
    ruta = linea.get("ruta") or "/msg"
    partes = [f"{metodo} {ruta}"]
    if linea.get("auth"):
        partes.append(f"auth={linea['auth']}")
    if linea.get("raw"):
        partes.append("raw")
    partes.append(json.dumps(linea.get("request"), ensure_ascii=False))
    return " ".join(partes)


def comparar(store: Store, r: Respuesta, hipotesis: str = "") -> Diferencia | None:
    """Ejecuta en el clon (sobre `store`, que avanza) la misma request y compara con la real."""
    status, cuerpo = responder(store, *reconstruir(r.linea))
    if status == r.status and iguales(r.body, cuerpo):
        return None
    return Diferencia(
        r.id, r.linea.get("seq", ""), describir_request(r.linea),
        f"{r.status} {json.dumps(r.body, ensure_ascii=False)}",
        f"{status} {json.dumps(cuerpo, ensure_ascii=False)}",
        hipotesis or r.linea.get("hipotesis", ""),
    )
