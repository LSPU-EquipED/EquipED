"""Tests for GAD's evidence-grounding fallback search."""

from __future__ import annotations

from server.modules.agents.gad.grounding import ground_single_excerpt

_CHUNKS = [
    {
        "chunk_id": "chunk_1",
        "text": "Women are inherently too emotional for leadership.",
    },
    {
        "chunk_id": "chunk_2",
        "text": "The classroom had twelve male and eight female students.",
    },
]


def test_ground_single_excerpt_found_in_claimed_chunk() -> None:
    result = ground_single_excerpt(
        "Women are inherently too emotional for leadership.", "chunk_1", _CHUNKS
    )
    assert result == ("Women are inherently too emotional for leadership.", "chunk_1")


def test_ground_single_excerpt_found_in_different_chunk_via_fallback() -> None:
    result = ground_single_excerpt(
        "twelve male and eight female students", "chunk_1", _CHUNKS
    )
    assert result == ("twelve male and eight female students", "chunk_2")


def test_ground_single_excerpt_not_found_anywhere_returns_none() -> None:
    result = ground_single_excerpt(
        "This exact sentence is not in any chunk.", "chunk_1", _CHUNKS
    )
    assert result is None


def test_ground_single_excerpt_unknown_claimed_chunk_still_falls_back() -> None:
    result = ground_single_excerpt(
        "twelve male and eight female students", "does_not_exist", _CHUNKS
    )
    assert result == ("twelve male and eight female students", "chunk_2")
