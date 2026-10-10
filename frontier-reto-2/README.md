# Caja negra · reemplazo, especificación y log

Reemplazo del servicio «caja negra» (Reto 2 del hackathon Frontier): responde con el mismo status y
el mismo cuerpo que el original, errores incluidos, en su **versión 2** (la vigente desde el incidente
de las 16:00). El enunciado del reto está en [`docs/ENUNCIADO.md`](docs/ENUNCIADO.md).

| Entregable | Archivo |
|---|---|
| Especificación (7 secciones, cada comportamiento con su evidencia y confianza) | [`SPEC.md`](SPEC.md) |
| Log de experimentos (una línea por request al original) | [`experimentos.jsonl`](experimentos.jsonl) |
| Reemplazo | `core/` + `server/`, desplegado en Render ([`render.yaml`](render.yaml)) |

Requisitos: **Python 3.10 o superior**. Sin dependencias externas (solo biblioteca estándar).
Todos los comandos se corren desde esta carpeta (`frontier-reto-2/`).

## 1. Levantar el reemplazo

```bash
TEAM_TOKEN=mi-token PORT=8000 python3 -m server.app
```

Probarlo (el control de `PING` es 64; ver «Integridad» en la spec):

```bash
curl -s -X POST localhost:8000/__reset -H 'Authorization: Bearer mi-token'                  # {"ok": true}
curl -s -X POST localhost:8000/msg -H 'Authorization: Bearer mi-token' -d '{"m":"PING;64"}'  # {"pong": true}
curl -s -X POST localhost:8000/msg -H 'Authorization: Bearer mi-token' -d '{"m":"ALTA;Ana;50"}'  # 201 {"cuentaId": "AC-0001"}
curl -s localhost:8000/health                                                                # 401: /health también exige token
```

Para calcular el control de cualquier mensaje:

```bash
python3 -c "from core.checksum import firmar; print(firmar('CONSULTA;AC-0001'))"   # CONSULTA;AC-0001;14
```

## 2. Verificar

```bash
python3 -m unittest discover -s tests     # tests unitarios, del servidor HTTP y de las herramientas
python3 -m tools.replay                   # reproduce TODO el log contra el núcleo: debe dar 100 %
python3 -m tools.replay pruebas/ejemplos.jsonl
python3 -m tools.spec_build --check       # valida la spec contra el log
```

- `tools.replay` pasa cada secuencia del log por el núcleo y compara status y cuerpo con lo que
  respondió el original. Es la prueba de regresión: un cambio que rompa algo ya observado aparece aquí.
- `tools.spec_build --check` exige que cada id citado en la spec exista en el log, que el núcleo lo
  reproduzca, y que solo los comportamientos `supuesto` vayan sin evidencia.
- `pruebas/ejemplos.jsonl` se grabó con la v1: el replay la corre en modo v1 (ver §4).

Contra un reemplazo desplegado (necesita `TEAM_TOKEN` en `.env`; nunca toca el original):

```bash
python3 -m tools.remote_replay https://mi-reemplazo.onrender.com --solo-v2
```

`--solo-v2` manda solo las secuencias grabadas después del incidente; sin la opción, las de la
mañana difieren a propósito (límite de TRANSFER y formato del saldo).

## 3. Cómo está hecho

```
core/          núcleo puro: responder(método, ruta, auth, cuerpo) -> (status, cuerpo)
  http.py        rutas, autenticación, límite de 8192 bytes, JSON, estado detenido (E599)
  checksum.py    dígito de control (variante de ISO 7064 MOD 97-10)
  parser.py      separa el mensaje y aplica el orden de validación (E103…E302)
  commands.py    PING, ALTA, CONSULTA, DEPOSITO, TRANSFER, ANULA, HALT
  state.py       estado por token: cuentas, operaciones, contadores, versión, detenido
  errors.py      catálogo exacto de errores (código -> status y mensaje)
server/app.py  adaptador HTTP (biblioteca estándar, un proceso, estado en memoria)
tools/         harness, reproductores, fuzzer, canario, revalidación y generador de la spec
experiments/   un script por lote de hipótesis (e01…e16), siempre a través del harness
tests/         tests del núcleo, del servidor y de las herramientas
behaviors.json registro de comportamientos del que se genera SPEC.md
canario.jsonl  una línea por corrida del canario (así se fechó el incidente)
docs/          enunciado, diseño y arquitectura
```

Los comentarios del código citan entre paréntesis los ids de `experimentos.jsonl` que prueban cada
regla, por ejemplo `# 50001 -> E506 (1463)`.

## 4. Versiones del original

A las 16:00 el original pasó a la versión 2 (sección 6 de la spec): el límite de TRANSFER bajó de
100000 a 50000 y `saldo` pasó de entero a string con 2 decimales; además `HALT;1` detiene el
servicio (503 E599) hasta `/__reset`. El núcleo tiene `State.version`: el servidor usa la **v2**; la
v1 solo existe para que el replay reproduzca el log de la mañana (`tools/replay.py`, `CORTE_V2`).

## 5. Explorar el original (solo durante el reto)

```bash
cp .env.example .env      # completar BLACKBOX_URL, BLACKBOX_TOKEN y TEAM_TOKEN; .env no se versiona
git switch develop        # el harness solo corre en develop: los ids del log deben ser lineales
python3 -m experiments.e01_ejemplos
python3 -m tools.fuzz --secuencias 20 --semilla 7     # fuzzer diferencial (--dry-run: sin red)
python3 -m tools.canary                               # suite fija: detecta cambios de versión
python3 -m tools.revalidar                            # reenvía el log viejo y lista lo que cambió
```

Reglas que el código hace cumplir:
- Todo request al original pasa por `tools/harness.py`, que lo registra en `experimentos.jsonl` con su
  hipótesis, censura los tokens (el repo es público), limita a 8 req/s y lleva el cupo diario.
- El reemplazo nunca llama al original: el servidor no conoce su URL ni su token.
- El fuzzer y el canario nunca envían `HALT` con argumento (salvo `--con-e520`, que manda `HALT;x`).

## 6. Despliegue

Render, desde la rama `main` (auto-deploy): `rootDir: frontier-reto-2`, arranque
`python3 -m server.app`, variable `TEAM_TOKEN` definida en el panel. Un solo proceso, porque el estado
vive en memoria. Ramas: `feature/*` y `fix/*` salen de `develop`; cada release se fusiona a `main` con
un tag (`v0.1` … `v0.6`).
