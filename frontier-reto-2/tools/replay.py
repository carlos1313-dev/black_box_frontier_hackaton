"""Reproductor: log JSONL -> core.http.responder -> diff -> % de conformidad.

Uso: python3 -m tools.replay [ruta_log]   (por defecto experimentos.jsonl)
Exit code 1 si hay diferencias.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from core import Store, responder

RAIZ = Path(__file__).resolve().parent.parent
LOG_POR_DEFECTO = RAIZ / "experimentos.jsonl"


@dataclass
class Resultado:
    total: int = 0  # líneas comparadas
    ok: int = 0
    ignoradas: int = 0
    diferencias: list = field(default_factory=list)

    @property
    def porcentaje(self) -> float:
        return 100.0 * self.ok / self.total if self.total else 100.0


def _parse_json(valor):
    """Devuelve (es_json, valor_parseado). Un str se intenta parsear como JSON."""
    if isinstance(valor, str):
        try:
            return True, json.loads(valor)
        except ValueError:
            return False, valor
    return True, valor


def iguales(esperado, obtenido) -> bool:
    """Regla del README: ambos JSON -> igualdad por valor; si no, texto exacto."""
    ej, ev = _parse_json(esperado)
    oj, ov = _parse_json(obtenido)
    if ej and oj:
        return ev == ov and _tipos_iguales(ev, ov)
    return esperado == obtenido


def _tipos_iguales(a, b) -> bool:
    # En Python True == 1; el evaluador distingue true de 1.
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, dict):
        return all(_tipos_iguales(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return all(_tipos_iguales(x, y) for x, y in zip(a, b))
    return True


def leer_log(ruta) -> list[dict]:
    lineas = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                lineas.append(json.loads(linea))
    return lineas


TOKEN_PROPIO = "<token-propio>"


def reconstruir(e: dict) -> tuple[str, str, str | None, bytes | None]:
    """Línea del log -> (metodo, ruta, authorization, cuerpo) para `responder`."""
    metodo = e.get("metodo") or "POST"
    ruta = e.get("ruta") or "/msg"
    auth = e.get("auth")
    if auth is None:
        authorization = "Bearer " + TOKEN_PROPIO
    elif auth == "ninguno":
        authorization = None
    else:
        authorization = auth  # ya trae los alias <token-propio> / <token-equipo>
    req = e.get("request")
    if e.get("raw") is True:
        cuerpo = req.encode("utf-8") if isinstance(req, str) else b""
    elif req is None:
        cuerpo = None
    else:
        cuerpo = json.dumps(req).encode("utf-8")
    return metodo, ruta, authorization, cuerpo


def replay(lineas: list[dict]) -> Resultado:
    res = Resultado()
    secuencias: dict = {}
    for e in sorted(lineas, key=lambda x: x.get("id", x.get("n", 0))):
        secuencias.setdefault(e.get("seq"), []).append(e)

    for seq, entradas in secuencias.items():
        store = Store(TOKEN_PROPIO)  # cada seq empieza con estado nuevo
        for e in entradas:
            if str(e.get("conclusion") or "").startswith("INFRA"):
                res.ignoradas += 1
                continue
            status, cuerpo = responder(store, *reconstruir(e))
            res.total += 1
            if status == e["status"] and iguales(e["response"], cuerpo):
                res.ok += 1
            else:
                res.diferencias.append((e, seq, status, cuerpo))
    return res


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ruta = Path(argv[0]) if argv else LOG_POR_DEFECTO
    res = replay(leer_log(ruta))
    for e, seq, status, cuerpo in res.diferencias:
        print(f"DIFF id={e.get('id')} seq={seq} {e.get('metodo') or 'POST'} {e.get('ruta') or '/msg'}")
        print(f"  request:  {json.dumps(e.get('request'), ensure_ascii=False)}")
        print(f"  esperado: {e['status']} {json.dumps(e['response'], ensure_ascii=False)}")
        print(f"  obtenido: {status} {json.dumps(cuerpo, ensure_ascii=False)}")
    print(f"conformidad: {res.ok}/{res.total} ({res.porcentaje:.1f}%)")
    print(f"ignoradas (INFRA): {res.ignoradas}")
    return 1 if res.diferencias else 0


if __name__ == "__main__":
    sys.exit(main())
