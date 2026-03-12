# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a separate location for copying
COPY pyproject.toml .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir hatchling \
    && pip install --no-cache-dir -e ".[dev]" --target /app/deps

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /app/deps /usr/local/lib/python3.12/site-packages

# Copy application source
COPY src/ ./src/
COPY pyproject.toml .
COPY alembic.ini .
COPY alembic/ ./alembic/

# Install the package itself (not deps, already copied)
RUN pip install --no-cache-dir --no-deps -e .

# Non-root user for security
RUN addgroup --system mnemo && adduser --system --group mnemo
USER mnemo

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

CMD ["uvicorn", "mnemo.main:app", "--host", "0.0.0.0", "--port", "8000"]
