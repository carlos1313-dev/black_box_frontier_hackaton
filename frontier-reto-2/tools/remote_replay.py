"""Reproduce el log contra un reemplazo DESPLEGADO (nunca contra el original).

Uso: python3 -m tools.remote_replay https://mi-reemplazo.onrender.com [ruta_log]
Lee TEAM_TOKEN de .env. Exit code 1 si hay diferencias o algún paso tarda más de 5 s.
"""

import json
import sys
import time
import urllib.error
import urllib.request

from tools.harness import _cargar_env
from tools.replay import LOG_POR_DEFECTO, TOKEN_PROPIO, iguales, leer_log, reconstruir

# En el original el token del equipo era inválido (id 29); en el reemplazo es el válido,
# así que esa línea se reproduce con otro token inválido.
TOKEN_INVALIDO = "cn-p-token-invalido-para-replay"
LIMITE_S = 5.0


def enviar(base, metodo, ruta, authorization, cuerpo):
    headers = {"Content-Type": "application/json"} if cuerpo is not None else {}
    if authorization is not None:
        headers["Authorization"] = authorization
    req = urllib.request.Request(base + ruta, data=cuerpo, method=metodo, headers=headers)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    texto = raw.decode("utf-8", errors="replace")
    try:
        body = json.loads(texto)
    except ValueError:
        body = texto
    return status, body, time.monotonic() - t0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    base = argv[0].rstrip("/")
    lineas = sorted(leer_log(argv[1] if len(argv) > 1 else LOG_POR_DEFECTO), key=lambda l: l["id"])
    token = _cargar_env()["TEAM_TOKEN"]
    difs, lentos, peor = [], [], 0.0
    for e in lineas:
        if str(e.get("conclusion", "")).startswith("INFRA"):
            continue
        metodo, ruta, auth, cuerpo = reconstruir(e)
        if auth is not None:
            auth = auth.replace("<token-equipo>", TOKEN_INVALIDO).replace(TOKEN_PROPIO, token)
        status, body, dt = enviar(base, metodo, ruta, auth, cuerpo)
        peor = max(peor, dt)
        if dt > LIMITE_S:
            lentos.append((e["id"], round(dt, 2)))
        if not (status == e["status"] and iguales(e["response"], body)):
            difs.append(e["id"])
            print(f"DIFF id={e['id']} {metodo} {ruta} {e.get('request')!r}\n"
                  f"  original: {e['status']} {json.dumps(e['response'], ensure_ascii=False)}\n"
                  f"  deploy:   {status} {json.dumps(body, ensure_ascii=False)}")
    n = len(lineas)
    print(f"deploy: {n - len(difs)}/{n} iguales al original · peor latencia {peor:.2f}s · pasos > 5 s: {lentos or 'ninguno'}")
    return 1 if difs or lentos else 0


if __name__ == "__main__":
    sys.exit(main())
