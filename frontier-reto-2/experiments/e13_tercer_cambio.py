"""E13 · Búsqueda del tercer cambio v2 (la revalidación del log solo explica 2: ids 1486-2392).

Hipótesis: con el saldo ahora en formato decimal, los montos podrían aceptar decimales.
"""

from tools.harness import Harness


def main():
    h = Harness()
    s = h.secuencia("e13-montos-decimales", "v2: ¿los montos aceptan decimales ahora que el saldo es decimal?")
    s.msg("ALTA;Ana", "cuenta")
    s.msg("ALTA;Zoe", "cuenta 2")
    for monto in ("1.50", "1.5", "0.50", "100.00", "1,50", "10.000", "007", "1e3"):
        print(monto, s.msg(f"DEPOSITO;AC-0001;{monto}", f"v2: monto {monto!r} en DEPOSITO (v1: E303)"))
    print(s.msg("CONSULTA;AC-0001", "v2: saldo tras los intentos"))
    s.msg("DEPOSITO;AC-0001;100000", "fondos")
    print(s.msg("TRANSFER;AC-0001;AC-0002;2.50", "v2: monto decimal en TRANSFER"))
    print(s.msg("CONSULTA;AC-0002", "v2: saldo destino"))


if __name__ == "__main__":
    main()
