from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import exc, text

from interview.db import Database
from interview.enums import (
    ChecklistStatus,
    InterviewStatus,
    Track,
    TurnRole,
)
from interview.models import Candidate, ChecklistItem, Interview, TaskScore, Turn


def test_creates_the_database_directory(tmp_path):
    target = tmp_path / "nested" / "deeper" / "test.db"
    db = Database(f"sqlite:///{target}")
    db.create_all()
    assert target.exists()
    db.dispose()


def test_candidate_round_trips(database):
    with database.session() as session:
        candidate = Candidate(name="Ada Lovelace", email="ada@example.com")
        session.add(candidate)
        session.flush()
        candidate_id = candidate.id

    with database.session() as session:
        loaded = session.get(Candidate, candidate_id)
        assert loaded is not None
        assert loaded.name == "Ada Lovelace"
        assert loaded.resume_ref is None


def test_an_interview_starts_in_created(session, build_interview):
    interview = build_interview(session)
    assert interview.status is InterviewStatus.CREATED
    assert interview.room_id is None
    assert interview.started_at is None
    assert interview.ended_at is None
    assert interview.created_at is not None


def test_checklist_items_start_pending_and_keep_their_order(session, build_interview):
    interview = build_interview(session, items=("first", "second", "third"))
    assert [item.position for item in interview.checklist_items] == [0, 1, 2]
    assert [item.text for item in interview.checklist_items] == [
        "first",
        "second",
        "third",
    ]
    assert all(
        item.status is ChecklistStatus.PENDING for item in interview.checklist_items
    )


def test_turns_come_back_in_time_order(session, build_interview):
    interview = build_interview(session)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    interview.turns.append(
        Turn(role=TurnRole.AGENT, text="second", ts=base + timedelta(seconds=5))
    )
    interview.turns.append(Turn(role=TurnRole.CANDIDATE, text="first", ts=base))
    session.flush()
    session.expire(interview, ["turns"])
    assert [turn.text for turn in interview.turns] == ["first", "second"]


def test_enums_are_stored_as_their_values(session, build_interview):
    interview = build_interview(session)
    interview.checklist_items[0].track = Track.SITUATIONAL
    session.flush()

    status = session.execute(
        text("SELECT status FROM interview WHERE id = :id"), {"id": interview.id}
    ).scalar()
    track = session.execute(
        text("SELECT track FROM checklist_item WHERE interview_id = :id"),
        {"id": interview.id},
    ).scalar()

    assert status == "created"
    assert track == "situational"


def test_deleting_a_candidate_removes_interviews_and_children(session, build_interview):
    interview = build_interview(session)
    interview_id = interview.id
    interview.turns.append(Turn(role=TurnRole.AGENT, text="hello"))
    session.flush()

    assert session.execute(text("SELECT COUNT(*) FROM checklist_item")).scalar() == 2
    assert session.execute(text("SELECT COUNT(*) FROM turn")).scalar() == 1

    session.delete(interview.candidate)
    session.flush()

    assert session.get(Interview, interview_id) is None
    remaining_items = session.execute(
        text("SELECT COUNT(*) FROM checklist_item")
    ).scalar()
    remaining_turns = session.execute(text("SELECT COUNT(*) FROM turn")).scalar()

    assert remaining_items == 0
    assert remaining_turns == 0


def test_deleting_an_interview_removes_its_checklist_items(session, build_interview):
    interview = build_interview(session)
    item_ids = [item.id for item in interview.checklist_items]

    session.delete(interview)
    session.flush()

    assert all(session.get(ChecklistItem, item_id) is None for item_id in item_ids)


def test_duplicate_candidate_email_is_rejected(session):
    session.add(Candidate(name="First", email="dup@example.com"))
    session.flush()
    session.add(Candidate(name="Second", email="dup@example.com"))
    with pytest.raises(exc.IntegrityError):
        session.flush()
    session.rollback()


def test_duplicate_checklist_position_is_rejected(session, build_interview):
    interview = build_interview(session)
    session.add(
        ChecklistItem(
            interview_id=interview.id,
            track=Track.RESUME,
            text="clashes with position zero",
            position=0,
        )
    )
    with pytest.raises(exc.IntegrityError):
        session.flush()
    session.rollback()


def test_one_score_per_checklist_item(session, build_interview):
    interview = build_interview(session)
    item = interview.checklist_items[0]
    for score in (7, 8):
        session.add(
            TaskScore(
                interview_id=interview.id,
                checklist_item_id=item.id,
                score=score,
                rationale="reason",
            )
        )
    with pytest.raises(exc.IntegrityError):
        session.flush()
    session.rollback()


@pytest.mark.parametrize("score", [-1, 11])
def test_scores_outside_zero_to_ten_are_rejected(session, build_interview, score):
    interview = build_interview(session)
    item = interview.checklist_items[0]
    session.add(
        TaskScore(
            interview_id=interview.id,
            checklist_item_id=item.id,
            score=score,
            rationale="out of range",
        )
    )
    with pytest.raises(exc.IntegrityError):
        session.flush()
    session.rollback()


def test_foreign_keys_are_enforced(session):
    session.add(
        Interview(candidate_id="no-such-candidate", jd_ref="jd.md", time_budget_s=300)
    )
    with pytest.raises(exc.IntegrityError):
        session.flush()
    session.rollback()


def test_a_turn_can_exist_without_a_checklist_item(session, build_interview):
    interview = build_interview(session)
    interview.turns.append(Turn(role=TurnRole.AGENT, text="Welcome."))
    session.flush()
    assert interview.turns[0].checklist_item_id is None
