"""
Application constants.
Error codes, permission scopes, education levels, and other enums per spec.
"""

from enum import StrEnum

# ── Error Codes ────────────────────────────────────────────────────────────────
# Per spec section 12: Error Handling
# Machine-readable, stable, UPPER_SNAKE_CASE


class ErrorCode(StrEnum):
    """Standard error codes returned by the API."""

    # Validation errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_CSV_FORMAT = "INVALID_CSV_FORMAT"
    INVALID_COUNTRY_CODE = "INVALID_COUNTRY_CODE"

    # Authentication errors (401)
    INVALID_API_KEY = "INVALID_API_KEY"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"  # noqa: S105

    # Authorization errors (403)
    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
    HTTP_NOT_ALLOWED = "HTTP_NOT_ALLOWED"

    # Not found errors (404)
    DECK_NOT_FOUND = "DECK_NOT_FOUND"
    CARD_NOT_FOUND = "CARD_NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"

    # Conflict errors (409)
    DECK_NAME_CONFLICT = "DECK_NAME_CONFLICT"
    SESSION_ALREADY_ENDED = "SESSION_ALREADY_ENDED"
    API_KEY_ALREADY_EXISTS = "API_KEY_ALREADY_EXISTS"

    # Unprocessable entity (422)
    ANSWER_TOO_LONG = "ANSWER_TOO_LONG"

    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # Service unavailable (503)
    IMPORT_SERVICE_DOWN = "IMPORT_SERVICE_DOWN"


# ── Permission Scopes ──────────────────────────────────────────────────────────
# Per spec section 02: Authentication


class PermissionScope(StrEnum):
    """Permission scopes for API keys and JWT tokens."""

    DECKS_READ = "decks:read"
    DECKS_WRITE = "decks:write"
    SESSIONS_RUN = "sessions:run"
    PROGRESS_READ = "progress:read"
    IMPORT_WRITE = "import:write"
    ADMIN = "admin"


# Default scopes for newly created API keys (if not specified)
DEFAULT_API_KEY_SCOPES = [
    PermissionScope.DECKS_READ,
    PermissionScope.DECKS_WRITE,
    PermissionScope.SESSIONS_RUN,
    PermissionScope.PROGRESS_READ,
]


# ── Education Levels ───────────────────────────────────────────────────────────
# Per spec section 11: User Profiles


class EducationLevel(StrEnum):
    """User education level for profile personalization."""

    NONE = "none"
    SECONDARY = "secondary"
    UNDERGRADUATE = "undergraduate"
    POSTGRADUATE = "postgraduate"
    PROFESSIONAL = "professional"


# ── Session Modes ──────────────────────────────────────────────────────────────
# Per spec section 08: Study Sessions


class SessionMode(StrEnum):
    """Study session modes."""

    REVIEW = "review"  # Spaced repetition, full feedback
    QUIZ = "quiz"  # Multiple choice, self-testing
    EXAM = "exam"  # Timed, no feedback during session


# ── Import Modes ───────────────────────────────────────────────────────────────
# Per spec section 10: CSV Import


class ImportMode(StrEnum):
    """CSV import modes."""

    MERGE = "merge"  # Add new cards, skip duplicates
    REPLACE = "replace"  # Wipe deck and re-import


# ── Difficulty Levels ──────────────────────────────────────────────────────────
# Manual difficulty hint for flashcards (1-5)

MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
DEFAULT_DIFFICULTY = 3


# ── SM-2 Algorithm Constants ───────────────────────────────────────────────────
# Per spec section 05: Spaced Repetition

DEFAULT_EASE_FACTOR = 2.5
MIN_EASE_FACTOR = 1.3
EASE_FACTOR_INCREASE = 0.1
EASE_FACTOR_DECREASE = 0.15

# Score thresholds
MIN_SCORE = 0
MAX_SCORE = 5
PASSING_SCORE = 3  # Scores >= 3 are considered correct


# ── Limits and Constraints ─────────────────────────────────────────────────────

# Text length limits
MAX_DECK_NAME_LENGTH = 128
MAX_TAG_LENGTH = 32
MAX_QUESTION_LENGTH = 1000
MAX_ANSWER_LENGTH = 2000
MAX_SOURCE_REF_LENGTH = 255

# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Session limits
DEFAULT_SESSION_CARD_LIMIT = 20
MAX_SESSION_CARD_LIMIT = 100

# Daily goal defaults
DEFAULT_DAILY_GOAL_CARDS = 20
MIN_DAILY_GOAL_CARDS = 1
MAX_DAILY_GOAL_CARDS = 200

# Learning plan limits
MIN_PLAN_DAYS = 1
MAX_PLAN_DAYS = 365
