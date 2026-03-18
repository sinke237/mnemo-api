"""
Unit tests for edge cases in the SM-2 spaced repetition service.
"""

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


def test_sm2_lowest_passing_score(new_memory_state: CardMemoryState):
    """Test that a score of 3 is handled correctly."""
    state = update_memory_state_after_answer(new_memory_state, 3)
    assert state.ease_factor < 2.5
    assert state.repetitions == 1
    assert state.interval_days == 1
    assert state.streak == 1


def test_sm2_maximum_ease_factor(new_memory_state: CardMemoryState):
    """Test the behavior with a very high ease factor."""
    state = new_memory_state
    state.ease_factor = 5.0
    state.repetitions = 1
    state.interval_days = 1
    state = update_memory_state_after_answer(state, 5)
    assert state.interval_days > 1


def test_sm2_null_interval_days(new_memory_state: CardMemoryState):
    """Test that a null interval_days is handled correctly."""
    state = new_memory_state
    state.interval_days = None
    state = update_memory_state_after_answer(state, 5)
    assert state.interval_days is not None
