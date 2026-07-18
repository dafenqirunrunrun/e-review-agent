# E-Review Agent AI Service

FastAPI service for structured review analysis, schema validation and optional local AI experiments.

## Capabilities

- Rule/mock review analysis for normal demos and tests.
- Structured JSON output with schema validation and repair helpers.
- Optional remote provider adapters configured only through environment variables.
- Optional local model and RAG experiments. Model weights, FAISS indexes and private images are intentionally kept outside this repository.

## Install

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8008
```

## Health Check

```bash
curl http://localhost:8008/api/v1/health
```

## Test

```bash
python -m pytest
```

## Configuration

Copy `.env.example` into a local environment file if needed. Do not commit populated `.env` files. API keys and model paths should be provided by environment variables on the target machine.
