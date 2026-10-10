"""Reproductor: log JSONL -> core -> diff -> % de conformidad.

Uso: python3 -m tools.replay [ruta_log]   (por defecto experimentos.jsonl)
Exit code 1 si hay diferencias.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from core import State, handle

RAIZ = Path(__file__).resolve().parent.parent
LOG_POR_DEFECTO = RAIZ / "experimentos.jsonl"


@dataclass
class Resultado:
    total: int = 0  # líneas comparadas contra el core
    ok: int = 0
    fuera_de_core: int = 0
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


def es_de_core(entrada: dict) -> bool:
    metodo = entrada.get("metodo")
    ruta = entrada.get("ruta")
    if metodo is not None and metodo != "POST":
        return False
    if ruta is not None and ruta != "/msg":
        return False
    if "auth" in entrada:
        return False
    req = entrada.get("request")
    return isinstance(req, dict) and "m" in req


def replay(lineas: list[dict]) -> Resultado:
    res = Resultado()
    secuencias: dict = {}
    for e in sorted(lineas, key=lambda x: x.get("id", x.get("n", 0))):
        secuencias.setdefault(e.get("seq"), []).append(e)

    for seq, entradas in secuencias.items():
        state = State()
        for e in entradas:
            if str(e.get("conclusion") or "").startswith("INFRA"):
                res.ignoradas += 1
                continue
            if e.get("ruta") == "/__reset":
                # El core no responde a reset; solo reinicia el estado.
                state = State()
                res.fuera_de_core += 1
                continue
            if not es_de_core(e):
                res.fuera_de_core += 1
                continue
            status, cuerpo = handle(state, e["request"]["m"])
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
        print(f"DIFF id={e.get('id')} seq={seq}")
        print(f"  request:  {json.dumps(e['request'], ensure_ascii=False)}")
        print(f"  esperado: {e['status']} {json.dumps(e['response'], ensure_ascii=False)}")
        print(f"  obtenido: {status} {json.dumps(cuerpo, ensure_ascii=False)}")
    print(f"conformidad: {res.ok}/{res.total} ({res.porcentaje:.1f}%)")
    print(f"fuera de core: {res.fuera_de_core} | ignoradas (INFRA): {res.ignoradas}")
    return 1 if res.diferencias else 0


if __name__ == "__main__":
    sys.exit(main())
