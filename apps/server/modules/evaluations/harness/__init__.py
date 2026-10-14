"""Backend evaluation integration; specialist pipelines live in equiped_harness."""

from .envelope_map import get_criterion_envelope_key, get_envelope_criteria_map
from .supervisor import Supervisor

__all__ = ["Supervisor", "get_criterion_envelope_key", "get_envelope_criteria_map"]
