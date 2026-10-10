"""E11 · Confirmación de HALT (autorizado por el usuario). Único terreno sin explorar tras el 87/100.

Se detiene en el primer intento que no dé E520, mide el efecto (PING, CONSULTA, /health) y
repara con /__reset. Correr: flock /tmp/an/harness.lock python3 -m experiments.e11_halt_confirmacion
"""

from core.checksum import firmar
from tools.harness import Harness

CANDIDATOS = ["x", "CONFIRMAR", "CONFIRMO", "CONFIRMA", "CONFIRM", "SI", "YES", "TRUE", "OK", "1", "FORCE"]


def efecto(s, etapa):
    for hip, kw in [
        (f"{etapa}: ¿PING responde?", dict(body={"m": firmar("PING")})),
        (f"{etapa}: ¿CONSULTA responde y conserva el estado?", dict(body={"m": firmar("CONSULTA;AC-0001")})),
        (f"{etapa}: ¿ALTA sigue funcionando?", dict(body={"m": firmar("ALTA;Beto")})),
        (f"{etapa}: ¿GET /health sigue en 200?", dict(metodo="GET", ruta="/health")),
    ]:
        print("  ", s.http(hip, **kw))


def main():
    h = Harness()
    s = h.secuencia("halt-confirmacion", "con qué se confirma HALT y qué hace")
    s.m(firmar("ALTA;Ana"), "cuenta para ver el efecto de HALT")
    s.m(firmar("DEPOSITO;AC-0001;1000"), "saldo para ver el efecto de HALT")
    print(s.m(firmar("HALT;x"), "HALT;x: E520 de referencia"))
    # "x" de nuevo: ¿reenviar el mismo mensaje es la confirmación?
    intentos = [(f"HALT;{c}", f"¿'{c}' confirma HALT (reenvío)?") for c in CANDIDATOS]
    confirmado = None
    for cuerpo, hip in intentos:
        r = s.m(firmar(cuerpo), hip)
        print(cuerpo, r)
        if r.status != 409:
            confirmado = cuerpo
            break
    if confirmado is None:
        for campo in ("confirmacion", "confirmar", "confirm"):
            r = s.http(f"¿confirmación como campo '{campo}' del cuerpo?", body={"m": firmar("HALT;x"), campo: True})
            print(campo, r)
            if r.status != 409:
                confirmado = campo
                break
    if confirmado:
        efecto(s, f"tras confirmar HALT ({confirmado})")
        print("  ", s.http("reparar: ¿/__reset funciona tras HALT?", ruta="/__reset"))
        efecto(s, "tras /__reset")
    else:
        print("ninguna confirmación probada detuvo nada")


if __name__ == "__main__":
    main()
