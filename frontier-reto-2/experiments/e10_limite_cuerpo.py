"""E10 · Límite de tamaño del cuerpo (E101): frontera exacta, si mide el cuerpo o m, y su orden."""

import json

from core.checksum import firmar
from tools.harness import Harness


def main():
    h = Harness()
    s = h.secuencia("limite-cuerpo", "frontera exacta de E101 cuerpo demasiado grande")

    def cuerpo_de(n_bytes):
        # {"m": "ALTA;XXX…;cc"} con exactamente n_bytes bytes serializados
        base = len(json.dumps({"m": firmar("ALTA;")}, ensure_ascii=False))
        for extra in range(max(0, n_bytes - base - 4), n_bytes - base + 4):
            b = {"m": firmar("ALTA;" + "B" * extra)}
            if len(json.dumps(b, ensure_ascii=False).encode()) == n_bytes:
                return b
        raise ValueError(n_bytes)

    def pasa(n):
        r = s.http(f"búsqueda binaria de E101: cuerpo de {n} bytes", body=cuerpo_de(n))
        print(f"{n:>6} bytes", r.status, r.body)
        return r.status != 413

    bajo, alto = 3020, 10020  # 3020 pasa (id 83), ~10020 da 413 (id 931)
    while alto - bajo > 1:
        medio = (bajo + alto) // 2
        if pasa(medio):
            bajo = medio
        else:
            alto = medio
    print(f"máximo aceptado = {bajo} bytes, mínimo rechazado = {alto} bytes")

    s = h.secuencia("e101-orden", "qué mide E101 y en qué orden se evalúa")
    grande = "x" * (alto + 100)
    for hip, kw in [
        ("relleno en un campo extra con m pequeño: ¿mide el cuerpo entero?", dict(body={"m": "PING;64", "pad": grande})),
        ("cuerpo grande sin token: ¿E001 o E101 primero?", dict(body={"m": "PING;64", "pad": grande}, auth="ninguno")),
        ("cuerpo grande en ruta inexistente: ¿E404 o E101?", dict(ruta="/noexiste", body={"m": "PING;64", "pad": grande})),
        ("cuerpo grande no JSON: ¿E100 o E101?", dict(raw=grande)),
    ]:
        r = s.http(hip, **kw)
        print(f"{hip[:58]:60}", r.status, r.body)


if __name__ == "__main__":
    main()
