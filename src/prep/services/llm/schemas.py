"""Pydantic schemas for LLM structured outputs.

These schemas are used with Gemini's response_format parameter
to ensure type-safe, validated LLM responses for various tasks.
"""

from pydantic import BaseModel, Field


class SkillScoreChange(BaseModel):
    """Individual skill score change from LLM evaluation.

    Used for structured output when LLM evaluates a drill session
    and determines how each skill performed.
    """

    skill_id: str = Field(description="Skill identifier (UUID)")
    skill_name: str = Field(description="Skill name for validation")
    score_change: float = Field(
        description="Score delta: +1 (demonstrated), +0.5 (partial), -1 (not demonstrated), or 0 (not tested)",
        ge=-1.0,
        le=1.0,
    )
    was_tested: bool = Field(description="Whether skill was tested in this drill")
    evidence: str = Field(
        description="Direct quote from transcript demonstrating performance",
        min_length=10,
    )


class SkillEvaluation(BaseModel):
    """Complete skill evaluation for a drill session.

    Used as response_format for LLM skill scoring tasks.
    """

    drill_id: str = Field(description="Drill UUID")
    user_id: str = Field(description="User UUID")
    skill_scores: list[SkillScoreChange] = Field(
        description="List of skill evaluations",
        min_length=1,
    )


class DrillRecommendation(BaseModel):
    """LLM-generated drill recommendation.

    Used when selecting the best drill from multiple eligible options.
    """

    drill_id: str = Field(description="Selected drill UUID")
    reasoning: str = Field(
        description="2-3 sentence explanation for this recommendation",
    )


class UserProfileUpdate(BaseModel):
    """LLM-generated user profile update.

    Used to extract evolving user context and patterns from drill sessions.
    """

    summary: str = Field(
        description="Updated user summary merging previous context with new insights",
        min_length=50,
        max_length=1000,
    )
    new_insights: list[str] = Field(
        description="List of new patterns, strengths, or context discovered in this session",
        min_length=1,
    )
    key_strengths: list[str] | None = Field(
        default=None,
        description="Updated list of user's key strengths (optional)",
    )
    areas_for_growth: list[str] | None = Field(
        default=None,
        description="Updated list of areas needing improvement (optional)",
    )
