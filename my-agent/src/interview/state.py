"""Legal state changes for an interview and for its checklist items."""

from collections.abc import Mapping
from enum import Enum
from typing import TypeVar

from interview.enums import ChecklistStatus, InterviewStatus

StateT = TypeVar("StateT", bound=Enum)


class InvalidTransitionError(ValueError):
    """Raised when a state change is not part of the workflow."""


INTERVIEW_TRANSITIONS: Mapping[InterviewStatus, frozenset[InterviewStatus]] = {
    InterviewStatus.CREATED: frozenset({InterviewStatus.PREPARING}),
    InterviewStatus.PREPARING: frozenset({InterviewStatus.READY}),
    InterviewStatus.READY: frozenset({InterviewStatus.IN_PROGRESS}),
    InterviewStatus.IN_PROGRESS: frozenset({InterviewStatus.COMPLETED}),
    InterviewStatus.COMPLETED: frozenset(),
}

CHECKLIST_TRANSITIONS: Mapping[ChecklistStatus, frozenset[ChecklistStatus]] = {
    ChecklistStatus.PENDING: frozenset({ChecklistStatus.ASKED}),
    ChecklistStatus.ASKED: frozenset({ChecklistStatus.ANSWERED}),
    ChecklistStatus.ANSWERED: frozenset(),
}


def _transition(
    current: StateT,
    target: StateT,
    table: Mapping[StateT, frozenset[StateT]],
    kind: str,
) -> StateT:
    if target not in table.get(current, frozenset()):
        raise InvalidTransitionError(
            f"cannot move {kind} from {current.value!r} to {target.value!r}"
        )
    return target


def can_transition(
    current: StateT, target: StateT, table: Mapping[StateT, frozenset[StateT]]
) -> bool:
    return target in table.get(current, frozenset())


def transition_interview(
    current: InterviewStatus, target: InterviewStatus
) -> InterviewStatus:
    return _transition(current, target, INTERVIEW_TRANSITIONS, "interview")


def transition_checklist_item(
    current: ChecklistStatus, target: ChecklistStatus
) -> ChecklistStatus:
    return _transition(current, target, CHECKLIST_TRANSITIONS, "checklist item")


def interview_can_transition(current: InterviewStatus, target: InterviewStatus) -> bool:
    return can_transition(current, target, INTERVIEW_TRANSITIONS)


def checklist_item_can_transition(
    current: ChecklistStatus, target: ChecklistStatus
) -> bool:
    return can_transition(current, target, CHECKLIST_TRANSITIONS)
