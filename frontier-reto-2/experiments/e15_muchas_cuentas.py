"""E15 · Tercer cambio v2: ¿hay un tope de cuentas u operaciones? (v1 nunca pasó de ~5 cuentas por secuencia)."""

from tools.harness import Harness


def main():
    h = Harness()
    s = h.secuencia("e15-muchas-cuentas", "v2: ¿ALTA tiene un tope de cuentas por token?")
    for i in range(1, 26):
        r = s.msg(f"ALTA;C{i}", f"v2: ALTA n.º {i}: ¿sigue dando AC-{i:04d}?")
        if r.status != 201:
            print("TOPE", i, r)
            break
    print(r)
    for i in range(1, 26):
        r = s.msg("DEPOSITO;AC-0001;1", f"v2: DEPOSITO n.º {i}: ¿sigue dando OP-{i:04d}?")
        if r.status != 200:
            print("TOPE OP", i, r)
            break
    print(r, s.msg("CONSULTA;AC-0001", "v2: saldo tras 25 depósitos de 1 -> \"0.25\""))


if __name__ == "__main__":
    main()
