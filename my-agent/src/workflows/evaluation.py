"""Scoring a finished interview from its transcript."""

import logging
from dataclasses import dataclass
from typing import Any

from livekit.agents import inference
from livekit.agents.llm import LLM
from sqlalchemy import delete

from config import Settings
from interview.db import Database
from interview.enums import TurnRole
from interview.models import ChecklistItem, Interview, TaskScore, Turn
from prompts import PromptCatalog, catalog
from workflows.replies import ReplyError, as_json_object
from workflows.tool_loop import complete_with_tools

logger = logging.getLogger("workflows.evaluation")

PROMPT_NAME = "evaluation"
MIN_SCORE = 0
MAX_SCORE = 10


class EvaluationError(ReplyError):
    """Raised when an interview cannot be scored."""


@dataclass(frozen=True)
class GeneratedScore:
    checklist_item_id: str
    score: int
    rationale: str


def format_checklist(items: list[ChecklistItem]) -> str:
    return "\n".join(f"- [{item.id}] {item.text}" for item in items)


def format_transcript(turns: list[Turn]) -> str:
    if not turns:
        return "(nothing was said)"
    return "\n".join(
        f"{'interviewer' if turn.role is TurnRole.AGENT else 'candidate'}: "
        f"{turn.text.strip()}"
        for turn in turns
    )


async def evaluate_interview(
    interview_id: str,
    *,
    database: Database,
    model: LLM,
    prompts: PromptCatalog = catalog,
) -> list[GeneratedScore]:
    with database.session() as session:
        interview = session.get(Interview, interview_id)
        if interview is None:
            raise EvaluationError(f"no interview {interview_id!r}")
        item_ids = {item.id for item in interview.checklist_items}
        checklist = format_checklist(interview.checklist_items)
        transcript = format_transcript(interview.turns)

    if not item_ids:
        raise EvaluationError(f"interview {interview_id!r} has no checklist to score")

    reply = await complete_with_tools(
        model,
        system=prompts.load(PROMPT_NAME),
        user=f"# Checklist\n\n{checklist}\n\n# Transcript\n\n{transcript}",
    )
    scores = parse_scores(reply, item_ids)

    with database.session() as session:
        session.execute(delete(TaskScore).where(TaskScore.interview_id == interview_id))
        for score in scores:
            session.add(
                TaskScore(
                    interview_id=interview_id,
                    checklist_item_id=score.checklist_item_id,
                    score=score.score,
                    rationale=score.rationale,
                )
            )

    logger.info("scored %d items for interview %s", len(scores), interview_id)
    return scores


def parse_scores(reply: str, item_ids: set[str]) -> list[GeneratedScore]:
    payload = as_json_object(reply, error=EvaluationError, what="evaluation reply")
    entries = payload.get("scores")
    if not isinstance(entries, list):
        raise EvaluationError("the evaluation reply had no scores list")

    scores: list[GeneratedScore] = []
    for entry in entries:
        score = _as_score(entry, item_ids)
        if score is None:
            logger.warning("dropping an unusable score entry: %r", entry)
            continue
        scores.append(score)

    if not scores:
        raise EvaluationError("the evaluation reply had no usable scores")
    return scores


def _as_score(entry: Any, item_ids: set[str]) -> GeneratedScore | None:
    if not isinstance(entry, dict):
        return None
    item_id = entry.get("item_id")
    if item_id not in item_ids:
        return None
    score = _as_whole_number(entry.get("score"))
    if score is None or not MIN_SCORE <= score <= MAX_SCORE:
        return None
    rationale = entry.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        return None
    return GeneratedScore(item_id, score, rationale.strip())


def _as_whole_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


async def run_evaluation(
    interview_id: str, *, settings: Settings, database: Database
) -> None:
    """Background entry point. Never raises, so scoring cannot take the app down."""
    try:
        await evaluate_interview(
            interview_id,
            database=database,
            model=inference.LLM(model=settings.workflow_model),
        )
    except Exception:
        logger.exception("scoring failed for interview %s", interview_id)
