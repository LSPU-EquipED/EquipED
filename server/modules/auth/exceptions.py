"""Auth domain exceptions."""


class AuthError(Exception):
    """Base auth-domain exception."""


class InvalidCredentialsError(AuthError):
    """Raised when login credentials are invalid."""


class InactiveUserError(AuthError):
    """Raised when an inactive user attempts to authenticate."""


__all__ = ["AuthError", "InactiveUserError", "InvalidCredentialsError"]
