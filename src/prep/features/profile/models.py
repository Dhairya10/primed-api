"""Pydantic models for profile feature."""

from pydantic import BaseModel, Field


class ProfileScreenResponse(BaseModel):
    """Response model for profile screen endpoint."""

    first_name: str | None = Field(None, description="User's first name")
    last_name: str | None = Field(None, description="User's last name")
    email: str = Field(description="User's email address")
    num_drills_left: int = Field(ge=0, description="Number of drill credits remaining for the user")
    discipline: str | None = Field(None, description="User's target discipline")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "num_drills_left": 10,
                "discipline": "product",
            }
        }
