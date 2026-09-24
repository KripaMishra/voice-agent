"""Persistent entities: candidates, interviews, checklist items, turns, scores."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from interview.enums import ChecklistStatus, InterviewStatus, Track, TurnRole


class Base(DeclarativeBase):
    pass


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


def _enum_column(enum_type: type[Enum], length: int) -> SAEnum:
    return SAEnum(
        enum_type,
        values_callable=lambda enum: [member.value for member in enum],
        native_enum=False,
        length=length,
        validate_strings=True,
    )


class Candidate(Base):
    __tablename__ = "candidate"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    resume_ref: Mapped[str | None] = mapped_column(String(500), default=None)

    interviews: Mapped[list[Interview]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class Interview(Base):
    __tablename__ = "interview"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    jd_ref: Mapped[str] = mapped_column(String(500))
    room_id: Mapped[str | None] = mapped_column(String(200), default=None)
    status: Mapped[InterviewStatus] = mapped_column(
        _enum_column(InterviewStatus, 16), default=InterviewStatus.CREATED
    )
    time_budget_s: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    candidate: Mapped[Candidate] = relationship(back_populates="interviews")
    checklist_items: Mapped[list[ChecklistItem]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="ChecklistItem.position",
    )
    turns: Mapped[list[Turn]] = relationship(
        back_populates="interview", cascade="all, delete-orphan", order_by="Turn.ts"
    )
    task_scores: Mapped[list[TaskScore]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )


class ChecklistItem(Base):
    __tablename__ = "checklist_item"
    __table_args__ = (
        UniqueConstraint("interview_id", "position", name="uq_checklist_item_position"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    interview_id: Mapped[str] = mapped_column(
        ForeignKey("interview.id", ondelete="CASCADE"), index=True
    )
    track: Mapped[Track] = mapped_column(_enum_column(Track, 16))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[ChecklistStatus] = mapped_column(
        _enum_column(ChecklistStatus, 16), default=ChecklistStatus.PENDING
    )
    position: Mapped[int] = mapped_column(Integer)

    interview: Mapped[Interview] = relationship(back_populates="checklist_items")
    task_scores: Mapped[list[TaskScore]] = relationship(back_populates="checklist_item")


class Turn(Base):
    __tablename__ = "turn"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    interview_id: Mapped[str] = mapped_column(
        ForeignKey("interview.id", ondelete="CASCADE"), index=True
    )
    checklist_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("checklist_item.id", ondelete="SET NULL"), default=None
    )
    role: Mapped[TurnRole] = mapped_column(_enum_column(TurnRole, 16))
    text: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="turns")


class TaskScore(Base):
    __tablename__ = "task_score"
    __table_args__ = (
        UniqueConstraint(
            "interview_id", "checklist_item_id", name="uq_task_score_per_item"
        ),
        CheckConstraint("score >= 0 AND score <= 10", name="ck_task_score_range"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    interview_id: Mapped[str] = mapped_column(
        ForeignKey("interview.id", ondelete="CASCADE"), index=True
    )
    checklist_item_id: Mapped[str] = mapped_column(
        ForeignKey("checklist_item.id", ondelete="CASCADE")
    )
    score: Mapped[int] = mapped_column(Integer)
    rationale: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    interview: Mapped[Interview] = relationship(back_populates="task_scores")
    checklist_item: Mapped[ChecklistItem] = relationship(back_populates="task_scores")
