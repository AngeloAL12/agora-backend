# Agora Backend

Backend sencillo con FastAPI para el proyecto Agora.

## Requisitos

- Python 3.11 o superior

## Instalacion

Sincroniza dependencias (incluyendo desarrollo):

```bash
uv sync --group dev
```

## Ejecutar la API

```bash
uv run uvicorn app.main:app --reload
```

La API quedara disponible en `http://127.0.0.1:8000`.

## Endpoints de ejemplo

- `GET /`
- `GET /test`

## Pruebas

```bash
uv run pytest
```
