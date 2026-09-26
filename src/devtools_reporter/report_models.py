from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BuildState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class ReleaseDecision(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class BuildEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: str = Field(min_length=1, max_length=100)
    state: BuildState
    duration_seconds: float = Field(ge=0)
    detail: str = Field(min_length=1, max_length=500)


class ReleaseOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    commit_sha: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    environment: str = Field(min_length=1, max_length=50)
    started_at: datetime

    @field_validator("started_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("started_at must include a timezone")
        return value


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    operation: ReleaseOperation
    events: list[BuildEvent] = Field(min_length=1)


class ReportAccepted(BaseModel):
    release_id: str
    decision: ReleaseDecision
    message_id: str
    report_url: str


def decide_release(events: list[BuildEvent]) -> ReleaseDecision:
    return (
        ReleaseDecision.BLOCKED
        if any(event.state is BuildState.FAILED for event in events)
        else ReleaseDecision.READY
    )
