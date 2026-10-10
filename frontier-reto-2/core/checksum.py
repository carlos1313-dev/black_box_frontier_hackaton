"""Dígito de control del servicio (variante ISO 7064 MOD 97-10).

Derivado de pruebas/ejemplos.jsonl (20/20). Casos de borde aún por confirmar:
resto 0 o 1, ceros a la izquierda, caracteres no ASCII.
"""


def control(cuerpo: str) -> int:
    """Control para `cuerpo`, el mensaje sin el último campo ";control"."""
    digitos = "".join(
        c if c.isdigit() else str(ord(c) - 64)  # A=1 … Z=26
        for c in cuerpo.upper()
        if c.isascii() and c.isalnum()  # se descartan ; - y espacios
    )
    if not digitos:
        return 98 % 97
    return (98 - int(digitos + "00") % 97) % 97


def firmar(cuerpo: str) -> str:
    """Devuelve el mensaje completo `cuerpo;control`."""
    return f"{cuerpo};{control(cuerpo)}"
