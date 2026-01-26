"""Pydantic models for onboarding feature."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.prep.database.models import DisciplineType


class UserProfileRequest(BaseModel):
    """Request model for updating user profile."""

    discipline: DisciplineType = Field(description="User's target discipline")
    first_name: str = Field(max_length=255, description="User's first name (required)")
    last_name: str | None = Field(None, max_length=255, description="User's last name (optional)")
    onboarding_completed: bool | None = None
    bio: str | None = Field(None, max_length=500)

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "discipline": "product",
                "first_name": "John",
                "last_name": "Doe",
                "onboarding_completed": True,
            }
        }


class UserProfileResponse(BaseModel):
    """Response model for user profile."""

    id: UUID
    user_id: UUID
    discipline: str | None = None
    first_name: str
    last_name: str | None = None
    onboarding_completed: bool
    bio: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime


class UserProfileUpdateResponse(BaseModel):
    """Response model for profile update."""

    discipline: str
    first_name: str
    last_name: str | None = None
    onboarding_completed: bool
    message: str = "Profile updated successfully"
