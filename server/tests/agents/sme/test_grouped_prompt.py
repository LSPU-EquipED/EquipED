from __future__ import annotations

import json

from server.modules.agents.sme.grouped_prompt import build_group_prompt

CODES = ("A-02", "A-05")
TITLES = {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"}


def test_build_group_prompt_is_valid_json_with_expected_keys():
    prompt = build_group_prompt("assessment_alignment", CODES, TITLES, "some SLM text")
    payload = json.loads(prompt)
    assert payload["agent"] == "sme"
    assert payload["group"] == "assessment_alignment"
    assert set(payload["criteria"]) == {"A-02", "A-05"}
    assert "document_text" in payload


def test_build_group_prompt_includes_scoring_rule_per_code():
    prompt = build_group_prompt("assessment_alignment", CODES, TITLES, "text")
    payload = json.loads(prompt)
    assert "5+" in payload["criteria"]["A-02"]["scoring_rule"]
    assert "moderate scale" in payload["criteria"]["A-05"]["scoring_rule"].lower() or (
        "80" in payload["criteria"]["A-05"]["scoring_rule"]
    )


def test_build_group_prompt_prepends_preamble():
    without = build_group_prompt("assessment_alignment", CODES, TITLES, "text")
    with_preamble = build_group_prompt(
        "assessment_alignment", CODES, TITLES, "text", prompt_preamble="SYSTEM RULES"
    )
    assert with_preamble.startswith("SYSTEM RULES")
    assert without != with_preamble


def test_build_group_prompt_slices_long_text():
    long_text = "x" * 50000
    prompt = build_group_prompt(
        "task_execution",
        ("A-01",),
        {"A-01": "Learner Transformation"},
        long_text,
    )
    payload = json.loads(prompt)
    assert len(payload["document_text"]) < len(long_text)


def test_op01_scoring_rule_includes_both_branches():
    prompt = build_group_prompt(
        "document_wide", ("OP-01",), {"OP-01": "Topic Coherence"}, "text"
    )
    payload = json.loads(prompt)
    rule = payload["criteria"]["OP-01"]["scoring_rule"]
    assert "issue" in rule.lower()
    assert "moderate scale" in rule.lower()
