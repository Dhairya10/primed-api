"""JWKS (JSON Web Key Set) fetching and caching for JWT verification."""

import logging
from datetime import datetime

import httpx
from jose import jwk
from jose.backends import ECKey, RSAKey

logger = logging.getLogger(__name__)


class JWKSCache:
    """
    Manages JWKS fetching and caching with automatic refresh.

    Fetches JWKS from Supabase on initialization and caches keys in-memory
    with TTL. Automatically refreshes keys when cache expires or when an
    unknown key ID is encountered.

    Attributes:
        jwks_url: URL to fetch JWKS from (typically /.well-known/jwks.json)
        cache_ttl: Cache time-to-live in seconds (default: 3600 = 1 hour)
        _keys: Cached JWKS keys dictionary (kid -> key) - supports RSA and EC keys
        _last_refresh: Timestamp of last successful JWKS fetch
        _http_client: HTTP client for fetching JWKS

    Example:
        >>> cache = JWKSCache("https://project.supabase.co/.well-known/jwks.json")
        >>> await cache.refresh_keys()
        >>> signing_key = await cache.get_signing_key("key-id-123")
    """

    def __init__(self, jwks_url: str, cache_ttl: int = 3600):
        """
        Initialize JWKS cache.

        Args:
            jwks_url: URL to fetch JWKS from
            cache_ttl: Cache TTL in seconds (default: 1 hour)
        """
        self.jwks_url = jwks_url
        self.cache_ttl = cache_ttl
        self._keys: dict[str, RSAKey | ECKey] = {}
        self._last_refresh: datetime | None = None
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, read=30.0, connect=10.0, write=10.0)
        )

    async def get_signing_key(self, kid: str) -> RSAKey | ECKey:
        """
        Get signing key by key ID (kid).

        Automatically refreshes JWKS if:
        1. Cache has expired (TTL exceeded)
        2. Key ID not found in cache (new key rotation)

        Args:
            kid: Key ID from JWT header

        Returns:
            Public key for signature verification (RSA or EC)

        Raises:
            ValueError: If key ID not found after refresh
            httpx.HTTPError: If JWKS fetch fails

        Example:
            >>> key = await cache.get_signing_key("abc123")
            >>> # Use key to verify JWT signature
        """
        # Check if cache needs refresh
        if self._needs_refresh():
            await self.refresh_keys()

        # Try to get key from cache
        key = self._keys.get(kid)

        # If key not found, try refreshing once (key rotation case)
        if key is None:
            logger.warning(
                f"Key ID '{kid}' not found in cache, refreshing JWKS",
                extra={"kid": kid, "cached_kids": list(self._keys.keys())},
            )
            await self.refresh_keys()
            key = self._keys.get(kid)

        if key is None:
            raise ValueError(
                f"Key ID '{kid}' not found in JWKS. Available keys: {list(self._keys.keys())}"
            )

        return key

    async def refresh_keys(self) -> None:
        """
        Fetch JWKS from Supabase and update cache.

        Makes HTTP request to JWKS endpoint and parses public keys.
        Updates cache atomically to avoid race conditions.

        Raises:
            httpx.HTTPError: If HTTP request fails
            ValueError: If JWKS response is invalid

        Example:
            >>> await cache.refresh_keys()
            >>> # Cache now contains latest keys from Supabase
        """
        try:
            logger.info(f"Fetching JWKS from {self.jwks_url}")
            response = await self._http_client.get(self.jwks_url)
            response.raise_for_status()

            jwks_data = response.json()
            keys_list = jwks_data.get("keys", [])

            if not keys_list:
                logger.warning(
                    "JWKS response contains no keys - this may indicate the Supabase "
                    "project has not generated JWT keys yet. Token verification will fail "
                    "until keys are available.",
                    extra={"jwks_url": self.jwks_url},
                )
                # Update cache with empty dict and timestamp
                self._keys = {}
                self._last_refresh = datetime.utcnow()
                return

            # Parse keys and build cache
            new_keys: dict[str, RSAKey | ECKey] = {}
            for key_data in keys_list:
                kid = key_data.get("kid")
                if not kid:
                    logger.warning("JWKS key missing 'kid', skipping")
                    continue

                # Detect algorithm from key data
                alg = key_data.get("alg", "RS256")  # Default to RS256 for backward compat
                kty = key_data.get("kty")  # Key type: RSA or EC

                # Determine algorithm based on key type
                if kty == "EC":
                    # Elliptic Curve key - use ES256
                    algorithm = "ES256"
                elif kty == "RSA":
                    # RSA key - use RS256
                    algorithm = "RS256"
                else:
                    # Fall back to algorithm specified in key data
                    algorithm = alg

                # Convert JWK to key object (automatically detects RSA vs EC)
                key = jwk.construct(key_data, algorithm=algorithm)
                new_keys[kid] = key

                logger.debug(
                    f"Loaded key {kid} (type: {kty}, algorithm: {algorithm})",
                    extra={"kid": kid, "kty": kty, "alg": algorithm},
                )

            # Atomic update
            self._keys = new_keys
            self._last_refresh = datetime.utcnow()

            logger.info(
                "JWKS cache refreshed successfully",
                extra={
                    "key_count": len(new_keys),
                    "key_ids": list(new_keys.keys()),
                    "ttl_seconds": self.cache_ttl,
                },
            )

        except httpx.HTTPError as e:
            logger.error(
                f"Failed to fetch JWKS from {self.jwks_url}: {e}",
                exc_info=True,
                extra={"error_type": "jwks_fetch_failed"},
            )
            raise

        except Exception as e:
            logger.error(
                f"Failed to parse JWKS: {e}",
                exc_info=True,
                extra={"error_type": "jwks_parse_failed"},
            )
            raise

    def _needs_refresh(self) -> bool:
        """
        Check if cache needs refresh based on TTL.

        Returns:
            True if cache is stale or never initialized
        """
        if self._last_refresh is None:
            return True

        age = (datetime.utcnow() - self._last_refresh).total_seconds()
        return age >= self.cache_ttl

    async def close(self) -> None:
        """
        Close HTTP client and cleanup resources.

        Should be called during application shutdown.

        Example:
            >>> await cache.close()
        """
        await self._http_client.aclose()
        logger.info("JWKS cache closed")
