# Mnemo Learning API

Spaced repetition and active recall, delivered as a developer API.

**Version:** 1.0.0 · **Author:** Enow Sinke · **Spec:** [API Specification v1.0](docs/spec.md)

[![CI](https://github.com/sinke237/mnemo-api/actions/workflows/ci.yml/badge.svg)](https://github.com/sinke237/mnemo-api/actions/workflows/ci.yml)

---

## Prerequisites

- Python 3.12+
- Docker Desktop (for Postgres + Redis)
- Git

## Local Setup (under 5 minutes)

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

**3. Start Postgres and Redis**
```bash
docker compose up postgres redis -d
```

**4. Install Python dependencies**
```bash
pip install -e ".[dev]"
```

**5. Run database migrations**
```bash
alembic upgrade head
```

**6. Start the API**
```bash
uvicorn mnemo.main:app --reload
```

**7. Verify it's running**
```bash
curl http://localhost:8000/v1/health
# {"status":"ok","db":"ok","redis":"ok","version":"1.0.0"}
```

API docs: http://localhost:8000/docs

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
ruff check src/ tests/

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

## Project Structure

```
mnemo-api/
├── src/mnemo/
│   ├── api/v1/
│   │   ├── routes/        # Endpoint handlers (one file per resource)
│   │   └── router.py      # Aggregates all v1 routes
│   ├── core/
│   │   └── config.py      # Settings loaded from environment
│   ├── db/
│   │   ├── database.py    # SQLAlchemy async engine + session
│   │   └── redis.py       # Redis connection
│   ├── models/            # SQLAlchemy ORM models (added per phase)
│   ├── schemas/           # Pydantic request/response schemas
│   ├── services/          # Business logic (no FastAPI dependencies)
│   ├── workers/           # Background job handlers (CSV import, etc.)
│   └── main.py            # FastAPI app, middleware, lifecycle
├── tests/
│   ├── unit/              # Fast tests, no external dependencies
│   └── integration/       # Tests that require DB + Redis
├── alembic/               # Database migrations
├── scripts/               # Utility scripts
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## Build Phases

| Phase | What Ships | Status |
|-------|-----------|--------|
| 0 | Repo, infrastructure, health check | ✅ Complete |
| 1 | Authentication (API keys + JWT) | 🔜 Next |
| 2 | User profiles + timezone resolution | ⏳ Planned |
| 3 | Decks & Flashcards CRUD | ⏳ Planned |
| 4 | CSV Import (async) | ⏳ Planned |
| 5 | Spaced Repetition (SM-2) | ⏳ Planned |
| 6 | Study Sessions | ⏳ Planned |
| 7 | Progress & Analytics | ⏳ Planned |
| 8 | Learning Plan Generator | ⏳ Planned |
| 9 | Rate Limiting & Hardening | ⏳ Planned |

---

## API Reference

Base URL: `https://api.mnemo.dev/v1`

See `/docs` (local) or the [API Specification](docs/spec.md) for full endpoint documentation.
