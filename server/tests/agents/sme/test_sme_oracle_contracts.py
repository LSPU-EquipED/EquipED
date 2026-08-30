"""Contract tests for the SME per-criterion oracle lane."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from server.core.config import get_settings
from server.core.llm import ResponseContract
from server.modules.agents.sme.fallback import registry
from server.modules.agents.sme.fallback.criterion_contracts import (
    RESPONSE_SCHEMAS,
    validate,
)


def _criterion_payloads():
    return {
        "A-01": {
            "tasks": [
                {"id": 1, "text": "task", "bloom_level": "apply", "evidence": "e"}
            ]
        },
        "A-02": {
            "assessments": [
                {
                    "id": 1,
                    "text": "quiz",
                    "assessment_type": "objective_test",
                    "evidence": "e",
                }
            ]
        },
        "A-03": {
            "mechanisms": [
                {
                    "id": 1,
                    "text": "checkpoint",
                    "monitoring_type": "checkpoint",
                    "evidence": "e",
                }
            ]
        },
        "A-04": {
            "mechanisms": [
                {
                    "id": 1,
                    "text": "feedback",
                    "feedback_type": "rubric",
                    "evidence": "e",
                }
            ]
        },
        "A-05": {
            "objectives": [{"id": 1, "text": "objective"}],
            "assessments": [
                {
                    "id": 2,
                    "text": "quiz",
                    "assessment_type": "objective_test",
                    "evidence": "e",
                }
            ],
            "alignment": [
                {
                    "objective_id": 1,
                    "is_measured": True,
                    "assessment_ids": [2],
                    "evidence": "e",
                }
            ],
        },
        "OP-01": {
            "topics": [{"id": 1, "title": "topic"}],
            "transitions": [
                {"from_id": 1, "to_id": 1, "is_coherent": True, "reason": "r"}
            ],
        },
        "OP-02": {
            "interactive_elements": [{"id": 1, "text": "activity", "evidence": "e"}]
        },
        "OP-03": {
            "tasks": [
                {
                    "id": 1,
                    "text": "task",
                    "directions": "do it",
                    "has_clear_directions": True,
                    "evidence": "e",
                }
            ]
        },
        "OP-04": {
            "sections": [{"id": 1, "title": "section", "is_clean": True, "issue": ""}]
        },
        "OP-05": {
            "enhancement_activities": [{"id": 1, "text": "activity", "evidence": "e"}]
        },
    }


class TypedCriterionClient:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def generate(self, prompt, *, response_contract, **kwargs):
        assert isinstance(response_contract, ResponseContract)
        self.calls.append((prompt, response_contract))
        return json.dumps(self.payload)


@pytest.mark.parametrize("code", sorted(registry.REGISTERED_CODES))
def test_per_criterion_oracle_uses_typed_transport(code, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(
        registry,
        "get_settings",
        lambda: settings.__class__(
            **{
                **{
                    field: getattr(settings, field)
                    for field in settings.__dataclass_fields__
                },
                "llm_response_mode": "json_schema",
            }
        ),
    )
    client = TypedCriterionClient(_criterion_payloads()[code])
    score, _, _ = registry.run_criterion(code, client, "canonical text")
    assert 1 <= score <= 4
    assert len(client.calls) == 1
    contract = client.calls[0][1]
    assert tuple(contract.schema["required"]) == tuple(
        RESPONSE_SCHEMAS[code]["required"]
    )


@pytest.mark.parametrize("code", sorted(registry.REGISTERED_CODES))
@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "extra_nested",
        "root_type",
        "item_type",
        "bool_int",
        "enum",
        "duplicate",
    ],
)
def test_per_criterion_contract_rejects_mutations(code, mutation):
    payload = deepcopy(_criterion_payloads()[code])
    root = next(iter(payload))
    if mutation == "missing":
        payload.pop(root)
    elif mutation == "extra":
        payload["unknown"] = []
    elif mutation == "root_type":
        payload = []
    elif mutation == "item_type":
        payload[root] = ["wrong"]
    else:
        rows = payload[root]
        if mutation == "extra_nested":
            rows[0]["unknown"] = 1
        elif mutation == "bool_int":
            key = next((k for k, value in rows[0].items() if type(value) is int), None)
            if key is None:
                pytest.skip("criterion has no integer field")
            rows[0][key] = True
        elif mutation == "enum":
            key = next(
                (k for k in rows[0] if k.endswith("type") or k == "bloom_level"), None
            )
            if key is None:
                pytest.skip("criterion has no enum field")
            rows[0][key] = "invalid"
        elif mutation == "duplicate":
            if "id" not in rows[0]:
                pytest.skip("criterion has no identity")
            rows.append(deepcopy(rows[0]))
    client = TypedCriterionClient(payload)
    with pytest.raises((ValueError, TypeError)):
        registry.run_criterion(code, client, "canonical text")
    assert len(client.calls) == 1


def test_validate_a05_normalizes_alignment_rows_without_raising() -> None:
    payload = {
        "objectives": [
            {"id": 1, "text": "Obj 1"},
            {"id": 2, "text": "Obj 2"},
            {"id": 3, "text": "Obj 3"},
        ],
        "assessments": [
            {
                "id": 10,
                "text": "Quiz",
                "assessment_type": "objective_test",
                "evidence": "Evidence",
            }
        ],
        "alignment": [
            # duplicate for obj 1 (first wins)
            {
                "objective_id": 1,
                "is_measured": True,
                "assessment_ids": [10, 10, 999],
                "evidence": "Ev 1",
            },
            {
                "objective_id": 1,
                "is_measured": False,
                "assessment_ids": [],
                "evidence": "",
            },
            # obj 2 is missing from alignment list -> should be filled as unmeasured
            # unknown obj 99 -> should be dropped
            {
                "objective_id": 99,
                "is_measured": True,
                "assessment_ids": [10],
                "evidence": "Ev 99",
            },
            # obj 3 claims measured but empty assessment_ids/evidence ->
            # demoted to unmeasured
            {
                "objective_id": 3,
                "is_measured": True,
                "assessment_ids": [999],
                "evidence": "",
            },
        ],
    }
    validated = validate("A-05", payload)
    assert len(validated["alignment"]) == 3
    assert [row["objective_id"] for row in validated["alignment"]] == [1, 2, 3]

    # Obj 1: kept first row, deduplicated and filtered valid assessments
    assert validated["alignment"][0] == {
        "objective_id": 1,
        "is_measured": True,
        "assessment_ids": [10],
        "evidence": "Ev 1",
    }
    # Obj 2: filled missing
    assert validated["alignment"][1] == {
        "objective_id": 2,
        "is_measured": False,
        "assessment_ids": [],
        "evidence": "",
    }
    # Obj 3: demoted because invalid assessment id / empty evidence
    assert validated["alignment"][2] == {
        "objective_id": 3,
        "is_measured": False,
        "assessment_ids": [],
        "evidence": "",
    }


def test_validate_defaults_emptyable_fields() -> None:
    # A-01 without evidence
    a01 = {"tasks": [{"id": 1, "text": "Task", "bloom_level": "apply"}]}
    val_a01 = validate("A-01", a01)
    assert val_a01["tasks"][0]["evidence"] == ""

    # OP-03 without directions / evidence
    op03 = {"tasks": [{"id": 1, "text": "Task", "has_clear_directions": True}]}
    val_op03 = validate("OP-03", op03)
    assert val_op03["tasks"][0]["directions"] == ""
    assert val_op03["tasks"][0]["evidence"] == ""

    # OP-01 without reason
    op01 = {
        "topics": [{"id": 1, "title": "Topic"}],
        "transitions": [{"from_id": 1, "to_id": 1, "is_coherent": True}],
    }
    val_op01 = validate("OP-01", op01)
    assert val_op01["transitions"][0]["reason"] == ""

    # OP-04 without issue
    op04 = {"sections": [{"id": 1, "title": "Sec", "is_clean": True}]}
    val_op04 = validate("OP-04", op04)
    assert val_op04["sections"][0]["issue"] == ""
