"""E05 · Reprueba de verbos con resto 0/1, comando oculto HALT y reglas de la sugerencia."""

from tools.harness import Harness


def main():
    h = Harness()
    s = h.secuencia("verbos-resto01", "RETIRA/AYUDA/PONG con el control corregido (98-resto)")
    for v in ("RETIRA", "AYUDA", "PONG"):
        print(f"{v:12}", s.msg(v, f"¿existe {v}? reprueba con control corregido; PONG a distancia 1 de PING"))

    s = h.secuencia("sugerencia", "la sugerencia es el comando a distancia Levenshtein <= 2")
    for v, hip in [
        ("pin", "minúsculas: ¿la sugerencia sale en mayúsculas?"),
        ("ALT", "empate a distancia 1 entre ALTA y HALT: ¿cuál gana?"),
        ("HALTA", "empate a distancia 1 entre ALTA y HALT"),
        ("CONSULTAXX", "distancia 2 → hay sugerencia"),
        ("CONSULTAXXX", "distancia 3 → sin sugerencia"),
        ("AL", "distancia 2 de ALTA, 3 de HALT"),
    ]:
        print(f"{v:12}", s.msg(v, hip))

    s = h.secuencia("halt", "qué hace HALT y si congela el estado del token")
    print("ALTA       ", s.msg("ALTA;Ana", "preparar cuenta antes de HALT"))
    print("DEPOSITO   ", s.msg("DEPOSITO;AC-0001;1000", "preparar saldo antes de HALT"))
    print("HALT       ", s.msg("HALT", "HALT sin argumentos: ¿qué responde?"))
    print("HALT;x     ", s.msg("HALT;x", "HALT con un argumento: ¿aridad?"))
    print("PING       ", s.msg("PING", "PING después de HALT: ¿el servicio sigue respondiendo?"))
    print("CONSULTA   ", s.msg("CONSULTA;AC-0001", "CONSULTA después de HALT: ¿estado intacto?"))
    print("DEPOSITO   ", s.msg("DEPOSITO;AC-0001;5", "DEPOSITO después de HALT: ¿se aceptan escrituras?"))
    print("GET health ", s.http("GET /health después de HALT", metodo="GET", ruta="/health"))


if __name__ == "__main__":
    main()
