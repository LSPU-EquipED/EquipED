"""build_group_prompt uses the passed scoring rule, falling back to the constant."""

from __future__ import annotations

import json

from server.modules.agents.sme.group_prompt import (
    FALLBACK_SCORING_RULES,
    build_group_prompt,
)


def test_build_group_prompt_prefers_passed_scoring_rule() -> None:
    prompt = build_group_prompt(
        "assessment_alignment",
        ("A-02", "A-05"),
        {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"},
        {"A-02": "desc a02", "A-05": "desc a05"},
        {"A-02": "EDITED RULE: count things differently"},
        "some document text",
    )
    payload = json.loads(prompt)
    assert payload["criteria"]["A-02"]["scoring_rule"] == (
        "EDITED RULE: count things differently"
    )
    # A-05 not in the passed dict -> falls back to the constant.
    assert (
        payload["criteria"]["A-05"]["scoring_rule"] == FALLBACK_SCORING_RULES["A-05"]
    )


def test_fallback_scoring_rules_has_all_ten_codes() -> None:
    assert set(FALLBACK_SCORING_RULES) == {
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
