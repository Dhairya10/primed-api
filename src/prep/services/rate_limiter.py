"""Rate limiting service for API endpoints."""

import logging
from typing import Callable

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.prep.services.auth.models import JWTUser

logger = logging.getLogger(__name__)


def get_user_id_or_ip(request: Request) -> str:
    """
    Extract user ID from JWT token or fall back to IP address.
    
    This function is used as the key_func for rate limiting:
    - Authenticated requests: Rate limited per user ID
    - Unauthenticated requests: Rate limited per IP address
    
    Args:
        request: FastAPI request object
        
    Returns:
        User ID string or IP address
    """
    # Try to get user from request state (set by auth dependency)
    user: JWTUser | None = getattr(request.state, "user", None)
    
    if user and user.id:
        # Use user ID for authenticated requests
        return f"user:{user.id}"
    
    # Fall back to IP address for unauthenticated requests
    return f"ip:{get_remote_address(request)}"


# Initialize rate limiter with in-memory storage
limiter = Limiter(
    key_func=get_user_id_or_ip,
    default_limits=[],  # No global limits, we'll apply per-endpoint
    storage_uri="memory://",  # In-memory storage for single-instance deployment
)


# Rate limit tier definitions
class RateLimitTiers:
    """
    Rate limit tiers for different endpoint categories.
    
    All limits are per-user (based on JWT user ID) for authenticated endpoints.
    Unauthenticated endpoints use IP-based rate limiting.
    """
    
    # Standard authenticated endpoints (most GET operations)
    DEFAULT = ["100 per minute", "1000 per hour"]
    
    # State-changing operations (POST/PUT)
    WRITE = ["30 per minute", "200 per hour"]
    
    # Expensive LLM operations (accounts for retry logic)
    # Increased from 5/min to 10/min to handle LLM retries (3 attempts)
    LLM_HEAVY = ["10 per minute", "30 per hour"]
    
    # WebSocket connection creation (strict limit)
    WEBSOCKET = ["3 per minute", "10 per hour"]
    
    # Public endpoints (no rate limit for health checks)
    # Note: Health check should be exempted entirely, but other public
    # endpoints can use this tier if needed
    PUBLIC = ["20 per minute", "100 per hour"]



# Convenience decorators for common tiers
# Note: These decorators require the endpoint to have a 'request: Request' parameter
# as per slowapi documentation requirements
default_rate_limit = limiter.limit(";".join(RateLimitTiers.DEFAULT))
write_rate_limit = limiter.limit(";".join(RateLimitTiers.WRITE))
llm_heavy_rate_limit = limiter.limit(";".join(RateLimitTiers.LLM_HEAVY))
websocket_rate_limit = limiter.limit(";".join(RateLimitTiers.WEBSOCKET))
public_rate_limit = limiter.limit(";".join(RateLimitTiers.PUBLIC))
