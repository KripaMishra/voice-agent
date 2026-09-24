"""One interview, from adding a candidate through to a scored transcript.

Everything below the voice layer is real here: the document store, the
checklist job, the session's turn recording, the state machine, and the
evaluator. Only the model and the search are faked, because the point is to
prove the wiring between the pieces rather than the quality of any prompt.
"""

import json
import re
from types import SimpleNamespace

import pytest
from conftest import TEST_LIVEKIT_API_KEY, TEST_LIVEKIT_API_SECRET, TEST_LIVEKIT_URL
from fakes import FakeModel, FakeStream, RecordingSearch, text_chunk
from fastapi.testclient import TestClient

from api.app import create_app
from config import Settings
from interview.enums import TurnRole
from workflows import evaluation, preparation
from workflows.session import InterviewSession

CHECKLIST = json.dumps(
    {
        "items": [
            {"track": "resume", "text": "Tell me about the dispatch migration."},
            {"track": "situational", "text": "How would you route 40,000 loads?"},
            {"track": "discussion", "text": "Where would this pipeline break first?"},
        ]
    }
)

RESUME = """\
Ada Lovelace — backend engineer, ten years. Led the dispatch migration at
Acme Freight and ran the cutover with no downtime.
"""

JD = "Backend Engineer. We move freight and are rebuilding the routing layer."

ANSWER = "I ran the cutover in stages and watched the p99."


class ScoresItemsFromThePrompt:
    """Scores whatever checklist ids it is handed, so scores match real items."""

    def __init__(self, *, limit: int | None = None) -> None:
        self.limit = limit
        self.calls = 0

    def chat(self, *, chat_ctx, tools=None, **_kwargs):
        self.calls += 1
        prompt = "\n".join(
            str(item.content) for item in chat_ctx.items if hasattr(item, "content")
        )
        ids = re.findall(r"- \[(\w+)\]", prompt)
        if self.limit is not None:
            ids = ids[: self.limit]
        return FakeStream(
            [
                text_chunk(
                    json.dumps(
                        {
                            "scores": [
                                {
                                    "item_id": item_id,
                                    "score": 7,
                                    "rationale": "Reasonable.",
                                }
                                for item_id in ids
                            ]
                        }
                    )
                )
            ]
        )


@pytest.fixture
def wired(api_database, tmp_path, monkeypatch):
    (tmp_path / "resume.md").write_text(RESUME, encoding="utf-8")
    (tmp_path / "jd.md").write_text(JD, encoding="utf-8")

    checklist_model = FakeModel([text_chunk(CHECKLIST)])
    scorer = ScoresItemsFromThePrompt()

    monkeypatch.setattr(
        preparation, "inference", SimpleNamespace(LLM=lambda **_: checklist_model)
    )
    monkeypatch.setattr(
        preparation, "build_search", lambda _settings: RecordingSearch()
    )
    monkeypatch.setattr(
        evaluation, "inference", SimpleNamespace(LLM=lambda **_: scorer)
    )

    settings = Settings(
        documents_dir=str(tmp_path),
        livekit_url=TEST_LIVEKIT_URL,
        livekit_api_key=TEST_LIVEKIT_API_KEY,
        livekit_api_secret=TEST_LIVEKIT_API_SECRET,
    )
    with TestClient(create_app(api_database, settings)) as client:
        yield SimpleNamespace(client=client, database=api_database, scorer=scorer)


def add_candidate(client) -> str:
    return client.post(
        "/candidate/add",
        json={
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "resume_ref": "resume.md",
        },
    ).json()["id"]


def create_interview(client, candidate_id: str) -> str:
    return client.post(
        "/interview/create", json={"candidate_id": candidate_id, "jd_ref": "jd.md"}
    ).json()["id"]


def test_a_candidate_becomes_a_scored_interview(wired):
    client = wired.client

    created = client.post(
        "/interview/create",
        json={"candidate_id": add_candidate(client), "jd_ref": "jd.md"},
    ).json()

    prepared = client.get(f"/interview/{created['id']}").json()
    item_ids = [item["id"] for item in prepared["checklist_items"]]

    started = client.post(f"/interview/{created['id']}/start").json()

    # What the voice agent does while the session runs.
    session = InterviewSession(created["id"], wired.database)
    for item in prepared["checklist_items"]:
        session.record_turn(TurnRole.AGENT, item["text"], checklist_item_id=item["id"])
        session.record_turn(TurnRole.CANDIDATE, ANSWER, checklist_item_id=item["id"])
        session.mark_answered(item["id"])

    ended = client.post(f"/interview/{created['id']}/end").json()
    final = client.get(f"/interview/{created['id']}").json()

    assert created["status"] == "preparing"
    assert created["time_budget_s"] == 300

    assert prepared["status"] == "ready"
    assert {item["track"] for item in prepared["checklist_items"]} == {
        "resume",
        "situational",
        "discussion",
    }

    assert started["status"] == "in_progress"
    assert started["started_at"] is not None
    assert started["room_id"] == f"interview-{created['id']}"
    assert started["token"]

    assert ended["status"] == "completed"
    assert ended["ended_at"] is not None

    assert final["status"] == "completed"
    assert [turn["role"] for turn in final["turns"]] == ["agent", "candidate"] * 3
    assert final["turns"][0]["text"] == "Tell me about the dispatch migration."
    assert [item["status"] for item in final["checklist_items"]] == ["answered"] * 3

    assert [score["score"] for score in final["task_scores"]] == [7, 7, 7]
    assert {score["checklist_item_id"] for score in final["task_scores"]} == set(
        item_ids
    )
    assert wired.scorer.calls == 1


def test_a_session_where_nothing_was_said_is_still_scored(wired):
    wired.scorer.limit = 1
    client = wired.client

    interview_id = create_interview(client, add_candidate(client))
    client.post(f"/interview/{interview_id}/start")
    client.post(f"/interview/{interview_id}/end")

    final = client.get(f"/interview/{interview_id}").json()

    assert final["status"] == "completed"
    assert final["turns"] == []
    assert len(final["task_scores"]) == 1
    assert final["task_scores"][0]["score"] == 7


def test_a_finished_interview_cannot_be_scored_again(wired):
    client = wired.client

    interview_id = create_interview(client, add_candidate(client))
    client.post(f"/interview/{interview_id}/start")
    client.post(f"/interview/{interview_id}/end")
    client.post(f"/interview/{interview_id}/end")

    assert wired.scorer.calls == 1
