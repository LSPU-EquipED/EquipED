"""Shared infra exceptions for the server core layer."""


class CoreError(Exception):
    """Base error for core infrastructure failures."""


class ConfigurationError(CoreError):
    """Raised when required runtime configuration is missing or invalid."""


class DependencyUnavailableError(CoreError):
    """Raised when an optional runtime dependency is not installed."""


class InfrastructureUnavailableError(CoreError):
    """Raised when an infrastructure singleton cannot be created."""


class ReadinessError(CoreError):
    """Raised when readiness checks fail."""


__all__ = [
    "CoreError",
    "ConfigurationError",
    "DependencyUnavailableError",
    "InfrastructureUnavailableError",
    "ReadinessError",
]
