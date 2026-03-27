# Plan for Extending the Mnemo API

## Context & Findings
- **Framework/Language:** FastAPI, Python 3.12, SQLAlchemy (asyncio), Pydantic v2.
- **Dependency:** `passlib[bcrypt]` is already in `pyproject.toml`, so we will use it for password hashing.
- **Database Migrations:** Managed by Alembic. There's a `tests` directory mimicking a standard async SQLAlchemy/FastAPI structure.
- **Auth Flow:** Currently API keys are exchanged for short-lived JWT tokens (`POST /v1/auth/token`). Tokens are cached with user properties (e.g. `scopes`).
- **User Management:** Defined in `src/mnemo/models/user.py`, created via `UserCreate` in `src/mnemo/schemas/user.py`, validated with strict timezone rules.
- **Endpoints:** We need to add multiple endpoints for self-registration, password login, and admin actions, preserving the existing error format (`ErrorCode`, `ErrorResponse`).

## 1. Database Schema & Models
- Modify `src/mnemo/models/user.py`:
  - Add `password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)`
  - Add `role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")`
  - Add `admin_access_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)`
  - Add `admin_access_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)`
- Generate Alembic migration:
  - We'll create an alembic revision file (e.g., `alembic/versions/xxxx_add_user_auth_fields.py`) that adds `password_hash`, `role`, `admin_access_granted`, and `admin_access_granted_at` to the `users` table.

## 2. Authentication & Hashing Service
- Create/modify password hashing utilities (e.g. in `src/mnemo/services/auth.py` or new `src/mnemo/services/password.py`):
  - Add `get_password_hash(password: str) -> str` using `passlib.context.CryptContext(schemes=["bcrypt"], deprecated="auto")`.
  - Add `verify_password(plain_password: str, hashed_password: str) -> bool`.

## 3. Schemas (`src/mnemo/schemas/`)
- **User Schemas (`user.py`):**
  - Update `UserCreate` schema (or create new ones) to optionally accept `password`.
  - Add a schema for Admin-provisioning user (`AdminUserCreate`), allowing an optional `role` field.
  - Create `UserListResponse` and `UserListItem` matching the spec for `/v1/admin/users`.
- **Auth Schemas (`auth.py`):**
  - Create `LoginRequest` containing `display_name` and `password`.

## 4. API Routes Implementation
- **Registration (`POST /v1/user/provision`)**:
  - Add to `src/mnemo/api/v1/routes/users.py` (or a dedicated router if preferred, but `users.py` or `auth.py` fit best). Let's use `users.py` for `/v1/user/provision` and `/v1/admin/provision`.
  - Endpoint logic: extract body, hash password (if present), create User, and implicitly create an API key (because response expects an API key). Wait, the spec says "match existing api_key format exactly". We'll call `create_api_key`.
- **Login (`POST /v1/auth/login`)**:
  - Add to `src/mnemo/api/v1/routes/auth.py`.
  - Lookup user by `display_name`. If found and password matches, generate JWT using `create_access_token`. Wait, the existing `POST /v1/auth/token` expects `user_id` and `scopes` derived from an API key. We need to fetch the user's primary API key scopes, or just assign default user scopes if they don't have a specific API key bound. I'll need to check how to assign scopes. The spec says "keep the response contract identical so the Flutter client can use either interchangeably."
- **Admin Endpoints (`src/mnemo/api/v1/routes/admin.py` or `users.py`)**:
  - Create a new router `admin.py` with prefix `/admin`.
  - `POST /v1/admin/provision` (provision user, allow `role="admin"` if caller is admin).
  - `GET /v1/admin/users` (list users with pagination and stats: `deck_count`, `has_granted_admin_access`).
  - `DELETE /v1/admin/users/{userId}` (cascade delete within transaction).
  - `GET /v1/admin/users/{userId}/decks` (check `admin_access_granted` flag, then call `deck_service.list_decks`).
- **User Consent (`POST/DELETE /v1/user/grant-admin-access`)**:
  - Add to `src/mnemo/api/v1/routes/users.py` or similar. Update `admin_access_granted` flag.

## 5. Security & Rate Limiting
- Use existing `Depends(require_user_scope(PermissionScope.ADMIN))` or custom logic to ensure Admin routes verify JWT role. Wait, the spec says "require valid JWT with role = 'admin'". We need to ensure the JWT contains the role, or we look it up from the User object. Actually, the existing JWT gets scopes. If we want `role="admin"`, we can check the User's `role` property in the DB during auth, or check `PermissionScope.ADMIN` if the admin role maps to that scope.
- Return 403 (Forbidden) for unauthorized admin access, 401 for bad login, 409 for conflicts.
- Passwords should never be returned or logged.

## 6. Testing
- Implement integration tests covering the required test cases in `tests/integration/test_auth_flow.py`, `tests/integration/test_admin_users.py`, etc.
- Run `pytest` to ensure nothing is broken and new tests pass.

## Actions to perform in Code mode:
1. Generate the alembic migration and update `models/user.py`.
2. Update `schemas/user.py` and `schemas/auth.py`.
3. Add password hashing utility (using `passlib`).
4. Modify `services/user.py` to support password insertion, role setting, and admin grants.
5. Create new endpoints in `routes/auth.py`, `routes/users.py`, and a new `routes/admin.py`.
6. Integrate `admin.py` into `v1/router.py`.
7. Write `tests/integration/test_registration_login.py` and `tests/integration/test_admin.py`.
8. Check test results and finalize.
