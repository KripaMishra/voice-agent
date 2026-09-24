"""Interview lifecycle endpoints."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.dependencies import DatabaseDep, SessionDep, SettingsDep
from api.schemas import (
    InterviewCreate,
    InterviewDetail,
    InterviewRead,
    InterviewStarted,
)
from config import ConfigurationError
from interview.enums import InterviewStatus
from interview.models import Candidate, Interview, utcnow
from interview.state import InvalidTransitionError, transition_interview
from interview.tokens import build_candidate_token, room_name_for
from workflows.evaluation import run_evaluation
from workflows.preparation import run_preparation

router = APIRouter(prefix="/interview", tags=["interview"])


def load_interview(session: Session, interview_id: str) -> Interview:
    interview = session.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such interview")
    return interview


def advance(interview: Interview, target: InterviewStatus) -> None:
    try:
        interview.status = transition_interview(interview.status, target)
    except InvalidTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post(
    "/create", response_model=InterviewRead, status_code=status.HTTP_201_CREATED
)
def create_interview(
    payload: InterviewCreate,
    session: SessionDep,
    settings: SettingsDep,
    database: DatabaseDep,
    background: BackgroundTasks,
) -> Interview:
    if session.get(Candidate, payload.candidate_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such candidate")

    interview = Interview(
        candidate_id=payload.candidate_id,
        jd_ref=payload.jd_ref,
        time_budget_s=payload.time_budget_s or settings.session_budget_s,
        status=InterviewStatus.CREATED,
    )
    advance(interview, InterviewStatus.PREPARING)
    session.add(interview)
    session.flush()

    # Commit before handing off, so the job cannot start against an interview
    # that the request's own transaction has not written yet.
    session.commit()

    background.add_task(
        run_preparation, interview.id, settings=settings, database=database
    )
    return interview


@router.post("/{interview_id}/start", response_model=InterviewStarted)
def start_interview(
    interview_id: str, session: SessionDep, settings: SettingsDep
) -> InterviewStarted:
    interview = load_interview(session, interview_id)

    try:
        livekit_url, api_key, api_secret = settings.livekit_credentials()
    except ConfigurationError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    if interview.status is not InterviewStatus.IN_PROGRESS:
        advance(interview, InterviewStatus.IN_PROGRESS)
        interview.started_at = utcnow()

    if interview.room_id is None:
        interview.room_id = room_name_for(interview.id)
    session.flush()

    return InterviewStarted(
        **InterviewRead.model_validate(interview).model_dump(),
        token=build_candidate_token(
            room_name=interview.room_id, api_key=api_key, api_secret=api_secret
        ),
        livekit_url=livekit_url,
    )


@router.post("/{interview_id}/end", response_model=InterviewRead)
def end_interview(
    interview_id: str,
    session: SessionDep,
    settings: SettingsDep,
    database: DatabaseDep,
    background: BackgroundTasks,
) -> Interview:
    interview = load_interview(session, interview_id)
    if interview.status is InterviewStatus.COMPLETED:
        return interview
    advance(interview, InterviewStatus.COMPLETED)
    interview.ended_at = utcnow()

    # Commit before handing off, for the same reason create does.
    session.commit()

    background.add_task(
        run_evaluation, interview.id, settings=settings, database=database
    )
    return interview


@router.get("/{interview_id}", response_model=InterviewDetail)
def get_interview(interview_id: str, session: SessionDep) -> Interview:
    interview = session.scalar(
        select(Interview)
        .where(Interview.id == interview_id)
        .options(
            selectinload(Interview.checklist_items),
            selectinload(Interview.turns),
            selectinload(Interview.task_scores),
        )
    )
    if interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such interview")
    return interview
