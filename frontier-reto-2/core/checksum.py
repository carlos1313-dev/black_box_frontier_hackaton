"""Dígito de control del servicio (variante ISO 7064 MOD 97-10).

Derivado de pruebas/ejemplos.jsonl (20/20). Rango 2..98: con resto 0 el control
es 98 y con resto 1 es 97, sin módulo final (experimentos ids 79-82).
"""


def control(cuerpo: str) -> int:
    """Control para `cuerpo`, el mensaje sin el último campo ";control"."""
    digitos = "".join(
        c if c.isdigit() else str(ord(c) - 64)  # A=1 … Z=26
        for c in cuerpo.upper()
        if c.isascii() and c.isalnum()  # se descartan ; - y espacios
    )
    if not digitos:
        return 98
    return 98 - int(digitos + "00") % 97


def firmar(cuerpo: str) -> str:
    """Devuelve el mensaje completo `cuerpo;control`."""
    return f"{cuerpo};{control(cuerpo)}"
