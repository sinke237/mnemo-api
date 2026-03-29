# Task Plan for Mnemo API Extension

1.  **Add Database Changes**
    *   Update `src/mnemo/models/user.py` to add `password_hash`, `role`, `admin_access_granted`, and `admin_access_granted_at`.
    *   Generate and create a new Alembic migration script for these fields. Note: We must also update `tests/unit/test_user_service_exceptions.py` or existing tests if they create users manually, but the `create_user` schema shouldn't break existing tests since `password` and `role` will be optional.

2.  **Add Password Hashing Utility**
    *   Create `src/mnemo/utils/password.py` utilizing `passlib[bcrypt]` to hash and verify passwords.

3.  **Update Schemas**
    *   Update `src/mnemo/schemas/user.py`:
        *   Add `password` to `UserCreate` (optional).
        *   Add `role` to `UserCreate` (optional, default `"user"`).
        *   Create `UserListItem` matching the response spec for `/v1/admin/users`.
        *   Create `UserListResponse` matching the paginated response spec.
        *   Add `admin_access_granted` and `deck_count` (optional) to `UserListItem`.
        *   Add `has_granted_admin_access` to `UserListItem` (alias for `admin_access_granted`).
        *   Update `UserResponse` to include new fields optionally if necessary (but follow spec).
    *   Update `src/mnemo/schemas/auth.py`:
        *   Add `LoginRequest` with `display_name` and `password`.

4.  **Implement New Services & Update Existing Ones**
    *   Update `src/mnemo/services/user.py`:
        *   Modify `create_user` to accept and hash `password`, set `role`. Check for `display_name` uniqueness to return 409 if conflict.
        *   Add logic to list users with pagination (`list_users` for admin).
        *   Add logic to check `display_name` uniqueness.
        *   Update `delete_user` to ensure cascade is working. Wait, cascade delete is on DB models (SQLAlchemy), just verify relationships.
    *   Add login logic in `src/mnemo/services/auth.py`:
        *   `authenticate_user(display_name, password)` returning User or None.

5.  **Implement API Endpoints**
    *   **User Registration**: Add `POST /v1/user/provision` in `src/mnemo/api/v1/routes/users.py`.
        *   Extract body, check uniqueness.
        *   Create user, create API key.
        *   Return `user_id`, `api_key`, `display_name`, `role`.
    *   **Password Login**: Add `POST /v1/auth/login` in `src/mnemo/api/v1/routes/auth.py`.
        *   Validate credentials -> 401 if wrong.
        *   Return JWT token response matching `POST /v1/auth/token`. Provide user's API key scopes (or default scopes + admin scope if role is "admin") to the JWT.
    *   **Admin Endpoints**: Create `src/mnemo/api/v1/routes/admin.py` and register it in `router.py`.
        *   `POST /v1/admin/provision`: Requires admin JWT. Accepts `role` field.
        *   `GET /v1/admin/users`: Lists users.
        *   `DELETE /v1/admin/users/{userId}`: Deletes user.
        *   `GET /v1/admin/users/{userId}/decks`: Admin access to decks, gated by `admin_access_granted`.
    *   **User Consent**: Add `POST/DELETE /v1/user/grant-admin-access` in `src/mnemo/api/v1/routes/users.py`.
        *   Toggles `admin_access_granted` for the authenticated user.

6.  **Write Tests**
    *   Add tests in `tests/integration/test_auth_flow.py` for `/v1/auth/login`.
    *   Create `tests/integration/test_registration.py` for `/v1/user/provision`.
    *   Create `tests/integration/test_admin.py` for admin endpoints.

7.  **Final Summary**
    *   Ensure all spec requirements are strictly met, including error response formatting and idempotency.

Does this plan look good? Should I switch to Code mode to execute these steps?