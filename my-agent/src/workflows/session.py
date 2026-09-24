"""The stateful half of a running interview.

One instance per interview. Progress lives in the store rather than in memory,
so every turn is written as it happens and the next decision reads what was
actually said.
"""

from collections.abc import Callable
from datetime import datetime

from interview.db import Database
from interview.enums import ChecklistStatus, TurnRole
from interview.models import ChecklistItem, Interview, Turn, utcnow
from interview.state import (
    InvalidTransitionError,
    transition_checklist_item,
)


class SessionError(RuntimeError):
    """Raised when a session cannot be driven."""


class InterviewSession:
    def __init__(self, interview_id: str, database: Database) -> None:
        self.interview_id = interview_id
        self._database = database

    def _interview(self, session) -> Interview:
        interview = session.get(Interview, self.interview_id)
        if interview is None:
            raise SessionError(f"no interview {self.interview_id!r}")
        return interview

    def record_turn(
        self,
        role: TurnRole,
        text: str,
        *,
        checklist_item_id: str | None = None,
        at: datetime | None = None,
    ) -> str:
        with self._database.session() as session:
            self._interview(session)
            turn = Turn(
                interview_id=self.interview_id,
                checklist_item_id=checklist_item_id,
                role=role,
                text=text,
                ts=at or utcnow(),
            )
            session.add(turn)
            session.flush()
            return turn.id

    def mark_asked(self, item_id: str) -> None:
        self._edit_item(
            item_id,
            lambda status: transition_checklist_item(status, ChecklistStatus.ASKED),
        )

    def mark_answered(self, item_id: str) -> None:
        """Close an item out. An item still pending counts as having been asked."""

        def advance(status: ChecklistStatus) -> ChecklistStatus:
            if status is ChecklistStatus.PENDING:
                status = transition_checklist_item(status, ChecklistStatus.ASKED)
            return transition_checklist_item(status, ChecklistStatus.ANSWERED)

        self._edit_item(item_id, advance)

    def _edit_item(
        self, item_id: str, advance: Callable[[ChecklistStatus], ChecklistStatus]
    ) -> None:
        with self._database.session() as session:
            self._interview(session)
            item = session.get(ChecklistItem, item_id)
            if item is None or item.interview_id != self.interview_id:
                raise SessionError(f"no checklist item {item_id!r} on this interview")
            try:
                item.status = advance(item.status)
            except InvalidTransitionError as exc:
                raise SessionError(str(exc)) from exc

    def pending_items(self) -> list[ChecklistItem]:
        with self._database.session() as session:
            interview = self._interview(session)
            return [
                item
                for item in interview.checklist_items
                if item.status is not ChecklistStatus.ANSWERED
            ]

    def leftover_seconds(self, now: datetime | None = None) -> float | None:
        """Seconds left in the budget, or None if the session never started."""
        with self._database.session() as session:
            interview = self._interview(session)
            if interview.started_at is None:
                return None
            elapsed = ((now or utcnow()) - interview.started_at).total_seconds()
            return interview.time_budget_s - elapsed

    def is_finished(self, now: datetime | None = None) -> bool:
        if not self.pending_items():
            return True
        leftover = self.leftover_seconds(now)
        return leftover is not None and leftover <= 0

    def format_checklist(self) -> str:
        with self._database.session() as session:
            interview = self._interview(session)
            return "\n".join(
                f"- [{item.id}] {item.text}" for item in interview.checklist_items
            )
