"""Pydantic models for database entities."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DisciplineType(str, Enum):
    """User discipline categories for multi-discipline interview platform."""

    PRODUCT = "product"
    DESIGN = "design"
    ENGINEERING = "engineering"
    MARKETING = "marketing"


class DrillSessionStatus(str, Enum):
    """Drill session lifecycle status."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class EvaluationStatus(str, Enum):
    """AI feedback generation status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProblemType(str, Enum):
    """Problem statement types for interview questions."""

    BEHAVIORAL = "behavioral"
    GUESSTIMATION = "guesstimation"
    METRICS = "metrics"
    PROBLEM_SOLVING = "problem_solving"
    PRODUCT_DESIGN = "product_design"
    PRODUCT_IMPROVEMENT = "product_improvement"
    PRODUCT_STRATEGY = "product_strategy"
    DESIGN_APPROACH = "design_approach"
    USER_RESEARCH = "user_research"
    CAMPAIGN_STRATEGY = "campaign_strategy"
    CHANNEL_STRATEGY = "channel_strategy"
    GROWTH = "growth"
    MARKET_ANALYSIS = "market_analysis"


class EvaluationCriteria(BaseModel):
    """Evaluation criteria structure for problem statements."""

    categories: list[dict[str, Any]]
    total_weight: int = Field(default=100, ge=100, le=100)


class Drill(BaseModel):
    """Drill model."""

    id: UUID
    title: str = Field(max_length=255)
    display_title: str | None = None
    discipline: DisciplineType
    problem_type: ProblemType | None = None
    description: str | None = None
    is_active: bool = Field(default=False)
    created_at: datetime
    updated_at: datetime


class DrillCreate(BaseModel):
    """Schema for creating a drill."""

    title: str = Field(max_length=255)
    display_title: str | None = None
    discipline: DisciplineType
    is_active: bool = False


class DrillResponse(BaseModel):
    """Drill discovery response for home screen."""

    id: UUID
    display_title: str
    discipline: DisciplineType
    problem_type: ProblemType | None = None


class DrillSession(BaseModel):
    """Drill session model."""

    id: UUID
    user_id: UUID
    problem_id: UUID
    status: DrillSessionStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    transcript: dict[str, Any] | None = None
    feedback_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


# ============================================================================
# SEARCH MODELS
# ============================================================================


class SkillTestedInfo(BaseModel):
    """Skill information for drill cards."""

    id: UUID
    name: str


class DrillResponse(BaseModel):
    """Unified drill card response."""

    id: UUID
    title: str  # Use display_title
    description: str | None = None
    problem_type: ProblemType | None = None
    discipline: DisciplineType
    skills_tested: list[SkillTestedInfo] = Field(default_factory=list)
    is_completed: bool = False
    recommendation_reasoning: str | None = None  # Only for home screen


class DrillSearchResult(DrillResponse):
    """Search result uses same schema as drill card."""

    type: Literal["problem"] = "problem"
