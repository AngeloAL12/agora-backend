# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync --group dev

# Run development server
uv run uvicorn app.main:app --reload

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/app/models/test_auth.py

# Run a single test
uv run pytest tests/app/models/test_auth.py::test_create_user

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Auto-fix lint issues
uv run ruff check . --fix

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Architecture

FastAPI backend for an authentication and role-management system. Early-stage project with models and infrastructure in place, routers/schemas/services directories ready for feature development.

**Stack:** FastAPI, SQLAlchemy 2.0 (ORM), PostgreSQL (prod) / SQLite (tests), Alembic (migrations), Pydantic Settings, Python-JOSE (JWT), Passlib/bcrypt.

**Structure:**
- `app/main.py` — FastAPI app, current endpoints (`/`, `/test`, `/health/db`)
- `app/core/config.py` — Pydantic `BaseSettings`; requires `DATABASE_URL` and `SECRET_KEY` in `.env`
- `app/core/database.py` — SQLAlchemy engine, `SessionLocal`, `Base`, `get_db()` dependency
- `app/models/auth/` — ORM models: `User`, `Role`, `UserSession`, `StaffWhitelist`
- `app/routers/`, `app/schemas/`, `app/services/` — empty, ready for expansion
- `alembic/` — migrations; `env.py` auto-discovers `app/models`
- `tests/conftest.py` — pytest fixtures; uses SQLite in-memory DB for all tests

**Key patterns:**
- DB sessions injected via `Depends(get_db)` in route handlers
- SQLAlchemy 2.0 style: `Mapped[type]` and `mapped_column()` in all models
- `server_default=func.now()` for `created_at`; `onupdate=func.now()` for `updated_at`
- Tests create/drop tables per-session; use `db` fixture for DB-dependent tests

## Environment

Copy `.env.example` to `.env` and set:
- `DATABASE_URL` — PostgreSQL connection string (Neon or local)
- `SECRET_KEY` — JWT signing key
- `ALGORITHM` — defaults to `HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES` — defaults to `30`

## Code Quality

Pre-commit hooks enforce ruff lint/format on commit and pytest (80% coverage minimum) on push. Conventional commit messages are required. Coverage threshold is enforced in CI (`.github/workflows/ci.yml`).
