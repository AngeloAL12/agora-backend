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

## Sincronizar BD en equipo

Cuando alguien jala cambios del repositorio, debe aplicar las migraciones para tener el
mismo esquema de base de datos que el resto del equipo.

1. Jalar cambios:

```bash
git pull origin <tu-rama>
```

2. Instalar/sincronizar dependencias:

```bash
uv sync --group dev
```

3. Configurar variables en `.env`:

- `DATABASE_URL`
- `SECRET_KEY`

4. Aplicar migraciones:

```bash
uv run alembic upgrade head
```

> Si aparece error `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xf3`, forzar cliente UTF-8:
>
> - Windows (PowerShell): `setx PGCLIENTENCODING UTF8` y reiniciar terminal
> - En app (SQLAlchemy): `connect_args={"options": "-c client_encoding=UTF8"}`
>
> - PostgreSQL: `SHOW client_encoding; SHOW lc_messages;` -> ideal `UTF8`.

5. Verificar revision actual:

```bash
uv run alembic current
```

Debe mostrar la revision en `head`.

6. (Opcional) Verificar tablas creadas:

```bash
uv run python -c "from sqlalchemy import create_engine, inspect; from app.core.config import settings; e=create_engine(settings.DATABASE_URL); print(inspect(e).get_table_names())"
```
