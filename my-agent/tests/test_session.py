"""Driving a running interview: turns, checklist progress, and the clock."""

from datetime import UTC, datetime, timedelta

import pytest

from interview.enums import ChecklistStatus, InterviewStatus, TurnRole
from interview.models import ChecklistItem, Interview, Turn
from workflows.session import InterviewSession, SessionError, complete_interview

STARTED = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_records_a_turn_against_the_interview(database, make_session):
    session, item_ids = make_session()

    session.record_turn(
        TurnRole.AGENT, "Tell me about the migration.", checklist_item_id=item_ids[0]
    )
    session.record_turn(TurnRole.CANDIDATE, "I led the cutover.")

    with database.session() as db:
        turns = db.query(Turn).all()
        assert [(turn.role, turn.text) for turn in turns] == [
            (TurnRole.AGENT, "Tell me about the migration."),
            (TurnRole.CANDIDATE, "I led the cutover."),
        ]
        assert turns[0].checklist_item_id == item_ids[0]
        assert turns[1].checklist_item_id is None


def test_a_turn_cannot_be_recorded_for_an_unknown_interview(database):
    with pytest.raises(SessionError, match="no interview"):
        InterviewSession("nope", database).record_turn(TurnRole.AGENT, "Hello.")


def test_marking_asked_then_answered_walks_the_item(database, make_session):
    session, item_ids = make_session()

    session.mark_asked(item_ids[0])
    assert _status(database, item_ids[0]) is ChecklistStatus.ASKED

    session.mark_answered(item_ids[0])
    assert _status(database, item_ids[0]) is ChecklistStatus.ANSWERED


def test_answering_a_question_that_was_never_marked_asked_still_closes_it(
    database, make_session
):
    session, item_ids = make_session()

    session.mark_answered(item_ids[0])

    assert _status(database, item_ids[0]) is ChecklistStatus.ANSWERED


def test_an_answer_cannot_be_recorded_twice(database, make_session):
    session, item_ids = make_session()
    session.mark_answered(item_ids[0])

    with pytest.raises(SessionError, match="answered"):
        session.mark_answered(item_ids[0])


def test_an_item_from_another_interview_is_refused(database, make_session):
    _, (other_item,) = make_session(items=("Someone else's question.",))
    session, _ = make_session()

    with pytest.raises(SessionError, match="no checklist item"):
        session.mark_answered(other_item)


def test_pending_items_exclude_the_answered_ones(make_session):
    session, item_ids = make_session(items=("Q1", "Q2", "Q3"))

    session.mark_answered(item_ids[0])

    assert [item.id for item in session.pending_items()] == item_ids[1:]


def test_leftover_time_is_unknown_until_the_session_starts(make_session):
    session, _ = make_session(items=("Q1",))

    assert session.leftover_seconds(STARTED) is None


def test_leftover_time_counts_down_from_the_budget(make_session):
    session, _ = make_session(items=("Q1",), started_at=STARTED)

    assert session.leftover_seconds(STARTED) == 300
    assert session.leftover_seconds(STARTED + timedelta(seconds=90)) == 210


def test_a_session_is_not_finished_while_time_and_questions_remain(make_session):
    session, _ = make_session(items=("Q1",), started_at=STARTED)

    assert not session.is_finished(STARTED + timedelta(seconds=10))


def test_a_session_finishes_when_the_budget_runs_out(make_session):
    session, _ = make_session(items=("Q1", "Q2"), started_at=STARTED)

    assert session.is_finished(STARTED + timedelta(seconds=300))
    assert session.is_finished(STARTED + timedelta(seconds=301))


def test_a_session_finishes_when_the_checklist_runs_out(database, make_session):
    session, item_ids = make_session(items=("Q1",), started_at=STARTED)

    session.mark_answered(item_ids[0])

    assert session.is_finished(STARTED + timedelta(seconds=1))


def test_a_session_that_never_started_cannot_run_out_of_time(make_session):
    session, _ = make_session(items=("Q1",))

    assert not session.is_finished(STARTED + timedelta(days=1))


def test_formats_the_checklist_with_ids(make_session):
    session, item_ids = make_session(items=("Why?", "How?"))

    formatted = session.format_checklist()

    assert f"- [{item_ids[0]}] Why?" in formatted
    assert f"- [{item_ids[1]}] How?" in formatted


def test_completing_a_running_interview_stamps_the_end_time(database, make_session):
    session, _ = make_session()

    assert complete_interview(session.interview_id, database) is True

    with database.session() as db:
        interview = db.get(Interview, session.interview_id)
        assert interview.status is InterviewStatus.COMPLETED
        assert interview.ended_at is not None


def test_completing_an_interview_twice_reports_no_change(database, make_session):
    session, _ = make_session()
    complete_interview(session.interview_id, database)

    assert complete_interview(session.interview_id, database) is False


def test_an_interview_that_was_never_running_is_left_alone(database, make_session):
    session, _ = make_session(status=InterviewStatus.READY)

    assert complete_interview(session.interview_id, database) is False


def test_an_unknown_interview_reports_no_change(database):
    assert complete_interview("nope", database) is False


def test_a_session_can_complete_its_own_interview(database, make_session):
    session, _ = make_session()

    assert session.complete() is True
    assert session.complete() is False


def _status(database, item_id: str) -> ChecklistStatus:
    with database.session() as session:
        return session.get(ChecklistItem, item_id).status
