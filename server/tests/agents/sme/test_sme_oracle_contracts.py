"""Contract tests for the SME grouped and per-criterion oracle lanes."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib import import_module

import pytest
from server.core.config import get_settings
from server.core.llm import ResponseContract
from server.modules.agents.sme import extraction, registry
from server.modules.agents.sme.criterion_contracts import RESPONSE_SCHEMAS
from server.tests.agents.helpers import _ALL_BASKETS_IN_ORDER

SME_EXTRACTION_PROMPT = import_module(
    "server.alembic.versions.20260811_0002_seed_sme_extraction_prompt"
).SME_EXTRACTION_PROMPT


class RecordingClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        return json.dumps(self.responses[len(self.prompts) - 1])


def test_grouped_prompts_preserve_oracle_sentinels_and_do_not_use_old_caps():
    def sampled_marker(name: str) -> str:
        length = 36_000
        chunk_size = 9_000 // 6
        starts = [(i * length) // 6 for i in range(5)] + [length - chunk_size]
        source = ["a"] * length
        marker = f"{name}-SAMPLED"
        start = starts[4] + 100
        source[start : start + len(marker)] = marker
        return "".join(source)

    texts = {
        "A1": "A1-OBJECTIVE "
        + "x" * 3900
        + "\nPerformance Tasks\n"
        + "y" * 1000
        + "A1-BODY",
        "A2": "z" * 100 + "Performance Tasks\n" + "q" * 8700 + "A2-BOTTOM",
        "A3": "z" * 100 + "Performance Tasks\n" + "q" * 8700 + "A3-BOTTOM",
        "A4": "z" * 100 + "Performance Tasks\n" + "q" * 8700 + "A4-BOTTOM",
        "B1": sampled_marker("B1"),
        "B2": sampled_marker("B2"),
    }
    for index, name in enumerate(("A1", "A2", "A3", "A4", "B1", "B2")):
        client = RecordingClient(_ALL_BASKETS_IN_ORDER)
        registry.run_grouped(client, texts[name])
        assert len(client.prompts) == 6
        assert f"{name}-" in client.prompts[index]


class TypedGroupedClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, response_contract, **kwargs):
        assert isinstance(response_contract, ResponseContract)
        self.prompts.append(prompt)
        return json.dumps(_ALL_BASKETS_IN_ORDER[len(self.prompts) - 1])


def test_grouped_canonical_source_fits_default_budget() -> None:
    source = (
        "Learning objectives and assessment information.\n"
        + "x" * 9000
        + "\nPerformance Tasks\n"
        + "y" * 9000
        + "\nQuestions for Reflection\n"
        + "z" * 18000
    )
    client = TypedGroupedClient()
    results = registry.run_grouped(
        client, source, prompt_preamble=SME_EXTRACTION_PROMPT
    )
    assert len(client.prompts) == 6
    budget = get_settings().sme_total_prompt_budget_chars
    assert all(len(prompt) <= budget for prompt in client.prompts)
    assert all(prompt.startswith(SME_EXTRACTION_PROMPT) for prompt in client.prompts)
    assert len(results) == 10


def test_over_budget_does_not_send_grouped_transport_and_returns_honest_failure(
    monkeypatch,
):
    settings = get_settings()

    def tiny():
        return settings.__class__(
            **{
                **{
                    field: getattr(settings, field)
                    for field in settings.__dataclass_fields__
                },
                "sme_total_prompt_budget_chars": 1000,
            }
        )

    monkeypatch.setattr(registry, "get_settings", tiny)
    monkeypatch.setattr(extraction, "get_settings", tiny)
    client = RecordingClient(_ALL_BASKETS_IN_ORDER)
    assert registry.run_grouped(client, "z" * 100_000, prompt_preamble="p" * 1000) == {}
    assert client.prompts == []


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
