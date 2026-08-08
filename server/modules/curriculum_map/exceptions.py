"""Exceptions for curriculum map catalog and roadmap operations."""

class RoadmapNotFoundError(Exception):
    """Raised when the requested program roadmap does not exist."""

__all__ = ["RoadmapNotFoundError"]
