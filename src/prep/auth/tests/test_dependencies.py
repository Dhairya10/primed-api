"""Tests for authentication dependencies."""

from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError

from src.prep.auth.dependencies import get_current_user, set_jwt_validator
from src.prep.auth.models import JWTUser


@pytest.fixture(autouse=True)
def mock_posthog():
    """Auto-mock PostHogService for all tests."""
    with patch("src.prep.auth.dependencies.PostHogService") as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_jwt_validator():
    """Provide mock JWT validator for tests."""
    validator = Mock()
    validator.verify_token = AsyncMock()
    return validator


@pytest.fixture(autouse=True)
def setup_jwt_validator(mock_jwt_validator):
    """Auto-setup mock JWT validator for all tests."""
    set_jwt_validator(mock_jwt_validator)
    yield
    # Reset to None after each test
    set_jwt_validator(None)


@pytest.mark.asyncio
class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    async def test_valid_token_returns_user_data(
        self, mock_user_id: UUID, valid_jwt_token: str, mock_jwt_validator
    ):
        """Test successful authentication with valid token."""
        # Arrange
        mock_jwt_validator.verify_token.return_value = {
            "sub": str(mock_user_id),
            "email": "test@example.com",
            "user_metadata": {"full_name": "Test User"},
        }
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_jwt_token)

        # Act
        result = await get_current_user(credentials=credentials)

        # Assert
        assert isinstance(result, JWTUser)
        assert result.id == mock_user_id
        assert result.email == "test@example.com"
        assert result.user_metadata == {"full_name": "Test User"}
        mock_jwt_validator.verify_token.assert_called_once_with(valid_jwt_token)

    async def test_missing_sub_claim_raises_401(self, valid_jwt_token: str, mock_jwt_validator):
        """Test that missing 'sub' claim raises 401 error."""
        # Arrange
        mock_jwt_validator.verify_token.return_value = {"email": "test@example.com"}
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_jwt_token)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials)

        assert exc_info.value.status_code == 401
        assert "missing user ID" in exc_info.value.detail

    async def test_missing_email_raises_401(
        self, mock_user_id: UUID, valid_jwt_token: str, mock_jwt_validator
    ):
        """Test that missing 'email' claim raises 401 error."""
        # Arrange
        mock_jwt_validator.verify_token.return_value = {"sub": str(mock_user_id)}
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_jwt_token)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials)

        assert exc_info.value.status_code == 401
        assert "missing email" in exc_info.value.detail

    async def test_invalid_token_raises_401(self, valid_jwt_token: str, mock_jwt_validator):
        """Test that invalid token raises 401 error."""
        # Arrange
        mock_jwt_validator.verify_token.side_effect = JWTError("Invalid token")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_jwt_token)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials)

        assert exc_info.value.status_code == 401
        assert "Invalid authentication credentials" in exc_info.value.detail

    async def test_expired_token_raises_401(self, valid_jwt_token: str, mock_jwt_validator):
        """Test that expired token raises 401 error."""
        # Arrange
        mock_jwt_validator.verify_token.side_effect = JWTError("Token expired")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_jwt_token)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials)

        assert exc_info.value.status_code == 401

    async def test_malformed_token_raises_401(self, valid_jwt_token: str, mock_jwt_validator):
        """Test that malformed token raises 401 error."""
        # Arrange
        mock_jwt_validator.verify_token.side_effect = JWTError("Malformed token")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_jwt_token)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials)

        assert exc_info.value.status_code == 401

    async def test_authentication_logs_success(
        self, mock_user_id: UUID, valid_jwt_token: str, mock_jwt_validator
    ):
        """Test that successful authentication is logged."""
        # Arrange
        mock_jwt_validator.verify_token.return_value = {
            "sub": str(mock_user_id),
            "email": "test@example.com",
            "user_metadata": {},
        }
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_jwt_token)

        # Act
        with patch("src.prep.auth.dependencies.logger") as mock_logger:
            result = await get_current_user(credentials=credentials)

            # Assert
            assert isinstance(result, JWTUser)
            assert result.id == mock_user_id
            # Should log successful authentication
            mock_logger.info.assert_called_once()

    async def test_authentication_logs_failure(self, valid_jwt_token: str, mock_jwt_validator):
        """Test that failed authentication is logged."""
        # Arrange
        mock_jwt_validator.verify_token.side_effect = JWTError("Invalid token")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_jwt_token)

        # Act & Assert
        with patch("src.prep.auth.dependencies.logger") as mock_logger:
            with pytest.raises(HTTPException):
                await get_current_user(credentials=credentials)

            mock_logger.warning.assert_called_once()
