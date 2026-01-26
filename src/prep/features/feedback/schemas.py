"""Pydantic models for drill feedback structured output."""

from enum import Enum

from pydantic import BaseModel, Field


class SkillPerformance(str, Enum):
    """Skill performance evaluation levels."""

    DEMONSTRATED = "Demonstrated"
    PARTIALLY = "Partially"
    DID_NOT_DEMONSTRATE = "Did not demonstrate"


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
