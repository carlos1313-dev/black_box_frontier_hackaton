import contextlib
import copy
import io
import json
import unittest

from tools import canary, fuzz, spec_build
from tools.comun import HarnessFalso
from tools.replay import leer_log, LOG_POR_DEFECTO


def _halt_con_args(m) -> bool:
    # Verificación independiente de la del fuzzer.
    if not isinstance(m, str):
        return False
    segs = m.split(";")
    return segs[0].strip().upper() == "HALT" and len(segs) > 2


class TestFuzz(unittest.TestCase):
    def test_dry_run_sin_divergencias_ni_halt_con_args(self):
        for semilla in (1, 2):
            h = HarnessFalso()
            res = fuzz.correr(h, 40, semilla, 600, salida=lambda *_: None)
            self.assertEqual(res.diferencias, [], f"semilla {semilla}")
            self.assertGreater(res.pasos, 40)
            self.assertLessEqual(res.requests, 600)
            self.assertEqual(res.requests, h.n_requests)  # se cuentan también los resets
            for linea in h.lineas:
                req = linea["request"]
                if isinstance(req, dict):
                    self.assertFalse(_halt_con_args(req.get("m")), req)
                if linea.get("raw"):
                    self.assertNotIn("halt", str(req).lower())

    def test_cli_dry_run(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            codigo = fuzz.main(["--secuencias", "50", "--semilla", "1", "--dry-run"])
        self.assertEqual(codigo, 0)
        self.assertRegex(out.getvalue(), r"divergencias 0 / pasos \d+")

    def test_reproducible_por_semilla(self):
        a, b = HarnessFalso(), HarnessFalso()
        fuzz.correr(a, 15, 5, 600, salida=lambda *_: None)
        fuzz.correr(b, 15, 5, 600, salida=lambda *_: None)
        self.assertEqual([l["request"] for l in a.lineas], [l["request"] for l in b.lineas])

    def test_max_requests_se_respeta(self):
        h = HarnessFalso()
        res = fuzz.correr(h, 200, 3, 50, salida=lambda *_: None)
        self.assertLessEqual(res.requests, 50)
        self.assertEqual(res.requests, h.n_requests)

    def test_deteccion_de_halt(self):
        for m in ("HALT;x;42", "halt;x;42", "HaLt;a;b;c", " HALT;x;1", "HALT ;x;1"):
            self.assertTrue(fuzz.es_halt_con_args(m), m)
        for m in ("HALT;71", "HALTA;19", "PING;64", "HALT", 5):
            self.assertFalse(fuzz.es_halt_con_args(m), m)
        with self.assertRaises(AssertionError):
            fuzz.verificar_seguro(fuzz.Paso("m", "hAlT;x;42", "h"))
        with self.assertRaises(AssertionError):
            fuzz.verificar_seguro(fuzz.Paso("http", {"raw": "{\"m\":\"HALT;x;42\"}"}, "h"))
        fuzz.verificar_seguro(fuzz.Paso("m", "HALT;71", "h"))  # sin argumentos: permitido


class TestCanary(unittest.TestCase):
    def test_dry_run_sale_0_y_no_escribe(self):
        existia = canary.LOG_CANARIO.exists()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            codigo = canary.main(["--dry-run"])
        self.assertEqual(codigo, 0)
        self.assertIn("canario OK", out.getvalue())
        self.assertEqual(canary.LOG_CANARIO.exists(), existia)

    def test_por_defecto_no_envia_e520(self):
        h = HarnessFalso()
        canary.ejecutar(h)
        self.assertFalse(any(_halt_con_args((l["request"] or {}).get("m")) for l in h.lineas
                             if isinstance(l["request"], dict)))

    def test_cubre_todos_los_errores_conocidos(self):
        h = HarnessFalso()
        canary.ejecutar(h, con_e520=True)
        codigos = {l["response"].get("error") for l in h.lineas if isinstance(l["response"], dict)}
        esperado = {"E001", "E100", "E102", "E103", "E104", "E201", "E202", "E301", "E302", "E303",
                    "E304", "E401", "E402", "E404", "E506", "E507", "E520"}
        self.assertTrue(esperado <= codigos, esperado - codigos)


class TestSpecBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log = leer_log(LOG_POR_DEFECTO)
        with open(spec_build.BEHAVIORS_POR_DEFECTO, encoding="utf-8") as f:
            cls.datos = json.load(f)

    def test_behaviors_de_ejemplo_valido(self):
        errores, _ = spec_build.validar(self.datos, self.log)
        self.assertEqual(errores, [])

    def test_evidencia_inexistente(self):
        d = copy.deepcopy(self.datos)
        d["comportamientos"][0]["evidencia"] = [999999]
        errores, _ = spec_build.validar(d, self.log)
        self.assertTrue(any("999999" in e and "no existe" in e for e in errores), errores)

    def test_evidencia_no_reproducida(self):
        log = copy.deepcopy(self.log)
        for e in log:
            if e["id"] == 23:
                e["response"] = {"ok": False}
        errores, _ = spec_build.validar(self.datos, log)
        self.assertTrue(any("NO reproduce" in e and "23" in e for e in errores), errores)

    def test_reglas_de_confianza_y_ids(self):
        d = copy.deepcopy(self.datos)
        d["comportamientos"] += [
            {"id": "X-01", "seccion": 1, "comportamiento": "a", "evidencia": [], "confianza": "supuesto"},
            {"id": "X-02", "seccion": 1, "comportamiento": "a", "evidencia": [], "confianza": "confirmado"},
            {"id": "X-03", "seccion": 1, "comportamiento": "a", "evidencia": [23], "confianza": "confirmado"},
            {"id": "X-03", "seccion": 9, "comportamiento": "a", "evidencia": [23], "confianza": "dudoso"},
        ]
        errores, avisos = spec_build.validar(d, self.log)
        texto = "\n".join(errores)
        self.assertNotIn("X-01", texto)  # supuesto sin evidencia es válido
        self.assertIn("X-02: solo 'supuesto'", texto)
        self.assertIn("X-03: id duplicado", texto)
        self.assertIn("sección 9", texto)
        self.assertIn("confianza 'dudoso'", texto)
        self.assertTrue(any("X-03" in a and "una sola evidencia" in a for a in avisos), avisos)
        self.assertFalse(any("X-03" in e and "una sola" in e for e in errores))

    def test_generar_spec(self):
        md = spec_build.generar(self.datos)
        titulos = [l for l in md.splitlines() if l.startswith("## ")]
        self.assertEqual([t.split(". ", 1)[1] for t in titulos], list(spec_build.SECCIONES.values()))
        self.assertEqual(md.count("| ID | Comportamiento | Evidencia | Confianza |"), 7)
        self.assertIn("| ENT-02 |", md)
        self.assertIn("31–39", md)
        self.assertIn("### ALTA", md)

    def test_compactar(self):
        self.assertEqual(spec_build.compactar([24, 25]), "24, 25")
        self.assertEqual(spec_build.compactar([24, 25, 26, 27, 31]), "24–27, 31")
        self.assertEqual(spec_build.compactar([]), "")

    def test_cli_check(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(spec_build.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
