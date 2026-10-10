"""Re-envía al original cada secuencia del log (v1) y compara con la respuesta registrada.

    python3 -m tools.revalidar [--desde ID] [--hasta ID]

Sirve para detectar cambios de versión: cada request nuevo queda en experimentos.jsonl con la
hipótesis "v2: reproduce id N" y las diferencias se imprimen con ambos ids (antes/después).
SEGURIDAD: nunca reenvía HALT con argumentos; el token del equipo se sustituye por uno inválido.
"""

import argparse
import json
import sys

from tools.fuzz import es_halt_con_args
from tools.harness import ErrorRed, Harness
from tools.remote_replay import TOKEN_INVALIDO
from tools.replay import iguales, leer_log, LOG_POR_DEFECTO


def _kwargs(h, e):
    kw = {"metodo": e.get("metodo") or "POST", "ruta": e.get("ruta") or "/msg"}
    auth = e.get("auth")
    if auth is not None:
        kw["auth"] = auth if auth == "ninguno" else (
            auth.replace("<token-propio>", h.token).replace("<token-equipo>", TOKEN_INVALIDO))
    if e.get("raw") is True:
        kw["raw"] = e["request"] if isinstance(e["request"], str) else ""
    elif e.get("request") is not None:
        kw["body"] = e["request"]
    return kw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools.revalidar")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10**9)
    a = ap.parse_args(argv)
    lineas = [l for l in sorted(leer_log(LOG_POR_DEFECTO), key=lambda l: l["id"])
              if a.desde <= l["id"] <= a.hasta and not str(l.get("conclusion", "")).startswith("INFRA")]
    secuencias: dict = {}
    for l in lineas:
        secuencias.setdefault(l["seq"], []).append(l)
    h = Harness()
    difs = total = 0
    for seq, entradas in secuencias.items():
        if "-v2-" in seq or "canario" in seq:
            continue  # ni revalidaciones ni el canario (ya comparado)
        s = h.secuencia(f"v2-{seq}"[:60], f"revalidación v2 de la secuencia {seq}")
        for i, e in enumerate(entradas):
            if i == 0 and e.get("ruta") == "/__reset":
                continue
            req = e.get("request")
            if isinstance(req, dict) and es_halt_con_args(req.get("m")):
                continue
            if e.get("raw") and "halt" in str(req).lower():
                continue
            try:
                r = s.http(f"v2: reproduce id {e['id']} ({e['hipotesis'][:80]})", **_kwargs(h, e))
            except ErrorRed as ex:
                print(f"[revalidar] {seq} abandonada: {ex}")
                break
            total += 1
            if not (r.status == e["status"] and iguales(e["response"], r.body)):
                difs += 1
                print(f"CAMBIO id={e['id']}->{r.id} seq={seq} {json.dumps(req, ensure_ascii=False)[:150]}\n"
                      f"  v1: {e['status']} {json.dumps(e['response'], ensure_ascii=False)[:200]}\n"
                      f"  v2: {r.status} {json.dumps(r.body, ensure_ascii=False)[:200]}", flush=True)
    print(f"revalidados {total}, cambios {difs}")
    return 1 if difs else 0


if __name__ == "__main__":
    sys.exit(main())
