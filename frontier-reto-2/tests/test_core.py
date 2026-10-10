import unittest
from pathlib import Path

from core import State, Store, handle, responder
from core.checksum import control, firmar
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
        self.assertEqual(handle(State(), 5)[1]["error"], "E102")

    def test_checksum_rango_98(self):
        # ids 79-82 de experimentos.jsonl: control 97 y 98 existen, 0 y 1 no.
        self.assertEqual(control("ALTA;Anaafg"), 97)
        self.assertEqual(control("ALTA;Anaaaq"), 98)

    def test_ping_no_valida_control_pero_si_aridad(self):
        self.assertEqual(handle(State(), "ping;XX")[0], 200)
        self.assertEqual(handle(State(), "PING;x;21")[1]["error"], "E302")
        self.assertEqual(handle(State(), "PING;;64")[1]["error"], "E104")

    def test_sugerencia(self):
        body = handle(State(), " PING;64")[1]
        self.assertEqual(body["sugerencia"], "PING")
        self.assertNotIn("sugerencia", handle(State(), firmar("SALDOS;AC-0001"))[1])

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


class TestHttp(unittest.TestCase):
    def setUp(self):
        self.store = Store("tok")
        self.auth = "Bearer tok"

    def msg(self, cuerpo, auth="Bearer tok"):
        return responder(self.store, "POST", "/msg", auth, cuerpo)

    def test_ruta_desconocida_antes_que_auth(self):
        self.assertEqual(responder(self.store, "GET", "/msg", None, None)[1]["error"], "E404")

    def test_auth(self):
        self.assertEqual(responder(self.store, "GET", "/health", None, None)[0], 401)
        self.assertEqual(responder(self.store, "GET", "/health", "bearer tok", None)[0], 401)
        self.assertEqual(responder(self.store, "GET", "/health", self.auth, None), (200, {"ok": True}))

    def test_cuerpo(self):
        self.assertEqual(self.msg(b"no json")[1]["error"], "E100")
        self.assertEqual(self.msg(None)[1]["error"], "E100")
        self.assertEqual(self.msg(b'{"M":"PING;64"}')[1]["error"], "E102")
        self.assertEqual(self.msg(b'{"m":""}')[1]["error"], "E103")
        self.assertEqual(self.msg(b'{"m":"PING;64","x":1}')[0], 200)
        self.assertEqual(self.msg(b"no json", auth=None)[0], 401)

    def test_reset_y_x_req(self):
        self.msg(('{"m":"%s"}' % firmar("ALTA;A")).encode())
        self.assertEqual(self.store.ultimo_x_req, 1)
        responder(self.store, "POST", "/__reset", self.auth, None)
        self.assertIsNone(self.store.ultimo_x_req)
        self.msg(b'{"m":"PING;64"}')
        self.assertEqual(self.store.ultimo_x_req, 2)  # el reset no reinicia X-Req
        cuerpo = ('{"m":"%s"}' % firmar("ALTA;B")).encode()
        self.assertEqual(self.msg(cuerpo)[1], {"cuentaId": "AC-0001"})  # sí reinicia el estado


if __name__ == "__main__":
    unittest.main()
