import unittest
from pathlib import Path

from core import State, handle
from core.checksum import firmar
from tools.replay import leer_log, replay

RAIZ = Path(__file__).resolve().parent.parent


class TestReplay(unittest.TestCase):
    def _conformidad(self, ruta):
        res = replay(leer_log(RAIZ / ruta))
        self.assertGreater(res.total, 0)
        self.assertEqual(res.diferencias, [])
        self.assertEqual(res.ok, res.total)

    def test_ejemplos(self):
        self._conformidad("pruebas/ejemplos.jsonl")

    def test_experimentos(self):
        self._conformidad("experimentos.jsonl")


class TestCore(unittest.TestCase):
    def test_ping(self):
        self.assertEqual(handle(State(), "PING;64"), (200, {"pong": True}))

    def test_m_no_string(self):
        status, _ = handle(State(), 5)
        self.assertEqual(status, 400)

    def test_control_antes_que_comando(self):
        # SUPUESTO de orden: E202 antes que E301.
        self.assertEqual(handle(State(), "XX;1")[1]["error"], "E202")

    def test_deposito_y_anula(self):
        s = State()
        handle(s, firmar("ALTA;A"))
        self.assertEqual(handle(s, firmar("DEPOSITO;AC-0001;10"))[1]["operacionId"], "OP-0001")
        self.assertEqual(handle(s, firmar("CONSULTA;AC-0001"))[1]["saldo"], 10)
        self.assertEqual(handle(s, firmar("ANULA;OP-0001"))[1], {"ok": True, "anulada": "OP-0001"})
        self.assertEqual(handle(s, firmar("CONSULTA;AC-0001"))[1]["saldo"], 0)


if __name__ == "__main__":
    unittest.main()
