"""Request and response models for the HTTP API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from interview.enums import ChecklistStatus, InterviewStatus, Track, TurnRole


class CandidateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    resume_ref: str | None = Field(default=None, max_length=500)


class CandidateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    resume_ref: str | None = Field(default=None, max_length=500)


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    resume_ref: str | None


class InterviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    jd_ref: str = Field(min_length=1, max_length=500)
    time_budget_s: int | None = Field(default=None, gt=0)


class InterviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    jd_ref: str
    room_id: str | None
    status: InterviewStatus
    time_budget_s: int
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


class ChecklistItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    track: Track
    text: str
    status: ChecklistStatus
    position: int


class TurnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: TurnRole
    text: str
    ts: datetime
    checklist_item_id: str | None


class TaskScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    checklist_item_id: str
    score: int
    rationale: str


class InterviewDetail(InterviewRead):
    model_config = ConfigDict(from_attributes=True)

    checklist_items: list[ChecklistItemRead]
    turns: list[TurnRead]
    task_scores: list[TaskScoreRead]


class InterviewStarted(InterviewRead):
    token: str
    livekit_url: str
