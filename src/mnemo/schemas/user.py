"""
User profile schemas.
Request/response models per spec section 11: User Profiles.
"""

from datetime import datetime

from pydantic import BaseModel, Field, computed_field, field_validator

from mnemo.core.constants import DEFAULT_DAILY_GOAL_CARDS, EducationLevel
from mnemo.utils.local_time import to_local_time


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
            }
        },
        "from_attributes": True,
    }
