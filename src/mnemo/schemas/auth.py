"""
Authentication schemas.
Token request/response models per spec section 02: Authentication.
"""

from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    """Request body for POST /v1/auth/token"""

    user_id: str = Field(..., description="User ID (usr_xxxxxxxx)", pattern=r"^usr_[a-f0-9]{16}$")
    api_key: str = Field(
        ...,
        description="API key (mnm_live_xxx or mnm_test_xxx)",
        min_length=40,  # mnm_live_ (9) + 64 hex chars = 73
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "usr_a1b2c3d4e5f6g7h8",
                "api_key": (
                    "mnm_live_abcdef1234567890abcdef1234567890" "abcdef1234567890abcdef1234567890"
                ),
            }
        }
    }


class TokenResponse(BaseModel):
    """Response for successful token generation"""

    access_token: str = Field(..., description="JWT access token")
    expires_in: int = Field(..., description="Token lifetime in seconds")
    token_type: str = Field(default="Bearer", description="Token type (always 'Bearer')")

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        }
    }
