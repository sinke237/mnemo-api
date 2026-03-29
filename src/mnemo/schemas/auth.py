"""
Authentication schemas.
Token request/response models per spec section 02: Authentication.
"""

from typing import Literal

from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    """Request body for POST /v1/auth/token"""

    user_id: str = Field(
        ..., description="User ID (usr_[a-f0-9]{16})", pattern=r"^usr_[a-f0-9]{16}$"
    )
    api_key: str = Field(
        ...,
        description="API key (mnm_live_xxx or mnm_test_xxx)",
        pattern=r"^mnm_(live|test)_[a-f0-9]{64}$",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "usr_a1b2c3d4e5f6a7b8",
                "api_key": (
                    "mnm_live_abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
                ),
            }
        }
    }


class TokenResponse(BaseModel):
    """Response for successful token generation"""

    access_token: str = Field(..., description="JWT access token")
    expires_in: int = Field(..., gt=0, description="Token lifetime in seconds")
    token_type: Literal["Bearer"] = Field(
        default="Bearer", description="Token type (always 'Bearer')"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "<jwt_token_placeholder>",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        }
    }


class LoginRequest(BaseModel):
    """Request body for POST /v1/auth/login (password-based login)."""

    display_name: str = Field(..., min_length=3, description="User display name")
    password: str = Field(..., min_length=8, description="User password")

    model_config = {
        "json_schema_extra": {
            "example": {
                "display_name": "Enow Sinke",
                "password": "securePass123",
            }
        }
    }
