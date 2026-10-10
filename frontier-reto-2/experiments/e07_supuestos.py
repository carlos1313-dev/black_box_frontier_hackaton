"""E07 · Cierre de supuestos: formato del control fuera de PING, máximo del monto,
orden de errores en TRANSFER, regla de la sugerencia, JSON de borde. Sin confirmar HALT."""

from core.checksum import control
from tools.harness import Harness


def correr(s, pasos):
    for m, hip in pasos:
        print(f"{m[:44]:46}", s.m(m, hip))


def main():
    h = Harness()
    c = control("ALTA;Mateo")  # 3
    correr(h.secuencia("control-formato", "qué formatos de control acepta un comando que sí valida"), [
        (f"ALTA;Mateo;0{c}", "control con cero a la izquierda en ALTA"),
        (f"ALTA;Mateo;+{c}", "control con signo + en ALTA"),
        (f"ALTA;Mateo; {c}", "control con espacio en ALTA"),
        (f"ALTA;Mateo;{c}.0", "control decimal en ALTA"),
        (f"ALTA;Mateo;{c + 97}", "control congruente módulo 97 en ALTA"),
        (f"HALT;x;{control('HALT;x') + 1}", "HALT con control inválido: ¿valida el control? (no puede confirmar)"),
        ("HALTX;" + str(control("HALTX")), "HALT a distancia 1 y ALTA a distancia 2: ¿menor distancia u orden?"),
    ])
    pasos = [("ALTA;Ana", "AC-0001")]
    for monto, hip in [
        ("999999999999999", "15 dígitos"),
        ("9007199254740991", "máximo entero seguro de JS"),
        ("9007199254740992", "máximo seguro + 1"),
        ("10000000000000000", "17 dígitos"),
    ]:
        cuerpo = f"DEPOSITO;AC-0001;{monto}"
        pasos.append((f"{cuerpo};{control(cuerpo)}", f"frontera del monto: {hip}"))
    pasos.append((f"CONSULTA;AC-0001;{control('CONSULTA;AC-0001')}", "saldo tras depósitos grandes: ¿cómo se serializa?"))
    correr(h.secuencia("monto-maximo", "dónde está el máximo del monto"), [(m if ";" in m[5:] and m.count(";") > 1 else f"{m};{control(m)}", hip) for m, hip in pasos])

    def f(cuerpo):
        return f"{cuerpo};{control(cuerpo)}"
    correr(h.secuencia("orden-transfer", "orden de E303, E304, E401 y E506 en TRANSFER"), [
        (f("ALTA;Ana"), "AC-0001"),
        (f("TRANSFER;AC-0001;AC-0001;abc"), "monto inválido y misma cuenta: ¿E303 o E304?"),
        (f("TRANSFER;AC-0099;AC-0099;100"), "misma cuenta inexistente: ¿E304 o E401?"),
        (f("TRANSFER;AC-0099;AC-0098;abc"), "monto inválido y cuentas inexistentes: ¿E303 o E401?"),
        (f("TRANSFER;AC-0099;AC-0001;200000"), "origen inexistente y sobre el límite: ¿E401 o E506?"),
        (f("TRANSFER;AC-0001;AC-0099;200000"), "destino inexistente y sobre el límite: ¿E401 o E506?"),
    ])
    s = h.secuencia("json-borde", "parseo de JSON en casos de borde")
    for raw, hip in [
        ('{"m": NaN}', "NaN no es JSON válido estricto"),
        ('{"m":"PING;64"}   ', "espacios al final del JSON"),
        ('{"m":"ALTA;x;1","m":"PING;64"}', "clave duplicada: ¿gana la última?"),
        ('﻿{"m":"PING;64"}', "BOM UTF-8 al inicio"),
    ]:
        print(f"{raw[:44]!r:46}", s.http(hip, raw=raw))


if __name__ == "__main__":
    main()
