"""Pydantic schemas for skills endpoints."""

from enum import Enum
from pydantic import BaseModel, Field


class SkillZone(str, Enum):
    """Skill performance zones based on score."""

    RED = "red"  # Score 0-1: Needs work
    YELLOW = "yellow"  # Score 2-4: Developing
    GREEN = "green"  # Score 5-7: Strong


class SkillScore(BaseModel):
    """Individual skill score with zone and testing status."""

    id: str
    name: str
    score: float
    zone: SkillZone | None = Field(
        default=None,
        description="red/yellow/green zone, or null if untested",
    )
    is_tested: bool
    last_tested_at: str | None = None


class SkillMapResponse(BaseModel):
    """Response for GET /skills/me endpoint."""

    skills: list[SkillScore]
    total_completed_sessions: int
    untested_skills_count: int


class SkillInfo(BaseModel):
    """Skill metadata."""

    id: str
    name: str
    description: str | None
    current_score: float
    zone: SkillZone | None


class SessionPerformance(BaseModel):
    """Session performance summary for skill history."""

    session_id: str
    drill_title: str
    product_logo_url: str | None
    completed_at: str
    performance: str  # demonstrated, partially_demonstrated, did_not_demonstrate
    score_change: str  # e.g. "+1", "-1", "+0.5"
    score_after: float


class SkillHistoryResponse(BaseModel):
    """Response for GET /skills/me/{skill_id}/history endpoint."""

    skill: SkillInfo
    sessions: list[SessionPerformance]
    total_tested: int
