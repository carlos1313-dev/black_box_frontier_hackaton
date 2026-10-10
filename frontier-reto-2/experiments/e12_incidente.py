"""E12 · Incidente v2 (detectado por el canario a las 16:00, ids 1416, 1419, 1420, 1438).

Cambios vistos: CONSULTA devuelve el saldo como texto con 2 decimales (centavos), y TRANSFER de
100000 ahora da E506. Aquí se miden las fronteras exactas de ambos.
"""

from tools.harness import Harness


def main():
    h = Harness()
    # -- límite de TRANSFER: búsqueda binaria entre 40000 (ok, 1418) y 100000 (E506, 1420)
    s = h.secuencia("e12-limite-transfer", "v2: ¿cuál es el nuevo límite por operación de TRANSFER?")
    s.msg("ALTA;Lucia", "cuenta origen")
    s.msg("ALTA;Mateo", "cuenta destino")
    s.msg("DEPOSITO;AC-0001;5000000", "v2: fondos para la búsqueda; ¿DEPOSITO sigue sin límite?")
    ok, malo = 40000, 100000
    while malo - ok > 1:
        mid = (ok + malo) // 2
        r = s.msg(f"TRANSFER;AC-0001;AC-0002;{mid}", f"v2: búsqueda del límite de TRANSFER, prueba {mid}")
        print("TRANSFER", mid, r)
        if r.status == 200:
            ok = mid
        else:
            malo = mid
    print("LIMITE: ok", ok, "E506 desde", malo)
    s.msg(f"TRANSFER;AC-0001;AC-0002;{ok}", f"v2: el límite {ok} se acepta (confirmación)")
    s.msg(f"TRANSFER;AC-0001;AC-0002;{malo}", f"v2: {malo} da E506 (confirmación)")
    r = s.msg("CONSULTA;AC-0001", "v2: formato del saldo tras la búsqueda")
    print(r)
    r = s.msg("TRANSFER;AC-0002;AC-0001;10", "v2: E506 sigue antes que E507? (transfer pequeña, con saldo)")
    print(r)

    # -- formato del saldo
    s = h.secuencia("e12-formato-saldo", "v2: saldo como texto con 2 decimales (monto/100)")
    s.msg("ALTA;Ana", "cuenta")
    s.msg("ALTA;Zoe", "cuenta 2")
    for dep, hip in (("5", "¿5 -> \"0.05\"?"), ("1234", "¿1239 -> \"12.39\"?"),
                     ("9999999999", "¿monto máximo -> 100000012.38?")):
        s.msg(f"DEPOSITO;AC-0001;{dep}", f"v2: depósito {dep}")
        print(s.msg("CONSULTA;AC-0001", f"v2: formato del saldo {hip}"))
    s2 = h.secuencia("e12-saldo-negativo", "v2: formato de un saldo negativo")
    s2.msg("ALTA;Ana", "cuenta A")
    s2.msg("ALTA;Zoe", "cuenta B")
    s2.msg("DEPOSITO;AC-0001;150", "OP-0001")
    s2.msg("TRANSFER;AC-0001;AC-0002;150", "OP-0002 deja A en 0")
    s2.msg("ANULA;OP-0001", "anular el depósito deja A en -150")
    print(s2.msg("CONSULTA;AC-0001", "v2: ¿saldo negativo -> \"-1.50\"?"))
    print(s2.msg("CONSULTA;AC-0002", "v2: B con 150 -> \"1.50\""))


if __name__ == "__main__":
    main()
