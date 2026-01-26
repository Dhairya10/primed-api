"""Request and response validators for drill session endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CheckDrillEligibilityResponse(BaseModel):
    """Eligibility check for drills (similar to interviews)."""

    eligible: bool = Field(description="Whether user is eligible to start a drill")
    num_drills: int = Field(ge=0, description="Number of drills remaining")
    message: str = Field(description="Human-readable message about eligibility status")


class DrillSessionStartRequest(BaseModel):
    """Request model for starting a drill session."""

    problem_id: UUID


class DrillSessionStartResponse(BaseModel):
    """Response model for starting a drill session."""

    session_id: UUID
    signed_url: str  # Empty - voice agent deprecated
    status: str  # Session status
    message: str
    problem: dict  # Includes: id, display_title, title, description, discipline, problem_type
    started_at: datetime


class DrillSessionStatusResponse(BaseModel):
    """Response model for drill session status."""

    session_id: UUID
    status: str  # in_progress, completed, abandoned
    started_at: datetime
    completed_at: datetime | None = None
    duration_minutes: float | None = None
    has_transcript: bool
    has_feedback_summary: bool  # Feedback available


class AbandonDrillSessionRequest(BaseModel):
    """Request model for abandoning drill session."""

    exit_feedback: dict | None = None


class AbandonDrillSessionResponse(BaseModel):
    """Response model for abandon drill endpoint."""

    session_id: UUID
    status: str  # Should be "abandoned"
    abandoned_at: str
