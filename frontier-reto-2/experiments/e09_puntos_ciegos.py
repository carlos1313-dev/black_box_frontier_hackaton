"""E09 · Puntos ciegos tras 82/100: HTTP de borde, límites de tamaño, repeticiones y aridad por comando."""

from core.checksum import firmar
from tools.harness import Harness


def main():
    h = Harness()
    t = h.token
    s = h.secuencia("http-borde", "rutas, métodos y headers no probados")
    P = {"m": "PING;64"}
    for hip, kw in [
        ("query string en /msg: ¿se ignora o es ruta desconocida?", dict(ruta="/msg?x=1", body=P)),
        ("query string en /health", dict(metodo="GET", ruta="/health?x=1")),
        ("POST /health", dict(ruta="/health", body=P)),
        ("HEAD /health", dict(metodo="HEAD", ruta="/health")),
        ("OPTIONS /msg", dict(metodo="OPTIONS", ruta="/msg")),
        ("DELETE /msg", dict(metodo="DELETE", ruta="/msg", body=P)),
        ("/health/ con barra final", dict(metodo="GET", ruta="/health/")),
        ("doble barra //msg", dict(ruta="//msg", body=P)),
        ("Authorization con doble espacio", dict(body=P, auth=f"Bearer  {t}")),
        ("Authorization con espacio final", dict(body=P, auth=f"Bearer {t} ")),
        ("m con espacio final en el control", dict(body={"m": firmar("ALTA;Ana") + " "})),
        ("m con salto de línea final", dict(body={"m": firmar("ALTA;Ana") + "\n"})),
        ("m objeto anidado", dict(body={"m": {"m": "PING;64"}})),
        ("m de 10 000 caracteres", dict(body={"m": firmar("ALTA;" + "B" * 10000)})),
        ("m de 100 000 caracteres", dict(body={"m": firmar("ALTA;" + "C" * 100000)})),
        ("cuerpo de ~1 MB", dict(body={"m": firmar("ALTA;" + "D" * 1000000)})),
    ]:
        r = s.http(hip, **kw)
        print(f"{hip[:52]:54}", r.status, str(r.body)[:120])

    s = h.secuencia("repeticiones", "memoria: mensajes idénticos repetidos y fallos consecutivos")
    pasos = [
        ("ALTA;Ana", "AC-0001"), ("ALTA;Beto", "AC-0002"),
        ("DEPOSITO;AC-0001;1000", "depósito"),
        ("DEPOSITO;AC-0001;1000", "el MISMO depósito repetido: ¿duplicado detectado?"),
        ("TRANSFER;AC-0001;AC-0002;100", "transferencia"),
        ("TRANSFER;AC-0001;AC-0002;100", "la MISMA transferencia repetida"),
        ("CONSULTA;AC-0001", "saldo tras repeticiones"),
    ]
    for c, hip in pasos:
        print(f"{c:36}", s.m(firmar(c), hip))
    for i in range(5):
        print("E202 consecutivo", i + 1, s.msg("CONSULTA;AC-0001", f"fallo de control consecutivo n.º {i + 1}: ¿bloqueo?", control="corrupto"))
    print("tras 5 fallos   ", s.m(firmar("CONSULTA;AC-0001"), "¿la cuenta sigue operable tras 5 controles inválidos?"))
    print("tras 5 fallos   ", s.m(firmar("DEPOSITO;AC-0001;1"), "¿se aceptan escrituras tras 5 controles inválidos?"))

    s = h.secuencia("aridad-extra", "aridad con argumentos de más y espacios dentro de campos")
    s.m(firmar("ALTA;Ana"), "AC-0001")
    for c, hip in [
        ("CONSULTA;AC-0001;x", "CONSULTA con 2 argumentos"),
        ("DEPOSITO;AC-0001;100;x", "DEPOSITO con 3 argumentos"),
        ("DEPOSITO;AC-0001", "DEPOSITO con 1 argumento"),
        ("TRANSFER;AC-0001;AC-0002;100;x", "TRANSFER con 4 argumentos"),
        ("ANULA;OP-0001;x", "ANULA con 2 argumentos"),
        ("ANULA", "ANULA sin argumentos"),
        ("DEPOSITO; AC-0001;100", "espacio antes del id de cuenta"),
        ("DEPOSITO;AC-0001; 100", "espacio antes del monto"),
        ("ALTA; ", "nombre de solo un espacio"),
        ("ALTA;123", "nombre numérico"),
    ]:
        print(f"{c:36}", s.m(firmar(c), hip))


if __name__ == "__main__":
    main()
