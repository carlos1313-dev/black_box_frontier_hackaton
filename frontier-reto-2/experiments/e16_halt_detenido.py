"""E16 · HALT confirmado (E11: HALT;1 -> 503 E599, 3281). Qué valores confirman y qué responde el
servicio detenido a cada tipo de request (orden de validación). Siempre termina con /__reset.

Correr: flock /tmp/an/harness.lock python3 -m experiments.e16_halt_detenido
"""

from core.checksum import firmar
from tools.harness import Harness

VALORES = ["0", "2", "01", "11", "true", "yes", "si", "y"]


def detenido(s, hip):
    """Lo que responde el servicio detenido, de lo más externo a lo más interno."""
    casos = [
        ("GET /noexiste", dict(metodo="GET", ruta="/noexiste")),
        ("sin auth", dict(body={"m": firmar("PING")}, auth="ninguno")),
        ("GET /health", dict(metodo="GET", ruta="/health")),
        ("cuerpo > 8192", dict(raw='{"m":"' + "A" * 9000 + '"}')),
        ("JSON inválido (E100)", dict(raw="esto no es json")),
        ("m no string (E102)", dict(body={"m": 5})),
        ("sin control (E103)", dict(body={"m": "ALTA;Ana"})),
        ("segmento vacío (E104)", dict(body={"m": firmar("ALTA;;Ana")})),
        ("control mal formado (E201)", dict(body={"m": "ALTA;Ana;X"})),
        ("control inválido (E202)", dict(body={"m": "ALTA;Ana;" + str((int(firmar("ALTA;Ana").split(";")[-1]) + 1) % 97)})),
        ("comando desconocido (E301)", dict(body={"m": firmar("FOO")})),
        ("aridad (E302)", dict(body={"m": firmar("HALT")})),
        ("HALT;x (E520)", dict(body={"m": firmar("HALT;x")})),
        ("PING", dict(body={"m": firmar("PING")})),
    ]
    for etiqueta, kw in casos:
        print(f"  {etiqueta}:", s.http(f"{hip}: {etiqueta}", **kw))


def main():
    h = Harness()
    s = h.secuencia("halt-detenido", "¿HALT;1 detiene sin HALT;x previo? ¿qué responde detenido?")
    print("HALT;1 directo:", s.m(firmar("HALT;1"), "¿HALT;1 detiene sin un HALT;x previo?"))
    detenido(s, "detenido")
    print("reset:", s.http("reparar con /__reset", ruta="/__reset"))
    print("PING:", s.m(firmar("PING"), "¿vuelve a responder tras el reset?"))

    s = h.secuencia("halt-valores", "¿qué otros argumentos confirman HALT?")
    print("halt;1:", s.m(firmar("halt;1"), "¿el comando en minúsculas también confirma?"))
    if s.m(firmar("PING"), "¿quedó detenido?").status == 503:
        s.http("reparar con /__reset", ruta="/__reset")
    for v in VALORES:
        r = s.m(firmar(f"HALT;{v}"), f"¿'{v}' confirma HALT?")
        print(f"HALT;{v}:", r)
        if r.status == 503:
            s.http("reparar con /__reset", ruta="/__reset")
    s.http("cierre: /__reset", ruta="/__reset")


if __name__ == "__main__":
    main()
