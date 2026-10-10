"""Fuzzer diferencial: genera secuencias realistas (con mutaciones), las envía al original por el
harness y compara cada respuesta con la del clon (`core.responder`).

    python3 -m tools.fuzz --secuencias N --semilla S [--max-requests 600] [--dry-run]

Con --dry-run el original se sustituye por un harness falso (sin red, sin log).

SEGURIDAD: nunca se genera el comando HALT con argumentos (ni en ninguna combinación de
mayúsculas). `verificar_seguro` se ejecuta antes de CADA envío y aborta si lo detecta.
"""

import argparse
import json
import random
import sys
import unicodedata
from dataclasses import dataclass, field

from core import Store
from core.checksum import control, firmar
from core.commands import COMANDOS
from tools.harness import ErrorRed

from .comun import Diferencia, HarnessFalso, comparar
from .replay import TOKEN_PROPIO

PROB_MUTACION = 0.30
PROB_NO_MSG = 0.05

NOMBRES = ["Lucia", "Mateo", "Ana Maria", "Jose-Luis", "Núñez", "Zoe", "Camila Rojas", "Ñandú",
           "李雷", "O'Brien", "Beto", "x", "Carlos S", "María"]
MONTOS_FRONTERA = ["1", "100000", "100001", "9999999999", "10000000000", "0", "007", "-5",
                   "1.5", "abc", "+5", "1e3", "99999999999999999999", "000", "1_0"]
CONTROLES_MALFORMADOS = ["X", "5X", "-3", "+5", " 5", "003", "123", "1.5", "0", "1", "99", "100",
                         "٣", "5 ", "0x1", "NaN"]
IDS_CUENTA_MALOS = ["AC-9999", "ac-0001", "Ac-0001", "AC-0000", "AC-1", "AC-00001", "OP-0001",
                    "AC-0001 ", " AC-0001", "AC_0001", "AC0001", "-AC-0001"]
IDS_OP_MALOS = ["OP-0099", "op-0001", "OP-0000", "OP-1", "AC-0001", "OP-00001", "OP-0001 ", "OP0001"]


# -- seguridad ---------------------------------------------------------------

def es_halt_con_args(m) -> bool:
    """True si `m` es un HALT con argumentos (cualquier mayúscula; tolera espacios alrededor)."""
    if not isinstance(m, str):
        return False
    segs = m.split(";")
    primero = unicodedata.normalize("NFKC", segs[0]).strip().upper()
    return primero == "HALT" and len(segs) > 2


def verificar_seguro(paso: "Paso") -> None:
    """Falla (AssertionError) si el paso podría ejecutar HALT con argumentos."""
    p = paso.payload
    if paso.tipo == "m":
        if es_halt_con_args(p):
            raise AssertionError(f"HALT con argumentos generado: {p!r}")
    else:
        for clave in ("body", "raw"):
            v = p.get(clave)
            if v is not None and "halt" in json.dumps(v).lower():
                raise AssertionError(f"HALT en cuerpo no-/msg: {p!r}")


# -- pasos --------------------------------------------------------------------

@dataclass
class Paso:
    tipo: str  # "m" -> Secuencia.m(payload) | "http" -> Secuencia.http(**payload)
    payload: object
    hipotesis: str


def _firmado(segs: list[str]) -> str:
    return firmar(";".join(segs))


class Generador:
    """Genera pasos de una secuencia leyendo el estado vivo del modelo (`store`)."""

    def __init__(self, rng: random.Random, store: Store):
        self.rng = rng
        self.store = store

    @property
    def estado(self):
        return self.store.estado(TOKEN_PROPIO)

    # -- mensajes válidos ---------------------------------------------------

    def _monto_deposito(self) -> int:
        r = self.rng.random()
        if r < 0.60:
            return self.rng.randint(1, 5000)
        if r < 0.85:
            return self.rng.randint(1, 100000)
        if r < 0.95:
            return self.rng.randint(100001, 1000000)
        return self.rng.randint(1, 9999999999)

    def _valido(self, primero: bool) -> tuple[list[str], str]:
        """Segmentos (sin control) de un mensaje válido en el estado actual + etiqueta."""
        rng, st = self.rng, self.estado
        cuentas = list(st.cuentas)
        con_saldo = [c for c in cuentas if st.cuentas[c].saldo > 0]
        vivas = [o for o, op in st.operaciones.items() if not op.anulada]
        if not cuentas:
            cmd = rng.choices(["ALTA", "PING", "CONSULTA", "DEPOSITO", "TRANSFER", "ANULA"],
                              [10, 2, 1, 1, 1, 1])[0]
        else:
            pesos = {"ALTA": 4 if len(cuentas) < 2 else 1, "DEPOSITO": 4,
                     "TRANSFER": 5 if len(cuentas) >= 2 else 0,
                     "CONSULTA": 4, "ANULA": 3 if st.operaciones else 0, "PING": 1}
            cmd = rng.choices(list(pesos), list(pesos.values()))[0]
        if cmd == "PING":
            return ["PING"], "PING"
        if cmd == "ALTA":
            return ["ALTA", rng.choice(NOMBRES)], "ALTA"
        if cmd == "CONSULTA":
            return ["CONSULTA", rng.choice(cuentas) if cuentas else "AC-0001"], "CONSULTA"
        if cmd == "DEPOSITO":
            c = rng.choice(cuentas) if cuentas else "AC-0001"
            return ["DEPOSITO", c, str(self._monto_deposito())], "DEPOSITO"
        if cmd == "TRANSFER":
            if not cuentas:
                return ["TRANSFER", "AC-0001", "AC-0002", str(rng.randint(1, 1000))], "TRANSFER"
            if not con_saldo:  # nadie tiene fondos: primero un depósito
                return ["DEPOSITO", rng.choice(cuentas), str(self._monto_deposito())], "DEPOSITO"
            o = rng.choice(con_saldo)
            d = rng.choice([c for c in cuentas if c != o])
            saldo = st.cuentas[o].saldo
            tope = min(saldo, 100000)
            monto = tope if rng.random() < 0.1 else rng.randint(1, tope)
            return ["TRANSFER", o, d, str(monto)], "TRANSFER"
        # ANULA
        if st.operaciones:
            pool = list(st.operaciones) if (not vivas or rng.random() < 0.1) else vivas
            return ["ANULA", rng.choice(pool)], "ANULA"
        return ["ANULA", "OP-0001"], "ANULA"

    # -- mutaciones (devuelven (m, etiqueta) o None si no aplican) ------------

    def _m_control_incorrecto(self, segs, tag):
        cuerpo = ";".join(segs)
        c = control(cuerpo)
        otro = self.rng.choice([x for x in range(2, 99) if x != c])
        return f"{cuerpo};{otro}", "control incorrecto"

    def _m_control_malformado(self, segs, tag):
        return f"{';'.join(segs)};{self.rng.choice(CONTROLES_MALFORMADOS)}", "control mal formado"

    def _m_sin_control(self, segs, tag):
        return ";".join(segs), "sin campo de control"

    def _m_mayusculas(self, segs, tag):
        cmd = segs[0]
        nuevo = self.rng.choice([
            cmd.lower(), cmd.capitalize(),
            "".join(self.rng.choice((ch.lower(), ch.upper())) for ch in cmd),
        ])
        return _firmado([nuevo] + segs[1:]), f"comando en otras mayúsculas ({nuevo})"

    def _m_distancia(self, segs, tag):
        rng = self.rng
        for _ in range(10):
            k = rng.randint(1, 3)
            s = segs[0]
            for _ in range(k):
                op = rng.choice("idst")
                pos = rng.randrange(len(s) + 1)
                letra = rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                if op == "i":
                    s = s[:pos] + letra + s[pos:]
                elif op == "d" and len(s) > 1:
                    pos = min(pos, len(s) - 1)
                    s = s[:pos] + s[pos + 1:]
                elif op == "s":
                    pos = min(pos, len(s) - 1)
                    s = s[:pos] + letra + s[pos + 1:]
                elif op == "t" and len(s) > 1:
                    pos = min(pos, len(s) - 2)
                    s = s[:pos] + s[pos + 1] + s[pos] + s[pos + 2:]
            if s and s.upper() not in COMANDOS:
                if rng.random() < 0.85:
                    m = _firmado([s] + segs[1:])
                else:
                    m = f"{';'.join([s] + segs[1:])};{rng.randint(2, 98)}"
                return m, f"comando a distancia {k} de {tag} ({s})"
        return None

    def _m_aridad(self, segs, tag):
        rng = self.rng
        if len(segs) > 1 and rng.random() < 0.5:
            nuevo = segs[:-1]
            et = "un argumento de menos"
        else:
            nuevo = segs + [rng.choice(["x", "AC-0001", "100", "Extra"])]
            et = "un argumento de más"
        return _firmado(nuevo), f"aridad errónea: {et}"

    def _m_monto(self, segs, tag):
        if tag not in ("DEPOSITO", "TRANSFER"):
            return None
        nuevo = segs[:-1] + [self.rng.choice(MONTOS_FRONTERA)]
        return _firmado(nuevo), f"monto en frontera ({nuevo[-1]})"

    def _m_id(self, segs, tag):
        rng = self.rng
        if tag == "ANULA":
            idx, malos = 1, IDS_OP_MALOS
        elif tag in ("CONSULTA", "DEPOSITO"):
            idx, malos = 1, IDS_CUENTA_MALOS
        elif tag == "TRANSFER":
            idx, malos = rng.choice([1, 2]), IDS_CUENTA_MALOS
        else:
            return None
        if rng.random() < 0.4:
            nuevo_id = segs[idx].lower()
        else:
            nuevo_id = rng.choice(malos)
        nuevo = list(segs)
        nuevo[idx] = nuevo_id
        return _firmado(nuevo), f"id inexistente o en minúsculas ({nuevo_id!r})"

    def _m_vacios(self, segs, tag):
        rng = self.rng
        variante = rng.choice(["medio", "final", "inicio", "doble"])
        if variante == "medio":
            nuevo = list(segs)
            nuevo.insert(rng.randint(1, len(segs)), "")
            return _firmado(nuevo), "segmento vacío intermedio"
        if variante == "final":
            return _firmado(segs) + ";", "segmento vacío al final"
        if variante == "inicio":
            return ";" + _firmado(segs), "segmento vacío al inicio"
        return ";".join(segs) + ";;" + str(control(";".join(segs))), "segmentos vacíos dobles"

    def _m_halt0(self, segs, tag):
        return firmar("HALT"), "HALT sin argumentos"

    def _m_autotransfer(self, segs, tag):
        cuentas = list(self.estado.cuentas)
        c = self.rng.choice(cuentas) if cuentas else "AC-0001"
        return _firmado(["TRANSFER", c, c, str(self.rng.randint(1, 1000))]), "auto-transferencia"

    def _m_anula_repetida(self, segs, tag):
        ops = [o for o, op in self.estado.operaciones.items() if op.anulada]
        if not ops:
            return None
        return _firmado(["ANULA", self.rng.choice(ops)]), "ANULA repetida"

    def _m_anula_deposito(self, segs, tag):
        ops = [o for o, op in self.estado.operaciones.items() if op.tipo == "DEPOSITO"]
        if not ops:
            return None
        return _firmado(["ANULA", self.rng.choice(ops)]), "ANULA de un depósito"

    def _m_saldo_insuficiente(self, segs, tag):
        rng, st = self.rng, self.estado
        cuentas = list(st.cuentas)
        if len(cuentas) < 2:
            return None
        o = rng.choice(cuentas)
        d = rng.choice([c for c in cuentas if c != o])
        if rng.random() < 0.2:
            monto, et = rng.randint(100001, 200000), "saldo insuficiente y sobre el límite"
        else:
            monto, et = min(st.cuentas[o].saldo + rng.randint(1, 1000), 100000), "saldo insuficiente"
        return _firmado(["TRANSFER", o, d, str(max(monto, 1))]), et

    def _mutar(self, segs, tag):
        rng = self.rng
        tipos = [
            (self._m_control_incorrecto, 3), (self._m_control_malformado, 2), (self._m_sin_control, 1),
            (self._m_mayusculas, 2), (self._m_distancia, 2), (self._m_aridad, 2), (self._m_monto, 3),
            (self._m_id, 3), (self._m_vacios, 2), (self._m_halt0, 1), (self._m_autotransfer, 1),
            (self._m_anula_repetida, 1), (self._m_anula_deposito, 1), (self._m_saldo_insuficiente, 2),
        ]
        orden = list(tipos)
        rng.shuffle(orden)
        # Muestreo ponderado sin reemplazo: se prueban hasta que una aplica.
        while orden:
            fns, pesos = zip(*orden)
            fn = rng.choices(fns, pesos)[0]
            orden = [t for t in orden if t[0] is not fn]
            r = fn(segs, tag)
            if r is not None:
                return r
        return None

    # -- requests que no son /msg -----------------------------------------------

    def _http(self) -> Paso:
        rng = self.rng
        tipo = rng.choice(["health", "ruta", "auth", "no_json", "sin_m"])
        if tipo == "health":
            return Paso("http", {"metodo": "GET", "ruta": "/health"}, "fuzz: GET /health")
        if tipo == "ruta":
            metodo, ruta = rng.choice([("GET", "/noexiste"), ("POST", "/noexiste"), ("GET", "/msg"),
                                       ("PUT", "/msg"), ("POST", "/msg/"), ("POST", "/MSG"),
                                       ("GET", "/"), ("GET", "/__reset"), ("POST", "/health")])
            kw = {"metodo": metodo, "ruta": ruta}
            if metodo != "GET":
                kw["body"] = {"m": "PING;64"}
            return Paso("http", kw, f"fuzz: ruta/método inexistente {metodo} {ruta}")
        if tipo == "auth":
            auth = rng.choice(["ninguno", "Bearer cn-p-desconocido", "Bearer ", "Basic abc"])
            return Paso("http", {"body": {"m": "PING;64"}, "auth": auth}, f"fuzz: auth inválida ({auth})")
        if tipo == "no_json":
            raw = rng.choice(["esto no es json", "{\"m\": \"PING;64\"", "", "[1,2", "{'m':'PING;64'}",
                              "{\"m\":\"PING;64\"}   ", "null", "[]", "5", "\"PING;64\""])
            return Paso("http", {"raw": raw}, f"fuzz: cuerpo no JSON o raro ({raw!r})")
        body = rng.choice([{}, {"M": "PING;64"}, {"m": 5}, {"m": None}, {"m": ["PING;64"]},
                           {"x": 1, "m": "PING;64"}, {"m": True}])
        return Paso("http", {"body": body}, f"fuzz: m ausente o no string ({json.dumps(body)})")

    # -- API ------------------------------------------------------------------------

    def siguiente(self, i: int) -> Paso:
        rng = self.rng
        if rng.random() < PROB_NO_MSG:
            return self._http()
        for _ in range(30):
            segs, tag = self._valido(primero=(i == 0))
            if rng.random() < PROB_MUTACION:
                r = self._mutar(segs, tag)
                if r is not None:
                    m, et = r
                    if not es_halt_con_args(m):
                        return Paso("m", m, f"fuzz: mutación {et}")
                    continue
            m = _firmado(segs)
            if not es_halt_con_args(m):
                return Paso("m", m, f"fuzz: válido {tag}")
        return Paso("m", "PING;64", "fuzz: válido PING (respaldo)")


# -- ejecución --------------------------------------------------------------------

def plan_longitud(rng: random.Random) -> int:
    """~40 % de 1 paso, ~45 % de 2-5, ~15 % de 6-12 (distribución del set de evaluación)."""
    r = rng.random()
    if r < 0.40:
        return 1
    if r < 0.85:
        return rng.randint(2, 5)
    return rng.randint(6, 12)


@dataclass
class Resumen:
    secuencias: int = 0
    pasos: int = 0
    requests: int = 0  # pasos + resets
    diferencias: list[Diferencia] = field(default_factory=list)


def enviar(seq, paso: Paso):
    verificar_seguro(paso)
    if paso.tipo == "m":
        return seq.m(paso.payload, paso.hipotesis)
    return seq.http(paso.hipotesis, **paso.payload)


def correr(harness, secuencias: int, semilla: int, max_requests: int, salida=print) -> Resumen:
    res = Resumen()
    for n in range(1, secuencias + 1):
        rng = random.Random(f"fuzz-{semilla}-{n}")
        largo = plan_longitud(rng)
        restante = max_requests - res.requests
        if restante < 2:
            salida(f"[fuzz] tope de {max_requests} requests alcanzado: {res.secuencias}/{secuencias} secuencias")
            break
        largo = min(largo, restante - 1)  # el reset también cuenta
        seq = harness.secuencia(f"fuzz-{semilla}-{n}", f"fuzz semilla {semilla}, secuencia {n} ({largo} pasos)")
        res.requests += 1
        res.secuencias += 1
        store = Store(TOKEN_PROPIO)  # modelo vivo: avanza al comparar cada respuesta
        gen = Generador(rng, store)
        for i in range(largo):
            paso = gen.siguiente(i)
            res.requests += 1
            try:
                r = enviar(seq, paso)
            except ErrorRed as e:
                # Estado del original incierto: se abandona la secuencia; la siguiente arranca con reset.
                salida(f"[fuzz] secuencia {n} abandonada por error de red: {e}")
                break
            res.pasos += 1
            d = comparar(store, r, paso.hipotesis)
            if d is not None:
                res.diferencias.append(d)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools.fuzz", description=__doc__.split("\n")[0])
    ap.add_argument("--secuencias", type=int, required=True)
    ap.add_argument("--semilla", type=int, required=True)
    ap.add_argument("--max-requests", type=int, default=600)
    ap.add_argument("--dry-run", action="store_true", help="harness falso: sin red ni log")
    a = ap.parse_args(argv)

    if a.dry_run:
        harness = HarnessFalso()
    else:
        from .harness import Harness  # solo aquí: exige .env, rama develop y toca el original
        harness = Harness()
    res = correr(harness, a.secuencias, a.semilla, a.max_requests)
    for d in res.diferencias:
        print(d.texto())
    print(f"requests {res.requests} (máx {a.max_requests}), secuencias {res.secuencias}")
    print(f"divergencias {len(res.diferencias)} / pasos {res.pasos}")
    return 1 if res.diferencias else 0


if __name__ == "__main__":
    sys.exit(main())
