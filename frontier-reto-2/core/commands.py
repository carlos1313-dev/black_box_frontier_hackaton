"""Comandos del servicio y despacho."""

from dataclasses import dataclass
from typing import Callable

from . import parser
from .errors import ErrorServicio
from .state import Operacion, State

LIMITE_TRANSFER = 100000
# "operacion": monto > LIMITE_TRANSFER -> E506 (límite por operación).
# "acumulado": acumulado_transfer + monto > LIMITE_ACUMULADO -> E506.
# SUPUESTO: aún no sabemos cuál es; los ejemplos cumplen "operacion".
LIMITE_MODO = "operacion"
# SUPUESTO: tope usado solo en modo "acumulado" (140000 acumulado pasa en los ejemplos;
# el valor real es desconocido).
LIMITE_ACUMULADO = 150000

OK_RECIBIDO = "recieved"  # sic, error ortográfico del original


@dataclass
class Comando:
    aridad: int
    ejecutar: Callable[[State, list[str]], tuple[int, dict]]
    valida_control: bool = True  # PING no valida el control (ids 61-67)


def _monto(texto: str) -> int:
    # SUPUESTO: monto = enteros positivos en dígitos ASCII ("07" vale 7); 0, negativos,
    # decimales, signos o vacío -> E303.
    if not (texto.isascii() and texto.isdigit()) or int(texto) <= 0:
        raise ErrorServicio("E303")
    return int(texto)


def _cuenta(state: State, cid: str):
    cuenta = state.cuentas.get(cid)
    if cuenta is None:
        raise ErrorServicio("E401")
    return cuenta


def _ping(state, args):
    return 200, {"pong": True}


def _alta(state, args):
    # SUPUESTO: cualquier nombre no vacío (repetido incluido) es válido; espacios, guion y no-ASCII (76-78) y 3000 caracteres (83) pasan.
    return 201, {"cuentaId": state.nueva_cuenta(args[0])}


def _consulta(state, args):
    cuenta = _cuenta(state, args[0])
    return 200, {"cuenta_id": args[0], "saldo": cuenta.saldo}


def _deposito(state, args):
    # Validación de argumentos antes que existencia.
    monto = _monto(args[1])
    cuenta = _cuenta(state, args[0])
    cuenta.saldo += monto
    # SUPUESTO: los fallos no consumen IDs (el ID se asigna solo al tener éxito).
    oid = state.nueva_operacion(Operacion("DEPOSITO", None, args[0], monto))
    return 200, {"status": OK_RECIBIDO, "operacionId": oid}


def _transfer(state, args):
    monto = _monto(args[2])
    origen = _cuenta(state, args[0])
    destino = _cuenta(state, args[1])  # SUPUESTO: destino inexistente -> E401 (tras origen)
    # SUPUESTO: E506 se evalúa antes que E507 (en el ejemplo 9 el saldo alcanzaba).
    if LIMITE_MODO == "operacion":
        if monto > LIMITE_TRANSFER:
            raise ErrorServicio("E506")
    else:
        if state.acumulado_transfer + monto > LIMITE_ACUMULADO:
            raise ErrorServicio("E506")
    if origen.saldo < monto:
        raise ErrorServicio("E507")
    # SUPUESTO: transferir a la misma cuenta se acepta (efecto neto nulo).
    origen.saldo -= monto
    destino.saldo += monto
    state.acumulado_transfer += monto
    oid = state.nueva_operacion(Operacion("TRANSFER", args[0], args[1], monto))
    return 200, {"status": OK_RECIBIDO, "operacionId": oid}


def _anula(state, args):
    op = state.operaciones.get(args[0])
    if op is None:
        # SUPUESTO: ANULA de una operación inexistente -> 404 E402.
        raise ErrorServicio("E402")
    if op.anulada:
        return 200, {"ok": False, "motivo": "ya anulada"}
    destino = state.cuentas[op.destino]
    # SUPUESTO: si revertir deja el saldo del destino negativo (ya gastó el dinero) -> E507.
    if destino.saldo < op.monto:
        raise ErrorServicio("E507")
    destino.saldo -= op.monto
    if op.origen is not None:
        state.cuentas[op.origen].saldo += op.monto
    # SUPUESTO: anular una transferencia no libera el acumulado de límite.
    op.anulada = True
    return 200, {"ok": True, "anulada": args[0]}


COMANDOS: dict[str, Comando] = {
    "PING": Comando(0, _ping, valida_control=False),
    "ALTA": Comando(1, _alta),
    "CONSULTA": Comando(1, _consulta),
    "DEPOSITO": Comando(2, _deposito),
    "TRANSFER": Comando(3, _transfer),
    "ANULA": Comando(1, _anula),
}


def handle(state: State, m) -> tuple[int, dict | str]:
    """Procesa el valor del campo `m` y devuelve (status, cuerpo)."""
    if not isinstance(m, str):
        # m no string -> E102 (ids 45, 46, 48); core.http ya lo filtra antes.
        return ErrorServicio("E102").respuesta()
    try:
        msg = parser.separar(m)
        parser.validar(msg, COMANDOS)
        return COMANDOS[msg.comando].ejecutar(state, msg.args)
    except ErrorServicio as e:
        return e.respuesta()
