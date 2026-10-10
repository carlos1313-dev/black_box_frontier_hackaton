"""Canario de cambios: una secuencia fija que toca cada comando y cada código de error conocido.

    python3 -m tools.canary [--dry-run] [--con-e520]

Compara cada respuesta del original con la del clon (`core.responder`). Imprime OK o las diferencias,
agrega una línea a canario.jsonl y sale con 1 si hay diferencias. Con --dry-run usa un harness falso
y no escribe nada.

HALT con argumentos (E520) NO se envía por defecto: si el servicio cambiara y ese comando pasara a
detenerlo de verdad, el canario lo dispararía. Se incluye solo con --con-e520.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from core import Store

from .comun import Diferencia, HarnessFalso, comparar
from .replay import TOKEN_PROPIO

RAIZ = Path(__file__).resolve().parent.parent
LOG_CANARIO = RAIZ / "canario.jsonl"

# Cada paso: (tipo, argumento, hipótesis).
#   "msg": cuerpo sin control, firmado con `Secuencia.msg`   ("auto" por defecto)
#   "msg_ctrl": (cuerpo, control literal)
#   "m": valor literal de `m`
#   "http": kwargs de `Secuencia.http`
# Los requests están tomados del log (ids entre paréntesis).
PASOS = [
    ("m", "PING;64", "PING responde pong (2)"),
    ("m", "PING;XX", "PING no valida el control (61)"),
    ("msg", "ALTA;Lucia", "ALTA crea AC-0001 (4)"),
    ("msg", "ALTA;Mateo", "ALTA crea AC-0002 (5)"),
    ("msg", "ALTA;Beto", "ALTA crea AC-0003, sin fondos (172-173)"),
    ("msg", "CONSULTA;AC-0001", "CONSULTA saldo 0 (6)"),
    ("msg", "DEPOSITO;AC-0001;250000", "DEPOSITO sin límite, OP-0001 (7)"),
    ("msg", "TRANSFER;AC-0001;AC-0002;40000", "TRANSFER ok, OP-0002 (8)"),
    ("msg", "CONSULTa;AC-0002", "comando en mayúsculas/minúsculas mezcladas (12)"),
    ("msg", "TRANSFER;AC-0001;AC-0002;100000", "TRANSFER en el límite, OP-0003 (11)"),
    ("msg", "TRANSFER;AC-0001;AC-0002;120000", "E506 límite excedido (10)"),
    ("msg", "TRANSFER;AC-0003;AC-0001;500000", "E506 antes que E507 (204)"),
    ("msg", "TRANSFER;AC-0003;AC-0001;5000", "E507 saldo insuficiente (203)"),
    ("msg", "TRANSFER;AC-0001;AC-0001;100", "E304 origen = destino (200)"),
    ("msg", "ANULA;OP-0003", "ANULA ok (14)"),
    ("msg", "ANULA;OP-0003", "ANULA repetida: ya anulada (15)"),
    ("msg", "ANULA;OP-0099", "E402 operación inexistente (219)"),
    ("msg", "CONSULTA;AC-0009", "E401 cuenta inexistente (16)"),
    ("msg", "DEPOSITO;AC-0001;0", "E303 monto inválido (182)"),
    ("msg", "SALDOS;AC-0001", "E301 sin sugerencia (13)"),
    ("msg", "HALTA", "E301 con sugerencia ALTA: gana a HALT en el empate (158)"),
    ("msg", "HALT", "HALT sin argumentos: E302 (165)"),
    ("msg_ctrl", ("DEPOSITO;AC-0002;700", "5X"), "E201 control mal formado (18)"),
    ("msg_ctrl", ("ALTA;Lucia", 83), "E202 control inválido (3)"),
    ("msg", "ALTA;Lucia;Gomez", "E302 aridad inválida (21)"),
    ("m", "PING;", "E104 segmento vacío (59)"),
    ("m", "", "E103 falta control (47)"),
    ("msg", "CONSULTA;AC-0001", "el estado persiste: saldo tras TRANSFER y ANULA (179)"),
    ("http", {"metodo": "GET", "ruta": "/health"}, "GET /health 200 (23)"),
    ("http", {"metodo": "GET", "ruta": "/noexiste"}, "E404 ruta desconocida (34)"),
    ("http", {"body": {"m": "PING;64"}, "auth": "ninguno"}, "E001 sin token (25)"),
    ("http", {"raw": "esto no es json"}, "E100 json inválido (40)"),
    ("http", {"body": {}}, "E102 falta m (44)"),
    ("http", {"body": {"m": 123}}, "E102 m no string (45)"),
]

# HALT con argumento: solo con --con-e520 (ver docstring).
PASO_E520 = ("msg", "HALT;x", "E520 HALT con argumento (166)")


def _pasos(con_e520: bool) -> list:
    pasos = list(PASOS)
    if con_e520:
        i = next(k for k, p in enumerate(pasos) if p[1] == "HALT")
        pasos.insert(i + 1, PASO_E520)
    return pasos


def ejecutar(harness, con_e520: bool = False) -> tuple[list[int], int, list[Diferencia]]:
    """Devuelve (ids del log de la corrida, pasos, diferencias)."""
    seq = harness.secuencia("canario", "canario de cambios: secuencia fija sobre cada comando y error")
    store = Store(TOKEN_PROPIO)
    ids: list[int] = []
    difs: list[Diferencia] = []
    pasos = _pasos(con_e520)
    for tipo, arg, hip in pasos:
        if tipo == "msg":
            r = seq.msg(arg, hip)
        elif tipo == "msg_ctrl":
            r = seq.msg(arg[0], hip, control=arg[1])
        elif tipo == "m":
            r = seq.m(arg, hip)
        else:
            r = seq.http(hip, **arg)
        ids.append(r.id)
        d = comparar(store, r, hip)
        if d is not None:
            difs.append(d)
    ids.insert(0, ids[0] - 1)  # el reset que abrió la secuencia
    return ids, len(pasos), difs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools.canary", description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="harness falso: sin red ni escritura")
    ap.add_argument("--con-e520", action="store_true", help="incluye HALT con argumento (E520)")
    a = ap.parse_args(argv)

    if a.dry_run:
        harness = HarnessFalso()
    else:
        from .harness import Harness
        harness = Harness()
    ids, pasos, difs = ejecutar(harness, a.con_e520)

    if difs:
        for d in difs:
            print(d.texto())
        print(f"canario: {len(difs)} diferencia(s) en {pasos} pasos")
    else:
        print(f"canario OK: {pasos} pasos sin diferencias")
    if not a.dry_run:
        resumen = {"ts": datetime.now().isoformat(timespec="seconds"), "pasos": pasos,
                   "diferencias": len(difs), "ids": ids, "detalle": [d.como_dict() for d in difs]}
        with LOG_CANARIO.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(resumen, ensure_ascii=False) + "\n")
    return 1 if difs else 0


if __name__ == "__main__":
    sys.exit(main())
