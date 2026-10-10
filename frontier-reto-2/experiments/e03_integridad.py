"""E03 · Integridad: orden de errores del control/comando/aridad y bordes del control."""

import itertools
import string

from core.checksum import control
from tools.harness import Harness


def resto(cuerpo: str) -> int:
    d = "".join(c if c.isdigit() else str(ord(c) - 64) for c in cuerpo.upper() if c.isascii() and c.isalnum())
    return int(d + "00") % 97


def nombre_con_resto(r: int) -> str:
    for a, b, c in itertools.product(string.ascii_uppercase, repeat=3):
        n = "Ana" + a.lower() + b.lower() + c.lower()
        if resto(f"ALTA;{n}") == r:
            return n


def main():
    s = Harness().secuencia("integridad", "orden de errores de integridad y bordes del control")
    r1, r0 = nombre_con_resto(1), nombre_con_resto(0)
    largo = "A" * 3000
    pruebas = [
        ("PING sin campo de control", "PING"),
        ("control vacío 'PING;'", "PING;"),
        ("comando vacío ';64'", ";64"),
        ("PING;XX: ¿PING ignora el control?", "PING;XX"),
        ("control con cero a la izquierda 064", "PING;064"),
        ("control con signo +64", "PING;+64"),
        ("control con espacio ' 64'", "PING; 64"),
        ("control decimal 64.0", "PING;64.0"),
        ("control negativo congruente -33", "PING;-33"),
        ("control congruente mod 97: 161", "PING;161"),
        ("comando desconocido + control inválido: ¿E202 o E301?", f"SALDOS;AC-0001;{control('SALDOS;AC-0001') + 1}"),
        ("comando desconocido + control mal formado: ¿E201 o E301?", "SALDOS;AC-0001;XX"),
        ("aridad inválida + control inválido: ¿E202 o E302?", f"ALTA;Lucia;Gomez;{control('ALTA;Lucia;Gomez') + 1}"),
        ("aridad inválida + control mal formado: ¿E201 o E302?", "ALTA;Lucia;Gomez;XX"),
        ("PING con un argumento extra: ¿E302?", f"PING;x;{control('PING;x')}"),
        ("todo en minúsculas 'ping;64'", "ping;64"),
        ("espacio antes del comando", " PING;64"),
        ("campo vacío intermedio 'PING;;64'", "PING;;64"),
        ("nombre con espacio", f"ALTA;Ana Maria;{control('ALTA;Ana Maria')}"),
        ("guion dentro del nombre se ignora en el control (= ALTA;Lucia → 82)", "ALTA;Lu-cia;82"),
        ("acento: control calculado ignorando la í", f"ALTA;Lucía;{control('ALTA;Lucía')}"),
        (f"resto 1 ({r1}): control 0", f"ALTA;{r1};0"),
        (f"resto 1 ({r1}): control 97", f"ALTA;{r1};97"),
        (f"resto 0 ({r0}): control 1", f"ALTA;{r0};1"),
        (f"resto 0 ({r0}): control 98", f"ALTA;{r0};98"),
        ("nombre de 3000 caracteres: ¿límite de longitud?", f"ALTA;{largo};{control('ALTA;' + largo)}"),
    ]
    for hip, m in pruebas:
        print(f"{m[:40]!r:44}", s.m(m, hip))


if __name__ == "__main__":
    main()
