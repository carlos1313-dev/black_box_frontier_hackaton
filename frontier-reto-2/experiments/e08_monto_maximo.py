"""E08 · Búsqueda binaria del monto máximo de DEPOSITO (15 dígitos ya es inválido, id 235)."""

from core.checksum import firmar
from tools.harness import Harness


def main():
    s = Harness().secuencia("monto-binaria", "frontera exacta del monto máximo")
    s.m(firmar("ALTA;Ana"), "cuenta para depositar")

    def valido(monto: int) -> bool:
        r = s.m(firmar(f"DEPOSITO;AC-0001;{monto}"), f"búsqueda binaria del máximo: ¿{monto} es válido?")
        print(f"{monto:>16}", r)
        return r.status == 200

    bajo, alto = 500000, 999999999999999  # bajo válido (id 174), alto inválido (id 235)
    while alto - bajo > 1:
        medio = (bajo + alto) // 2
        if valido(medio):
            bajo = medio
        else:
            alto = medio
    print(f"\nmáximo válido = {bajo}, mínimo inválido = {alto}")


if __name__ == "__main__":
    main()
