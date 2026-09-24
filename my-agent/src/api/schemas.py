"""Request and response models for the HTTP API."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
