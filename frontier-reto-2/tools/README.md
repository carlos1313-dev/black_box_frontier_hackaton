# Herramientas

- `harness.py` — único cliente del original. Solo corre en la rama `develop`; escribe `experimentos.jsonl`.
- Experimentos: un script por lote en `experiments/`, ejecutado desde `frontier-reto-2/`:
  `python3 -m experiments.e01_ejemplos`
- Configuración: copiar `.env.example` a `.env` (nunca se versiona).
