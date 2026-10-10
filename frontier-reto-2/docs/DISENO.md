# Diseño · Réplica de la Caja Negra

Complementa a `ARQUITECTURA.md`: aquí se detalla **cómo** se construye cada componente.
Convención: lo marcado como **hipótesis** aún no está probado contra el original; nada de eso entra a la spec sin evidencia.

## 1. Estructura del repositorio

```
frontier-reto-2/
├── core/                  # lógica del servicio, sin dependencias HTTP
│   ├── checksum.py        # cálculo y validación del control MOD 97
│   ├── parser.py          # split del mensaje, aridad, tipos de argumentos
│   ├── commands.py        # PING, ALTA, CONSULTA, DEPOSITO, TRANSFER, ANULA, …
│   ├── state.py           # estado por token y reset
│   └── errors.py          # catálogo de errores: código, status, texto exacto
├── server/app.py          # adaptador HTTP (Starlette/FastAPI modo crudo)
├── tools/
│   ├── harness.py         # único cliente del original; escribe experimentos.jsonl
│   ├── replay.py          # reproductor: log → core → diff → % conformidad
│   ├── fuzz.py            # fuzzer diferencial
│   ├── canary.py          # suite fija periódica
│   └── spec_build.py      # validador + generador de SPEC.md
├── hipotesis.yaml         # backlog de hipótesis
├── behaviors.yaml         # registro de comportamientos (fuente de la spec)
├── experimentos.jsonl     # entregable
├── SPEC.md                # entregable (generado)
├── .env                   # BLACKBOX_URL, BLACKBOX_TOKEN, TEAM_TOKEN (no se versiona)
└── pruebas/ejemplos.jsonl
```

## 2. Núcleo (`core/`)

### 2.1 Interfaz

```python
def handle(state: State, m: str) -> tuple[int, dict | str]:
    """Procesa el contenido del campo m y devuelve (status, cuerpo)."""
```

El adaptador HTTP resuelve todo lo previo a `m` (ruta, método, auth, JSON); el núcleo no conoce HTTP.
El reproductor y el fuzzer llaman a `handle` directamente.

### 2.2 Modelo de estado (por token)

| Campo | Tipo | Observado en |
|---|---|---|
| `cuentas` | `id → {nombre, saldo}` | ejemplos 3–5, 8 |
| `operaciones` | `id → {tipo, origen, destino, monto, anulada}` | ejemplos 6, 7, 10, 13, 14 |
| `siguiente_cuenta` | entero, formato `AC-%04d` | ejemplos 3, 4 |
| `siguiente_operacion` | entero, formato `OP-%04d` | ejemplos 6, 7, 10, 18 |
| `acumulado_transfer` | entero (**hipótesis**: si el límite es acumulado) | ejemplos 9, 10 |

Abiertas: si un request fallido consume número de ID; qué pasa después de `9999`; si `X-Req` es un contador por token.

### 2.3 Formato del mensaje

`COMANDO;arg1;…;argN;control`. El último campo es siempre el control; se separa con el último `;`.

### 2.4 Dígito de control

Verificado contra los 20 ejemplos (20/20):

```python
def control(cuerpo: str) -> int:
    # cuerpo = mensaje sin ";control"
    digitos = "".join(
        c if c.isdigit() else str(ord(c) - 64)   # A=1 … Z=26
        for c in cuerpo.upper() if c.isalnum()   # se descartan ; y -
    )
    return (98 - int(digitos + "00") % 97) % 97
```

Ejemplo: `PING` → `16 9 14 7` + `00` = `16914700`; `16914700 mod 97 = 34`; `98 − 34 = 64` → `PING;64`.

Por confirmar: resto 0 o 1 (¿el control esperado es 97/98 o 0/1?); ceros a la izquierda (`07` vs `7`); acentos y `ñ` (`isalnum` los acepta en Python); espacios; signos en montos.

### 2.5 Orden de validación

El primer paso que falla define la respuesta.

| # | Paso | Error | Estado |
|---|---|---|---|
| 1 | Autenticación Bearer | ? | hipótesis |
| 2 | Ruta y método | ? (cuerpo exacto de 404) | hipótesis |
| 3 | Cuerpo JSON con campo `m` string | ? | hipótesis |
| 4 | Formato del control (numérico) | 400 `E201` "control mal formado" | visto (ej. 17) |
| 5 | Valor del control | 400 `E202` "control inválido" | visto (ej. 2) |
| 6 | Comando conocido (no distingue mayúsculas) | 400 `E301` "comando desconocido " | visto (ej. 11, 12) |
| 7 | Aridad | 400 `E302` "aridad inválida" | visto (ej. 20) |
| 8 | Tipos y rangos de argumentos | ? | hipótesis |
| 9 | Existencia de cuenta/operación | 404 `E401` "cuenta inexistente" | visto (ej. 15) |
| 10 | Reglas de negocio | 422 `E506` "límite excedido", 422 `E507` "saldo insuficiente" | visto (ej. 9, 16) |

El orden entre 5, 6 y 7 **no está fijado**: en los ejemplos de E301 y E302 el control era válido. Es el primer bloque de experimentos.

### 2.6 Comandos conocidos

| Comando | Argumentos | Efecto | Respuesta OK | Evidencia (ejemplos) |
|---|---|---|---|---|
| `PING` | — | ninguno | 200 `{"pong":true}` | 1 |
| `ALTA` | nombre | crea cuenta con saldo 0 | 201 `{"cuentaId":"AC-0001"}` | 3, 4, 5 |
| `CONSULTA` | cuenta | ninguno | 200 `{"cuenta_id":"AC-0001","saldo":0}` | 5, 8, 11, 19 |
| `DEPOSITO` | cuenta; monto | suma al saldo | 200 `{"status":"recieved","operacionId":"OP-0001"}` | 6, 18, 19 |
| `TRANSFER` | origen; destino; monto | mueve saldo | 200 `{"status":"recieved","operacionId":"OP-0002"}` | 7, 8, 10, 11 |
| `ANULA` | operación | revierte la operación | 200 `{"ok":true,"anulada":"OP-0003"}`; repetida: 200 `{"ok":false,"motivo":"ya anulada"}` | 13, 14, 16, 19 |

Detalles a respetar: `"recieved"` con el error ortográfico, `cuentaId` vs `cuenta_id`, espacio final en `"comando desconocido "`.

Abiertos: comandos no descubiertos (barrido de diccionario); límite de TRANSFER por operación o acumulado (100 000 pasa, 120 000 no); montos 0, negativos, decimales; transferencia a la misma cuenta; ANULA de depósitos, de operaciones inexistentes, o cuando el destino ya gastó el saldo.

## 3. Adaptador HTTP (`server/app.py`)

- Starlette/FastAPI **en modo crudo**: rutas que reciben `Request`, leen el cuerpo como bytes y construyen la respuesta a mano. Se evita la validación automática (sus 422 no coinciden con el original).
- Ruta comodín para cualquier método y ruta no reconocidos, que devuelve el cuerpo exacto del original (texto o JSON, carácter por carácter).
- Auth: solo `Bearer <TEAM_TOKEN>` es válido; cualquier otro caso replica la respuesta del original sin token o con token inválido.
- `POST /__reset` reinicia el estado; `GET /health` → 200.
- Estado en memoria por token, en un único proceso (`uvicorn --workers 1`).
- Pendiente de medir en el original: qué responde a métodos distintos, cuerpos no JSON, `Content-Type` ausente y cuerpos muy grandes.

## 4. Harness (`tools/harness.py`)

- Lee `BLACKBOX_URL` y `BLACKBOX_TOKEN` desde `.env`.
- API: `secuencia(seq, hipotesis)` hace `POST /__reset` y abre una secuencia; `enviar(cuerpo, hipotesis, control="auto" | "corrupto" | valor)`.
- Cada request escribe una línea en `experimentos.jsonl` con `id` incremental, `seq`, `x_req` (header `X-Req`), `hipotesis`, `request`, `status`, `response` (JSON o texto crudo) y `conclusion` (opcional, se completa después).
- Limitador: máximo 8 req/s. Si aparece el header `X-Frontier-Infra: rate-limit`, la respuesta se marca como de infraestructura y se reintenta; no se usa como evidencia.
- Contador de cupo diario con alerta al 80 %.
- Primer uso: reproducir la secuencia de `pruebas/ejemplos.jsonl` como `seq` propia. Sirve como evidencia citable y detecta si el servicio ya cambió desde la mañana.

## 5. Verificación

- **Reproductor:** agrupa el log por `seq`, ejecuta cada secuencia sobre un estado nuevo en `core/` y compara status y cuerpo con la regla del evaluador (JSON por valor, texto exacto). Salida: % de conformidad y lista de diferencias. Es el gate de deploy.
- **Fuzzer:** genera secuencias de 1 a 12 pasos (como el set de evaluación) mezclando mensajes válidos y mutaciones (control corrupto, aridad, mayúsculas, montos límite). Las envía vía harness y compara contra `core/`. Cada divergencia se convierte en hipótesis.
- **Canario:** suite fija de unas 30 requests cada 45 min; si cambia algo, registra la hora y los ids en la bitácora.
- **Spec:** `behaviors.yaml` con entradas `{id, seccion, comportamiento, evidencia: [ids], confianza}`. `spec_build.py` falla si un id citado no existe o si `core/` no reproduce esa línea, y genera `SPEC.md` con las 7 secciones del README.

## 6. Plan de experimentos inicial

| Bloque | Pregunta | Ejemplo de prueba |
|---|---|---|
| Entrada | Respuesta sin token, con token inválido, con otro esquema | `POST /msg` sin `Authorization` |
| Entrada | Rutas inexistentes y otros métodos | `GET /msg`, `GET /x`, `POST /x` |
| Entrada | Cuerpo inválido | no JSON, sin `m`, `m` numérico, `m` vacío, `m` muy largo |
| Integridad | Orden E202 vs E301/E302 | comando desconocido con control inválido |
| Integridad | Bordes del control | `07` vs `7`, resto 0/1, acentos, espacios |
| Comandos | Comandos ocultos | barrido de verbos bancarios con control válido |
| Comandos | Validación de argumentos | montos 0, negativos, decimales, cuenta en minúsculas |
| Memoria | Límite de TRANSFER | ¿acumulado? ¿ANULA libera límite? |
| Memoria | IDs | ¿un fallo consume número? ¿`X-Req` cuenta requests? |

## 7. Modelos y agentes

| Trabajo | Modelo | Motivo |
|---|---|---|
| Hipótesis, ambigüedades, redacción y auditoría de la spec | Opus | Una afirmación falsa resta puntos |
| Harness, núcleo, servidor, fuzzer, deploy | Sonnet | Código bien especificado |
| Barrido de diccionario, formateo de logs, resumen de diffs | Haiku | Volumen alto, riesgo bajo |

Regla: **un token, un solo agente contra el original**. Los agentes paralelos se usan para trabajo offline (núcleo, deploy, validador de spec).

Cupo diario (8 000): exploración ~3 000 · fuzzing ~2 000 · canario ~300 · reserva para cambios de la tarde ~2 700.

## 8. Riesgos del proyecto

| Riesgo | Mitigación |
|---|---|
| El servicio cambia cerca de las 20:00 | Canario hasta el final y reserva de cupo; congelar a las 19:30 con margen para un ajuste |
| Arranque en frío de Render | Plan Starter (no se duerme); `/health` monitoreado |
| Afirmaciones falsas en la spec | Validador obligatorio; confianza "probable" o "supuesto" cuando no hay repetición |
| Agotar el cupo | Contador en el harness; fuzzing dirigido en vez de aleatorio puro |
| Respuestas no JSON mal copiadas | Guardar el cuerpo crudo en el log y devolverlo tal cual |

## 9. Plan hasta las 20:00

| Hora | Hito |
|---|---|
| 11:55 | Presentación de la arquitectura |
| 12:00–13:00 | Harness, núcleo base y reproductor; los 20 ejemplos pasan en local |
| 13:00–13:30 | Primer deploy en Render y validación del entrypoint |
| 13:30–16:00 | Exploración por secciones; el canario corre desde aquí |
| 16:00–18:00 | Fuzzing diferencial y cierre de divergencias |
| 18:00–19:30 | Spec final y revisión de cambios del día |
| 19:30–20:00 | Congelar y entregar |
