"""
Custom exceptions for the Mnemo API.
Provides domain-specific exception types for cleaner error handling.
"""

# ── User & Profile Exceptions ──────────────────────────────────────────────────


class UserError(Exception):
    """Base exception for user-related errors."""

    pass


class UserNotFoundError(UserError):
    """Raised when a user does not exist."""

    pass


class InvalidCountryCodeError(UserError):
    """Raised when an invalid or unsupported country code is provided."""

    pass


class InvalidTimezoneError(UserError):
    """Raised when an invalid timezone is provided."""

    pass


class MissingTimezoneError(UserError):
    """Raised when timezone is required but not provided (multi-TZ countries)."""

    pass


class TimezoneNotAllowedError(UserError):
    """Raised when trying to change timezone for single-TZ country."""

    pass


# ── API Key Exceptions ─────────────────────────────────────────────────────────


class APIKeyError(Exception):
    """Base exception for API key-related errors."""

    pass


class InvalidAPIKeyError(APIKeyError):
    """Raised when an API key is invalid or revoked."""

    pass


class APIKeyOwnerMismatchError(APIKeyError):
    """Raised when an API key does not belong to the specified user."""

    pass


# ── Authentication Exceptions ──────────────────────────────────────────────────


class AuthenticationError(Exception):
    """Base exception for authentication-related errors."""

    pass


class TokenExpiredError(AuthenticationError):
    """Raised when a JWT token has expired."""

    pass


class InvalidTokenError(AuthenticationError):
    """Raised when a JWT token is malformed or invalid."""

    pass


class InsufficientScopeError(AuthenticationError):
    """Raised when a token or API key lacks required permissions."""

    pass


# ── Idempotency Exceptions ─────────────────────────────────────────────────────


class IdempotencyConflictError(Exception):
    """Raised when an idempotency key has already been used."""

    pass


# ── Deck & Card Exceptions ─────────────────────────────────────────────────────


class DeckError(Exception):
    """Base exception for deck-related errors."""

    pass


class DeckNotFoundError(DeckError):
    """Raised when a deck does not exist or is not accessible."""

    pass


class DeckNameConflictError(DeckError):
    """Raised when a deck name conflicts for the same user."""

    pass


class CardError(Exception):
    """Base exception for card-related errors."""

    pass


class CardNotFoundError(CardError):
    """Raised when a card does not exist or is not accessible."""

    pass


# ── Session Exceptions ───────────────────────────────────────────────────────


class SessionError(Exception):
    """Base exception for session-related errors."""

    pass


class SessionNotFoundError(SessionError):
    """Raised when a session does not exist or is not accessible."""

    pass


# ── Plan Exceptions ───────────────────────────────────────────────────────────


class PlanError(Exception):
    """Base exception for study plan errors."""

    pass


class PlanNotFoundError(PlanError):
    """Raised when no active study plan exists for a user."""

    pass


class SessionAlreadyEndedError(SessionError):
    """Raised when an action is attempted on a session that has already ended."""

    pass


class AnswerTooLongError(SessionError):
    """Raised when a submitted answer exceeds the maximum allowed length."""

    pass


class NoCardsAvailableError(SessionError):
    """Raised when a session has no available cards to act on."""

    pass
