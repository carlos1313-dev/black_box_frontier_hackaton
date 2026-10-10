"""Catálogo de errores del servicio: código -> (status HTTP, mensaje exacto)."""

CATALOGO: dict[str, tuple[int, str]] = {
    # Capa HTTP (ids de experimentos.jsonl entre paréntesis).
    "E001": (401, "no autorizado"),  # (24-30, 56)
    "E404": (404, "ruta desconocida"),  # (31-39)
    "E100": (400, "json inválido"),  # (40-43)
    "E102": (400, "falta m"),  # (44-50, 52)
    "E103": (400, "falta control"),  # (47, 58)
    "E104": (400, "segmento vacío"),  # (59, 60, 75)
    "E201": (400, "control mal formado"),
    "E202": (400, "control inválido"),
    "E301": (400, "comando desconocido "),  # OJO: espacio final, es parte del original
    "E302": (400, "aridad inválida"),
    "E303": (400, "monto inválido"),  # (182-189, 193, 205, 206)
    "E304": (400, "origen y destino iguales"),  # (200)
    "E401": (404, "cuenta inexistente"),
    "E402": (404, "operación inexistente"),  # (219-221)
    "E506": (422, "límite excedido"),
    # HALT con argumento: no cambia nada (166-170).
    "E520": (409, "operación destructiva: detiene el servicio; reenvía con confirmación"),
    "E507": (422, "saldo insuficiente"),
}


class ErrorServicio(Exception):
    """Error de negocio/validación con código del catálogo."""

    def __init__(self, codigo: str, extra: dict | None = None):
        super().__init__(codigo)
        self.codigo = codigo
        self.extra = extra or {}  # claves adicionales del cuerpo (p. ej. "sugerencia")

    def respuesta(self) -> tuple[int, dict]:
        status, mensaje = CATALOGO[self.codigo]
        return status, {"error": self.codigo, "mensaje": mensaje, **self.extra}
