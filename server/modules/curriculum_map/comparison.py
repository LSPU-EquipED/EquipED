"""Pure I/E/D comparison logic -- no LLM, no IO, fully unit-testable.

Mirrors the design spec's priority-ordered rule (design doc section 5):
``is_addressed`` is checked first and always wins over whatever
``observed_level`` the LLM returned, so a not-addressed objective never
carries a stray depth reading.
"""

from __future__ import annotations

_LEVEL_ORDER: dict[str, int] = {"I": 0, "E": 1, "D": 2}


def compare_objective(
    *, is_addressed: bool, observed_level: str | None, expected_level: str
) -> str:
    """Return one of ``match``, ``under-developed``, ``over-developed``,
    ``not_addressed`` for a single mapped objective.
    """
    if not is_addressed:
        return "not_addressed"

    observed_rank = _LEVEL_ORDER.get(observed_level or "", -1)
    expected_rank = _LEVEL_ORDER[expected_level]

    if observed_rank == expected_rank:
        return "match"
    if observed_rank < expected_rank:
        return "under-developed"
    return "over-developed"


__all__ = ["compare_objective"]
