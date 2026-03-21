import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.exceptions import (
    AnswerTooLongError,
    DeckNotFoundError,
    SessionAlreadyEndedError,
    SessionNotFoundError,
)
from mnemo.models import Deck, Flashcard, Session, User
from mnemo.models.session import SessionStatus
from mnemo.schemas.session import Answer, SessionStart
from mnemo.services.session import SessionService


def _make_result(scalar=None, scalars=None, scalar_one=0):
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    result.scalars.return_value.all.return_value = scalars or []
    result.scalar_one.return_value = scalar_one
    return result


@pytest.fixture
def mock_db_session():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _make_result()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    return db


@pytest.fixture
def mock_user():
    return User(id=str(uuid.uuid4()), country="US", timezone="America/New_York")


@pytest.fixture
def session_service(mock_db_session, mock_user):
    return SessionService(mock_db_session, mock_user)


@pytest.mark.asyncio
async def test_start_session_deck_not_found(session_service, mock_db_session):
    mock_db_session.execute.return_value = _make_result(scalar=None)
    session_data = SessionStart(deck_id=str(uuid.uuid4()))

    with pytest.raises(DeckNotFoundError):
        await session_service.start_session(session_data)


@pytest.mark.asyncio
async def test_start_session_no_cards(session_service, mock_db_session, mock_user):
    deck_id = uuid.uuid4()
    deck = Deck(id=str(deck_id), user_id=mock_user.id, name="Test Deck")

    mock_db_session.execute.side_effect = [
        _make_result(scalar=deck),
        _make_result(scalars=[]),
    ]

    session_data = SessionStart(deck_id=str(deck_id))
    session = await session_service.start_session(session_data)

    assert session.cards_total == 0
    assert session.current_card is None


@pytest.mark.asyncio
async def test_answer_card_session_not_found(session_service, mock_db_session):
    mock_db_session.execute.return_value = _make_result(scalar=None)
    answer_data = Answer(answer="test")

    with pytest.raises(SessionNotFoundError):
        await session_service.answer_card(uuid.uuid4(), answer_data)


@pytest.mark.asyncio
async def test_answer_card_session_already_ended(session_service, mock_db_session):
    session = Session(status=SessionStatus.ENDED)
    mock_db_session.execute.return_value = _make_result(scalar=session)
    answer_data = Answer(answer="test")

    with pytest.raises(SessionAlreadyEndedError):
        await session_service.answer_card(uuid.uuid4(), answer_data)


@pytest.mark.asyncio
async def test_answer_card_answer_too_long(session_service, mock_db_session):
    session = Session(status=SessionStatus.ACTIVE)
    mock_db_session.execute.return_value = _make_result(scalar=session)
    answer_data = Answer.model_construct(answer="a" * 2001)

    with pytest.raises(AnswerTooLongError):
        await session_service.answer_card(uuid.uuid4(), answer_data)


@pytest.mark.asyncio
async def test_skip_card_no_more_cards(session_service, mock_db_session):
    session_id = uuid.uuid4()
    session = Session(id=session_id, status=SessionStatus.ACTIVE)
    mock_db_session.execute.side_effect = [
        _make_result(scalar=session),
        _make_result(scalar=None),
    ]

    with pytest.raises(Exception, match="No more cards to skip"):
        await session_service.skip_card(session_id)


@pytest.mark.asyncio
async def test_end_session_not_found(session_service, mock_db_session):
    mock_db_session.execute.return_value = _make_result(scalar=None)

    with pytest.raises(SessionNotFoundError):
        await session_service.end_session(uuid.uuid4())


@pytest.mark.asyncio
async def test_get_session_summary_not_found(session_service, mock_db_session):
    mock_db_session.execute.return_value = _make_result(scalar=None)

    with pytest.raises(SessionNotFoundError):
        await session_service.get_session_summary(uuid.uuid4())


@pytest.mark.asyncio
async def test_evaluate_answer_logic(session_service):
    assert session_service._evaluate_answer("apple", "apple") == 5
    assert session_service._evaluate_answer("apple", "Apple") == 5
    assert session_service._evaluate_answer("orange", "apple") == 0
    assert session_service._evaluate_answer("the apple", "the apple") == 5
    assert session_service._evaluate_answer("the apple", "an apple") >= 2
    assert session_service._evaluate_answer("", "apple") == 0
    assert session_service._evaluate_answer("apple", "") == 0


@pytest.mark.asyncio
async def test_start_session_with_due_only(session_service, mock_db_session, mock_user):
    deck_id = uuid.uuid4()
    deck = Deck(id=str(deck_id), user_id=mock_user.id, name="Test Deck")
    card1 = Flashcard(id=str(uuid.uuid4()), deck_id=str(deck_id), question="q1", answer="a1")

    mock_db_session.execute.side_effect = [
        _make_result(scalar=deck),
        _make_result(scalars=[card1]),
    ]

    session_data = SessionStart(deck_id=str(deck_id), due_only=True)
    await session_service.start_session(session_data)

    query_str = str(mock_db_session.execute.call_args_list[1].args[0])
    assert "card_memory_states" in query_str


@pytest.mark.asyncio
async def test_start_session_with_focus_weak(session_service, mock_db_session, mock_user):
    deck_id = uuid.uuid4()
    deck = Deck(id=str(deck_id), user_id=mock_user.id, name="Test Deck")
    card1 = Flashcard(id=str(uuid.uuid4()), deck_id=str(deck_id), question="q1", answer="a1")

    mock_db_session.execute.side_effect = [
        _make_result(scalar=deck),
        _make_result(scalars=[card1]),
    ]

    session_data = SessionStart(deck_id=str(deck_id), focus_weak=True)
    await session_service.start_session(session_data)

    query_str = str(mock_db_session.execute.call_args_list[1].args[0])
    assert "ease_factor" in query_str


@pytest.mark.asyncio
async def test_answer_card_no_more_cards(session_service, mock_db_session):
    session_id = uuid.uuid4()
    session = Session(id=session_id, status=SessionStatus.ACTIVE)
    mock_db_session.execute.side_effect = [
        _make_result(scalar=session),
        _make_result(scalar=None),
    ]
    answer_data = Answer(answer="test")

    with pytest.raises(Exception, match="No more cards to answer"):
        await session_service.answer_card(session_id, answer_data)
