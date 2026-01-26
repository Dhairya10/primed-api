"""FastAPI dependencies for JWT authentication using Supabase."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from src.prep.auth.models import JWTUser
from src.prep.services import PostHogService

security = HTTPBearer()
logger = logging.getLogger(__name__)

# Global JWT validator instance (initialized in main.py startup)
_jwt_validator = None


def set_jwt_validator(validator):
    """
    Set the global JWT validator instance.

    Called during application startup to initialize the JWT validator.

    Args:
        validator: JWTValidator instance
    """
    global _jwt_validator
    _jwt_validator = validator


def get_jwt_validator():
    """
    Get the global JWT validator instance.

    Returns:
        JWTValidator instance

    Raises:
        RuntimeError: If JWT validator not initialized
    """
    if _jwt_validator is None:
        raise RuntimeError(
            "JWT validator not initialized. "
            "Ensure application startup event calls set_jwt_validator()."
        )
    return _jwt_validator


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> JWTUser:
    """
    Extract and validate user data from JWT token using local verification.

    Uses JWKS-based local JWT verification for fast, network-independent
    authentication. Includes structured logging and PostHog event tracking.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        JWTUser with id, email, and user_metadata

    Raises:
        HTTPException: 401 if token invalid/missing

    Example:
        @router.get("/me")
        async def get_profile(current_user: JWTUser = Depends(get_current_user)):
            return {"user_id": current_user.id, "email": current_user.email}
    """
    try:
        # Validate JWT locally using JWKS (no network call)
        validator = get_jwt_validator()
        claims = await validator.verify_token(credentials.credentials)

        # Extract claims from verified JWT
        user_id = claims.get("sub")
        email = claims.get("email")
        user_metadata = claims.get("user_metadata", {})

        if not user_id:
            logger.warning(
                f"Auth failed: missing user ID. Full claims: {claims}",
                extra={"error_type": "missing_sub_claim", "claims": claims},
            )
            posthog_service = PostHogService()
            posthog_service.capture(
                distinct_id="anonymous",
                event="authentication_failed",
                properties={"error": "missing_sub_claim"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
            )

        if not email:
            logger.warning(
                f"Auth failed: missing email. Full claims: {claims}",
                extra={"error_type": "missing_email_claim", "claims": claims},
            )
            posthog_service = PostHogService()
            posthog_service.capture(
                distinct_id=str(user_id),
                event="authentication_failed",
                properties={"error": "missing_email_claim"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing email",
            )

        logger.info(f"User authenticated: {user_id} ({email})")
        posthog_service = PostHogService()
        posthog_service.capture(
            distinct_id=str(user_id),
            event="user_authenticated",
            properties={"timestamp": datetime.utcnow().isoformat(), "email": email},
        )

        return JWTUser(id=UUID(user_id), email=email, user_metadata=user_metadata)

    except HTTPException:
        raise
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}", extra={"error": str(e)})
        posthog_service = PostHogService()
        posthog_service.capture(
            distinct_id="anonymous",
            event="authentication_failed",
            properties={"error": "jwt_verification_failed", "details": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    except Exception as e:
        logger.error(f"Auth failed: {str(e)}", exc_info=True)
        posthog_service = PostHogService()
        posthog_service.capture(
            distinct_id="anonymous",
            event="authentication_failed",
            properties={"error": "token_validation_failed"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
