"""Unit tests for the single-call curriculum-map LLM check.

Uses a fake client (same pattern as
tests/agents/test_curriculum_alignment.py) so no real LLM call happens.
"""

from __future__ import annotations

import json
from typing import Any

from server.modules.curriculum_map.alignment_check import run_alignment_llm


class FakeClient:
    def __init__(self, payload: dict[str, Any] | str) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def generate(self, prompt: str, **_: object) -> str:
        self.calls.append(prompt)
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


def test_happy_path_returns_all_objectives() -> None:
    client = FakeClient(
        {
            "results": [
                {
                    "objective_code": "IT08",
                    "is_addressed": True,
                    "observed_level": "I",
                    "evidence": "students work in pairs",
                }
            ]
        }
    )
    objectives = [{"code": "IT08", "description": "Teamwork"}]
    results = run_alignment_llm(client, objectives, "some SLM text")
    assert results == [
        {
            "objective_code": "IT08",
            "is_addressed": True,
            "observed_level": "I",
            "evidence": "students work in pairs",
        }
    ]
    assert len(client.calls) == 1


def test_hallucinated_objective_code_is_filtered() -> None:
    client = FakeClient(
        {
            "results": [
                {"objective_code": "IT08", "is_addressed": True, "observed_level": "E", "evidence": "x"},
                {"objective_code": "IT99", "is_addressed": True, "observed_level": "D", "evidence": "y"},
            ]
        }
    )
    objectives = [{"code": "IT08", "description": "Teamwork"}]
    results = run_alignment_llm(client, objectives, "text")
    assert [r["objective_code"] for r in results] == ["IT08"]


def test_malformed_json_returns_empty_list() -> None:
    client = FakeClient("not valid json")
    objectives = [{"code": "IT08", "description": "Teamwork"}]
    results = run_alignment_llm(client, objectives, "text")
    assert results == []


def test_empty_objectives_returns_empty_list_without_calling_llm() -> None:
    client = FakeClient({"results": []})
    results = run_alignment_llm(client, [], "text")
    assert results == []
    assert client.calls == []
