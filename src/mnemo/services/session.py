from datetime import datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession as DbSession
from sqlalchemy.orm import joinedload

from src.mnemo.core.exceptions import (
    AnswerTooLongError,
    DeckNotFoundError,
    SessionAlreadyEndedError,
    SessionNotFoundError,
)
from src.mnemo.models import (
    CardMemoryState,
    Deck,
    Flashcard,
    Session,
    SessionCard,
    User,
)
from src.mnemo.models.session import SessionStatus
from src.mnemo.schemas.session import (
    Answer,
    AnswerResult,
    SessionStart,
    SessionSummary,
)
from src.mnemo.schemas.session import (
    Session as SessionSchema,
)
from src.mnemo.services.spaced_repetition import (
    get_or_create_memory_state,
    update_memory_state_after_answer,
)
from src.mnemo.utils.local_time import to_local_time


class SessionService:
    def __init__(self, db: DbSession, user: User) -> None:
        self.db = db
        self.user = user

    async def start_session(self, session_data: SessionStart) -> SessionSchema:
        result = await self.db.execute(
            select(Deck).where(
                Deck.id == session_data.deck_id,
                Deck.user_id == self.user.id,
            )
        )
        deck = result.scalar_one_or_none()
        if not deck:
            raise DeckNotFoundError()

        card_query = select(Flashcard).where(Flashcard.deck_id == deck.id)

        if session_data.due_only:
            card_query = card_query.join(CardMemoryState).where(
                CardMemoryState.user_id == self.user.id,
                CardMemoryState.due_at <= datetime.utcnow(),
            )

        if session_data.focus_weak:
            card_query = card_query.outerjoin(
                CardMemoryState,
                and_(
                    CardMemoryState.card_id == Flashcard.id,
                    CardMemoryState.user_id == self.user.id,
                ),
            ).order_by(CardMemoryState.ease_factor.asc().nulls_last())
        else:
            card_query = card_query.order_by(func.random())

        if session_data.card_limit:
            card_query = card_query.limit(session_data.card_limit)

        cards_result = await self.db.execute(card_query)
        cards = list(cards_result.scalars().all())

        session_id = uuid4()
        expires_at = datetime.utcnow() + timedelta(hours=2)

        session = Session(
            id=session_id,
            user_id=self.user.id,
            deck_id=deck.id,
            mode=session_data.mode,
            status=SessionStatus.ACTIVE,
            card_limit=len(cards),
            time_limit_s=session_data.time_limit_s,
            expires_at=expires_at,
        )
        self.db.add(session)

        session_cards = []
        for card in cards:
            session_card = SessionCard(id=uuid4(), session_id=session_id, card_id=card.id)
            session_cards.append(session_card)
        self.db.add_all(session_cards)

        await self.db.flush()

        current_card_model = cards[0] if cards else None
        expires_at_local = to_local_time(expires_at, self.user.timezone)

        return SessionSchema(
            session_id=session.id,
            status=session.status,
            cards_total=len(cards),
            cards_done=0,
            current_card=current_card_model,
            expires_at=session.expires_at,
            expires_at_local=expires_at_local,
        )

    def _evaluate_answer(self, submitted_answer: str, canonical_answer: str) -> int:
        submitted_lower = submitted_answer.lower()
        canonical_lower = canonical_answer.lower()

        if submitted_lower == canonical_lower:
            return 5

        canonical_words = set(canonical_lower.split())
        submitted_words = set(submitted_lower.split())
        common_words = canonical_words.intersection(submitted_words)

        match_percentage = (
            len(common_words) / len(canonical_words) if len(canonical_words) > 0 else 0
        )

        if match_percentage > 0.9:
            return 5
        elif match_percentage > 0.75:
            return 4
        elif match_percentage > 0.5:
            return 3
        elif match_percentage > 0.25:
            return 2
        elif match_percentage > 0:
            return 1
        else:
            return 0

    async def answer_card(self, session_id: str, answer_data: Answer) -> AnswerResult:
        result = await self.db.execute(
            select(Session)
            .options(joinedload(Session.cards).joinedload(SessionCard.card))
            .where(Session.id == session_id, Session.user_id == self.user.id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise SessionNotFoundError()
        if session.status == SessionStatus.ENDED:
            raise SessionAlreadyEndedError()
        if len(answer_data.answer) > 2000:
            raise AnswerTooLongError()

        current_result = await self.db.execute(
            select(SessionCard)
            .where(SessionCard.session_id == session.id, ~SessionCard.answered)
            .order_by(SessionCard.created_at)
            .limit(1)
        )
        current_session_card = current_result.scalar_one_or_none()

        if not current_session_card:
            raise Exception("No more cards to answer in this session.")

        score = self._evaluate_answer(answer_data.answer, current_session_card.card.answer)
        is_correct = score >= 3

        current_session_card.answered = cast(Any, True)
        current_session_card.correct = cast(Any, is_correct)
        current_session_card.score = cast(Any, score)
        current_session_card.answered_at = cast(Any, datetime.utcnow())

        memory_state = await get_or_create_memory_state(
            self.db, str(current_session_card.card_id), self.user.id
        )
        if memory_state:
            update_memory_state_after_answer(memory_state, score)

        next_result = await self.db.execute(
            select(SessionCard)
            .where(SessionCard.session_id == session.id, ~SessionCard.answered)
            .order_by(SessionCard.created_at)
            .limit(1)
        )
        next_session_card = next_result.scalar_one_or_none()

        cards_done_result = await self.db.execute(
            select(func.count()).where(
                SessionCard.session_id == session.id,
                SessionCard.answered == True,  # noqa: E712
            )
        )
        cards_done = cards_done_result.scalar_one()

        correct_result = await self.db.execute(
            select(func.count()).where(
                SessionCard.session_id == session.id,
                SessionCard.correct == True,  # noqa: E712
            )
        )
        correct_so_far = correct_result.scalar_one()

        if not next_session_card:
            session.status = SessionStatus.ENDED
            session.ended_at = cast(Any, datetime.utcnow())

        await self.db.flush()

        return AnswerResult(
            score=score,
            is_correct=is_correct,
            canonical_answer=current_session_card.card.answer,
            feedback="Correct." if is_correct else "Incorrect.",
            next_card=next_session_card.card if next_session_card else None,
            session_progress={
                "cards_done": cards_done,
                "cards_total": session.card_limit,
                "correct_so_far": correct_so_far,
            },
        )

    async def skip_card(self, session_id: str) -> dict[str, Any]:
        result = await self.db.execute(
            select(Session).where(Session.id == session_id, Session.user_id == self.user.id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise SessionNotFoundError()
        if session.status == SessionStatus.ENDED:
            raise SessionAlreadyEndedError()

        current_result = await self.db.execute(
            select(SessionCard)
            .where(SessionCard.session_id == session.id, ~SessionCard.answered)
            .order_by(SessionCard.created_at)
            .limit(1)
        )
        current_session_card = current_result.scalar_one_or_none()

        if not current_session_card:
            raise Exception("No more cards to skip in this session.")

        current_session_card.created_at = cast(Any, datetime.utcnow())
        await self.db.flush()

        next_result = await self.db.execute(
            select(SessionCard)
            .where(SessionCard.session_id == session.id, ~SessionCard.answered)
            .order_by(SessionCard.created_at)
            .limit(1)
        )
        next_session_card = next_result.scalar_one_or_none()

        return {"next_card": next_session_card.card if next_session_card else None}

    async def end_session(self, session_id: str) -> dict[str, str]:
        result = await self.db.execute(
            select(Session).where(Session.id == session_id, Session.user_id == self.user.id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise SessionNotFoundError()
        if session.status == SessionStatus.ENDED:
            raise SessionAlreadyEndedError()

        session.status = SessionStatus.ENDED
        session.ended_at = cast(Any, datetime.utcnow())
        await self.db.flush()

        return {"message": "Session ended successfully."}

    async def get_session(self, session_id: str) -> SessionSchema:
        result = await self.db.execute(
            select(Session).where(Session.id == session_id, Session.user_id == self.user.id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise SessionNotFoundError()

        cards_done_result = await self.db.execute(
            select(func.count()).where(
                SessionCard.session_id == session.id,
                SessionCard.answered == True,  # noqa: E712
            )
        )
        cards_done = cards_done_result.scalar_one()

        current_result = await self.db.execute(
            select(SessionCard)
            .where(SessionCard.session_id == session.id, ~SessionCard.answered)
            .order_by(SessionCard.created_at)
            .limit(1)
        )
        current_card = current_result.scalar_one_or_none()

        expires_at_local = to_local_time(session.expires_at, self.user.timezone)

        return SessionSchema(
            session_id=session.id,
            status=session.status,
            cards_total=session.card_limit,
            cards_done=cards_done,
            current_card=current_card.card if current_card else None,
            expires_at=session.expires_at,
            expires_at_local=expires_at_local,
        )

    async def get_session_summary(self, session_id: str) -> SessionSummary:
        result = await self.db.execute(
            select(Session).where(Session.id == session_id, Session.user_id == self.user.id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise SessionNotFoundError()

        cards_answered_result = await self.db.execute(
            select(func.count()).where(
                SessionCard.session_id == session.id,
                SessionCard.answered == True,  # noqa: E712
            )
        )
        cards_answered = cards_answered_result.scalar_one()

        correct_result = await self.db.execute(
            select(func.count()).where(
                SessionCard.session_id == session.id,
                SessionCard.correct == True,  # noqa: E712
            )
        )
        correct_answers = correct_result.scalar_one()

        accuracy = correct_answers / cards_answered if cards_answered > 0 else 0

        time_taken_s = 0
        if session.ended_at:
            time_taken_s = int((session.ended_at - session.created_at).total_seconds())

        return SessionSummary(
            session_id=session.id,
            deck_id=session.deck_id,
            mode=session.mode,
            status=session.status,
            started_at=session.created_at,
            ended_at=session.ended_at,
            total_cards=session.card_limit,
            cards_answered=cards_answered,
            correct_answers=correct_answers,
            accuracy=accuracy,
            time_taken_s=time_taken_s,
        )
