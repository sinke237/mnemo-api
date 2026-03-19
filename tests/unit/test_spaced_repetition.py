"""
Unit tests for the SM-2 spaced repetition service.
"""

from datetime import UTC, datetime

import pytest

from mnemo.models import CardMemoryState
from mnemo.services.spaced_repetition import update_memory_state_after_answer


@pytest.fixture
def new_memory_state() -> CardMemoryState:
    """Returns a new CardMemoryState with default values."""
    return CardMemoryState(
        card_id="crd_123",
        user_id="usr_123",
        ease_factor=2.5,
        repetitions=0,
        interval_days=0,
        streak=0,
    )


def test_sm2_correct_answer_first_review(new_memory_state: CardMemoryState):
    """Test the first successful review of a new card."""
    state = update_memory_state_after_answer(new_memory_state, 5)
    assert state.repetitions == 1
    assert state.interval_days == 1
    assert state.streak == 1
    assert state.ease_factor > 2.5
    assert state.due_at is not None
    assert state.due_at > datetime.now(UTC)


def test_sm2_correct_answer_second_review(new_memory_state: CardMemoryState):
    """Test the second successful review of a card."""
    state = update_memory_state_after_answer(new_memory_state, 5)
    state = update_memory_state_after_answer(state, 5)
    assert state.repetitions == 2
    assert state.interval_days == 6
    assert state.streak == 2
    assert state.ease_factor > 2.6


def test_sm2_correct_answer_third_review(new_memory_state: CardMemoryState):
    """Test the third successful review of a card."""
    state = update_memory_state_after_answer(new_memory_state, 5)
    state = update_memory_state_after_answer(state, 5)
    state = update_memory_state_after_answer(state, 5)
    assert state.repetitions == 3
    assert state.interval_days > 6
    assert state.streak == 3


def test_sm2_incorrect_answer_resets_progress(new_memory_state: CardMemoryState):
    """Test that an incorrect answer resets the repetition count and streak."""
    state = update_memory_state_after_answer(new_memory_state, 5)
    state = update_memory_state_after_answer(state, 5)
    state = update_memory_state_after_answer(state, 1)
    assert state.repetitions == 0
    assert state.interval_days == 1
    assert state.streak == 0
    assert state.ease_factor < 2.5


def test_sm2_ease_factor_decreases_on_low_score(new_memory_state: CardMemoryState):
    """Test that the ease factor decreases with a low score."""
    state = update_memory_state_after_answer(new_memory_state, 3)
    assert state.ease_factor < 2.5


def test_sm2_ease_factor_does_not_go_below_minimum(new_memory_state: CardMemoryState):
    """Test that the ease factor does not drop below the minimum value."""
    state = new_memory_state
    for _ in range(10):
        state = update_memory_state_after_answer(state, 0)
    assert state.ease_factor == 1.3
