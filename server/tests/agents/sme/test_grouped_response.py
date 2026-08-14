from __future__ import annotations

import json

import pytest
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.sme.grouped_response import (
    build_group_response_schema,
    group_criterion_scores,
    parse_group_response,
)

CODES = ("A-02", "A-05")
TITLES = {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"}


def _payload(score=3, **overrides):
    entries = []
    for code in CODES:
        entries.append(
            {
                "criterion_id": code,
                "criterion_title": TITLES[code],
                "score": score,
                "justification": "justification text",
                "evidence": ["evidence quote"],
                **overrides,
            }
        )
    return json.dumps({"summary": "ok", "criterion_scores": entries})


def test_build_schema_has_one_entry_per_code():
    schema = build_group_response_schema(CODES, TITLES)
    prefix_items = schema["properties"]["criterion_scores"]["prefixItems"]
    assert [item["properties"]["criterion_id"]["const"] for item in prefix_items] == list(
        CODES
    )
    for item in prefix_items:
        assert "chunk_ids" not in item["properties"]


def test_parse_accepts_valid_payload():
    parsed = parse_group_response(_payload(), CODES, TITLES)
    assert parsed["summary"] == "ok"


def test_parse_rejects_non_json():
    with pytest.raises(AgentExecutionError):
        parse_group_response("not json", CODES, TITLES)


def test_group_criterion_scores_returns_one_per_code_in_order():
    parsed = parse_group_response(_payload(score=4), CODES, TITLES)
    scores = group_criterion_scores(parsed, CODES, TITLES)
    assert [s.criterion_id for s in scores] == list(CODES)
    assert all(s.score == 4 for s in scores)
    assert scores[0].chunk_ids == ()


def test_group_criterion_scores_rejects_wrong_code_order():
    entries = [
        {
            "criterion_id": "A-05",
            "criterion_title": "Objective Gauging",
            "score": 3,
            "justification": "j",
            "evidence": [],
        },
        {
            "criterion_id": "A-02",
            "criterion_title": "Varied Assessment Tools",
            "score": 3,
            "justification": "j",
            "evidence": [],
        },
    ]
    parsed = {"summary": "ok", "criterion_scores": entries}
    with pytest.raises(AgentExecutionError):
        group_criterion_scores(parsed, CODES, TITLES)


def test_group_criterion_scores_rejects_out_of_range_score():
    parsed = parse_group_response(_payload(score=4), CODES, TITLES)
    parsed["criterion_scores"][0]["score"] = 5
    with pytest.raises(AgentExecutionError):
        group_criterion_scores(parsed, CODES, TITLES)
