import pytest

from interview.enums import ChecklistStatus, InterviewStatus
from interview.state import (
    INTERVIEW_TRANSITIONS,
    InvalidTransitionError,
    interview_can_transition,
    transition_checklist_item,
    transition_interview,
)

LEGAL_INTERVIEW = [
    (InterviewStatus.CREATED, InterviewStatus.PREPARING),
    (InterviewStatus.PREPARING, InterviewStatus.READY),
    (InterviewStatus.READY, InterviewStatus.IN_PROGRESS),
    (InterviewStatus.IN_PROGRESS, InterviewStatus.COMPLETED),
]

LEGAL_CHECKLIST = [
    (ChecklistStatus.PENDING, ChecklistStatus.ASKED),
    (ChecklistStatus.ASKED, ChecklistStatus.ANSWERED),
]


def _every_ordered_pair(states):
    return [(a, b) for a in states for b in states if a != b]


ILLEGAL_INTERVIEW = [
    pair for pair in _every_ordered_pair(InterviewStatus) if pair not in LEGAL_INTERVIEW
]
ILLEGAL_CHECKLIST = [
    pair for pair in _every_ordered_pair(ChecklistStatus) if pair not in LEGAL_CHECKLIST
]


@pytest.mark.parametrize(("current", "target"), LEGAL_INTERVIEW)
def test_legal_interview_transitions_are_allowed(current, target):
    assert transition_interview(current, target) is target
    assert interview_can_transition(current, target)


@pytest.mark.parametrize(("current", "target"), ILLEGAL_INTERVIEW)
def test_every_other_interview_transition_is_rejected(current, target):
    with pytest.raises(InvalidTransitionError):
        transition_interview(current, target)
    assert not interview_can_transition(current, target)


@pytest.mark.parametrize(("current", "target"), LEGAL_CHECKLIST)
def test_legal_checklist_transitions_are_allowed(current, target):
    assert transition_checklist_item(current, target) is target


@pytest.mark.parametrize(("current", "target"), ILLEGAL_CHECKLIST)
def test_every_other_checklist_transition_is_rejected(current, target):
    with pytest.raises(InvalidTransitionError):
        transition_checklist_item(current, target)


@pytest.mark.parametrize("status", list(InterviewStatus))
def test_an_interview_cannot_transition_to_its_own_state(status):
    with pytest.raises(InvalidTransitionError):
        transition_interview(status, status)


@pytest.mark.parametrize("status", list(ChecklistStatus))
def test_a_checklist_item_cannot_transition_to_its_own_state(status):
    with pytest.raises(InvalidTransitionError):
        transition_checklist_item(status, status)


def test_completed_is_terminal():
    assert INTERVIEW_TRANSITIONS[InterviewStatus.COMPLETED] == frozenset()


def test_a_dropped_session_reaches_completed():
    assert (
        transition_interview(InterviewStatus.IN_PROGRESS, InterviewStatus.COMPLETED)
        is InterviewStatus.COMPLETED
    )


def test_a_session_cannot_restart_after_completing():
    assert not interview_can_transition(
        InterviewStatus.COMPLETED, InterviewStatus.IN_PROGRESS
    )


def test_an_interview_cannot_skip_the_checklist():
    assert not interview_can_transition(InterviewStatus.CREATED, InterviewStatus.READY)


def test_error_message_names_both_states():
    with pytest.raises(InvalidTransitionError) as excinfo:
        transition_interview(InterviewStatus.COMPLETED, InterviewStatus.READY)
    message = str(excinfo.value)
    assert "completed" in message
    assert "ready" in message
