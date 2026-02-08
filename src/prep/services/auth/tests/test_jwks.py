"""Tests for JWKS cache module."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from src.prep.services.auth.jwks import JWKSCache


@pytest.fixture
def mock_jwks_response():
    """Provide sample JWKS response."""
    return {
        "keys": [
            {
                "kid": "key-1",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": "xGOr-H7A-PWXlYL-iZ8c7Nw...",  # Truncated for brevity
                "e": "AQAB",
            },
            {
                "kid": "key-2",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": "yHPs-I8B-QXYmZM-jA9d8Ox...",
                "e": "AQAB",
            },
        ]
    }


@pytest.mark.asyncio
class TestJWKSCache:
    """Tests for JWKSCache class."""

    async def test_initialization(self):
        """Test JWKS cache initialization."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json", cache_ttl=3600)

        assert cache.jwks_url == "https://example.com/.well-known/jwks.json"
        assert cache.cache_ttl == 3600
        assert cache._keys == {}
        assert cache._last_refresh is None

    async def test_refresh_keys_success(self, mock_jwks_response):
        """Test successful JWKS fetch and cache update."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json")

        # Mock HTTP client
        mock_response = Mock()
        mock_response.json.return_value = mock_jwks_response
        mock_response.raise_for_status = Mock()

        cache._http_client.get = AsyncMock(return_value=mock_response)

        # Refresh keys
        await cache.refresh_keys()

        # Verify keys cached
        assert len(cache._keys) == 2
        assert "key-1" in cache._keys
        assert "key-2" in cache._keys
        assert cache._last_refresh is not None

    async def test_refresh_keys_http_error(self):
        """Test JWKS fetch failure with HTTP error."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json")

        # Mock HTTP error
        cache._http_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

        # Should raise HTTPError
        with pytest.raises(httpx.HTTPError):
            await cache.refresh_keys()

    async def test_refresh_keys_empty_response(self):
        """Test JWKS fetch with empty keys list logs warning but doesn't crash."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json")

        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = {"keys": []}
        mock_response.raise_for_status = Mock()

        cache._http_client.get = AsyncMock(return_value=mock_response)

        # Should not raise, but log warning
        await cache.refresh_keys()

        # Verify cache is updated with empty dict
        assert cache._keys == {}
        assert cache._last_refresh is not None

    async def test_get_signing_key_success(self, mock_jwks_response):
        """Test getting signing key by kid."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json")

        # Mock HTTP client
        mock_response = Mock()
        mock_response.json.return_value = mock_jwks_response
        mock_response.raise_for_status = Mock()

        cache._http_client.get = AsyncMock(return_value=mock_response)

        # Refresh keys first
        await cache.refresh_keys()

        # Get signing key
        key = await cache.get_signing_key("key-1")
        assert key is not None

    async def test_get_signing_key_unknown_kid_triggers_refresh(self, mock_jwks_response):
        """Test that unknown kid triggers JWKS refresh."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json")

        # Mock HTTP client
        mock_response = Mock()
        mock_response.json.return_value = mock_jwks_response
        mock_response.raise_for_status = Mock()

        cache._http_client.get = AsyncMock(return_value=mock_response)

        # Initially cache is empty, so requesting key should trigger refresh
        key = await cache.get_signing_key("key-1")
        assert key is not None

        # Verify refresh was called
        cache._http_client.get.assert_called_once()

    async def test_get_signing_key_not_found_after_refresh(self, mock_jwks_response):
        """Test getting signing key that doesn't exist even after refresh."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json")

        # Mock HTTP client
        mock_response = Mock()
        mock_response.json.return_value = mock_jwks_response
        mock_response.raise_for_status = Mock()

        cache._http_client.get = AsyncMock(return_value=mock_response)

        # Request non-existent key
        with pytest.raises(ValueError, match="Key ID 'unknown-key' not found in JWKS"):
            await cache.get_signing_key("unknown-key")

    async def test_needs_refresh_when_never_refreshed(self):
        """Test that cache needs refresh when never initialized."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json")

        assert cache._needs_refresh() is True

    async def test_needs_refresh_when_ttl_expired(self):
        """Test that cache needs refresh when TTL expired."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json", cache_ttl=10)

        # Set last refresh to 11 seconds ago
        cache._last_refresh = datetime.utcnow() - timedelta(seconds=11)

        assert cache._needs_refresh() is True

    async def test_no_refresh_needed_when_fresh(self):
        """Test that cache doesn't need refresh when fresh."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json", cache_ttl=3600)

        # Set last refresh to now
        cache._last_refresh = datetime.utcnow()

        assert cache._needs_refresh() is False

    async def test_close_cleanup(self):
        """Test cleanup of HTTP client on close."""
        cache = JWKSCache("https://example.com/.well-known/jwks.json")

        # Mock HTTP client close
        cache._http_client.aclose = AsyncMock()

        await cache.close()

        # Verify close was called
        cache._http_client.aclose.assert_called_once()
