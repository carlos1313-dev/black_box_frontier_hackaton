"""E14 · Tercer cambio v2: puntos que la revalidación no pudo reproducir o nunca se combinaron.

- Content-Type (ids 53-54): el log no guarda el header, así que la revalidación mandó application/json.
- Orden de E506 (nuevo límite 50000) frente a E304/E401/E507.
"""

from core.checksum import firmar
from tools.harness import Harness


def main():
    h = Harness()
    s = h.secuencia("e14-content-type", "v2: ¿cambió el manejo del Content-Type? (v1: 53-54 sin efecto)")
    p = {"m": "PING;64"}
    print("text/plain", s.http("v2: Content-Type text/plain con cuerpo JSON (v1: 53)", body=p, content_type="text/plain"))
    print("sin CT", s.http("v2: sin Content-Type con cuerpo JSON (v1: 54)", body=p, content_type=None))
    print("form", s.http("v2: Content-Type form-urlencoded", body={"m": firmar("ALTA;Ana")},
                         content_type="application/x-www-form-urlencoded"))

    s = h.secuencia("e14-orden-limite", "v2: orden de validación de TRANSFER con el nuevo límite")
    s.msg("ALTA;Ana", "AC-0001")
    s.msg("ALTA;Zoe", "AC-0002")
    s.msg("DEPOSITO;AC-0001;200000", "fondos")
    print("self", s.msg("TRANSFER;AC-0001;AC-0001;60000", "v2: E304 antes que E506 (como v1)?"))
    print("inex", s.msg("TRANSFER;AC-0001;AC-0009;60000", "v2: E401 antes que E506 (como v1)?"))
    print("sinfondos", s.msg("TRANSFER;AC-0002;AC-0001;60000", "v2: E506 antes que E507 con 50000<monto<=100000"))
    print("max", s.msg("DEPOSITO;AC-0001;10000000000", "v2: monto máximo sigue en 9999999999 (v1: 302)"))


if __name__ == "__main__":
    main()
