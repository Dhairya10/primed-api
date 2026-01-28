"""Data models for authentication."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class JWTUser(BaseModel):
    """
    User data extracted from JWT token.

    Contains core identity information from Supabase JWT claims.
    Used for authentication and JIT (Just-In-Time) profile provisioning.

    Attributes:
        id: User UUID from 'sub' claim
        email: User email from 'email' claim
        user_metadata: Additional OAuth metadata (full_name, avatar_url, etc.)

    Example:
        >>> user = JWTUser(
        ...     id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        ...     email="user@example.com",
        ...     user_metadata={"full_name": "John Doe"}
        ... )
    """

    id: UUID
    email: str
    user_metadata: dict[str, Any] = {}
