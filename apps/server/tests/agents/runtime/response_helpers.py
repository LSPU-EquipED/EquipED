"""Strict ITSO response fixtures used by runtime tests."""

from __future__ import annotations

from equiped_harness.agents.itso.response import ITSO_CRITERIA_TITLES


def itso_response(*, chunk_ids: tuple[str, ...] = ("c1",), score: int = 3) -> dict:
    """Return a schema-valid, explicitly ungrounded ITSO runtime fixture."""
    return {
        "summary": "Runtime fixture evaluation.",
        "criterion_scores": [
            {
                "criterion_id": criterion_id,
                "criterion_title": title,
                "score": score,
                "justification": (
                    "Compared with the retrieved public reference [source 1]."
                    if criterion_id in {"ITSO-01", "ITSO-02"}
                    else "Evidence supports the assigned score."
                ),
                "chunk_ids": list(chunk_ids),
                "evidence": [],
            }
            for criterion_id, title in ITSO_CRITERIA_TITLES.items()
        ],
    }
