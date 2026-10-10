# Herramientas

- `harness.py` — único cliente del original. Solo corre en la rama `develop`; escribe `experimentos.jsonl`.
- Experimentos: un script por lote en `experiments/`, ejecutado desde `frontier-reto-2/`:
  `python3 -m experiments.e01_ejemplos`
- Configuración: copiar `.env.example` a `.env` (nunca se versiona).
- Reproductor offline sobre todo el log: `python3 -m tools.replay [ruta_log]`
  (por defecto `experimentos.jsonl`; también `pruebas/ejemplos.jsonl`). Exit code 1 si hay diferencias.

## Servidor

Un solo proceso (el estado vive en memoria). Desde `frontier-reto-2/`:

```
TEAM_TOKEN=<token> uvicorn server.app:app --host 0.0.0.0 --port $PORT --workers 1
```

También descrito en `render.yaml`; dependencias en `requirements.txt`. `GET /health` exige
`Authorization: Bearer <TEAM_TOKEN>` igual que el original, así que un health check de la plataforma sin
cabecera recibirá 401.
