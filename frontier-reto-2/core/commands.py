"""Comandos del servicio y despacho. Los números entre paréntesis son ids de experimentos.jsonl."""

import re
from dataclasses import dataclass
from typing import Callable

from . import parser
from .errors import ErrorServicio
from .state import Operacion, State

# Límite SOLO por operación: monto > 100000 -> E506 (177); el acumulado no cuenta (176).
# DEPOSITO no tiene límite (174).
LIMITE_TRANSFER = 100000
# Monto máximo 9999999999; 10000000000 -> E303 (búsqueda binaria, ids 298, 302).
MONTO_MAXIMO = 9999999999

OK_RECIBIDO = "recieved"  # sic, error ortográfico del original

_RE_MONTO = re.compile(r"[1-9][0-9]*")


@dataclass
class Comando:
    aridad: int
    ejecutar: Callable[[State, list[str]], tuple[int, dict]]
    valida_control: bool = True  # PING no valida el control (61-67)


def _monto(texto: str) -> int:
    # Válido solo si es ^[1-9][0-9]*$: 0, -5, 1.5, abc, 007, +5, 1e3 y 20 dígitos -> E303 (182-189, 205, 206).
    # Largo antes que int(): un monto de miles de dígitos haría fallar int().
    if len(texto) > len(str(MONTO_MAXIMO)) or not _RE_MONTO.fullmatch(texto) or int(texto) > MONTO_MAXIMO:
        raise ErrorServicio("E303")
    return int(texto)


def _cuenta(state: State, cid: str):
    # Comparación exacta, case-sensitive (191, 192, 221); CONSULTA;OP-0001 -> E401 (224).
    cuenta = state.cuentas.get(cid)
    if cuenta is None:
        raise ErrorServicio("E401")
    return cuenta


def _ping(state, args):
    return 200, {"pong": True}


def _alta(state, args):
    # Nombre repetido crea otra cuenta (223); espacios, guion, no-ASCII y 3000 caracteres pasan (76-78, 83).
    return 201, {"cuentaId": state.nueva_cuenta(args[0])}


def _consulta(state, args):
    cuenta = _cuenta(state, args[0])
    return 200, {"cuenta_id": args[0], "saldo": cuenta.saldo}


def _deposito(state, args):
    # El monto se valida ANTES que la existencia de la cuenta (193).
    monto = _monto(args[1])
    cuenta = _cuenta(state, args[0])
    cuenta.saldo += monto
    # Los fallos no consumen IDs (195): el ID se asigna solo al tener éxito.
    oid = state.nueva_operacion(Operacion("DEPOSITO", None, args[0], monto))
    return 200, {"status": OK_RECIBIDO, "operacionId": oid}


def _transfer(state, args):
    # SUPUESTO: orden E303 -> E304 -> E401 (origen) -> E401 (destino) -> E506 -> E507.
    # E506 antes que E507 está confirmado (204).
    monto = _monto(args[2])
    if args[0] == args[1]:
        raise ErrorServicio("E304")  # (200)
    origen = _cuenta(state, args[0])  # (201)
    destino = _cuenta(state, args[1])  # (202)
    if monto > LIMITE_TRANSFER:
        raise ErrorServicio("E506")
    if origen.saldo < monto:
        raise ErrorServicio("E507")
    origen.saldo -= monto
    destino.saldo += monto
    oid = state.nueva_operacion(Operacion("TRANSFER", args[0], args[1], monto))
    return 200, {"status": OK_RECIBIDO, "operacionId": oid}


def _anula(state, args):
    # Inexistente o mal formado -> E402 (219-221); ANULA no consume OP-id (222).
    op = state.operaciones.get(args[0])
    if op is None:
        raise ErrorServicio("E402")
    if op.anulada:
        return 200, {"ok": False, "motivo": "ya anulada"}
    # Permite saldos negativos: el destino ya pudo gastar (215, 216). ANULA de un DEPOSITO resta el monto (217, 218).
    state.cuentas[op.destino].saldo -= op.monto
    if op.origen is not None:
        state.cuentas[op.origen].saldo += op.monto
    op.anulada = True
    return 200, {"ok": True, "anulada": args[0]}


def _halt(state, args):
    # SUPUESTO: cualquier valor del argumento da E520 y no cambia nada (166-170).
    raise ErrorServicio("E520")


# El orden importa: define el desempate de la sugerencia de E301 (core.parser.sugerencia).
COMANDOS: dict[str, Comando] = {
    "PING": Comando(0, _ping, valida_control=False),
    "ALTA": Comando(1, _alta),
    "CONSULTA": Comando(1, _consulta),
    "DEPOSITO": Comando(2, _deposito),
    "TRANSFER": Comando(3, _transfer),
    "ANULA": Comando(1, _anula),
    "HALT": Comando(1, _halt),  # comando oculto
}


def handle(state: State, m) -> tuple[int, dict | str]:
    """Procesa el valor del campo `m` y devuelve (status, cuerpo)."""
    if not isinstance(m, str):
        # m no string -> E102 (45, 46, 48); core.http ya lo filtra antes.
        return ErrorServicio("E102").respuesta()
    try:
        msg = parser.separar(m)
        parser.validar(msg, COMANDOS)
        return COMANDOS[msg.comando].ejecutar(state, msg.args)
    except ErrorServicio as e:
        return e.respuesta()
