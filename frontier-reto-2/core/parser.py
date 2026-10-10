"""Parseo e integridad del mensaje `CMD;arg1;…;control`."""

from dataclasses import dataclass
from typing import Callable

from .checksum import control
from .errors import ErrorServicio

# Orden de evaluación de las validaciones de integridad (configurable).
# Evidencia: E103 (ids 47, 58), E104 evaluado antes que E302 (59, 72, 75),
# E201 -> E202 -> E301 -> E302 (68-71).
ORDEN_VALIDACION = ("E103", "E104", "E201", "E202", "E301", "E302")


@dataclass
class Mensaje:
    cuerpo: str  # mensaje sin ";control"
    control: str  # último campo, tal cual
    comando_crudo: str  # primer campo, tal cual
    comando: str  # primer campo, en mayúsculas (sin strip: " PING" es desconocido, id 74)
    args: list[str]
    segmentos: list[str]  # split por ';' de todo el mensaje
    tiene_control: bool  # el mensaje contiene al menos un ';'


def separar(m: str) -> Mensaje:
    # El control es el último campo (rpartition por ';').
    cuerpo, sep, ctrl = m.rpartition(";")
    campos = cuerpo.split(";")
    return Mensaje(cuerpo, ctrl, campos[0], campos[0].upper(), campos[1:], m.split(";"), bool(sep))


def _control_numerico(ctrl: str) -> bool:
    # SUPUESTO: "numérico" (para comandos distintos de PING) = solo dígitos ASCII, sin signo
    # ni espacios; "064" cuenta como 64. Solo se probó con "XX" (ids 69, 71).
    return ctrl.isascii() and ctrl.isdigit()


def _levenshtein(a: str, b: str) -> int:
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (ca != cb)))
        previa = actual
    return previa[-1]


def sugerencia(comando_crudo: str, comandos: dict) -> str | None:
    """Sugerencia de E301: comando a distancia de Levenshtein <= 2 de `cmd.upper()`.

    Sin strip (" PING" está a distancia 1, id 74). Gana la menor distancia; en empate, el primero
    en el orden de `comandos` (ALTA gana a HALT en 157 y 158). Distancia 3 -> sin sugerencia (160).
    Se devuelve en mayúsculas (156). Verificado contra todos los E301 del log.
    """
    objetivo = comando_crudo.upper()
    mejor, mejor_d = None, 3
    for nombre in comandos:
        d = _levenshtein(objetivo, nombre)
        if d < mejor_d:
            mejor, mejor_d = nombre, d
    return mejor


def validar(msg: Mensaje, comandos: dict) -> None:
    """Lanza ErrorServicio según ORDEN_VALIDACION. No toca estado."""
    cmd = comandos.get(msg.comando)
    # PING no valida el control (ids 61-67, 73); los demás sí (68-71).
    valida_control = cmd.valida_control if cmd is not None else True

    def e103():
        if not msg.tiene_control:
            raise ErrorServicio("E103")

    def e104():
        if any(seg == "" for seg in msg.segmentos):
            raise ErrorServicio("E104")

    def e201():
        if valida_control and not _control_numerico(msg.control):
            raise ErrorServicio("E201")

    def e202():
        if valida_control and (
            not _control_numerico(msg.control) or int(msg.control) != control(msg.cuerpo)
        ):
            raise ErrorServicio("E202")

    def e301():
        if cmd is None:
            extra = {}
            sug = sugerencia(msg.comando_crudo, comandos)
            if sug is not None:
                extra["sugerencia"] = sug
            raise ErrorServicio("E301", extra)

    def e302():
        if cmd is not None and len(msg.args) != cmd.aridad:
            raise ErrorServicio("E302")

    pasos: dict[str, Callable[[], None]] = {
        "E103": e103, "E104": e104, "E201": e201, "E202": e202, "E301": e301, "E302": e302,
    }
    for codigo in ORDEN_VALIDACION:
        pasos[codigo]()
