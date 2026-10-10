# Especificación del servicio «caja negra»

## 1. Entrada

El servicio expone tres rutas exactas. Todas exigen `Authorization: Bearer <token>`. Los cuerpos de respuesta son siempre JSON (`Content-Type: application/json; charset=utf-8`). El cuerpo de `POST /msg` admite hasta 8192 bytes.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| ENT-01 | Rutas conocidas: `POST /msg`, `POST /__reset`, `GET /health`. Cualquier otra combinación de método y ruta responde 404 `{"error":"E404","mensaje":"ruta desconocida"}` en JSON; no hay 405. | 31–35, 39 | confirmado |
| ENT-02 | Las rutas distinguen mayúsculas y no admiten barra final: `/MSG` y `/msg/` dan E404. | 37, 38 | confirmado |
| ENT-03 | Una ruta desconocida responde E404 aunque no haya token: la ruta se resuelve antes que la autenticación. | 36 | probable |
| ENT-04 | Las tres rutas exigen el header `Authorization` exactamente igual a `Bearer <token>`. Sin header, con token desconocido, sin prefijo, con prefijo vacío → 401 `{"error":"E001","mensaje":"no autorizado"}`. Incluye `GET /health` y `POST /__reset`. | 24–27, 30, 56 | confirmado |
| ENT-05 | El prefijo distingue mayúsculas: `bearer <token>` → E001. | 28 | probable |
| ENT-06 | Solo el token propio es válido: un token válido de otro contexto (el del equipo) → E001. | 29 | probable |
| ENT-07 | La autenticación se evalúa antes que el cuerpo: sin token y con cuerpo no JSON → E001. | 55 | probable |
| ENT-08 | `GET /health` con token → 200 `{"ok":true}`. | 23, 170 | confirmado |
| ENT-09 | `POST /__reset` con token → 200 `{"ok":true}` y reinicia el estado del token. | 1, 22, 57, 84 | confirmado |
| ENT-10 | El cuerpo se interpreta como JSON sin importar el `Content-Type` (text/plain o ausente). | 53, 54 | confirmado |
| ENT-11 | Cuerpo no parseable como JSON (texto, JSON truncado, vacío o ausente) → 400 `{"error":"E100","mensaje":"json inválido"}`. | 40–43 | confirmado |
| ENT-12 | El parser es JSON estricto: `NaN` y un BOM UTF-8 inicial → E100. | 248, 251 | probable |
| ENT-13 | Se aceptan espacios al final del JSON; con la clave `m` duplicada gana la última. | 249, 250 | probable |
| ENT-14 | Cuerpo JSON que no es objeto, sin clave `m`, o con `m` no string (número, null, array) → 400 `{"error":"E102","mensaje":"falta m"}`. La clave distingue mayúsculas (`M` → E102). | 44–46, 48–50, 52 | confirmado |
| ENT-15 | Los campos extra del cuerpo se ignoran. | 51 | probable |
| ENT-16 | Un `m` de 3000 caracteres se acepta; el único límite de tamaño observado es el del cuerpo (ENT-20). | 83 | probable |
| ENT-17 | El query string se ignora: `POST /msg?x=1` y `GET /health?x=1` responden como sin él. | 918, 919 | confirmado |
| ENT-18 | `POST /health`, `HEAD /health`, `OPTIONS /msg`, `DELETE /msg`, `/health/` y `//msg` → E404. HEAD responde 404 sin cuerpo. | 920–925 | confirmado |
| ENT-19 | El valor de `Authorization` se recorta: un espacio final se acepta, pero `Bearer` seguido de dos espacios → E001. | 926, 927 | probable |
| ENT-20 | Límite de tamaño: un cuerpo de más de 8192 bytes → 413 `{"error":"E101","mensaje":"cuerpo demasiado grande"}`; 8192 exactos se aceptan. Mide el cuerpo entero (un campo extra de relleno también cuenta), no solo `m`. | 931–933, 974, 975, 977 | confirmado |
| ENT-21 | E101 se evalúa después de la ruta y la autenticación y antes del parseo JSON: cuerpo grande sin token → E001; en ruta inexistente → E404; no JSON → E101. | 978–980 | probable |
| ENT-22 | El límite se mide en bytes UTF-8 y solo se aplica a `POST /msg`; un cuerpo que no es UTF-8 válido → E100. | — | supuesto |

## 2. Integridad

Un mensaje es el string `m` con la forma `COMANDO;arg1;…;argN;control`. Se divide por `;`; el último segmento es el dígito de control.

**Algoritmo del control** (variante de ISO 7064 MOD 97-10):

1. Tomar el mensaje sin el último segmento (`;control`).
2. Pasar a mayúsculas y quedarse solo con letras A–Z y dígitos 0–9 ASCII (se descartan `;`, `-`, espacios y caracteres no ASCII).
3. Reemplazar cada letra por su posición (A=1 … Z=26); los dígitos quedan igual; concatenar y añadir `00`.
4. `control = 98 − (N mod 97)`, entero en el rango 2..98.

Ejemplo: `PING` → `16 9 14 7` + `00` = `16914700`; `16914700 mod 97 = 34`; `98 − 34 = 64` → `PING;64`.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| INT-01 | `m` sin ningún `;` (incluido el string vacío) → 400 `{"error":"E103","mensaje":"falta control"}`. | 47, 58 | confirmado |
| INT-02 | Si algún segmento es vacío (`PING;`, `;64`, `PING;;64`) → 400 `{"error":"E104","mensaje":"segmento vacío"}`. | 59, 60, 75 | confirmado |
| INT-03 | El control se calcula con el algoritmo descrito arriba; reproduce todos los mensajes aceptados del log. | 2–21, 76–78 | confirmado |
| INT-04 | El control esperado está en 2..98, sin módulo final: resto 1 exige 97 y resto 0 exige 98; 0 y 1 son rechazados. | 79–82 | confirmado |
| INT-05 | El cálculo ignora mayúsculas/minúsculas y todo lo que no sea letra o dígito ASCII (`;`, `-`, espacio, `í`). | 12, 76–78 | confirmado |
| INT-06 | El control debe ser de 1 o 2 dígitos ASCII. Letras, signo, espacio, decimal o 3+ dígitos → 400 `{"error":"E201","mensaje":"control mal formado"}`. | 18, 69, 71, 227–230 | confirmado |
| INT-07 | El control se compara como texto: `03` no equivale a `3` → E202. | 226 | probable |
| INT-08 | Control bien formado pero distinto del esperado → 400 `{"error":"E202","mensaje":"control inválido"}`. | 3, 68, 70, 79, 81, 231 | confirmado |
| INT-09 | El control se valida antes que el comando y la aridad: comando desconocido o aridad inválida con control malo → E201/E202. | 68–71 | confirmado |
| INT-10 | PING no valida el control: acepta cualquier segmento no vacío (`XX`, `064`, `+64`, ` 64`, `64.0`, `-33`, `161`). Sí aplica E103, E104 y la aridad. | 59, 61–67, 72 | confirmado |
| INT-11 | HALT sí valida el control como el resto de comandos. | 231 | probable |
| INT-12 | Espacio o salto de línea después del control → E201: el control no se recorta. | 928, 929 | confirmado |

## 3. Comandos

El nombre del comando no distingue mayúsculas. Los ids de cuenta (`AC-%04d`) y de operación (`OP-%04d`) se comparan de forma exacta. Un monto válido es un entero `^[1-9][0-9]*$` no mayor que 9999999999.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| CMD-01 | El nombre del comando no distingue mayúsculas (`CONSULTa`, `ping`). | 12, 73 | confirmado |
| CMD-02 | Comandos existentes: PING, ALTA, CONSULTA, DEPOSITO, TRANSFER, ANULA y el oculto HALT. Un barrido de ~60 verbos bancarios no encontró otros. | 85, 87–100, 102–134, 136–150, 152, 165 | probable |
| CMD-03 | Aridad (argumentos sin contar el control): PING 0, ALTA 1, CONSULTA 1, DEPOSITO 2, TRANSFER 3, ANULA 1, HALT 1. Con menos o más argumentos → 400 `{"error":"E302","mensaje":"aridad inválida"}`. HALT con 2 o más argumentos no se probó (riesgo de confirmarlo); el reemplazo responde E302. | 21, 72, 139–143, 165, 166, 951–956 | confirmado |
| CMD-04 | `PING` → 200 `{"pong":true}`. | 2, 51, 73 | confirmado |
| CMD-05 | `ALTA;nombre` → 201 `{"cuentaId":"AC-0001"}`; ids secuenciales `AC-%04d` desde AC-0001 y saldo inicial 0. | 4–6 | confirmado |
| CMD-06 | ALTA acepta nombres con espacios, guiones, caracteres no ASCII, numéricos, de un solo espacio, muy largos y repetidos (cada ALTA crea una cuenta nueva). | 76–78, 83, 223, 959, 960 | confirmado |
| CMD-07 | `CONSULTA;cuenta` → 200 `{"cuenta_id":"AC-0001","saldo":0}` (la clave es `cuenta_id`, no `cuentaId`). | 6, 9, 12, 20 | confirmado |
| CMD-08 | Cuenta inexistente en CONSULTA, DEPOSITO o TRANSFER → 404 `{"error":"E401","mensaje":"cuenta inexistente"}`. La comparación es exacta: `ac-0001`, `AC-1` y `OP-0001` dan E401. | 16, 190–192, 201, 202, 224 | confirmado |
| CMD-09 | `DEPOSITO;cuenta;monto` → 200 `{"status":"recieved","operacionId":"OP-0001"}` ("recieved" con la errata) y suma el monto. No tiene el límite de TRANSFER. | 7, 19, 20, 174 | confirmado |
| CMD-10 | Monto válido solo si es `^[1-9][0-9]*$` y ≤ 9999999999. Cero, negativo, decimal, con signo, con ceros a la izquierda, notación científica, no numérico o ≥ 10000000000 → 400 `{"error":"E303","mensaje":"monto inválido"}`. Aplica a DEPOSITO y TRANSFER. | 182–189, 205, 206, 235, 298, 302 | confirmado |
| CMD-11 | `TRANSFER;origen;destino;monto` → 200 `{"status":"recieved","operacionId":"OP-…"}`; resta al origen y suma al destino. | 8, 9, 11, 12 | confirmado |
| CMD-12 | TRANSFER con origen igual al destino → 400 `{"error":"E304","mensaje":"origen y destino iguales"}`, aunque la cuenta no exista. | 200, 243 | confirmado |
| CMD-13 | Límite por operación: TRANSFER con monto > 100000 → 422 `{"error":"E506","mensaje":"límite excedido"}`; 100000 exacto pasa y el acumulado no cuenta. | 10, 175–177 | confirmado |
| CMD-14 | TRANSFER con saldo del origen menor que el monto → 422 `{"error":"E507","mensaje":"saldo insuficiente"}`. | 17, 203 | confirmado |
| CMD-15 | `ANULA;OP-xxxx` → 200 `{"ok":true,"anulada":"OP-xxxx"}` y revierte la operación: una TRANSFER devuelve el monto al origen y lo quita al destino; un DEPOSITO resta su monto. | 14, 17, 20, 215, 217, 218 | confirmado |
| CMD-16 | ANULA de una operación ya anulada → 200 `{"ok":false,"motivo":"ya anulada"}` (no es un error HTTP). | 15 | probable |
| CMD-17 | ANULA no verifica saldos: puede dejar una cuenta en negativo. | 215, 216 | probable |
| CMD-18 | ANULA de una operación inexistente o mal escrita (`OP-0099`, `AC-0001`, `op-0003`) → 404 `{"error":"E402","mensaje":"operación inexistente"}`. | 219–221 | confirmado |
| CMD-19 | `HALT;<argumento>` → 409 `{"error":"E520","mensaje":"operación destructiva: detiene el servicio; reenvía con confirmación"}` y no cambia nada: el servicio, el estado y las escrituras siguen funcionando. | 166–169 | probable |
| CMD-20 | La forma de confirmar HALT no se probó a propósito (podría detener un servicio compartido). El reemplazo responde E520 a cualquier argumento. | — | supuesto |
| CMD-21 | Los argumentos no se recortan: ` AC-0001` → E401 y ` 100` → E303. | 957, 958 | probable |

## 4. Memoria entre requests

Cada token tiene su propio estado. `POST /__reset` lo devuelve al inicial.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| MEM-01 | Tras `/__reset` los contadores vuelven al inicio: la primera ALTA de cada secuencia es AC-0001 y la primera operación OP-0001. | 4, 7, 76, 163, 164, 172, 174, 181, 195, 197, 199, 210, 212 | confirmado |
| MEM-02 | Cuentas y operaciones tienen contadores separados; DEPOSITO y TRANSFER comparten el contador de operaciones. | 4, 5, 7, 8, 11, 19 | confirmado |
| MEM-03 | Las operaciones fallidas no consumen id ni alteran saldos. | 3, 4, 10, 11, 194, 195, 207 | confirmado |
| MEM-04 | ANULA no consume id de operación. | 222 | probable |
| MEM-05 | El servicio recuerda qué operaciones están anuladas (segunda ANULA → `ok:false`) y conserva saldos negativos. | 15, 216 | probable |
| MEM-06 | El límite de TRANSFER no guarda memoria: dos TRANSFER de 100000 seguidas pasan. | 175, 176 | probable |
| MEM-07 | Header `X-Req` (los headers no se comparan): contador por token que sube en 1 por cada `POST /msg` autenticado, incluso con error de cuerpo, y que `/__reset` no reinicia. No aparece en 401, 404, `/health` ni `/__reset`. | 1–21, 23, 25, 34, 40 | confirmado |
| MEM-08 | No hay detección de duplicados ni bloqueo por fallos: el mismo DEPOSITO o TRANSFER repetido crea otra operación, y tras 5 E202 seguidos la cuenta sigue operable. | 938, 940, 947, 948 | confirmado |

## 5. Errores

Todos los errores tienen cuerpo `{"error": <código>, "mensaje": <texto>}`; E301 puede añadir `sugerencia`.

| Código | Status | Mensaje exacto |
|---|---|---|
| E001 | 401 | `no autorizado` |
| E404 | 404 | `ruta desconocida` |
| E100 | 400 | `json inválido` |
| E101 | 413 | `cuerpo demasiado grande` |
| E102 | 400 | `falta m` |
| E103 | 400 | `falta control` |
| E104 | 400 | `segmento vacío` |
| E201 | 400 | `control mal formado` |
| E202 | 400 | `control inválido` |
| E301 | 400 | `comando desconocido ` (con espacio final) |
| E302 | 400 | `aridad inválida` |
| E303 | 400 | `monto inválido` |
| E304 | 400 | `origen y destino iguales` |
| E401 | 404 | `cuenta inexistente` |
| E402 | 404 | `operación inexistente` |
| E506 | 422 | `límite excedido` |
| E507 | 422 | `saldo insuficiente` |
| E520 | 409 | `operación destructiva: detiene el servicio; reenvía con confirmación` |

**Orden de evaluación** (gana el primero que falla): ruta (E404) → autenticación (E001) → tamaño del cuerpo (E101) → JSON (E100) → `m` (E102) → `;` presente (E103) → segmentos no vacíos (E104) → formato del control (E201) → valor del control (E202) → comando (E301) → aridad (E302) → monto (E303) → origen ≠ destino (E304) → existencia (E401/E402) → límite (E506) → saldo (E507). PING omite E201 y E202.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| ERR-01 | E301 trae `sugerencia` cuando el comando (en mayúsculas, sin recortar espacios) está a distancia de Levenshtein ≤ 2 de un comando real; gana la menor distancia. A distancia 3 o más no hay clave `sugerencia`. | 13, 74, 100, 121, 144, 152–154, 156, 159, 160, 232 | confirmado |
| ERR-02 | Empate de distancia en la sugerencia: gana ALTA sobre HALT. | 157, 158 | confirmado |
| ERR-03 | Para empates no observados, el reemplazo desempata en el orden PING, ALTA, CONSULTA, DEPOSITO, TRANSFER, ANULA, HALT. | — | supuesto |
| ERR-04 | El mensaje de E301 lleva un espacio final: `comando desconocido `. | 13, 74 | confirmado |
| ERR-05 | El monto se valida antes que la existencia de las cuentas. | 193, 244 | confirmado |
| ERR-06 | En TRANSFER, E303 antes que E304 y E304 antes que E401. | 242, 243 | probable |
| ERR-07 | La existencia de cuentas (E401) se evalúa antes que el límite (E506), y el límite antes que el saldo (E507). | 204, 245, 246 | confirmado |

## 6. Cambios durante el día

El canario (`tools/canary.py`) repite una suite fija contra el original y la compara con el clon. Cada corrida queda en `canario.jsonl` y sus requests en el log.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| CAM-01 | A las 12:55 la secuencia de `pruebas/ejemplos.jsonl` (grabada en la mañana) se reprodujo sin diferencias. | 2–21 | confirmado |

## 7. Riesgos

Comportamientos que un cliente nuevo no debería heredar, con la forma de cerrarlos.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| RSK-01 | HALT es una operación destructiva disponible para cualquier token y protegida solo por un argumento de confirmación; además la sugerencia de E301 la revela (`HELP` → `HALT`). Cerrar: sacarla del protocolo público o exigir un rol de administración con confirmación fuera de banda. | 100, 133, 166 | confirmado |
| RSK-02 | El dígito de control es un checksum público, no una firma: detecta errores de tipeo pero no autentica ni impide manipular mensajes. Cerrar: firmar mensajes (HMAC por cliente) si se necesita integridad. | 80, 82 | confirmado |
| RSK-03 | PING acepta cualquier control: la validación de integridad es inconsistente entre comandos. Cerrar: aplicar la misma validación a todos. | 61, 66, 67 | confirmado |
| RSK-04 | ANULA no tiene autorización ni verificación de saldo: cualquiera puede anular cualquier operación y dejar saldos negativos. Cerrar: verificar saldo y restringir quién anula. | 215–218 | confirmado |
| RSK-05 | Ids secuenciales y predecibles (`AC-0001`, `OP-0001`) y respuestas distintas para existente/inexistente permiten enumerar cuentas y operaciones. Cerrar: ids opacos y aleatorios. | 4, 5, 16, 219 | confirmado |
| RSK-06 | El límite es solo por operación: se evade fraccionando el monto (dos TRANSFER de 100000 seguidas). Cerrar: límite acumulado por periodo. | 175, 176 | confirmado |
| RSK-07 | Contrato inconsistente: errata `recieved`, `cuentaId` frente a `cuenta_id`, espacio final en `comando desconocido `, y ANULA repetida devuelve 200. Un cliente nuevo no debe depender de esto. Cerrar: una versión nueva del contrato que lo corrija, manteniendo la actual para clientes existentes. | 4, 6, 7, 13, 15 | confirmado |
