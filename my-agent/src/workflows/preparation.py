"""Turning a created interview into a ready one.

Runs as an async job: the interview exists in `preparing` before this starts,
and only reaches `ready` once its checklist is stored. A failure leaves it in
`preparing`, which is the behaviour the PRD specifies; retry is still open.
"""

import logging
from pathlib import Path

from livekit.agents import inference
from livekit.agents.llm import LLM

from config import Settings
from interview.db import Database
from interview.enums import InterviewStatus
from interview.models import ChecklistItem, Interview
from interview.state import InvalidTransitionError, transition_interview
from workflows.checklist import generate_checklist
from workflows.documents import DocumentStore
from workflows.search import WebSearch, build_search

logger = logging.getLogger("workflows.preparation")


class PreparationError(RuntimeError):
    """Raised when an interview cannot be prepared."""


async def prepare_interview(
    interview_id: str,
    *,
    database: Database,
    documents: DocumentStore,
    model: LLM,
    search: WebSearch,
) -> None:
    with database.session() as session:
        interview = session.get(Interview, interview_id)
        if interview is None:
            raise PreparationError(f"no interview {interview_id!r}")
        if interview.status is not InterviewStatus.PREPARING:
            raise PreparationError(
                f"interview {interview_id!r} is {interview.status.value}, not preparing"
            )
        resume_ref = interview.candidate.resume_ref
        jd_ref = interview.jd_ref
        time_budget_s = interview.time_budget_s

    if not resume_ref:
        raise PreparationError("the candidate has no resume")

    items = await generate_checklist(
        model=model,
        search=search,
        resume=documents.read(resume_ref),
        jd=documents.read(jd_ref),
        time_budget_s=time_budget_s,
    )

    with database.session() as session:
        interview = session.get(Interview, interview_id)
        if interview is None:
            raise PreparationError(f"interview {interview_id!r} disappeared")
        for position, item in enumerate(items):
            session.add(
                ChecklistItem(
                    interview_id=interview_id,
                    track=item.track,
                    text=item.text,
                    position=position,
                )
            )
        try:
            interview.status = transition_interview(
                interview.status, InterviewStatus.READY
            )
        except InvalidTransitionError as exc:
            raise PreparationError(str(exc)) from exc

    logger.info("interview %s is ready with %d questions", interview_id, len(items))


async def run_preparation(
    interview_id: str, *, settings: Settings, database: Database
) -> None:
    """Background entry point. Never raises, so the job cannot take the app down."""
    try:
        await prepare_interview(
            interview_id,
            database=database,
            documents=DocumentStore(Path(settings.documents_dir)),
            model=inference.LLM(model=settings.workflow_model),
            search=build_search(settings),
        )
    except Exception:
        logger.exception(
            "checklist generation failed for interview %s; it stays in preparing",
            interview_id,
        )
