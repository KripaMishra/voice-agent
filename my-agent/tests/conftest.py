from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from config import Settings
from interview.db import Database
from interview.enums import InterviewStatus, Track
from interview.models import Candidate, ChecklistItem, Interview
from workflows.session import InterviewSession

TEST_LIVEKIT_URL = "wss://test.livekit.cloud"
TEST_LIVEKIT_API_KEY = "test-key"
TEST_LIVEKIT_API_SECRET = "test-secret-long-enough-to-satisfy-hs256"


@pytest.fixture
def database(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_all()
    yield db
    db.dispose()


@pytest.fixture
def api_database(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'api.db'}")
    yield database
    database.dispose()


@pytest.fixture
def api_settings():
    return Settings(
        livekit_url=TEST_LIVEKIT_URL,
        livekit_api_key=TEST_LIVEKIT_API_KEY,
        livekit_api_secret=TEST_LIVEKIT_API_SECRET,
    )


@pytest.fixture
def api_client(api_database, api_settings):
    with TestClient(create_app(api_database, api_settings)) as client:
        yield client


@pytest.fixture
def make_session(database):
    """An interview in the store, wrapped in a session, with its item ids."""

    def _make(*, items=("Q1", "Q2"), status=InterviewStatus.IN_PROGRESS, **overrides):
        with database.session() as session:
            candidate = Candidate(
                name="Ada Lovelace", email=f"ada-{uuid4().hex[:8]}@example.com"
            )
            interview = Interview(
                candidate=candidate,
                jd_ref="jd.md",
                time_budget_s=300,
                status=status,
                **overrides,
            )
            session.add(interview)
            session.flush()
            item_ids = []
            for position, text in enumerate(items):
                item = ChecklistItem(
                    interview_id=interview.id,
                    track=Track.RESUME,
                    text=text,
                    position=position,
                )
                session.add(item)
                session.flush()
                item_ids.append(item.id)
            return InterviewSession(interview.id, database), item_ids

    return _make


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
