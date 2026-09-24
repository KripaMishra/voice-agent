"""Scoring a finished interview from its transcript."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fakes import FakeModel, text_chunk
from sqlalchemy import select

from interview.enums import ChecklistStatus, InterviewStatus, Track, TurnRole
from interview.models import Candidate, ChecklistItem, Interview, TaskScore, Turn
from workflows import evaluation
from workflows.evaluation import (
    EvaluationError,
    GeneratedScore,
    evaluate_interview,
    format_checklist,
    format_transcript,
    parse_scores,
    run_evaluation,
)

ITEM_ID = "item-1"


def reply(*scores: dict) -> str:
    return json.dumps({"scores": list(scores)})


@pytest.fixture
def finished_interview(database):
    def _make(*, items=("Tell me about the migration.",), with_turns=True):
        with database.session() as session:
            candidate = Candidate(
                name="Ada Lovelace", email=f"ada-{uuid4().hex[:8]}@example.com"
            )
            interview = Interview(
                candidate=candidate,
                jd_ref="jd.md",
                time_budget_s=300,
                status=InterviewStatus.COMPLETED,
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
                    status=ChecklistStatus.ANSWERED,
                )
                session.add(item)
                session.flush()
                item_ids.append(item.id)
                if with_turns:
                    session.add(
                        Turn(
                            interview_id=interview.id,
                            checklist_item_id=item.id,
                            role=TurnRole.AGENT,
                            text=text,
                        )
                    )
                    session.add(
                        Turn(
                            interview_id=interview.id,
                            checklist_item_id=item.id,
                            role=TurnRole.CANDIDATE,
                            text="I ran the cutover with no downtime.",
                        )
                    )
            return interview.id, item_ids

    return _make


def test_formats_the_checklist_with_ids():
    item = SimpleNamespace(id="abc", text="Why did you do that?")

    assert format_checklist([item]) == "- [abc] Why did you do that?"


def test_formats_the_transcript_with_speakers():
    turns = [
        SimpleNamespace(role=TurnRole.AGENT, text="  Why?  "),
        SimpleNamespace(role=TurnRole.CANDIDATE, text="Because."),
    ]

    assert format_transcript(turns) == "interviewer: Why?\ncandidate: Because."


def test_an_empty_transcript_says_so():
    assert format_transcript([]) == "(nothing was said)"


def test_parses_scores():
    scores = parse_scores(
        reply({"item_id": ITEM_ID, "score": 8, "rationale": "Specific."}), {ITEM_ID}
    )

    assert scores == [
        GeneratedScore(checklist_item_id=ITEM_ID, score=8, rationale="Specific.")
    ]


def test_accepts_a_whole_number_written_as_a_float():
    scores = parse_scores(
        reply({"item_id": ITEM_ID, "score": 7.0, "rationale": "Fine."}), {ITEM_ID}
    )

    assert scores[0].score == 7


def test_drops_scores_for_items_that_are_not_in_the_checklist():
    scores = parse_scores(
        reply(
            {"item_id": "ghost", "score": 5, "rationale": "Nope."},
            {"item_id": ITEM_ID, "score": 6, "rationale": "Real."},
        ),
        {ITEM_ID},
    )

    assert [score.checklist_item_id for score in scores] == [ITEM_ID]


@pytest.mark.parametrize("score", [-1, 11, 4.5, "seven", True, None])
def test_drops_scores_that_are_not_whole_numbers_in_range(score):
    payload = json.dumps(
        {"scores": [{"item_id": ITEM_ID, "score": score, "rationale": "Hmm."}]}
    )

    with pytest.raises(EvaluationError, match="no usable scores"):
        parse_scores(payload, {ITEM_ID})


def test_drops_entries_without_a_usable_rationale():
    with pytest.raises(EvaluationError, match="no usable scores"):
        parse_scores(
            reply({"item_id": ITEM_ID, "score": 5, "rationale": "   "}), {ITEM_ID}
        )


def test_raises_without_a_scores_list():
    with pytest.raises(EvaluationError, match="no scores list"):
        parse_scores('{"results": []}', {ITEM_ID})


def test_raises_without_json():
    with pytest.raises(EvaluationError, match="no JSON object"):
        parse_scores("I cannot score this.", {ITEM_ID})


async def test_stores_scores_for_the_interview(database, finished_interview):
    interview_id, item_ids = finished_interview()
    model = FakeModel(
        [
            text_chunk(
                reply(
                    {
                        "item_id": item_ids[0],
                        "score": 9,
                        "rationale": "Led the cutover end to end.",
                    }
                )
            )
        ]
    )

    scores = await evaluate_interview(interview_id, database=database, model=model)

    assert [score.score for score in scores] == [9]
    with database.session() as session:
        stored = session.scalars(
            select(TaskScore).where(TaskScore.interview_id == interview_id)
        ).all()
        assert [(row.checklist_item_id, row.score) for row in stored] == [
            (item_ids[0], 9)
        ]


async def test_sends_the_checklist_and_the_transcript(database, finished_interview):
    interview_id, item_ids = finished_interview()
    model = FakeModel(
        [text_chunk(reply({"item_id": item_ids[0], "score": 5, "rationale": "Okay."}))]
    )

    await evaluate_interview(interview_id, database=database, model=model)

    sent = "\n".join(str(item.content) for item in model.calls[0].chat.items)
    assert "Tell me about the migration." in sent
    assert "interviewer: Tell me about the migration." in sent
    assert "candidate: I ran the cutover with no downtime." in sent


async def test_scoring_twice_replaces_rather_than_duplicates(
    database, finished_interview
):
    interview_id, item_ids = finished_interview()
    first = FakeModel(
        [text_chunk(reply({"item_id": item_ids[0], "score": 3, "rationale": "Thin."}))]
    )
    second = FakeModel(
        [
            text_chunk(
                reply({"item_id": item_ids[0], "score": 9, "rationale": "Strong."})
            )
        ]
    )

    await evaluate_interview(interview_id, database=database, model=first)
    await evaluate_interview(interview_id, database=database, model=second)

    with database.session() as session:
        stored = session.scalars(
            select(TaskScore).where(TaskScore.interview_id == interview_id)
        ).all()
        assert [(row.score, row.rationale) for row in stored] == [(9, "Strong.")]


async def test_an_interview_without_a_checklist_cannot_be_scored(database):
    with database.session() as session:
        candidate = Candidate(name="Ada", email="ada@example.com")
        interview = Interview(
            candidate=candidate,
            jd_ref="jd.md",
            time_budget_s=300,
            status=InterviewStatus.COMPLETED,
        )
        session.add(interview)
        session.flush()
        interview_id = interview.id

    with pytest.raises(EvaluationError, match="no checklist"):
        await evaluate_interview(interview_id, database=database, model=FakeModel())


async def test_an_unknown_interview_cannot_be_scored(database):
    with pytest.raises(EvaluationError, match="no interview"):
        await evaluate_interview("nope", database=database, model=FakeModel())


async def test_run_evaluation_never_raises(database, monkeypatch):
    def exploding_llm(**_kwargs):
        raise RuntimeError("no model configured")

    monkeypatch.setattr(evaluation, "inference", SimpleNamespace(LLM=exploding_llm))

    await run_evaluation(
        "does-not-matter",
        settings=SimpleNamespace(workflow_model="x"),
        database=database,
    )


def test_ending_an_interview_runs_scoring(api_client, api_database, monkeypatch):
    started: list[str] = []

    async def record(interview_id, *, database, model):
        started.append(interview_id)

    monkeypatch.setattr(evaluation, "evaluate_interview", record)

    candidate_id = api_client.post(
        "/candidate/add", json={"name": "Ada", "email": "ada@example.com"}
    ).json()["id"]
    interview_id = api_client.post(
        "/interview/create", json={"candidate_id": candidate_id, "jd_ref": "jd.md"}
    ).json()["id"]

    with api_database.session() as session:
        session.get(Interview, interview_id).status = InterviewStatus.IN_PROGRESS

    api_client.post(f"/interview/{interview_id}/end")

    assert started == [interview_id]
