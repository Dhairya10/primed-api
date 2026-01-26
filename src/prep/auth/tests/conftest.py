"""Shared fixtures for authentication tests."""

from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest


@pytest.fixture
def mock_user_id() -> UUID:
    """Provide a consistent test user ID."""
    return UUID("123e4567-e89b-12d3-a456-426614174000")


@pytest.fixture
def valid_jwt_token() -> str:
    """Provide a mock valid JWT token for testing."""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock.token"


@pytest.fixture
def auth_headers(valid_jwt_token: str) -> dict[str, str]:
    """Generate auth headers for testing."""
    return {"Authorization": f"Bearer {valid_jwt_token}"}


@pytest.fixture
def mock_supabase_client(mock_user_id: UUID) -> Mock:
    """Mock Supabase client for testing."""
    mock_client = Mock()
    mock_auth = Mock()
    mock_auth.get_claims.return_value = {"sub": str(mock_user_id)}
    mock_client.auth = mock_auth
    return mock_client


@pytest.fixture
def mock_jwt_claims(mock_user_id: UUID) -> dict[str, Any]:
    """Provide mock JWT claims."""
    return {
        "sub": str(mock_user_id),
        "email": "test@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": 9999999999,
        "iat": 1234567890,
    }
