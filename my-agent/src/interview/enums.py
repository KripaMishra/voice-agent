"""Domain enums for interviews and the checklist they run."""

from enum import Enum


class InterviewStatus(str, Enum):
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Track(str, Enum):
    RESUME = "resume"
    SITUATIONAL = "situational"
    DISCUSSION = "discussion"


class ChecklistStatus(str, Enum):
    PENDING = "pending"
    ASKED = "asked"
    ANSWERED = "answered"


class TurnRole(str, Enum):
    AGENT = "agent"
    CANDIDATE = "candidate"
