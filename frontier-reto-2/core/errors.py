"""Catálogo de errores del servicio: código -> (status HTTP, mensaje exacto)."""

CATALOGO: dict[str, tuple[int, str]] = {
    "E201": (400, "control mal formado"),
    "E202": (400, "control inválido"),
    "E301": (400, "comando desconocido "),  # OJO: espacio final, es parte del original
    "E302": (400, "aridad inválida"),
    # SUPUESTO: código y texto de argumento inválido (monto no numérico, <= 0, etc.).
    # No observado en el original; E303 es un invento en la familia E3xx.
    "E303": (400, "argumento inválido"),
    "E401": (404, "cuenta inexistente"),
    # SUPUESTO: código y texto de operación inexistente (ANULA de un OP desconocido).
    "E402": (404, "operación inexistente"),
    "E506": (422, "límite excedido"),
    "E507": (422, "saldo insuficiente"),
}


class ErrorServicio(Exception):
    """Error de negocio/validación con código del catálogo."""

    def __init__(self, codigo: str):
        super().__init__(codigo)
        self.codigo = codigo

    def respuesta(self) -> tuple[int, dict]:
        status, mensaje = CATALOGO[self.codigo]
        return status, {"error": self.codigo, "mensaje": mensaje}
