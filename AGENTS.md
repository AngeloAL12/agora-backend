# AGENTS.md

## Fast start (trusted commands)
- Install deps: `uv sync --group dev`
- Run API: `uv run uvicorn app.main:app --reload`
- Apply migrations: `uv run alembic upgrade head`
- Create migration: `uv run alembic revision --autogenerate -m "message"`

## Verification order used by CI
- Lint first: `uv run ruff check .`
- Format check second: `uv run ruff format --check .`
- Tests last (CI gate): `uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80`

## Test execution shortcuts
- Full suite: `uv run pytest`
- Single file: `uv run pytest tests/app/routers/test_complaints.py`
- Single test: `uv run pytest tests/app/routers/test_complaints.py::test_create_complaint_no_images`

## Environment gotchas (important)
- `app.core.config.settings` is instantiated at import time and requires these vars: `DATABASE_URL`, `SECRET_KEY`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_PRIVATE`, `R2_BUCKET_PUBLIC`.
- CI provides those vars in `.github/workflows/ci.yml`; local runs need a populated `.env` (or exported env vars) before importing app modules.
- Tests default DB to SQLite in-memory when `DATABASE_URL` is unset in `tests/conftest.py`, but config validation still needs the required R2 vars.

## Architecture map (only non-obvious bits)
- App entrypoint: `app/main.py`.
- Router aggregation is explicit in `app/main.py` via `app.include_router(...)`.
- Active router modules are flat files: `app/routers/auth/`, `app/routers/clubs.py`, `app/routers/complaints.py`, `app/routers/health.py`.
- `app/routers/clubs/` and `app/routers/complaints/` directories currently only contain `__pycache__` (do not treat them as route package entrypoints).

## Migrations and model registration
- Alembic metadata comes from `app.core.database.Base` and imports all models through `import app.models` in `alembic/env.py`.
- New model modules must be re-exported in `app/models/__init__.py`; otherwise autogenerate can miss tables.
- Both runtime DB engine (`app/core/database.py`) and Alembic online migrations force PostgreSQL client encoding UTF-8 via `connect_args`.

## Git hooks / workflow constraints
- Pre-commit hooks run `ruff` + `ruff-format` on commit.
- Commit messages are enforced by `conventional-pre-commit` (`commit-msg` hook), so use conventional commit style.
- Pre-push hook runs `uv run pytest` (full suite).
