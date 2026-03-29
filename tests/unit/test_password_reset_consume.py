import pytest

from mnemo.models.user import User
from mnemo.services import password_reset as prs


@pytest.mark.asyncio
async def test_consume_token_marks_used(db_session):
    # Create a test user
    user = User(
        id="usr_test_consume",
        email="consume.test@example.com",
        normalized_email="consume.test@example.com",
        country="US",
        timezone="America/New_York",
        display_name="Consume Test",
    )
    user.role = "user"
    user.email_verified = False

    db_session.add(user)
    await db_session.flush()

    # Create a token
    token = await prs.create_token(db_session, user.id)

    # First consumption should return the row and mark used_at
    row = await prs.consume_token_by_plain(db_session, token)
    assert row is not None
    assert getattr(row, "used_at", None) is not None

    # Second consumption should return None (already used)
    row2 = await prs.consume_token_by_plain(db_session, token)
    assert row2 is None
