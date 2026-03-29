# Mnemo Learning API

Spaced repetition and active recall, delivered as a developer API.

**Version:** 1.0.0 · **Spec:** [API Specification v1.0](https://coming-soon)

[![CI](https://github.com/sinke237/mnemo-api/actions/workflows/ci.yml/badge.svg)](https://github.com/sinke237/mnemo-api/actions/workflows/ci.yml)

---

## Prerequisites

- Python 3.12+
- Docker Desktop (for Postgres + Redis)
- Git

## Quick Start (Recommended: Docker Compose)

Docker Compose runs Postgres, Redis, applies migrations, **seeds dummy data using the service layer**, and starts the API.

```bash
docker compose up --build
```

Seed data is created on startup via `scripts/seed_dummy_data.py`. The script uses the codebase services
to create **1 admin + 2 regular users**, decks, and cards, and writes the generated IDs and API keys to
`dev_docs/seed_data.md`.
If you run `docker compose down -v`, the Postgres volume is deleted and all seeded data is lost.
Bring the stack back up and re-run the seed step to regenerate keys:
```bash
docker compose up -d
docker compose exec api python -m scripts.seed_dummy_data --ensure-doc
```
Note: `--ensure-doc` does **not** overwrite `dev_docs/seed_data.md`. If the file already exists,
use the command without `--ensure-doc` (or delete the file first) to regenerate fresh IDs and keys:
```bash
docker compose exec api python -m scripts.seed_dummy_data
```

Verify the API:
```bash
curl http://localhost:8000/v1/health
# {"status":"ok","db":"ok","redis":"ok","version":"1.0.0"}
```

API docs: http://localhost:8000/docs

---

Notes on API keys
-----------------

When a user is provisioned the response includes `api_key` and `key_type`.
`key_type` will be `test` by default. Clients should display this clearly and
provide a separate flow for creating `live` keys (see `docs/api_keys.md`).

## Manual Run (each component separately)

Use this if you want to control each service or debug locally.

**1. Clone and enter the repo**
```bash
git clone https://github.com/sinke237/mnemo-api.git
cd mnemo-api
```

**2. Copy environment config**
```bash
cp .env.example .env
# The defaults work for local development — no changes needed to start
```

**3. Start Postgres**
```bash
docker compose up postgres -d
```

**4. Start Redis**
```bash
docker compose up redis -d
```

**5. Create virtual environment and install dependencies**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
pip install -e ".[dev]"
```

**6. Run database migrations**
```bash
alembic upgrade head
```

**7. Seed dummy data (via service layer)**
```bash
python -m scripts.seed_dummy_data
```
This creates 1 admin + 2 regular users and writes the generated IDs and API keys to
`dev_docs/seed_data.md`.

**8. Start the API**
```bash
uvicorn mnemo.main:app --reload
```

**9. Verify it's running**
```bash
curl http://localhost:8000/v1/health
# {"status":"ok","db":"ok","redis":"ok","version":"1.0.0"}
```

---

## Pre-Push / CI Pipeline Checks

To ensure your code passes the CI pipeline before pushing, make sure your virtual environment is activated and run the exact checks the pipeline runs:

```bash
# 1. Activate your virtual environment (if not already active)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Format code (auto-formats). Add --check for a dry-run/validation only.
black src/ tests/

# 3. Lint code (add --fix to auto-fix issues)
ruff check src/ tests/ alembic/versions/

# 4. Type check
mypy src/mnemo/

# 5. Run tests with coverage (fails if coverage is below 70%)
pytest tests/ -v

# 6. Check coverage (report only)
coverage report --show-missing
```

---

## Running Tests

```bash
# All tests with coverage
pytest

# A specific file
pytest tests/unit/test_health.py -v

# Skip coverage report
pytest --no-cov
```

## Linting & Formatting

```bash
# Lint
ruff check src/ tests/ alembic/versions/

# Format
black src/ tests/

# Type check
mypy src/mnemo/
```

## Database Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration (after changing a model)
alembic revision --autogenerate -m "description of change"

# Roll back one migration
alembic downgrade -1
```

---

## API Reference

Base URL: `https://api.mnemo.dev/v1`

See `/docs` (local) or the [API Specification](docs/spec.md) for full endpoint documentation.
