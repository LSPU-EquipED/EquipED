"""Curriculum reference document module."""

from .extraction import filter_curriculum_pages
from .service import (
    CurriculumReadiness,
    check_curriculum_readiness,
)

__all__ = [
    "CurriculumReadiness",
    "check_curriculum_readiness",
    "filter_curriculum_pages",
]
