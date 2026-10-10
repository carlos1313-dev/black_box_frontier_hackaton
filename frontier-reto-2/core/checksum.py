"""Dígito de control del servicio (variante ISO 7064 MOD 97-10).

control = 98 - (N mod 97), SIN módulo final: el rango válido es 2..98
(experimentos.jsonl ids 79-82: control 97 y 98 válidos, 0 y 1 inválidos).
Verificado contra pruebas/ejemplos.jsonl (20/20). Espacios, guiones y no-ASCII
no cuentan en el cálculo (ids 76-78).
"""


def control(cuerpo: str) -> int:
    """Control para `cuerpo`, el mensaje sin el último campo ";control"."""
    digitos = "".join(
        c if c.isdigit() else str(ord(c) - 64)  # A=1 … Z=26
        for c in cuerpo.upper()
        if c.isascii() and c.isalnum()  # se descartan ; - y espacios
    )
    if not digitos:
        return 98  # SUPUESTO: sin dígitos, N = 0 -> 98 (extrapolación de la fórmula, no probado)
    return 98 - int(digitos + "00") % 97


def firmar(cuerpo: str) -> str:
    """Devuelve el mensaje completo `cuerpo;control`."""
    return f"{cuerpo};{control(cuerpo)}"
