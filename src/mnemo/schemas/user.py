"""
User profile schemas.
Request/response models per spec section 11: User Profiles.
"""

from datetime import datetime
from typing import cast

from pydantic import BaseModel, Field, computed_field, field_validator

from mnemo.core.constants import DEFAULT_DAILY_GOAL_CARDS, EducationLevel
from mnemo.utils.local_time import to_local_time

# ── Self-service / admin provision schemas ────────────────────────────────────


class UserProvisionRequest(BaseModel):
    """Request body for POST /v1/user/provision (public self-registration)."""

    display_name: str | None = Field(
        None, max_length=100, description="Display name (must be unique if provided)"
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
    password: str | None = Field(
        None,
        min_length=8,
        max_length=72,
        description="Password (min 8 chars). If omitted the account is passwordless; "
        "login requires an API key.",
    )

    @field_validator("country")
    @classmethod
    def validate_country_uppercase(cls, v: str) -> str:
        return v.upper()

    model_config = {
        "json_schema_extra": {
            "example": {
                "display_name": "Enow Sinke",
                "country": "CM",
                "password": "securePass123",
            }
        }
    }


class AdminProvisionRequest(UserProvisionRequest):
    """Request body for POST /v1/admin/provision (admin-only user creation).

    Extends UserProvisionRequest with an optional role field — only an admin
    may create another admin.
    """

    role: str | None = Field(
        None,
        description="User role. Defaults to 'user'. Set to 'admin' to create an admin account.",
        examples=["user", "admin"],
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ("user", "admin"):
            raise ValueError("role must be 'user' or 'admin'")
        return v


class ProvisionResponse(BaseModel):
    """Response body for POST /v1/user/provision and POST /v1/admin/provision."""

    user_id: str = Field(..., description="Newly created user ID")
    api_key: str = Field(..., description="Plain API key — shown ONCE, store it immediately")
    display_name: str | None = Field(None, description="Display name")
    role: str = Field(..., description="User role ('user' or 'admin')")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "usr_a1b2c3d4e5f6g7h8",
                "api_key": "mnm_test_abcdef1234567890abcdef1234567890abcdef12345678",
                "display_name": "Enow Sinke",
                "role": "user",
            }
        }
    }


# ── Admin user-list schemas ───────────────────────────────────────────────────


class UserListItem(BaseModel):
    """Single user entry in the admin user list."""

    user_id: str
    display_name: str | None
    country: str
    role: str
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


# ── Admin-access consent schemas ──────────────────────────────────────────────


class GrantAdminAccessResponse(BaseModel):
    """Response for POST /v1/user/grant-admin-access."""

    admin_access_granted: bool
    granted_at: datetime | None = None


class UserCreate(BaseModel):
    """Request body for POST /v1/users (create user)"""

    display_name: str | None = Field(None, description="Name shown in reports", max_length=100)
    country: str = Field(
        ...,
        description="ISO 3166-1 alpha-2 country code (e.g., CM, US, GB)",
        pattern=r"^[A-Z]{2}$",
        examples=["CM", "NG", "US", "GB"],
    )
    locale: str | None = Field(
        None,
        description="BCP 47 locale tag (e.g., fr-CM, en-US)",
        pattern=r"^[a-z]{2}-[A-Z]{2}$",
        examples=["fr-CM", "en-NG", "en-US"],
    )
    timezone: str | None = Field(
        None,
        description=(
            "IANA timezone (optional, derived from country if not provided). "
            "For multi-timezone countries, user must select from dropdown."
        ),
        examples=["Africa/Douala", "America/New_York"],
    )
    education_level: EducationLevel | None = Field(
        None, description="Education level for personalization"
    )
    preferred_language: str = Field(
        default="en", description="BCP 47 language tag for explanations", pattern=r"^[a-z]{2}$"
    )
    daily_goal_cards: int = Field(
        default=DEFAULT_DAILY_GOAL_CARDS,
        description="Target cards to review per day",
        ge=1,
        le=200,
    )

    @field_validator("country")
    @classmethod
    def validate_country_uppercase(cls, v: str) -> str:
        """Ensure country code is uppercase"""
        return v.upper()

    model_config = {
        "json_schema_extra": {
            "example": {
                "display_name": "Enow Sinke",
                "country": "CM",
                "locale": "fr-CM",
                "education_level": "undergraduate",
                "preferred_language": "fr",
                "daily_goal_cards": 25,
            }
        }
    }


class UserUpdate(BaseModel):
    """Request body for PATCH /v1/users/{id} (update user profile)"""

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
    """Response for user profile (GET /v1/users/{id})"""

    id: str = Field(..., description="User ID (usr_xxxxxxxx)")
    display_name: str | None = Field(None, description="Display name")
    country: str = Field(..., description="ISO 3166-1 alpha-2 country code")
    locale: str | None = Field(None, description="BCP 47 locale tag")
    timezone: str = Field(..., description="IANA timezone (derived from country)")
    education_level: EducationLevel | None = Field(None, description="Education level")
    preferred_language: str = Field(..., description="BCP 47 language tag")
    daily_goal_cards: int = Field(..., description="Daily card review goal")
    created_at: datetime = Field(..., description="Account creation timestamp (UTC)")

    @computed_field(return_type=str)
    def local_time(self) -> str:
        """Account creation time in the user's local timezone."""
        local_time_value: str = to_local_time(self.created_at, self.timezone)
        return local_time_value

    @computed_field(return_type=str)
    def created_at_local(self) -> str:
        """Account creation time as a local-time companion field."""
        return cast(str, self.local_time)

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "usr_a1b2c3d4e5f6g7h8",
                "display_name": "Enow Sinke",
                "country": "CM",
                "locale": "fr-CM",
                "timezone": "Africa/Douala",
                "education_level": "undergraduate",
                "preferred_language": "fr",
                "daily_goal_cards": 25,
                "created_at": "2026-03-10T08:30:00Z",
                "local_time": "2026-03-10T09:30:00+01:00",
                "created_at_local": "2026-03-10T09:30:00+01:00",
            }
        },
        "from_attributes": True,
    }
