"""Tests for JWT validator module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from jose import JWTError

from src.prep.services.auth.jwt_validator import JWTValidator


@pytest.fixture
def mock_jwks_cache():
    """Provide mock JWKS cache."""
    cache = Mock()
    cache.get_signing_key = AsyncMock()
    return cache


@pytest.fixture
def mock_signing_key():
    """Provide mock RSA signing key."""
    key = Mock()
    # Mock RSA key attributes needed by python-jose
    key.to_pem = Mock(return_value=b"-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----")
    return key


@pytest.fixture
def sample_token():
    """
    Provide a sample JWT token (structure only for testing).

    Note: This is a mock token structure for testing parsing logic.
    Real tests should use actual signed tokens.
    """
    return "eyJhbGciOiJSUzI1NiIsImtpZCI6ImtleS0xIn0.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiYXVkIjoiYXV0aGVudGljYXRlZCIsImlzcyI6Imh0dHBzOi8vZXhhbXBsZS5jb20iLCJpYXQiOjE1MTYyMzkwMjIsImV4cCI6OTk5OTk5OTk5OX0.signature"


@pytest.mark.asyncio
class TestJWTValidator:
    """Tests for JWTValidator class."""

    async def test_initialization(self, mock_jwks_cache):
        """Test JWT validator initialization."""
        validator = JWTValidator(
            jwks_cache=mock_jwks_cache,
            issuer="https://example.com",
            audience="authenticated",
            leeway=10,
        )

        assert validator.jwks_cache == mock_jwks_cache
        assert validator.issuer == "https://example.com"
        assert validator.audience == "authenticated"
        assert validator.leeway == 10

    async def test_verify_token_extracts_kid_from_header(self, mock_jwks_cache, mock_signing_key):
        """Test that verify_token extracts kid from JWT header."""
        validator = JWTValidator(jwks_cache=mock_jwks_cache, issuer="https://example.com")

        # Mock the signing key retrieval
        mock_jwks_cache.get_signing_key.return_value = mock_signing_key

        # Mock jwt.decode to return claims
        with patch("src.prep.services.auth.jwt_validator.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"kid": "key-1", "alg": "RS256"}
            mock_jwt.decode.return_value = {
                "sub": "user-123",
                "email": "test@example.com",
                "aud": "authenticated",
                "iss": "https://example.com",
            }

            await validator.verify_token("sample.jwt.token")

            # Verify kid was extracted and used to fetch signing key
            mock_jwt.get_unverified_header.assert_called_once_with("sample.jwt.token")
            mock_jwks_cache.get_signing_key.assert_called_once_with("key-1")

    async def test_verify_token_missing_kid_raises_error(self, mock_jwks_cache):
        """Test that missing kid in JWT header raises JWTError."""
        validator = JWTValidator(jwks_cache=mock_jwks_cache, issuer="https://example.com")

        with patch("src.prep.services.auth.jwt_validator.jwt") as mock_jwt:
            # Header without kid
            mock_jwt.get_unverified_header.return_value = {"alg": "RS256"}

            with pytest.raises(JWTError, match="JWT header missing 'kid'"):
                await validator.verify_token("sample.jwt.token")

    async def test_verify_token_validates_signature(self, mock_jwks_cache, mock_signing_key):
        """Test that verify_token validates JWT signature."""
        validator = JWTValidator(jwks_cache=mock_jwks_cache, issuer="https://example.com")

        mock_jwks_cache.get_signing_key.return_value = mock_signing_key

        with patch("src.prep.services.auth.jwt_validator.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"kid": "key-1"}
            mock_jwt.decode.return_value = {
                "sub": "user-123",
                "email": "test@example.com",
            }

            await validator.verify_token("sample.jwt.token")

            # Verify jwt.decode was called with signature verification enabled
            mock_jwt.decode.assert_called_once()
            call_kwargs = mock_jwt.decode.call_args[1]
            assert call_kwargs["options"]["verify_signature"] is True
            assert call_kwargs["options"]["verify_exp"] is True
            assert call_kwargs["options"]["verify_iss"] is True
            assert call_kwargs["options"]["verify_aud"] is True

    async def test_verify_token_returns_claims(self, mock_jwks_cache, mock_signing_key):
        """Test that verify_token returns decoded claims."""
        validator = JWTValidator(jwks_cache=mock_jwks_cache, issuer="https://example.com")

        mock_jwks_cache.get_signing_key.return_value = mock_signing_key

        expected_claims = {
            "sub": "user-123",
            "email": "test@example.com",
            "user_metadata": {"name": "Test User"},
            "aud": "authenticated",
            "iss": "https://example.com",
            "exp": 9999999999,
            "iat": 1516239022,
        }

        with patch("src.prep.services.auth.jwt_validator.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"kid": "key-1"}
            mock_jwt.decode.return_value = expected_claims

            claims = await validator.verify_token("sample.jwt.token")

            assert claims == expected_claims
            assert claims["sub"] == "user-123"
            assert claims["email"] == "test@example.com"

    async def test_verify_token_jwt_error_handling(self, mock_jwks_cache, mock_signing_key):
        """Test that JWTError is raised and logged on verification failure."""
        validator = JWTValidator(jwks_cache=mock_jwks_cache, issuer="https://example.com")

        mock_jwks_cache.get_signing_key.return_value = mock_signing_key

        with patch("src.prep.services.auth.jwt_validator.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"kid": "key-1"}
            mock_jwt.decode.side_effect = JWTError("Signature verification failed")

            with pytest.raises(JWTError):
                await validator.verify_token("invalid.jwt.token")

    async def test_verify_token_uses_correct_issuer_and_audience(
        self, mock_jwks_cache, mock_signing_key
    ):
        """Test that verify_token uses configured issuer and audience."""
        validator = JWTValidator(
            jwks_cache=mock_jwks_cache,
            issuer="https://custom.supabase.co",
            audience="custom-audience",
        )

        mock_jwks_cache.get_signing_key.return_value = mock_signing_key

        with patch("src.prep.services.auth.jwt_validator.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"kid": "key-1"}
            mock_jwt.decode.return_value = {"sub": "user-123"}

            await validator.verify_token("sample.jwt.token")

            call_kwargs = mock_jwt.decode.call_args[1]
            assert call_kwargs["issuer"] == "https://custom.supabase.co"
            assert call_kwargs["audience"] == "custom-audience"

    async def test_verify_token_uses_leeway(self, mock_jwks_cache, mock_signing_key):
        """Test that verify_token uses configured leeway for clock skew."""
        validator = JWTValidator(
            jwks_cache=mock_jwks_cache, issuer="https://example.com", leeway=30
        )

        mock_jwks_cache.get_signing_key.return_value = mock_signing_key

        with patch("src.prep.services.auth.jwt_validator.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"kid": "key-1"}
            mock_jwt.decode.return_value = {"sub": "user-123"}

            await validator.verify_token("sample.jwt.token")

            call_kwargs = mock_jwt.decode.call_args[1]
            assert call_kwargs["leeway"] == 30

    def test_verify_token_sync_success(self, mock_jwks_cache, mock_signing_key):
        """Test synchronous token verification."""
        validator = JWTValidator(jwks_cache=mock_jwks_cache, issuer="https://example.com")

        # Pre-populate cache
        mock_jwks_cache._keys = {"key-1": mock_signing_key}

        expected_claims = {"sub": "user-123", "email": "test@example.com"}

        with patch("src.prep.services.auth.jwt_validator.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"kid": "key-1"}
            mock_jwt.decode.return_value = expected_claims

            claims = validator.verify_token_sync("sample.jwt.token")

            assert claims == expected_claims

    def test_verify_token_sync_key_not_in_cache(self, mock_jwks_cache):
        """Test sync verification raises error if key not in cache."""
        validator = JWTValidator(jwks_cache=mock_jwks_cache, issuer="https://example.com")

        # Empty cache
        mock_jwks_cache._keys = {}

        with patch("src.prep.services.auth.jwt_validator.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"kid": "key-1"}

            with pytest.raises(RuntimeError, match="JWKS cache not initialized"):
                validator.verify_token_sync("sample.jwt.token")
