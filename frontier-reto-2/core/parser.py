"""Parseo e integridad del mensaje `CMD;arg1;…;control`."""

from dataclasses import dataclass
from typing import Callable

from .checksum import control
from .errors import ErrorServicio

# Orden de evaluación de las validaciones de integridad (configurable).
# Los experimentos de orden E202 vs E301/E302 ajustarán esta tupla.
# SUPUESTO: E201 -> E202 -> E301 -> E302 (en los ejemplos solo se vio cada error aislado).
ORDEN_VALIDACION = ("E201", "E202", "E301", "E302")


@dataclass
class Mensaje:
    cuerpo: str  # mensaje sin ";control"
    control: str  # último campo, tal cual
    comando: str  # primer campo, en mayúsculas
    args: list[str]


def separar(m: str) -> Mensaje:
    # El control es el último campo (rpartition por ';').
    cuerpo, _, ctrl = m.rpartition(";")
    campos = cuerpo.split(";")
    return Mensaje(cuerpo, ctrl, campos[0].upper(), campos[1:])


def _control_numerico(ctrl: str) -> bool:
    # SUPUESTO: "numérico" = solo dígitos ASCII (sin signo ni espacios); "064" cuenta como 64.
    return ctrl.isascii() and ctrl.isdigit()


def validar(msg: Mensaje, comandos: dict) -> None:
    """Lanza ErrorServicio según ORDEN_VALIDACION. No toca estado."""

    def e201():
        if not _control_numerico(msg.control):
            raise ErrorServicio("E201")

    def e202():
        # Con control no numérico E201 ya habría saltado, salvo orden alterado.
        if not _control_numerico(msg.control) or int(msg.control) != control(msg.cuerpo):
            raise ErrorServicio("E202")

    def e301():
        if msg.comando not in comandos:
            raise ErrorServicio("E301")

    def e302():
        cmd = comandos.get(msg.comando)
        if cmd is not None and len(msg.args) != cmd.aridad:
            raise ErrorServicio("E302")

    pasos: dict[str, Callable[[], None]] = {
        "E201": e201, "E202": e202, "E301": e301, "E302": e302,
    }
    for codigo in ORDEN_VALIDACION:
        pasos[codigo]()
