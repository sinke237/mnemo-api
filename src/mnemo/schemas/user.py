"""
User profile schemas.
Request/response models for unified user creation.
"""

from datetime import datetime
from typing import cast

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator, model_validator

from mnemo.core.constants import EducationLevel
from mnemo.utils.local_time import to_local_time


def _validate_password_complexity(password: str) -> str:
    """
    Ensure password contains at least one uppercase, one lowercase, and one digit.
    Raises ValueError with the same message previously used by the inline validator.
    """
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_upper and has_lower and has_digit):
        raise ValueError(
            "Password must contain at least one uppercase letter, "
            "one lowercase letter, and one digit"
        )
    return password


# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED USER PROVISIONING
# ══════════════════════════════════════════════════════════════════════════════


class UserProvisionRequest(BaseModel):
    """
    UNIFIED user provisioning request.
    Used by both:
    - POST /v1/user/provision (public self-registration)
    - POST /v1/admin/provision (admin creates users)
    """

    email: EmailStr = Field(
        ...,
        description="Email address (must be unique, used for login and password reset)",
        examples=["enow.sinke@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Password (min 8 chars, max 72 for bcrypt compatibility)",
    )

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)

    display_name: str | None = Field(
        None,
        max_length=100,
        description="Display name (optional, must be unique if provided)",
    )
    country: str = Field(
        ...,
        description="ISO 3166-1 alpha-2 country code",
        pattern=r"^[A-Za-z]{2}$",
        examples=["CM", "US", "GB"],
    )
    timezone: str | None = Field(
        None,
        description="IANA timezone. Required for multi-timezone countries; inferred otherwise.",
        examples=["Africa/Douala", "America/New_York"],
    )

    # Admin-only fields (ignored in public endpoint)
    role: str | None = Field(
        None,
        description=(
            "User role (admin-only). Defaults to 'user'. " "Set to 'admin' for admin accounts."
        ),
        examples=["user", "admin"],
    )
    create_live_key: bool = Field(
        default=False,
        description="Create a live API key instead of test key (admin-only, default: false)",
    )

    @field_validator("country")
    @classmethod
    def validate_country_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ("user", "admin"):
            raise ValueError("role must be 'user' or 'admin'")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "enow.sinke@example.com",
                "password": "securePass123",
                "display_name": "Enow Sinke",
                "country": "CM",
                "role": "user",
                "create_live_key": False,
            }
        }
    }


class ProvisionResponse(BaseModel):
    """Response for successful user provisioning."""

    user_id: str = Field(..., description="Newly created user ID")
    email: str = Field(..., description="User email address")
    api_key: str = Field(
        ...,
        description="Plain API key — shown ONCE, store it immediately",
    )
    key_type: str = Field(
        ...,
        description="API key type: 'test' or 'live'",
        examples=["test", "live"],
    )
    display_name: str | None = Field(None, description="Display name (if provided)")
    role: str = Field(..., description="User role ('user' or 'admin')")
    email_verified: bool = Field(
        default=False,
        description="Email verification status (false until verified)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "usr_a1b2c3d4e5f6g7h8",
                "email": "enow.sinke@example.com",
                "api_key": "mnm_test_examplekey",
                "key_type": "test",
                "display_name": "Enow Sinke",
                "role": "user",
                "email_verified": False,
            }
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# PASSWORD MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════


class ChangePasswordRequest(BaseModel):
    """Request to change password."""

    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="New password (min 8 chars)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "current_password": "oldPass123",
                "new_password": "newSecurePass456",
            }
        }
    }

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)

    @model_validator(mode="after")
    def validate_new_not_current(self) -> "ChangePasswordRequest":
        # Ensure the new password is different from the current password
        if self.new_password == self.current_password:
            raise ValueError("new_password must differ from current_password")
        return self


class ChangePasswordResponse(BaseModel):
    """Response after successful password change."""

    message: str = "Password changed successfully"


class RequestPasswordResetRequest(BaseModel):
    """Request password reset email."""

    email: EmailStr = Field(..., description="Email address associated with the account")

    model_config = {"json_schema_extra": {"example": {"email": "enow.sinke@example.com"}}}


class RequestPasswordResetResponse(BaseModel):
    """Response for password reset request (always 200 to prevent email enumeration)."""

    message: str = "If an account exists with this email, a password reset link will be sent"


class ResetPasswordRequest(BaseModel):
    """Reset password with token from email."""

    token: str = Field(..., description="Password reset token from email")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="New password (min 8 chars)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "token": "reset_a1b2c3d4e5f6g7h8",
                "new_password": "newSecurePass456",
            }
        }
    }

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class ResetPasswordResponse(BaseModel):
    """Response after successful password reset."""

    message: str = "Password reset successfully"


# ══════════════════════════════════════════════════════════════════════════════
# API KEY MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════


class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key."""

    name: str | None = Field(None, max_length=100, description="Optional key name/description")
    is_live: bool = Field(
        default=False,
        description="Create live key (true) or test key (false, default)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Production API Key",
                "is_live": True,
            }
        }
    }


class CreateAPIKeyResponse(BaseModel):
    """Response with new API key (shown once)."""

    key_id: str = Field(..., description="API key ID")
    api_key: str = Field(..., description="Plain API key — shown ONCE, store immediately")
    key_type: str = Field(..., description="'test' or 'live'")
    name: str | None = Field(None, description="Key name/description")
    scopes: list[str] = Field(..., description="Permission scopes")
    created_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "key_id": "key_a1b2c3d4e5f6g7h8",
                "api_key": "mnm_live_abcdef1234567890abcdef1234567890abcdef12345678",
                "key_type": "live",
                "name": "Production API Key",
                "scopes": ["decks:read", "decks:write", "sessions:run"],
                "created_at": "2026-03-29T12:00:00Z",
            }
        }
    }


class APIKeyListItem(BaseModel):
    """Single API key in list (without showing the key)."""

    key_id: str
    name: str | None
    key_type: str  # "test" or "live"
    key_hint: str  # Last 4 chars
    scopes: list[str]
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class ListAPIKeysResponse(BaseModel):
    """List of user's API keys."""

    keys: list[APIKeyListItem]


class RevokeAPIKeyResponse(BaseModel):
    """Response after revoking an API key."""

    message: str = "API key revoked successfully"
    key_id: str
    revoked_at: datetime


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════


class UserListItem(BaseModel):
    """Single user entry in the admin user list."""

    user_id: str
    email: str
    display_name: str | None
    country: str
    role: str
    email_verified: bool
    created_at: datetime
    deck_count: int
    has_granted_admin_access: bool

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated response for GET /v1/admin/users."""

    users: list[UserListItem]
    total: int
    page: int
    per_page: int


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ACCESS CONSENT
# ══════════════════════════════════════════════════════════════════════════════


class GrantAdminAccessResponse(BaseModel):
    """Response for granting/revoking admin access to user's decks."""

    admin_access_granted: bool
    granted_at: datetime | None = None


class GrantAdminAccessRequest(BaseModel):
    """Request to grant/revoke admin access for a resource.

    If `resource` is omitted or null, this request uses legacy/global behavior
    and applies to the user's global `admin_access_granted` flag (i.e. applies to
    all resource types). If `resource` is provided, the consent applies to that
    resource type; `resource_id` may be provided to limit consent to a specific
    resource instance.

    Semantics enforced:
    - `resource` may be null to indicate legacy/global behavior; when null,
        `resource_id` must also be null.
    - `resource` when present must be a non-empty string.
    """

    resource: str | None = Field(
        None, description="Resource type to grant access for, e.g. 'decks'"
    )
    resource_id: str | None = Field(
        None, description="Optional specific resource id (null means all of the type)"
    )
    expires_at: datetime | None = Field(None, description="Optional expiry for this consent")

    model_config = {"json_schema_extra": {"example": {"resource": "decks", "resource_id": None}}}

    @model_validator(mode="after")
    def validate_resource_and_id(self) -> "GrantAdminAccessRequest":
        # If resource is omitted (legacy/global behavior), resource_id must be omitted too
        if self.resource is None and self.resource_id is not None:
            raise ValueError("resource_id must be null when resource is omitted (global consent)")
        # If resource is provided, it must be a non-empty string
        if self.resource is not None and not str(self.resource).strip():
            raise ValueError("resource must be a non-empty string when provided")
        return self


# ══════════════════════════════════════════════════════════════════════════════
# USER PROFILE (GET/PATCH)
# ══════════════════════════════════════════════════════════════════════════════


class UserUpdate(BaseModel):
    """Request body for PATCH /v1/users/{id} (update user profile)."""

    display_name: str | None = Field(None, max_length=100)
    locale: str | None = Field(None, pattern=r"^[a-z]{2}-[A-Z]{2}$")
    timezone: str | None = Field(
        None, description="IANA timezone (only for multi-timezone countries)"
    )
    education_level: EducationLevel | None = None
    preferred_language: str | None = Field(None, pattern=r"^[a-z]{2}$")
    daily_goal_cards: int | None = Field(None, ge=1, le=200)

    model_config = {
        "json_schema_extra": {
            "example": {
                "display_name": "Enow S.",
                "daily_goal_cards": 30,
            }
        }
    }


class UserResponse(BaseModel):
    """Response for user profile (GET /v1/users/{id})."""

    id: str = Field(..., description="User ID (usr_xxxxxxxx)")
    email: str = Field(..., description="Email address")
    email_verified: bool = Field(..., description="Email verification status")
    display_name: str | None = Field(None, description="Display name")
    country: str = Field(..., description="ISO 3166-1 alpha-2 country code")
    locale: str | None = Field(None, description="BCP 47 locale tag")
    timezone: str = Field(..., description="IANA timezone (derived from country)")
    education_level: EducationLevel | None = Field(None, description="Education level")
    preferred_language: str = Field(..., description="BCP 47 language tag")
    daily_goal_cards: int = Field(..., description="Daily card review goal")
    role: str = Field(..., description="User role")
    created_at: datetime = Field(..., description="Account creation timestamp (UTC)")

    @computed_field(return_type=str)
    def local_time(self) -> str:
        """Account creation time in the user's local timezone."""
        local_time_value: str = to_local_time(self.created_at, self.timezone)
        return local_time_value

    @computed_field(return_type=str)
    def created_at_local(self) -> str:
        """Compatibility alias for `local_time`.

        Historically the API exposed `created_at_local`; keep this companion
        computed field as an explicit alias for `local_time` so legacy clients
        depending on the older field name continue to work.
        """
        return cast(str, self.local_time)

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "usr_a1b2c3d4e5f6g7h8",
                "email": "enow.sinke@example.com",
                "email_verified": True,
                "display_name": "Enow Sinke",
                "country": "CM",
                "locale": "fr-CM",
                "timezone": "Africa/Douala",
                "education_level": "undergraduate",
                "preferred_language": "fr",
                "daily_goal_cards": 25,
                "role": "user",
                "created_at": "2026-03-10T08:30:00Z",
                "local_time": "2026-03-10T09:30:00+01:00",
                "created_at_local": "2026-03-10T09:30:00+01:00",
            }
        },
        "from_attributes": True,
    }
