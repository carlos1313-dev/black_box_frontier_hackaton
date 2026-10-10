"""Único cliente del servicio original.

Cada request que sale de aquí queda como una línea en experimentos.jsonl.
No usar curl ni otros clientes contra el original: la spec cita estos ids.

Uso típico (desde frontier-reto-2/, en la rama develop):

    from tools.harness import Harness
    h = Harness()
    s = h.secuencia("orden-errores", "¿E202 se evalúa antes que E301?")
    s.msg("SALDOS;AC-0001", "control inválido en comando desconocido", control="corrupto")
"""

import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

from core.checksum import control as calcular_control

RAIZ = Path(__file__).resolve().parent.parent
LOG = RAIZ / "experimentos.jsonl"
ESTADO = RAIZ / ".state"
RAMA_PERMITIDA = "develop"
INTERVALO = 1 / 8  # máx. 8 req/s (el límite del token es 10)
CUPO_DIA = 8000
HEADERS_UTILES = ("content-type", "x-req", "x-powered-by", "server", "x-frontier-infra")


def _cargar_env() -> dict:
    env = {}
    for linea in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _rama_actual() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=RAIZ, capture_output=True, text=True, check=True,
    ).stdout.strip()


def _leer_log() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


class Respuesta:
    def __init__(self, linea: dict):
        self.linea = linea
        self.id = linea["id"]
        self.status = linea["status"]
        self.body = linea["response"]
        self.x_req = linea["x_req"]

    def __repr__(self):
        return f"#{self.id} {self.status} {json.dumps(self.body, ensure_ascii=False)} (X-Req={self.x_req})"


class Harness:
    def __init__(self, permitir_cualquier_rama: bool = False):
        rama = _rama_actual()
        if rama != RAMA_PERMITIDA and not permitir_cualquier_rama:
            raise SystemExit(
                f"El harness solo corre en '{RAMA_PERMITIDA}' (rama actual: '{rama}'). "
                "Los ids del log deben ser únicos y lineales."
            )
        env = _cargar_env()
        self.url = env["BLACKBOX_URL"].rstrip("/")
        self.token = env["BLACKBOX_TOKEN"]
        lineas = _leer_log()
        self._siguiente_id = max((l["id"] for l in lineas), default=0) + 1
        self._n_seq = len({l["seq"] for l in lineas})
        self._ultimo_envio = 0.0
        ESTADO.mkdir(exist_ok=True)
        self._cupo_path = ESTADO / f"cupo-{date.today().isoformat()}.json"

    # -- cupo y ritmo ---------------------------------------------------

    def _contar_request(self) -> int:
        usado = json.loads(self._cupo_path.read_text())["usado"] if self._cupo_path.exists() else 0
        usado += 1
        self._cupo_path.write_text(json.dumps({"usado": usado}))
        if usado == int(CUPO_DIA * 0.8):
            print(f"[harness] AVISO: 80 % del cupo diario usado ({usado}/{CUPO_DIA})")
        if usado >= CUPO_DIA:
            raise SystemExit("[harness] Cupo diario agotado")
        return usado

    def _esperar_turno(self):
        espera = self._ultimo_envio + INTERVALO - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        self._ultimo_envio = time.monotonic()

    # -- envío crudo ------------------------------------------------------

    def _enviar(self, metodo: str, ruta: str, cuerpo: bytes | None, headers: dict):
        """Devuelve (status, headers, texto) sin interpretar el cuerpo."""
        for intento in range(5):
            self._esperar_turno()
            self._contar_request()
            req = urllib.request.Request(self.url + ruta, data=cuerpo, method=metodo, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    status, hdrs, raw = r.status, r.headers, r.read()
            except urllib.error.HTTPError as e:
                status, hdrs, raw = e.code, e.headers, e.read()
            hdrs = {k.lower(): v for k, v in hdrs.items()}
            if hdrs.get("x-frontier-infra") == "rate-limit":
                print(f"[harness] rate-limit de infraestructura, reintento {intento + 1}")
                time.sleep(1.5 * (intento + 1))
                continue
            return status, hdrs, raw.decode("utf-8", errors="replace")
        raise SystemExit("[harness] rate-limit persistente, abortando")

    def _registrar(self, seq, hipotesis, metodo, ruta, auth, cuerpo_enviado, status, hdrs, texto, extra=None):
        try:
            response = json.loads(texto)
        except ValueError:
            response = texto  # cuerpo no JSON: se guarda el texto exacto
        x_req = hdrs.get("x-req")
        if x_req is not None and x_req.isdigit():
            x_req = int(x_req)
        linea = {
            "id": self._siguiente_id,
            "seq": seq,
            "x_req": x_req,
            "hipotesis": hipotesis,
            "request": cuerpo_enviado,
            "status": status,
            "response": response,
        }
        # Campos extra solo cuando el request no es el caso normal (POST /msg con token propio)
        if (metodo, ruta) != ("POST", "/msg"):
            linea["metodo"], linea["ruta"] = metodo, ruta
        if auth != "propio":
            linea["auth"] = auth
        linea["headers"] = {k: v for k, v in hdrs.items() if k in HEADERS_UTILES}
        linea["ts"] = datetime.now().isoformat(timespec="seconds")
        if extra:
            linea.update(extra)
        with LOG.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
        self._siguiente_id += 1
        return Respuesta(linea)

    def http(self, seq, hipotesis, metodo="POST", ruta="/msg", body=None, raw=None,
             auth="propio", content_type="application/json"):
        """Request arbitrario. `body` se serializa a JSON; `raw` se envía tal cual (str).
        auth: "propio" | "ninguno" | cualquier otro string = valor completo del header Authorization."""
        headers = {}
        if auth == "propio":
            headers["Authorization"] = f"Bearer {self.token}"
        elif auth != "ninguno":
            headers["Authorization"] = auth
        if raw is not None:
            datos, enviado = raw.encode("utf-8"), raw
        elif body is not None:
            datos, enviado = json.dumps(body, ensure_ascii=False).encode("utf-8"), body
        else:
            datos, enviado = None, None
        if datos is not None and content_type:
            headers["Content-Type"] = content_type
        status, hdrs, texto = self._enviar(metodo, ruta, datos, headers)
        auth_log = auth if auth in ("propio", "ninguno") else auth.replace(self.token, "<token-propio>")
        return self._registrar(seq, hipotesis, metodo, ruta, auth_log, enviado, status, hdrs, texto)

    # -- secuencias -------------------------------------------------------

    def secuencia(self, etiqueta: str, hipotesis: str) -> "Secuencia":
        """Abre una secuencia nueva: hace POST /__reset y lo registra como su primera línea."""
        self._n_seq += 1
        seq = f"s{self._n_seq:03d}-{etiqueta}"
        r = self.http(seq, f"reset · {hipotesis}", metodo="POST", ruta="/__reset")
        print(f"[harness] secuencia {seq}: reset → {r.status}")
        return Secuencia(self, seq)

    def concluir(self, id_: int, conclusion: str):
        """Agrega la conclusión a una línea ya registrada (no altera la evidencia)."""
        lineas = _leer_log()
        for l in lineas:
            if l["id"] == id_:
                l["conclusion"] = conclusion
        with LOG.open("w", encoding="utf-8", newline="\n") as f:
            f.writelines(json.dumps(l, ensure_ascii=False) + "\n" for l in lineas)


class Secuencia:
    def __init__(self, h: Harness, seq: str):
        self.h, self.seq = h, seq

    def msg(self, cuerpo: str, hipotesis: str, control="auto") -> Respuesta:
        """Envía {"m": "<cuerpo>;<control>"}.
        control: "auto" (calculado), "corrupto" (auto+1 mod 97), "ninguno" (sin campo de control)
        o un valor literal (int/str) que se pega tal cual."""
        if control == "auto":
            m = f"{cuerpo};{calcular_control(cuerpo)}"
        elif control == "corrupto":
            m = f"{cuerpo};{(calcular_control(cuerpo) + 1) % 97}"
        elif control == "ninguno":
            m = cuerpo
        else:
            m = f"{cuerpo};{control}"
        return self.m(m, hipotesis)

    def m(self, m, hipotesis: str) -> Respuesta:
        """Envía {"m": m} exactamente como se pasa (m puede no ser string)."""
        return self.h.http(self.seq, hipotesis, body={"m": m})

    def http(self, hipotesis: str, **kw) -> Respuesta:
        return self.h.http(self.seq, hipotesis, **kw)
