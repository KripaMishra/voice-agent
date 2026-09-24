"""Candidate management endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import SessionDep
from api.schemas import CandidateCreate, CandidateRead, CandidateUpdate
from interview.models import Candidate

router = APIRouter(prefix="/candidate", tags=["candidate"])

DUPLICATE_EMAIL = "a candidate with that email already exists"


def load_candidate(session: Session, candidate_id: str) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such candidate")
    return candidate


def _flush_or_conflict(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_EMAIL) from exc


@router.post("/add", response_model=CandidateRead, status_code=status.HTTP_201_CREATED)
def add_candidate(payload: CandidateCreate, session: SessionDep) -> Candidate:
    candidate = Candidate(
        name=payload.name, email=payload.email, resume_ref=payload.resume_ref
    )
    session.add(candidate)
    _flush_or_conflict(session)
    return candidate


@router.get("/list", response_model=list[CandidateRead])
def list_candidates(session: SessionDep) -> list[Candidate]:
    return list(
        session.scalars(select(Candidate).order_by(Candidate.name, Candidate.id))
    )


@router.patch("/{candidate_id}", response_model=CandidateRead)
def update_candidate(
    candidate_id: str, payload: CandidateUpdate, session: SessionDep
) -> Candidate:
    candidate = load_candidate(session, candidate_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(candidate, field, value)
    _flush_or_conflict(session)
    return candidate


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_candidate(candidate_id: str, session: SessionDep) -> None:
    session.delete(load_candidate(session, candidate_id))
