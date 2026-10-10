"""E06 · Reglas de negocio: límite, argumentos de DEPOSITO, semántica de TRANSFER y ANULA."""

from tools.harness import Harness


def correr(s, pasos):
    for cuerpo, hip in pasos:
        print(f"{cuerpo[:38]:40}", s.msg(cuerpo, hip))


def main():
    h = Harness()
    correr(h.secuencia("limite", "límite de TRANSFER: ¿por operación o acumulado?"), [
        ("ALTA;Ana", "cuenta origen"),
        ("ALTA;Beto", "cuenta destino"),
        ("DEPOSITO;AC-0001;500000", "¿DEPOSITO tiene límite? 500000"),
        ("TRANSFER;AC-0001;AC-0002;100000", "100000 exacto pasa"),
        ("TRANSFER;AC-0001;AC-0002;100000", "segundo 100000: si falla E506 el límite es acumulado"),
        ("TRANSFER;AC-0001;AC-0002;100001", "100001: frontera del límite por operación"),
        ("TRANSFER;AC-0002;AC-0001;1", "¿el límite es por cuenta origen?"),
        ("CONSULTA;AC-0001", "saldo tras las transferencias"),
    ])
    correr(h.secuencia("args-deposito", "validación del monto y de la cuenta en DEPOSITO"), [
        ("ALTA;Ana", "cuenta de prueba"),
        ("DEPOSITO;AC-0001;0", "monto 0"),
        ("DEPOSITO;AC-0001;-5", "monto negativo"),
        ("DEPOSITO;AC-0001;1.5", "monto decimal"),
        ("DEPOSITO;AC-0001;abc", "monto no numérico"),
        ("DEPOSITO;AC-0001;007", "monto con ceros a la izquierda"),
        ("DEPOSITO;AC-0001;+5", "monto con signo +"),
        ("DEPOSITO;AC-0001;99999999999999999999", "monto enorme"),
        ("DEPOSITO;AC-0001;1e3", "notación científica"),
        ("DEPOSITO;AC-0099;100", "cuenta inexistente"),
        ("DEPOSITO;ac-0001;100", "id de cuenta en minúsculas"),
        ("DEPOSITO;AC-1;100", "id de cuenta sin ceros"),
        ("DEPOSITO;AC-0099;abc", "monto inválido en cuenta inexistente: ¿qué se valida primero?"),
        ("CONSULTA;AC-0001", "saldo tras los intentos"),
        ("DEPOSITO;AC-0001;1", "¿qué OP-id toca tras los fallos?"),
    ])
    correr(h.secuencia("transfer", "semántica de TRANSFER"), [
        ("ALTA;Ana", "AC-0001"),
        ("ALTA;Beto", "AC-0002"),
        ("DEPOSITO;AC-0001;1000", "saldo inicial"),
        ("TRANSFER;AC-0001;AC-0001;100", "transferencia a la misma cuenta"),
        ("TRANSFER;AC-0001;AC-0099;100", "destino inexistente"),
        ("TRANSFER;AC-0099;AC-0001;100", "origen inexistente"),
        ("TRANSFER;AC-0001;AC-0002;5000", "saldo insuficiente bajo el límite"),
        ("TRANSFER;AC-0001;AC-0002;200000", "insuficiente Y sobre el límite: ¿E506 o E507?"),
        ("TRANSFER;AC-0001;AC-0002;0", "monto 0"),
        ("TRANSFER;AC-0001;AC-0002;-5", "monto negativo"),
        ("CONSULTA;AC-0001", "saldo origen"),
        ("CONSULTA;AC-0002", "saldo destino"),
    ])
    correr(h.secuencia("anula", "semántica de ANULA"), [
        ("ALTA;Ana", "AC-0001"),
        ("ALTA;Beto", "AC-0002"),
        ("DEPOSITO;AC-0001;1000", "OP-0001"),
        ("TRANSFER;AC-0001;AC-0002;600", "OP-0002"),
        ("TRANSFER;AC-0002;AC-0001;600", "OP-0003: Beto queda en 0"),
        ("ANULA;OP-0002", "anular cuando el destino ya gastó el dinero"),
        ("CONSULTA;AC-0002", "¿saldo negativo?"),
        ("ANULA;OP-0001", "anular un DEPOSITO"),
        ("CONSULTA;AC-0001", "saldo tras anular el depósito"),
        ("ANULA;OP-0099", "operación inexistente"),
        ("ANULA;AC-0001", "id de cuenta en lugar de operación"),
        ("ANULA;op-0003", "id de operación en minúsculas"),
        ("DEPOSITO;AC-0001;1", "¿ANULA consume OP-id?"),
        ("ALTA;Ana", "nombre repetido"),
        ("CONSULTA;OP-0001", "CONSULTA con id de operación"),
    ])


if __name__ == "__main__":
    main()
