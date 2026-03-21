# US0002: Python Project Scaffold

> **Status:** Ready
> **Epic:** [EP0001](../epics/EP0001-foundation-scanner-inventory.md)
> **Created:** 2026-03-21
> **Approach:** TDD

## User Story

**As a** developer
**I want** a fully configured Python project skeleton with FastAPI, uv, ruff, mypy, pytest, and pre-commit
**So that** every subsequent story has a consistent, typed, linted, tested foundation to build on

## Context

### Background
Establishes the Python package structure under `netsentry/`, the `pyproject.toml` with all tooling configuration, Alembic initialised (no migrations yet — that's US0003), and the FastAPI application factory pattern. Pre-commit hooks enforce quality gates on every commit. All tooling must pass with zero errors on an empty project before any application code is written.

---

## Inherited Constraints

| Source | Type | Constraint | AC Implication |
|--------|------|------------|----------------|
| TRD | Stack | FastAPI 0.115+, Pydantic v2, aiosqlite 0.20+, APScheduler 3.x | All pinned in `pyproject.toml` with minimum versions |
| TRD | Dev tooling | uv, ruff, mypy, pytest-asyncio, pre-commit | All configured in `pyproject.toml` / `.pre-commit-config.yaml` |
| TRD ADR-001 | Architecture | Modular monolith; package structure mirrors functional modules | `netsentry/scanner/`, `netsentry/db/`, `netsentry/api/`, `netsentry/core/` |

---

## Acceptance Criteria

### AC1: Project installs cleanly
- **Given** a fresh virtual environment with `uv` installed
- **When** `uv pip install -e ".[dev]"` is run from the project root
- **Then** all dependencies install without errors and `python -c "import netsentry"` succeeds

### AC2: FastAPI application factory works
- **Given** the project is installed
- **When** `uvicorn netsentry.api.main:create_app --factory` is run
- **Then** the server starts, OpenAPI docs are available at `/docs`, and `GET /api/v1/system/health` returns 200

### AC3: ruff passes with zero violations
- **Given** the project scaffold code
- **When** `ruff check .` and `ruff format --check .` are run
- **Then** both exit with code 0 and zero violations/formatting issues

### AC4: mypy passes with zero errors
- **Given** the project scaffold code with strict mypy config
- **When** `mypy netsentry/` is run
- **Then** exit code 0, zero errors (strict mode: `disallow_untyped_defs = true`, `strict = true`)

### AC5: pytest runs successfully
- **Given** the test suite scaffold with at least one passing test per module
- **When** `pytest` is run
- **Then** all tests pass; coverage report generated; no warnings about missing fixtures

### AC6: pre-commit hooks pass on clean commit
- **Given** pre-commit installed and hooks configured
- **When** `pre-commit run --all-files` is run
- **Then** all hooks pass: ruff check, ruff format, mypy, trailing whitespace, end-of-file-fixer

### AC7: Alembic initialised
- **Given** the project is installed
- **When** `alembic current` is run
- **Then** output shows `<no current revision>` (Alembic configured but no migrations yet)

---

## Scope

### In Scope
- `pyproject.toml`: project metadata, dependencies (fastapi, pydantic≥2, uvicorn, aiosqlite, apscheduler, httpx, paramiko, python-nmap, scapy, apprise, anthropic), dev deps (pytest, pytest-asyncio, pytest-cov, ruff, mypy, pre-commit, httpx test client)
- Package structure: `netsentry/__init__.py`, `netsentry/api/`, `netsentry/core/`, `netsentry/db/`, `netsentry/scanner/`, `netsentry/integrations/`, `netsentry/notifications/`, `netsentry/events/`, `netsentry/identification/`, `netsentry/monitor/`, `netsentry/speedtest/`
- `netsentry/core/config.py`: Pydantic Settings class loading all env vars with defaults
- `netsentry/api/main.py`: FastAPI application factory, lifespan context manager (placeholder), CORS middleware, `/api/v1/system/health` endpoint
- `netsentry/api/v1/router.py`: APIRouter scaffold
- `alembic.ini` + `alembic/env.py`
- `.pre-commit-config.yaml`
- `pytest.ini` or `[tool.pytest.ini_options]` in `pyproject.toml`
- `tests/` directory with `conftest.py` and one test per module package

### Out of Scope
- Alembic migrations (US0003)
- Database connection setup (US0003)
- APScheduler lifecycle (US0007)
- Any scanner or integration code

---

## Technical Notes

### Application factory pattern
```python
# netsentry/api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: init DB, start scheduler (populated by later stories)
    yield
    # shutdown: stop scheduler, close DB

def create_app() -> FastAPI:
    app = FastAPI(title="NetSentry", lifespan=lifespan)
    app.include_router(v1_router, prefix="/api/v1")
    return app
```

### Config pattern (Pydantic Settings)
```python
# netsentry/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_path: str = "/data/netsentry.db"
    log_level: str = "INFO"
    scan_interval_arp: int = 300
    # ... all env vars from PRD §9
    
    class Config:
        env_file = ".env"
```

### mypy config (strict)
```toml
[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]
```

---

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| Missing required env var with no default | Pydantic Settings raises `ValidationError` at startup with clear field name |
| Invalid env var type (e.g., `SCAN_INTERVAL_ARP=abc`) | `ValidationError` with type error message |
| Import of optional `anthropic` package when not installed | Guarded import; `ImportError` caught; AI identification silently disabled |
| `uvicorn` port already in use | OS error propagated; process exits with non-zero |
| `alembic current` run before DB exists | Alembic creates the DB file; reports no current revision |
| mypy run on code with missing type annotation | Fails with `error: Function is missing a type annotation` |

---

## Test Scenarios (TDD)

- [ ] `test_health_endpoint_shape` — response body has `status` and `version` keys
- [ ] `test_settings_loads_defaults` — Settings() instantiates with all defaults
- [ ] `test_settings_overrides_from_env` — env var overrides default value
- [ ] `test_settings_invalid_type_raises` — invalid type raises ValidationError
- [ ] `test_openapi_docs_available` — `/docs` returns 200
- [ ] `test_app_factory_returns_fastapi_instance` — create_app() returns FastAPI
- [ ] `test_cors_header_present` — response includes CORS headers
- [ ] `test_package_imports_all_modules` — all `netsentry.*` subpackages importable

---

## Dependencies

### Story Dependencies
| Story | Type | What's Needed | Status |
|-------|------|---------------|--------|
| US0001 | Predecessor | Docker container to run the app in | Ready |

---

## Estimation
**Story Points:** 3
**Complexity:** Low — boilerplate configuration; no business logic

---

## Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-03-21 | sdlc-studio | Initial draft |
