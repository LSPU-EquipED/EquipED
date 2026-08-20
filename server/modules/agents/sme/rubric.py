"""Canonical SME rubric criterion codes."""

from __future__ import annotations

# Criterion codes handled by the SME engine.
REGISTERED_CODES: frozenset[str] = frozenset(
    {
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
    }
)

__all__ = ["REGISTERED_CODES"]
