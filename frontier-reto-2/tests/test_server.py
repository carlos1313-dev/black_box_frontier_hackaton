import json
import threading
import unittest
import urllib.error
import urllib.request

from server.app import crear_servidor


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = crear_servidor("prueba", "127.0.0.1", 0)  # puerto efímero
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        cls.hilo = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.hilo.start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pedir(self, metodo, ruta, cuerpo=None, token="prueba"):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        req = urllib.request.Request(
            self.base + ruta,
            data=cuerpo.encode() if cuerpo is not None else None,
            headers=headers,
            method=metodo,
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.headers, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                return e.code, e.headers, json.loads(e.read().decode())
            finally:
                e.close()

    def test_health(self):
        self.assertEqual(self.pedir("GET", "/health")[::2], (200, {"ok": True}))
        self.assertEqual(self.pedir("GET", "/health", token=None)[0], 401)

    def test_ping(self):
        status, headers, cuerpo = self.pedir("POST", "/msg", '{"m":"PING;64"}')
        self.assertEqual((status, cuerpo), (200, {"pong": True}))
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn("X-Req", headers)

    def test_ruta_inexistente(self):
        self.assertEqual(
            self.pedir("GET", "/noexiste")[::2],
            (404, {"error": "E404", "mensaje": "ruta desconocida"}),
        )
        self.assertEqual(self.pedir("PUT", "/msg", "{}")[0], 404)

    def test_doble_barra_es_ruta_desconocida(self):
        # http.server colapsa "//msg" a "/msg"; el original da E404 (id 925).
        status, _, cuerpo = self.pedir("POST", "//msg", '{"m": "PING;64"}')
        self.assertEqual((status, cuerpo["error"]), (404, "E404"))

    def test_query_string_se_ignora(self):
        status, _, cuerpo = self.pedir("POST", "/msg?x=1", '{"m": "PING;64"}')
        self.assertEqual((status, cuerpo), (200, {"pong": True}))

    def test_cuerpo_no_json(self):
        self.assertEqual(
            self.pedir("POST", "/msg", "esto no es json")[::2],
            (400, {"error": "E100", "mensaje": "json inválido"}),
        )

    def test_reset_y_estado(self):
        from core.checksum import firmar

        self.pedir("POST", "/__reset")
        alta = json.dumps({"m": firmar("ALTA;Ana")})
        self.assertEqual(self.pedir("POST", "/msg", alta)[2], {"cuentaId": "AC-0001"})
        self.pedir("POST", "/__reset")
        self.assertEqual(self.pedir("POST", "/msg", alta)[2], {"cuentaId": "AC-0001"})


if __name__ == "__main__":
    unittest.main()
