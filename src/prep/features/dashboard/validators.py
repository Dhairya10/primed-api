"""Pydantic validators for dashboard API endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.prep.database.models import EvaluationStatus, ProblemType


class AttemptSummary(BaseModel):
    """Summary of a single interview attempt."""

    session_id: UUID
    completed_at: datetime
    evaluation_status: EvaluationStatus


class DashboardProblem(BaseModel):
    """Interview card with all attempts grouped."""

    interview_id: UUID
    interview_title: str
    logo_url: str | None = None
    total_attempts: int
    can_retry: bool = Field(
        description="Whether user can attempt this interview again (< max_attempts_per_problem)"
    )
    latest_attempt: AttemptSummary
    previous_attempts: list[AttemptSummary] = Field(
        default=[], max_length=4, description="Up to 4 most recent previous attempts"
    )


class DashboardPagination(BaseModel):
    """Pagination metadata for dashboard response."""

    total: int
    limit: int
    offset: int
    has_more: bool


class DashboardResponse(BaseModel):
    """Response model for GET /api/v1/dashboard endpoint."""

    problems: list[DashboardProblem]
    pagination: DashboardPagination


class FeedbackDetailResponse(BaseModel):
    """Response model for GET /api/v1/feedback/{session_id} endpoint."""

    session_id: UUID
    title: str
    completed_at: datetime
    evaluation_status: EvaluationStatus
    summary: str | None = Field(None, description="Overall interview performance summary")
    interview_readiness: str | None = Field(
        None,
        description="Readiness level: not_ready, developing, interview_ready, or strong_performance",
    )
    strengths: list[str] | None = Field(
        None, description="1-2 key strengths demonstrated in the interview"
    )
    focus_areas: list[str] | None = Field(
        None, description="1-2 critical areas to focus on for improvement"
    )


class FeedbackProcessingResponse(BaseModel):
    """Response when feedback is still being processed."""

    session_id: UUID
    evaluation_status: EvaluationStatus
    message: str
    estimated_completion: datetime | None = None


class DrillAttemptSummary(BaseModel):
    """Summary of a single drill attempt."""

    session_id: UUID
    completed_at: datetime


class DashboardDrill(BaseModel):
    """Drill card with all attempts grouped."""

    problem_id: UUID
    display_title: str
    problem_type: ProblemType | None = None
    total_attempts: int
    can_retry: bool = Field(
        description="Whether user can attempt this drill again (< max_attempts_per_problem)"
    )
    latest_attempt: DrillAttemptSummary
    previous_attempts: list[DrillAttemptSummary] = Field(
        default=[], max_length=4, description="Up to 4 most recent previous attempts"
    )


class DrillsDashboardResponse(BaseModel):
    """Response model for GET /api/v1/dashboard/drills endpoint."""

    drills: list[DashboardDrill]
    pagination: DashboardPagination


class DashboardSession(BaseModel):
    """Individual drill session for dashboard (flat list)."""

    session_id: str
    drill_id: str
    drill_title: str
    product_logo_url: str | None
    completed_at: str
    problem_type: str | None


class DashboardSessionsResponse(BaseModel):
    """Response for dashboard sessions endpoint (flat list)."""

    data: list[DashboardSession]
    total: int
