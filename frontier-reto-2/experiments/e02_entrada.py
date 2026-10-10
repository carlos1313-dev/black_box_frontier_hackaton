"""E02 · Entrada: rutas, métodos, autenticación y forma del cuerpo."""

from tools.harness import Harness


def main():
    h = Harness()
    s = h.secuencia("entrada", "rutas, métodos, auth y forma del cuerpo")
    t, te = h.token, h.token_equipo
    P = {"m": "PING;64"}
    pruebas = [
        ("GET /health con token responde 200", dict(metodo="GET", ruta="/health")),
        ("GET /health no exige token", dict(metodo="GET", ruta="/health", auth="ninguno")),
        ("POST /msg sin Authorization se rechaza", dict(body=P, auth="ninguno")),
        ("POST /msg con token desconocido se rechaza", dict(body=P, auth="Bearer cn-p-desconocido")),
        ("POST /msg con el token sin prefijo Bearer", dict(body=P, auth=t)),
        ("el esquema 'bearer' en minúsculas se acepta", dict(body=P, auth=f"bearer {t}")),
        ("el token del equipo (ftr_) no es válido en el original", dict(body=P, auth=f"Bearer {te}")),
        ("Authorization 'Bearer ' vacío", dict(body=P, auth="Bearer ")),
        ("GET /msg: método no permitido o 404", dict(metodo="GET", ruta="/msg")),
        ("PUT /msg: método no permitido o 404", dict(metodo="PUT", ruta="/msg", body=P)),
        ("GET / raíz", dict(metodo="GET", ruta="/")),
        ("GET ruta inexistente: cuerpo exacto del 404", dict(metodo="GET", ruta="/noexiste")),
        ("POST ruta inexistente: cuerpo exacto del 404", dict(metodo="POST", ruta="/noexiste", body=P)),
        ("ruta inexistente sin token: ¿404 o 401 primero?", dict(metodo="GET", ruta="/noexiste", auth="ninguno")),
        ("/msg/ con barra final equivale a /msg", dict(ruta="/msg/", body=P)),
        ("/MSG en mayúsculas equivale a /msg", dict(ruta="/MSG", body=P)),
        ("GET /__reset", dict(metodo="GET", ruta="/__reset")),
        ("cuerpo que no es JSON", dict(raw="esto no es json")),
        ("JSON truncado", dict(raw='{"m": "PING;64"')),
        ("cuerpo vacío", dict(raw="")),
        ("sin cuerpo", dict()),
        ("objeto vacío {}", dict(body={})),
        ("m numérico", dict(body={"m": 123})),
        ("m null", dict(body={"m": None})),
        ("m string vacío", dict(body={"m": ""})),
        ("m array", dict(body={"m": ["PING;64"]})),
        ("cuerpo array JSON", dict(body=["PING;64"])),
        ("cuerpo string JSON", dict(body="PING;64")),
        ("campo extra en el cuerpo se ignora", dict(body={"m": "PING;64", "x": 1})),
        ("clave M en mayúscula no equivale a m", dict(body={"M": "PING;64"})),
        ("Content-Type text/plain con cuerpo JSON", dict(body=P, content_type="text/plain")),
        ("sin Content-Type con cuerpo JSON", dict(body=P, content_type=None)),
        ("sin token: ¿se valida auth antes que el cuerpo?", dict(raw="esto no es json", auth="ninguno")),
        ("POST /__reset sin token", dict(ruta="/__reset", auth="ninguno")),
    ]
    for hip, kw in pruebas:
        print(s.http(hip, **kw))


if __name__ == "__main__":
    main()
