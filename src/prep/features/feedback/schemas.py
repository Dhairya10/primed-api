"""Pydantic models for drill feedback structured output."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class SkillPerformance(str, Enum):
    """Skill performance evaluation levels."""

    DEMONSTRATED = "Demonstrated"
    PARTIAL = "Partial"
    MISSED = "Missed"


class SkillFeedback(BaseModel):
    """Feedback for a specific skill."""

    skill_name: str
    evaluation: SkillPerformance
    feedback: str = Field(description="2-3 sentences explaining performance")
    improvement_suggestion: str | None = Field(
        default=None,
        description="Actionable guidance (only if not demonstrated)",
    )


class DrillFeedback(BaseModel):
    """Complete drill feedback with skill-based evaluation."""

    summary: str = Field(description="2 sentence session summary")
    skills: list[SkillFeedback] = Field(min_length=1)

    # Optional metadata (added during storage)
    evaluation_meta: dict | None = None


class SessionFeedbackData(BaseModel):
    """Feedback payload for a drill session."""

    session_id: UUID
    drill_id: UUID
    drill_title: str
    product_logo_url: str | None = None
    completed_at: datetime | None = None
    feedback: DrillFeedback | None = None


class SessionFeedbackResponse(BaseModel):
    """Response wrapper for drill session feedback."""

    data: SessionFeedbackData
