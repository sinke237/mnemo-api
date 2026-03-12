-- Mnemo API — initial database setup
-- This runs once when the Docker Postgres container is first initialised.
-- Actual schema is managed by Alembic migrations.

-- Enable UUID extension (used for idempotency keys)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for future full-text search on card content
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Confirm setup
SELECT 'Database initialised successfully' AS status;
