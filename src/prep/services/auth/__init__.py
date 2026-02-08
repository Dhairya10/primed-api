"""Authentication module for JWT-based authentication."""

from src.prep.services.auth.dependencies import (
    get_current_user,
    get_jwt_validator,
    set_jwt_validator,
)
from src.prep.services.auth.exceptions import AuthenticationError, AuthorizationError
from src.prep.services.auth.jwks import JWKSCache
from src.prep.services.auth.jwt_validator import JWTValidator
from src.prep.services.auth.models import JWTUser

__all__ = [
    "get_current_user",
    "get_jwt_validator",
    "set_jwt_validator",
    "JWKSCache",
    "JWTValidator",
    "AuthenticationError",
    "AuthorizationError",
    "JWTUser",
]
