"""Valida behaviors.json contra el log y el clon, y genera SPEC.md.

    python3 -m tools.spec_build [--check] [--behaviors RUTA] [--log RUTA] [--salida RUTA]

Formato de behaviors.json:

    {"secciones": {"1": {"titulo": "Entrada", "intro": "texto opcional"}, ...},
     "comportamientos": [{"id": "ENT-01", "seccion": 1, "comportamiento": "...",
                          "evidencia": [24, 25], "confianza": "confirmado"}],
     "bloques": {"3": [{"titulo": "ALTA", "texto": "markdown libre"}]}}

Validaciones (error = exit 1): ids únicos, sección 1-7, confianza válida, cada evidencia existe en el
log, solo `supuesto` puede tener evidencia vacía y toda evidencia citada debe ser reproducida por el
clon (replay de la secuencia completa de esa línea). Aviso (no error): `confirmado` con una sola
evidencia.
"""

import argparse
import json
import sys
from pathlib import Path

from .replay import LOG_POR_DEFECTO, leer_log, replay

RAIZ = Path(__file__).resolve().parent.parent
BEHAVIORS_POR_DEFECTO = RAIZ / "behaviors.json"
SPEC_POR_DEFECTO = RAIZ / "SPEC.md"

SECCIONES = {
    1: "Entrada",
    2: "Integridad",
    3: "Comandos",
    4: "Memoria entre requests",
    5: "Errores",
    6: "Cambios durante el día",
    7: "Riesgos",
}
CONFIANZAS = ("confirmado", "probable", "supuesto")


# -- validación -------------------------------------------------------------------

def ids_no_reproducidos(lineas: list[dict]) -> set[int]:
    """Ids de líneas del log cuya respuesta el clon NO reproduce (replay por secuencia completa)."""
    return {e["id"] for e, *_ in replay(lineas).diferencias}


def ids_ignorados(lineas: list[dict]) -> set[int]:
    return {e["id"] for e in lineas if str(e.get("conclusion") or "").startswith("INFRA")}


def validar(datos: dict, lineas: list[dict]) -> tuple[list[str], list[str]]:
    """Devuelve (errores, avisos)."""
    errores: list[str] = []
    avisos: list[str] = []
    if not isinstance(datos, dict):
        return ["behaviors.json debe ser un objeto"], avisos

    ids_log = {e["id"] for e in lineas}
    malos = ids_no_reproducidos(lineas)
    infra = ids_ignorados(lineas)

    secciones = datos.get("secciones", {})
    if not isinstance(secciones, dict):
        errores.append("'secciones' debe ser un objeto")
        secciones = {}
    for k in secciones:
        if k not in {str(n) for n in SECCIONES}:
            errores.append(f"secciones: clave {k!r} fuera de 1-7")

    vistos: set[str] = set()
    por_seccion: dict[int, int] = {}
    comportamientos = datos.get("comportamientos", [])
    if not isinstance(comportamientos, list):
        errores.append("'comportamientos' debe ser una lista")
        comportamientos = []
    for i, c in enumerate(comportamientos):
        if not isinstance(c, dict):
            errores.append(f"comportamientos[{i}]: debe ser un objeto")
            continue
        cid = c.get("id")
        etiqueta = cid if isinstance(cid, str) and cid else f"comportamientos[{i}]"
        if not isinstance(cid, str) or not cid:
            errores.append(f"{etiqueta}: falta 'id'")
        elif cid in vistos:
            errores.append(f"{cid}: id duplicado")
        else:
            vistos.add(cid)
        sec = c.get("seccion")
        if isinstance(sec, bool) or not isinstance(sec, int) or sec not in SECCIONES:
            errores.append(f"{etiqueta}: sección {sec!r} inválida (debe ser 1-7)")
        else:
            por_seccion[sec] = por_seccion.get(sec, 0) + 1
        if not isinstance(c.get("comportamiento"), str) or not c["comportamiento"].strip():
            errores.append(f"{etiqueta}: falta el texto de 'comportamiento'")
        conf = c.get("confianza")
        if conf not in CONFIANZAS:
            errores.append(f"{etiqueta}: confianza {conf!r} inválida (use {', '.join(CONFIANZAS)})")
        evid = c.get("evidencia", [])
        if not isinstance(evid, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in evid):
            errores.append(f"{etiqueta}: 'evidencia' debe ser una lista de ids enteros")
            continue
        if not evid and conf != "supuesto":
            errores.append(f"{etiqueta}: solo 'supuesto' puede tener evidencia vacía")
        if len(set(evid)) != len(evid):
            avisos.append(f"{etiqueta}: evidencia con ids repetidos")
        for x in evid:
            if x not in ids_log:
                errores.append(f"{etiqueta}: la evidencia {x} no existe en el log")
            elif x in malos:
                errores.append(f"{etiqueta}: el clon NO reproduce la evidencia {x}")
            elif x in infra:
                avisos.append(f"{etiqueta}: la evidencia {x} está marcada INFRA (no se compara)")
        if conf == "confirmado" and len(set(evid)) == 1:
            avisos.append(f"{etiqueta}: 'confirmado' con una sola evidencia ({evid[0]})")

    bloques = datos.get("bloques", {})
    if not isinstance(bloques, dict):
        errores.append("'bloques' debe ser un objeto")
        bloques = {}
    for k, lista in bloques.items():
        if k not in {str(n) for n in SECCIONES}:
            errores.append(f"bloques: clave {k!r} fuera de 1-7")
        if not isinstance(lista, list):
            errores.append(f"bloques[{k}]: debe ser una lista")
            continue
        for j, b in enumerate(lista):
            if not isinstance(b, dict) or not b.get("titulo") or not isinstance(b.get("texto"), str):
                errores.append(f"bloques[{k}][{j}]: requiere 'titulo' y 'texto'")

    for n, nombre in SECCIONES.items():
        if por_seccion.get(n, 0) == 0:
            avisos.append(f"sección {n} ({nombre}) sin comportamientos")
    return errores, avisos


# -- generación -------------------------------------------------------------------

def compactar(ids: list[int]) -> str:
    """[24, 25, 26, 27, 31] -> '24–27, 31'. Solo se compactan rachas de 3 o más."""
    ids = sorted(set(ids))
    partes: list[str] = []
    i = 0
    while i < len(ids):
        j = i
        while j + 1 < len(ids) and ids[j + 1] == ids[j] + 1:
            j += 1
        if j - i >= 2:
            partes.append(f"{ids[i]}–{ids[j]}")
        else:
            partes.extend(str(x) for x in ids[i:j + 1])
        i = j + 1
    return ", ".join(partes)


def _celda(texto: str) -> str:
    return texto.strip().replace("|", "\\|").replace("\n", "<br>")


def generar(datos: dict) -> str:
    secciones = datos.get("secciones", {})
    bloques = datos.get("bloques", {})
    comps = datos.get("comportamientos", [])
    salida = ["# Especificación del servicio «caja negra»", ""]
    for n, nombre in SECCIONES.items():
        info = secciones.get(str(n), {})
        salida.append(f"## {n}. {info.get('titulo') or nombre}")
        salida.append("")
        if info.get("intro"):
            salida += [info["intro"].strip(), ""]
        for b in bloques.get(str(n), []):
            salida += [f"### {b['titulo']}", "", b["texto"].strip(), ""]
        filas = [c for c in comps if c["seccion"] == n]
        salida.append("| ID | Comportamiento | Evidencia | Confianza |")
        salida.append("| --- | --- | --- | --- |")
        for c in filas:
            evid = compactar(c.get("evidencia", [])) or "—"
            salida.append(f"| {c['id']} | {_celda(c['comportamiento'])} | {evid} | {c['confianza']} |")
        salida.append("")
    return "\n".join(salida)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools.spec_build", description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="solo valida; exit 1 si hay errores")
    ap.add_argument("--behaviors", type=Path, default=BEHAVIORS_POR_DEFECTO)
    ap.add_argument("--log", type=Path, default=LOG_POR_DEFECTO)
    ap.add_argument("--salida", type=Path, default=SPEC_POR_DEFECTO)
    a = ap.parse_args(argv)

    try:
        datos = json.loads(a.behaviors.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"ERROR: no se pudo leer {a.behaviors}: {e}")
        return 1
    errores, avisos = validar(datos, leer_log(a.log))
    for av in avisos:
        print(f"AVISO: {av}")
    for er in errores:
        print(f"ERROR: {er}")
    n = len(datos.get("comportamientos", [])) if isinstance(datos, dict) else 0
    print(f"{n} comportamientos, {len(errores)} error(es), {len(avisos)} aviso(s)")
    if errores:
        return 1
    if not a.check:
        a.salida.write_text(generar(datos), encoding="utf-8", newline="\n")
        print(f"escrito {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
