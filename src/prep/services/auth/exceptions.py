"""Custom exceptions for authentication and authorization."""


class AuthenticationError(Exception):
    """Raised when authentication fails (invalid credentials, expired tokens, etc.)."""

    pass


class AuthorizationError(Exception):
    """Raised when an authenticated user lacks permission to access a resource."""

    pass
