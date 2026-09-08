# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Most operational guidance (commands, env gotchas, architecture map, git hooks) is in **AGENTS.md** — read that first.

## Project overview

FastAPI REST backend for Agora, a campus community platform. Core domains: auth (JWT + Google/Microsoft OAuth2), clubs, complaints (with image uploads to Cloudflare R2), and campus map.

## Tech stack

- **Framework**: FastAPI + Uvicorn
- **ORM**: SQLAlchemy 2.0 (async-compatible sessions)
- **DB**: PostgreSQL in prod, SQLite in-memory for tests
- **Migrations**: Alembic (metadata from `app.core.database.Base`)
- **Validation**: Pydantic v2
- **Storage**: Aioboto3 → Cloudflare R2 (two buckets: private + public)
- **Tooling**: UV (package manager), Ruff (lint + format)

## Layer conventions

```
routers/ → schemas/ → services/ → models/ → database
```

- Routers handle HTTP, delegate business logic to services.
- Schemas (Pydantic) define request/response contracts separate from ORM models.
- Database dependency injected via `Depends(get_db)` — override in tests via `apply_override` fixture in `tests/conftest.py`.

## Test fixtures

Key fixtures in `tests/conftest.py`:

- `db` — test DB session (SQLite in-memory)
- `clean_db` — truncates all tables between tests
- `user_role` — pre-created role for test users
- `apply_override` — swaps `get_db` with test session

## Adding new models

Re-export new model modules in `app/models/__init__.py`; otherwise Alembic autogenerate misses the table.
