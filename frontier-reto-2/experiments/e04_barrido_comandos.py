"""E04 · Barrido de comandos ocultos: verbo sin argumentos y con control válido.
E301 = no existe; E302 = existe con otra aridad; otro resultado = existe sin argumentos."""

from tools.harness import Harness

VERBOS = """RETIRO RETIRA RETIRAR EXTRACTO MOVIMIENTOS HISTORIAL BAJA CIERRE CERRAR SALDO SALDOS BALANCE
LISTA LISTAR CUENTAS HELP AYUDA INFO VERSION STATUS ESTADO ECHO DEBUG ADMIN RESET PAGO PAGAR CARGO ABONO
CONGELA BLOQUEA DESBLOQUEA LIMITE OPERACION REVERSA REEMBOLSO DEPOSITAR TRANSFERENCIA TRANSFERIR PRESTAMO
INTERES CAMBIO MODIFICA RENOMBRA AUDITORIA LOG HORA FECHA HOLA TEST PONG DEPOSIT WITHDRAW BALANCE ACCOUNT
ALTA CONSULTA DEPOSITO TRANSFER ANULA PIN PINGG PIG DEPOSITOS TRANSFERS ANULAR CONSULTAR""".split()


def main():
    s = Harness().secuencia("barrido-comandos", "existen comandos además de los 6 conocidos")
    for v in dict.fromkeys(VERBOS):
        r = s.msg(v, f"¿existe el comando {v}? (E301 no, E302 sí con otra aridad)")
        if r.body != {"error": "E301", "mensaje": "comando desconocido "}:
            print(f"{v:14}", r)
    print("(el resto: E301 sin sugerencia)")


if __name__ == "__main__":
    main()
