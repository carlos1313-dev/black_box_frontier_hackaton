"""E01 · Reproduce pruebas/ejemplos.jsonl contra el original.

Hipótesis: el servicio vigente responde igual que la versión de la mañana.
Deja evidencia citable en nuestro log y detecta cambios tempranos.
"""

import json
from pathlib import Path

from tools.harness import Harness

EJEMPLOS = Path(__file__).resolve().parent.parent / "pruebas" / "ejemplos.jsonl"


def main():
    ejemplos = [json.loads(l) for l in EJEMPLOS.read_text(encoding="utf-8").splitlines() if l.strip()]
    s = Harness().secuencia("ejemplos", "la secuencia de ejemplos.jsonl se reproduce igual que en la mañana")
    difs = 0
    for e in ejemplos:
        r = s.m(e["request"]["m"], f"ejemplo n={e['n']} responde igual que en la mañana")
        igual = r.status == e["status"] and r.body == e["response"]
        difs += not igual
        print(("  =" if igual else "  ≠"), r, "" if igual else f"  esperado {e['status']} {e['response']}")
    print(f"\nDiferencias contra la mañana: {difs} / {len(ejemplos)}")


if __name__ == "__main__":
    main()
