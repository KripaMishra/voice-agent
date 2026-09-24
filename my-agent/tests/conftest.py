from uuid import uuid4

import pytest

from interview.db import Database
from interview.enums import Track
from interview.models import Candidate, ChecklistItem, Interview


@pytest.fixture
def database(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_all()
    yield db
    db.dispose()


@pytest.fixture
def session(database):
    with database.session() as active:
        yield active


@pytest.fixture
def build_interview():
    def _build(session, *, items=("Q1", "Q2"), **overrides):
        candidate = Candidate(
            name="Ada Lovelace", email=f"ada-{uuid4().hex[:8]}@example.com"
        )
        interview = Interview(
            candidate=candidate,
            jd_ref="jd/backend-engineer.md",
            time_budget_s=300,
            **overrides,
        )
        for position, text in enumerate(items):
            interview.checklist_items.append(
                ChecklistItem(track=Track.RESUME, text=text, position=position)
            )
        session.add(interview)
        session.flush()
        return interview

    return _build
