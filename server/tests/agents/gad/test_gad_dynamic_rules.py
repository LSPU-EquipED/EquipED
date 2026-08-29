"""Dynamic per-criterion counting rules for the GAD extraction prompt."""

from __future__ import annotations

import json

from server.modules.agents.gad.prompt import (
    FALLBACK_GAD_INSTRUCTIONS,
    build_combined_prompt,
)

_CHUNKS = [{"chunk_id": "c1", "text": "Sample learning material text."}]


def _instructions(prompt: str) -> str:
    return "\n".join(json.loads(prompt)["instructions"])


def test_all_five_codes_have_fallback_text() -> None:
    assert set(FALLBACK_GAD_INSTRUCTIONS) == {
        "GAD-01",
        "GAD-02",
        "GAD-03",
        "GAD-04",
        "GAD-05",
    }
    assert all(v.strip() for v in FALLBACK_GAD_INSTRUCTIONS.values())


def test_prompt_uses_fallback_when_no_rules_supplied() -> None:
    text = _instructions(
        build_combined_prompt(packed_chunks=_CHUNKS, prompt_version="v1")
    )
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-01"] in text
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-05"] in text


def test_supplied_rule_overrides_fallback_per_criterion() -> None:
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            prompt_version="v1",
            scoring_rules={"GAD-01": "EDITED GAD-01 COUNTING RULE"},
        )
    )
    assert "EDITED GAD-01 COUNTING RULE" in text
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-01"] not in text
    # untouched criteria still use the fallback
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-02"] in text


def test_structural_scaffold_survives_rule_injection() -> None:
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            prompt_version="v1",
            scoring_rules={c: f"rule {c}" for c in FALLBACK_GAD_INSTRUCTIONS},
        )
    )
    assert "exact 'excerpt'" in text
    assert "'chunk_id'" in text
    assert "Do NOT include" in text and "score" in text
    assert "10" in text  # MAX_INSTANCES_PER_CRITERION still stated
    # GAD-02 balance scaffold still present
    assert "female_count" in text and "male_count" in text


def test_blank_rule_falls_back() -> None:
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            prompt_version="v1",
            scoring_rules={"GAD-03": "   "},
        )
    )
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-03"] in text
