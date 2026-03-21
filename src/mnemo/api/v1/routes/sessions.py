from typing import Annotated, Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession as Session

from mnemo.api.dependencies import current_user_dep, db_dep
from mnemo.core import exceptions as exc
from mnemo.core.constants import ErrorCode
from mnemo.models import User
from mnemo.schemas import session as session_schema
from mnemo.services.session import SessionService

router = APIRouter()


def _session_not_found(session_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": ErrorCode.SESSION_NOT_FOUND.value,
                "message": "Session not found.",
                "status": 404,
                "session_id": session_id,
            }
        },
    )


@router.post("/", response_model=session_schema.Session, status_code=201)
async def start_session(
    session_data: session_schema.SessionStart,
    db: Annotated[Session, db_dep],
    current_user: Annotated[User, current_user_dep],
) -> session_schema.Session:
    """Starts a new study session."""
    service = SessionService(db, current_user)
    try:
        return await service.start_session(session_data)
    except exc.DeckNotFoundError as e:
        raise HTTPException(status_code=404, detail="Deck not found.") from e


@router.get("/{session_id}", response_model=session_schema.Session)
async def get_session(
    session_id: str,
    db: Annotated[Session, db_dep],
    current_user: Annotated[User, current_user_dep],
) -> session_schema.Session:
    """Gets the current state of a session."""
    service = SessionService(db, current_user)
    try:
        return await service.get_session(session_id)
    except exc.SessionNotFoundError as e:
        raise _session_not_found(session_id) from e


@router.post("/{session_id}/answer", response_model=session_schema.AnswerResult)
async def answer_card(
    session_id: str,
    answer_data: session_schema.Answer,
    db: Annotated[Session, db_dep],
    current_user: Annotated[User, current_user_dep],
) -> session_schema.AnswerResult:
    """Submits an answer for the current card in a session."""
    service = SessionService(db, current_user)
    try:
        return await service.answer_card(session_id, answer_data)
    except exc.SessionNotFoundError as e:
        raise _session_not_found(session_id) from e
    except exc.SessionAlreadyEndedError as e:
        raise HTTPException(status_code=409, detail="Session has already ended.") from e
    except exc.AnswerTooLongError as e:
        raise HTTPException(status_code=422, detail="Answer is too long.") from e
    except exc.NoCardsAvailableError as e:
        raise HTTPException(status_code=409, detail="No cards available in this session.") from e


@router.post("/{session_id}/skip")
async def skip_card(
    session_id: str,
    db: Annotated[Session, db_dep],
    current_user: Annotated[User, current_user_dep],
) -> dict[str, Any]:
    """Skips the current card in a session."""
    service = SessionService(db, current_user)
    try:
        return await service.skip_card(session_id)
    except exc.SessionNotFoundError as e:
        raise _session_not_found(session_id) from e
    except exc.SessionAlreadyEndedError as e:
        raise HTTPException(status_code=409, detail="Session has already ended.") from e
    except exc.NoCardsAvailableError as e:
        raise HTTPException(status_code=409, detail="No cards available in this session.") from e


@router.post("/{session_id}/end")
async def end_session(
    session_id: str,
    db: Annotated[Session, db_dep],
    current_user: Annotated[User, current_user_dep],
) -> dict[str, str]:
    """Ends a session early."""
    service = SessionService(db, current_user)
    try:
        return await service.end_session(session_id)
    except exc.SessionNotFoundError as e:
        raise _session_not_found(session_id) from e
    except exc.SessionAlreadyEndedError as e:
        raise HTTPException(status_code=409, detail="Session has already ended.") from e


@router.get("/{session_id}/summary", response_model=session_schema.SessionSummary)
async def get_session_summary(
    session_id: str,
    db: Annotated[Session, db_dep],
    current_user: Annotated[User, current_user_dep],
) -> session_schema.SessionSummary:
    """Gets the summary of a completed session."""
    service = SessionService(db, current_user)
    try:
        return await service.get_session_summary(session_id)
    except exc.SessionNotFoundError as e:
        raise _session_not_found(session_id) from e
