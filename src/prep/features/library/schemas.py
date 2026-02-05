from pydantic import BaseModel


class SkillSimple(BaseModel):
    """Simple skill representation."""

    id: str
    name: str


class LibraryMetadataResponse(BaseModel):
    """Response model for library metadata."""

    problem_types: list[str]
    skills: list[SkillSimple]
