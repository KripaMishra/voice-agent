"""Interview lifecycle endpoints."""

from types import SimpleNamespace

import pytest
from conftest import TEST_LIVEKIT_URL
from fastapi.testclient import TestClient
from jwt import decode

import api.routes.interviews as interviews
from api.app import create_app
from config import Settings
from interview.enums import ChecklistStatus, InterviewStatus, Track, TurnRole
from interview.models import ChecklistItem, Interview, TaskScore, Turn


@pytest.fixture(autouse=True)
def offline_jobs(monkeypatch):
    """Keep lifecycle tests off the network; the jobs are covered in their own tests."""
    preparation: list[str] = []
    evaluation: list[str] = []
    monkeypatch.setattr(
        interviews,
        "run_preparation",
        lambda interview_id, **_: preparation.append(interview_id),
    )
    monkeypatch.setattr(
        interviews,
        "run_evaluation",
        lambda interview_id, **_: evaluation.append(interview_id),
    )
    return SimpleNamespace(preparation=preparation, evaluation=evaluation)


def add_candidate(client, **overrides):
    payload = {"name": "Ada Lovelace", "email": "ada@example.com"}
    payload.update(overrides)
    return client.post("/candidate/add", json=payload).json()["id"]


def create_interview(client, candidate_id, **overrides):
    payload = {"candidate_id": candidate_id, "jd_ref": "jd/backend-engineer.md"}
    payload.update(overrides)
    return client.post("/interview/create", json=payload)


def force_status(database, interview_id, status, **fields):
    with database.session() as session:
        interview = session.get(Interview, interview_id)
        interview.status = status
        for field, value in fields.items():
            setattr(interview, field, value)


def test_create_returns_preparing(api_client):
    candidate_id = add_candidate(api_client)

    response = create_interview(api_client, candidate_id)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "preparing"
    assert body["candidate_id"] == candidate_id
    assert body["jd_ref"] == "jd/backend-engineer.md"
    assert body["room_id"] is None
    assert body["started_at"] is None
    assert body["ended_at"] is None


def test_create_defaults_the_budget_from_settings(api_database):
    with TestClient(create_app(api_database, Settings(session_budget_s=900))) as client:
        candidate_id = add_candidate(client)
        response = create_interview(client, candidate_id)

    assert response.json()["time_budget_s"] == 900


def test_create_accepts_an_explicit_budget(api_client):
    candidate_id = add_candidate(api_client)

    response = create_interview(api_client, candidate_id, time_budget_s=120)

    assert response.json()["time_budget_s"] == 120


def test_create_rejects_an_unusable_budget(api_client):
    candidate_id = add_candidate(api_client)

    assert (
        create_interview(api_client, candidate_id, time_budget_s=0).status_code == 422
    )


def test_create_for_an_unknown_candidate_is_not_found(api_client):
    assert create_interview(api_client, "no-such-candidate").status_code == 404


def test_create_rejects_unknown_fields(api_client):
    candidate_id = add_candidate(api_client)

    response = create_interview(api_client, candidate_id, track="resume")

    assert response.status_code == 422


def test_start_requires_a_ready_checklist(api_client):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]

    response = api_client.post(f"/interview/{interview_id}/start")

    assert response.status_code == 409
    assert "preparing" in response.json()["detail"]


def test_start_moves_a_ready_interview_into_progress(api_client, api_database):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]
    force_status(api_database, interview_id, InterviewStatus.READY)

    response = api_client.post(f"/interview/{interview_id}/start")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["started_at"] is not None


def test_start_returns_a_join_token_for_the_interview_room(api_client, api_database):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]
    force_status(api_database, interview_id, InterviewStatus.READY)

    body = api_client.post(f"/interview/{interview_id}/start").json()

    assert body["room_id"] == f"interview-{interview_id}"
    assert body["livekit_url"] == TEST_LIVEKIT_URL

    claims = decode(body["token"], options={"verify_signature": False})
    assert claims["sub"] == "candidate"
    assert claims["video"]["room"] == body["room_id"]
    assert claims["video"]["roomJoin"] is True


def test_start_hands_out_another_token_when_already_running(api_client, api_database):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]
    force_status(api_database, interview_id, InterviewStatus.READY)

    first = api_client.post(f"/interview/{interview_id}/start")
    second = api_client.post(f"/interview/{interview_id}/start")

    assert second.status_code == 200
    assert second.json()["room_id"] == first.json()["room_id"]
    assert second.json()["started_at"] == first.json()["started_at"]


def test_start_without_livekit_credentials_is_unavailable(api_database):
    with TestClient(create_app(api_database, Settings())) as client:
        candidate_id = add_candidate(client)
        interview_id = create_interview(client, candidate_id).json()["id"]
        force_status(api_database, interview_id, InterviewStatus.READY)

        response = client.post(f"/interview/{interview_id}/start")

        assert response.status_code == 503
        assert client.get(f"/interview/{interview_id}").json()["status"] == "ready"


def test_start_unknown_interview_is_not_found(api_client):
    assert api_client.post("/interview/nope/start").status_code == 404


def test_end_completes_a_running_interview(api_client, api_database):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]
    force_status(api_database, interview_id, InterviewStatus.IN_PROGRESS)

    response = api_client.post(f"/interview/{interview_id}/end")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["ended_at"] is not None


def test_end_is_idempotent(api_client, api_database):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]
    force_status(api_database, interview_id, InterviewStatus.IN_PROGRESS)

    first = api_client.post(f"/interview/{interview_id}/end").json()
    second = api_client.post(f"/interview/{interview_id}/end")

    assert second.status_code == 200
    assert second.json()["ended_at"] == first["ended_at"]


def test_end_rejects_an_interview_that_never_started(api_client):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]

    response = api_client.post(f"/interview/{interview_id}/end")

    assert response.status_code == 409


def test_a_completed_interview_cannot_be_restarted(api_client, api_database):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]
    force_status(api_database, interview_id, InterviewStatus.IN_PROGRESS)
    api_client.post(f"/interview/{interview_id}/end")

    assert api_client.post(f"/interview/{interview_id}/start").status_code == 409


def test_detail_includes_checklist_transcript_and_scores(api_client, api_database):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]

    with api_database.session() as session:
        interview = session.get(Interview, interview_id)
        item = ChecklistItem(
            interview_id=interview_id,
            track=Track.SITUATIONAL,
            text="Describe a hard bug you fixed.",
            position=0,
            status=ChecklistStatus.ANSWERED,
        )
        session.add(item)
        session.flush()
        session.add(
            Turn(
                interview_id=interview_id,
                checklist_item_id=item.id,
                role=TurnRole.AGENT,
                text="Tell me about a hard bug.",
            )
        )
        session.add(
            TaskScore(
                interview_id=interview_id,
                checklist_item_id=item.id,
                score=8,
                rationale="Clear and specific.",
            )
        )
        assert interview is not None

    body = api_client.get(f"/interview/{interview_id}").json()

    assert body["status"] == "preparing"
    assert [entry["text"] for entry in body["checklist_items"]] == [
        "Describe a hard bug you fixed."
    ]
    assert body["checklist_items"][0]["track"] == "situational"
    assert [entry["text"] for entry in body["turns"]] == ["Tell me about a hard bug."]
    assert body["turns"][0]["role"] == "agent"
    assert [(entry["score"], entry["rationale"]) for entry in body["task_scores"]] == [
        (8, "Clear and specific.")
    ]


def test_detail_of_a_fresh_interview_is_empty(api_client):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]

    body = api_client.get(f"/interview/{interview_id}").json()

    assert body["checklist_items"] == []
    assert body["turns"] == []
    assert body["task_scores"] == []


def test_detail_of_an_unknown_interview_is_not_found(api_client):
    assert api_client.get("/interview/nope").status_code == 404


def test_candidate_interviews_lists_their_own_in_creation_order(api_client):
    candidate_id = add_candidate(api_client)
    other_id = add_candidate(api_client, email="grace@example.com")
    first = create_interview(api_client, candidate_id, jd_ref="jd/one.md").json()["id"]
    second = create_interview(api_client, candidate_id, jd_ref="jd/two.md").json()["id"]
    create_interview(api_client, other_id, jd_ref="jd/other.md")

    body = api_client.get(f"/candidate/{candidate_id}/interviews").json()

    assert len(body) == 2
    assert {entry["id"] for entry in body} == {first, second}


def test_candidate_interviews_for_an_unknown_candidate_is_not_found(api_client):
    assert api_client.get("/candidate/nope/interviews").status_code == 404


def test_deleting_a_candidate_removes_their_interviews(api_client):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]

    api_client.delete(f"/candidate/{candidate_id}")

    assert api_client.get(f"/interview/{interview_id}").status_code == 404


def test_create_schedules_checklist_generation(api_client, offline_jobs):
    candidate_id = add_candidate(api_client)

    interview_id = create_interview(api_client, candidate_id).json()["id"]

    assert offline_jobs.preparation == [interview_id]


def test_end_schedules_scoring(api_client, api_database, offline_jobs):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]
    force_status(api_database, interview_id, InterviewStatus.IN_PROGRESS)

    api_client.post(f"/interview/{interview_id}/end")

    assert offline_jobs.evaluation == [interview_id]


def test_ending_twice_does_not_score_twice(api_client, api_database, offline_jobs):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]
    force_status(api_database, interview_id, InterviewStatus.IN_PROGRESS)

    api_client.post(f"/interview/{interview_id}/end")
    api_client.post(f"/interview/{interview_id}/end")

    assert offline_jobs.evaluation == [interview_id]


def test_interview_lifecycle_survives_a_round_trip_through_storage(
    api_client, api_database
):
    candidate_id = add_candidate(api_client)
    interview_id = create_interview(api_client, candidate_id).json()["id"]

    with api_database.session() as session:
        assert session.get(Interview, interview_id).status is InterviewStatus.PREPARING
