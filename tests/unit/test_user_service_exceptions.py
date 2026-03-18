"""
Unit tests for user service error handling with custom exceptions.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.exceptions import (
    InvalidCountryCodeError,
    InvalidTimezoneError,
    MissingTimezoneError,
    TimezoneNotAllowedError,
)
from mnemo.db.database import AsyncSessionLocal, engine
from mnemo.schemas.user import UserCreate, UserUpdate
from mnemo.services.user import create_user, update_user


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a clean database session for each test.
    Uses an explicit transaction + savepoint so test commits are isolated and rolled back.
    """
    async with engine.begin() as conn:
        async with AsyncSessionLocal(bind=conn) as session:
            try:
                yield session
            finally:
                await session.rollback()


@pytest.mark.asyncio
async def test_create_user_invalid_country_raises_error(db_session: AsyncSession) -> None:
    """Test that invalid country code raises InvalidCountryCodeError."""
    user_data = UserCreate(
        display_name="Test User",
        country="ZZ",  # Invalid country
        preferred_language="en",
        daily_goal_cards=20,
    )

    with pytest.raises(InvalidCountryCodeError) as exc_info:
        await create_user(db_session, user_data)

    assert "Unsupported country code: ZZ" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_user_derives_timezone_cm(db_session: AsyncSession) -> None:
    """Test that CM derives Africa/Douala when timezone is omitted."""
    user_data = UserCreate(
        display_name="Test User",
        country="CM",
        preferred_language="en",
        daily_goal_cards=20,
    )

    user = await create_user(db_session, user_data)
    assert user.timezone == "Africa/Douala"


@pytest.mark.asyncio
async def test_create_user_derives_timezone_ng(db_session: AsyncSession) -> None:
    """Test that NG derives Africa/Lagos when timezone is omitted."""
    user_data = UserCreate(
        display_name="Test User",
        country="NG",
        preferred_language="en",
        daily_goal_cards=20,
    )

    user = await create_user(db_session, user_data)
    assert user.timezone == "Africa/Lagos"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_data_kwargs",
    [
        {
            "display_name": "US User",
            "country": "US",
            "preferred_language": "en",
            "daily_goal_cards": 20,
        },  # Omitted
        {
            "display_name": "US User",
            "country": "US",
            "preferred_language": "en",
            "daily_goal_cards": 20,
            "timezone": None,
        },  # Explicitly None
    ],
)
async def test_create_user_multi_tz_missing_timezone_raises_error(
    db_session: AsyncSession, user_data_kwargs: dict
) -> None:
    """Test that multi-timezone country without timezone raises MissingTimezoneError."""
    user_data = UserCreate(**user_data_kwargs)

    with pytest.raises(MissingTimezoneError) as exc_info:
        await create_user(db_session, user_data)

    assert "multiple timezones" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_user_invalid_timezone_raises_error(db_session: AsyncSession) -> None:
    """Test that invalid timezone raises InvalidTimezoneError."""
    user_data = UserCreate(
        display_name="Test User",
        country="GB",
        timezone="Invalid/Timezone",  # Invalid IANA timezone
        preferred_language="en",
        daily_goal_cards=20,
    )

    with pytest.raises(InvalidTimezoneError) as exc_info:
        await create_user(db_session, user_data)

    assert "Invalid timezone" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_user_wrong_timezone_for_country_raises_error(
    db_session: AsyncSession,
) -> None:
    """Test that wrong timezone for country raises InvalidTimezoneError."""
    user_data = UserCreate(
        display_name="Test User",
        country="GB",  # Should use Europe/London
        timezone="America/New_York",  # Wrong timezone for GB
        preferred_language="en",
        daily_goal_cards=20,
    )

    with pytest.raises(InvalidTimezoneError) as exc_info:
        await create_user(db_session, user_data)

    assert "Invalid timezone" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_user_blank_timezone_raises_error(db_session: AsyncSession) -> None:
    """Test that blank/whitespace timezone raises InvalidTimezoneError."""
    user_data = UserCreate(
        display_name="Test User",
        country="GB",
        timezone="   ",  # Whitespace only
        preferred_language="en",
        daily_goal_cards=20,
    )

    with pytest.raises(InvalidTimezoneError) as exc_info:
        await create_user(db_session, user_data)

    assert "cannot be blank" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_user_invalid_timezone_raises_error(db_session: AsyncSession) -> None:
    """Test that updating with invalid timezone raises InvalidTimezoneError."""
    # First create a valid user
    user_data = UserCreate(
        display_name="Test User",
        country="US",
        timezone="America/New_York",
        preferred_language="en",
        daily_goal_cards=20,
    )
    user = await create_user(db_session, user_data)
    await db_session.commit()

    # Try to update with invalid timezone
    update_data = UserUpdate(timezone="Invalid/Zone")

    with pytest.raises(InvalidTimezoneError) as exc_info:
        await update_user(db_session, user.id, update_data)

    assert "Invalid timezone" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_user_timezone_not_allowed_for_single_tz_country(
    db_session: AsyncSession,
) -> None:
    """Test that changing timezone for single-TZ country raises TimezoneNotAllowedError."""
    # Create user in single-timezone country
    user_data = UserCreate(
        display_name="Test User",
        country="GB",  # Single timezone
        preferred_language="en",
        daily_goal_cards=20,
    )
    user = await create_user(db_session, user_data)
    await db_session.commit()

    # Try to change timezone (not allowed for GB)
    update_data = UserUpdate(timezone="Europe/Paris")

    with pytest.raises(TimezoneNotAllowedError) as exc_info:
        await update_user(db_session, user.id, update_data)

    assert "Cannot change timezone" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_user_wrong_timezone_for_multi_tz_country(
    db_session: AsyncSession,
) -> None:
    """Test that invalid timezone for multi-TZ country raises InvalidTimezoneError."""
    # Create user in multi-timezone country
    user_data = UserCreate(
        display_name="US User",
        country="US",
        timezone="America/New_York",
        preferred_language="en",
        daily_goal_cards=20,
    )
    user = await create_user(db_session, user_data)
    await db_session.commit()

    # Try to change to invalid timezone for US
    update_data = UserUpdate(timezone="Europe/London")

    with pytest.raises(InvalidTimezoneError) as exc_info:
        await update_user(db_session, user.id, update_data)

    assert "not valid for country US" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_user_valid_timezone_for_multi_tz_country_succeeds(
    db_session: AsyncSession,
) -> None:
    """Test that valid timezone change for multi-TZ country succeeds."""
    # Create user in multi-timezone country
    user_data = UserCreate(
        display_name="US User",
        country="US",
        timezone="America/New_York",
        preferred_language="en",
        daily_goal_cards=20,
    )
    user = await create_user(db_session, user_data)
    await db_session.commit()

    # Change to another valid US timezone
    update_data = UserUpdate(timezone="America/Los_Angeles")
    updated_user = await update_user(db_session, user.id, update_data)

    assert updated_user is not None
    assert updated_user.timezone == "America/Los_Angeles"


@pytest.mark.asyncio
async def test_update_user_not_found_returns_none(db_session: AsyncSession) -> None:
    """Test that updating non-existent user returns None."""
    update_data = UserUpdate(daily_goal_cards=50)
    result = await update_user(db_session, "usr_doesnotexist123", update_data)

    assert result is None
