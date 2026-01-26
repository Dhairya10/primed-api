"""Local JWT verification using JWKS for signature validation."""

import logging
from typing import Any

from jose import JWTError, jwt

from src.prep.auth.jwks import JWKSCache

logger = logging.getLogger(__name__)


class JWTValidator:
    """
    Verifies JWT tokens locally without network calls.

    Uses cached JWKS to verify JWT signatures cryptographically. Validates
    signature, expiration, issuer, and audience claims according to JWT spec.

    Supports both RS256 (RSA) and ES256 (Elliptic Curve) signing algorithms.

    Attributes:
        jwks_cache: JWKS cache instance for fetching signing keys
        issuer: Expected issuer (iss claim) - typically Supabase URL
        audience: Expected audience (aud claim) - typically "authenticated"
        leeway: Clock skew tolerance in seconds (default: 10)

    Example:
        >>> validator = JWTValidator(jwks_cache, "https://project.supabase.co")
        >>> claims = await validator.verify_token(jwt_token)
        >>> user_id = claims["sub"]
        >>> email = claims["email"]
    """

    def __init__(
        self,
        jwks_cache: JWKSCache,
        issuer: str,
        audience: str = "authenticated",
        leeway: int = 10,
    ):
        """
        Initialize JWT validator.

        Args:
            jwks_cache: JWKS cache for fetching signing keys
            issuer: Expected JWT issuer (Supabase project URL)
            audience: Expected JWT audience (default: "authenticated")
            leeway: Clock skew tolerance in seconds (default: 10)
        """
        self.jwks_cache = jwks_cache
        self.issuer = issuer
        self.audience = audience
        self.leeway = leeway

    async def verify_token(self, token: str) -> dict[str, Any]:
        """
        Verify JWT token and return claims.

        Performs the following validations:
        1. Decode JWT header to extract key ID (kid)
        2. Fetch signing key from JWKS cache
        3. Verify signature using public key (RSA or EC)
        4. Validate expiration (exp claim)
        5. Validate issuer (iss claim)
        6. Validate audience (aud claim)
        7. Validate not-before if present (nbf claim)

        Args:
            token: JWT token string (without "Bearer " prefix)

        Returns:
            Dictionary of verified claims including:
            - sub: User ID (UUID)
            - email: User email
            - user_metadata: User metadata from Supabase
            - exp: Expiration timestamp
            - iat: Issued at timestamp
            - iss: Issuer
            - aud: Audience

        Raises:
            JWTError: If token is invalid, expired, or signature verification fails

        Example:
            >>> try:
            ...     claims = await validator.verify_token(token)
            ...     print(f"User: {claims['sub']}")
            ... except JWTError as e:
            ...     print(f"Invalid token: {e}")
        """
        try:
            # Step 1: Decode header to get key ID (kid) without verification
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            if not kid:
                raise JWTError("JWT header missing 'kid' (key ID)")

            # Step 2: Fetch signing key from cache
            signing_key = await self.jwks_cache.get_signing_key(kid)

            # Step 3: Verify signature and decode claims
            # Support both RS256 (RSA) and ES256 (Elliptic Curve) algorithms
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "ES256"],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "require_exp": True,
                    "require_iat": True,
                    "leeway": self.leeway,
                },
            )

            logger.debug(
                "JWT verified successfully",
                extra={
                    "user_id": claims.get("sub"),
                    "kid": kid,
                    "exp": claims.get("exp"),
                },
            )

            return claims

        except JWTError as e:
            logger.warning(
                f"JWT verification failed: {e}",
                extra={"error_type": "jwt_verification_failed", "error": str(e)},
            )
            raise

        except Exception as e:
            logger.error(
                f"Unexpected error during JWT verification: {e}",
                exc_info=True,
                extra={"error_type": "jwt_verification_error"},
            )
            raise JWTError(f"JWT verification error: {e}") from e

    def verify_token_sync(self, token: str) -> dict[str, Any]:
        """
        Synchronous version of verify_token for non-async contexts.

        Note: This still requires JWKS cache to be initialized.
        Prefer async version when possible.

        Args:
            token: JWT token string

        Returns:
            Dictionary of verified claims

        Raises:
            JWTError: If token is invalid
            RuntimeError: If JWKS cache not initialized
        """
        # For sync version, we need keys to already be in cache
        # Decode header to get kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise JWTError("JWT header missing 'kid' (key ID)")

        # Get key from cache (must already be loaded)
        signing_key = self.jwks_cache._keys.get(kid)
        if signing_key is None:
            raise RuntimeError(
                f"JWKS cache not initialized or key '{kid}' not found. "
                "Call refresh_keys() first or use async verify_token()."
            )

        # Verify and decode
        # Support both RS256 (RSA) and ES256 (Elliptic Curve) algorithms
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=self.audience,
            issuer=self.issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
                "require_exp": True,
                "require_iat": True,
                "leeway": self.leeway,
            },
        )

        return claims
