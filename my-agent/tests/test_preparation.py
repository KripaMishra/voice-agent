"""Turning a created interview into a ready one."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fakes import FakeModel, RecordingSearch, text_chunk
from fastapi.testclient import TestClient

from api.app import create_app
from config import Settings
from interview.enums import InterviewStatus, Track
from interview.models import Candidate, Interview
from workflows import preparation
from workflows.checklist import ChecklistError
from workflows.documents import DocumentNotFoundError, DocumentStore
from workflows.preparation import PreparationError, prepare_interview, run_preparation

CHECKLIST = """{"items": [
    {"track": "resume", "text": "Tell me about the migration."},
    {"track": "discussion", "text": "How would you cache this?"}
]}"""


@pytest.fixture
def documents(tmp_path):
    (tmp_path / "resume.md").write_text("Ten years of Python.", encoding="utf-8")
    (tmp_path / "jd.md").write_text("Backend engineer.", encoding="utf-8")
    return DocumentStore(tmp_path)


@pytest.fixture
def make_interview(database):
    def _make(
        *,
        resume_ref="resume.md",
        status=InterviewStatus.PREPARING,
        jd_ref="jd.md",
        time_budget_s=300,
    ):
        with database.session() as session:
            candidate = Candidate(
                name="Ada Lovelace",
                email=f"ada-{uuid4().hex[:8]}@example.com",
                resume_ref=resume_ref,
            )
            interview = Interview(
                candidate=candidate,
                jd_ref=jd_ref,
                time_budget_s=time_budget_s,
                status=status,
            )
            session.add(interview)
            session.flush()
            return interview.id

    return _make


async def test_stores_the_checklist_and_marks_the_interview_ready(
    database, documents, make_interview
):
    interview_id = make_interview()

    await prepare_interview(
        interview_id,
        database=database,
        documents=documents,
        model=FakeModel([text_chunk(CHECKLIST)]),
        search=RecordingSearch(),
    )

    with database.session() as session:
        interview = session.get(Interview, interview_id)
        assert interview.status is InterviewStatus.READY
        assert [item.text for item in interview.checklist_items] == [
            "Tell me about the migration.",
            "How would you cache this?",
        ]
        assert [item.position for item in interview.checklist_items] == [0, 1]
        assert interview.checklist_items[0].track is Track.RESUME


async def test_passes_the_budget_through_to_the_checklist(
    database, documents, make_interview
):
    interview_id = make_interview(time_budget_s=600)
    model = FakeModel([text_chunk(CHECKLIST)])

    await prepare_interview(
        interview_id,
        database=database,
        documents=documents,
        model=model,
        search=RecordingSearch(),
    )

    assert "600 seconds" in str(model.calls[0].chat.items[0].content)


async def test_a_candidate_without_a_resume_cannot_be_prepared(
    database, documents, make_interview
):
    interview_id = make_interview(resume_ref=None)

    with pytest.raises(PreparationError, match="no resume"):
        await prepare_interview(
            interview_id,
            database=database,
            documents=documents,
            model=FakeModel([text_chunk(CHECKLIST)]),
            search=RecordingSearch(),
        )


async def test_an_interview_that_is_not_preparing_is_refused(
    database, documents, make_interview
):
    interview_id = make_interview(status=InterviewStatus.READY)

    with pytest.raises(PreparationError, match="not preparing"):
        await prepare_interview(
            interview_id,
            database=database,
            documents=documents,
            model=FakeModel([text_chunk(CHECKLIST)]),
            search=RecordingSearch(),
        )


async def test_an_unknown_interview_is_refused(database, documents):
    with pytest.raises(PreparationError, match="no interview"):
        await prepare_interview(
            "nope",
            database=database,
            documents=documents,
            model=FakeModel([text_chunk(CHECKLIST)]),
            search=RecordingSearch(),
        )


async def test_a_missing_document_stops_preparation(
    database, documents, make_interview
):
    interview_id = make_interview(jd_ref="missing.md")

    with pytest.raises(DocumentNotFoundError):
        await prepare_interview(
            interview_id,
            database=database,
            documents=documents,
            model=FakeModel([text_chunk(CHECKLIST)]),
            search=RecordingSearch(),
        )


async def test_a_failed_preparation_leaves_the_interview_preparing(
    database, documents, make_interview
):
    interview_id = make_interview()

    with pytest.raises(ChecklistError):
        await prepare_interview(
            interview_id,
            database=database,
            documents=documents,
            model=FakeModel([text_chunk("no checklist for you")]),
            search=RecordingSearch(),
        )

    with database.session() as session:
        interview = session.get(Interview, interview_id)
        assert interview.status is InterviewStatus.PREPARING
        assert interview.checklist_items == []


async def test_run_preparation_never_raises(database, tmp_path, monkeypatch):
    def exploding_llm(**_kwargs):
        raise RuntimeError("no model configured")

    monkeypatch.setattr(preparation, "inference", SimpleNamespace(LLM=exploding_llm))

    await run_preparation(
        "does-not-matter",
        settings=Settings(documents_dir=str(tmp_path)),
        database=database,
    )


def test_creating_an_interview_prepares_it(api_database, tmp_path, monkeypatch):
    (tmp_path / "resume.md").write_text("Ten years of Python.", encoding="utf-8")
    (tmp_path / "jd.md").write_text("Backend engineer.", encoding="utf-8")

    model = FakeModel([text_chunk(CHECKLIST)])
    monkeypatch.setattr(
        preparation, "inference", SimpleNamespace(LLM=lambda **_: model)
    )
    monkeypatch.setattr(
        preparation, "build_search", lambda _settings: RecordingSearch()
    )

    with TestClient(
        create_app(api_database, Settings(documents_dir=str(tmp_path)))
    ) as client:
        candidate_id = client.post(
            "/candidate/add",
            json={
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "resume_ref": "resume.md",
            },
        ).json()["id"]
        created = client.post(
            "/interview/create", json={"candidate_id": candidate_id, "jd_ref": "jd.md"}
        )
        detail = client.get(f"/interview/{created.json()['id']}").json()

    assert created.status_code == 201
    assert created.json()["status"] == "preparing"

    assert detail["status"] == "ready"
    assert [item["text"] for item in detail["checklist_items"]] == [
        "Tell me about the migration.",
        "How would you cache this?",
    ]
    assert [item["track"] for item in detail["checklist_items"]] == [
        "resume",
        "discussion",
    ]


def test_a_failed_preparation_leaves_the_api_interview_usable(
    api_database, tmp_path, monkeypatch
):
    model = FakeModel([text_chunk("not json")])
    monkeypatch.setattr(
        preparation, "inference", SimpleNamespace(LLM=lambda **_: model)
    )
    monkeypatch.setattr(
        preparation, "build_search", lambda _settings: RecordingSearch()
    )

    with TestClient(
        create_app(api_database, Settings(documents_dir=str(tmp_path)))
    ) as client:
        candidate_id = client.post(
            "/candidate/add",
            json={
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "resume_ref": "r.m",
            },
        ).json()["id"]
        created = client.post(
            "/interview/create", json={"candidate_id": candidate_id, "jd_ref": "jd.md"}
        )
        detail = client.get(f"/interview/{created.json()['id']}").json()
        started = client.post(f"/interview/{created.json()['id']}/start")

    assert created.status_code == 201
    assert detail["status"] == "preparing"
    assert detail["checklist_items"] == []
    assert started.status_code == 409
