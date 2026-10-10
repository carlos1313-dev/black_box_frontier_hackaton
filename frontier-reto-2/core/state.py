"""Estado del servicio por token. `State()` es el estado inicial."""

from dataclasses import dataclass, field


@dataclass
class Cuenta:
    nombre: str
    saldo: int = 0


@dataclass
class Operacion:
    tipo: str  # "DEPOSITO" | "TRANSFER"
    origen: str | None
    destino: str
    monto: int
    anulada: bool = False


@dataclass
class State:
    cuentas: dict[str, Cuenta] = field(default_factory=dict)
    operaciones: dict[str, Operacion] = field(default_factory=dict)
    siguiente_cuenta: int = 1
    siguiente_operacion: int = 1
    # Solo se usa si commands.LIMITE_MODO == "acumulado".
    acumulado_transfer: int = 0

    def nueva_cuenta(self, nombre: str) -> str:
        cid = "AC-%04d" % self.siguiente_cuenta
        self.siguiente_cuenta += 1
        self.cuentas[cid] = Cuenta(nombre)
        return cid

    def nueva_operacion(self, op: Operacion) -> str:
        oid = "OP-%04d" % self.siguiente_operacion
        self.siguiente_operacion += 1
        self.operaciones[oid] = op
        return oid
