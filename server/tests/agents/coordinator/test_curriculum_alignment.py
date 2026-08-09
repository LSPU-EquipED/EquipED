"""Unit tests for Coordinator's curriculum-aware A-05 extension.

``compute()`` is tested directly (pure facts -> band math, same shape as
``objective_alignment.compute``). ``evaluate_against_curriculum`` is tested
against a fake client for its guard clauses (never a hard failure -- always
falls back to ``None`` so the caller keeps the SLM-only A-05 score).
"""

from __future__ import annotations

import json
from typing import Any

from server.modules.agents.coordinator import curriculum as curriculum_alignment


class TestCurriculumAlignmentCompute:
    def test_all_objectives_addressed(self) -> None:
        objectives = [{"id": 1}, {"id": 2}, {"id": 3}]
        alignment = [
            {"objective_id": 1, "is_addressed": True},
            {"objective_id": 2, "is_addressed": True},
            {"objective_id": 3, "is_addressed": True},
        ]
        result = curriculum_alignment.compute(objectives, alignment, "curriculum text")
        assert result.aligned == 3
        assert result.total_objectives == 3
        assert result.score == 4  # 100%

    def test_duplicate_rows_do_not_inflate(self) -> None:
        # Same regression class as objective_alignment's 10/3 bug: distinct
        # addressed objectives must cap at the objective count.
        objectives = [{"id": 1}, {"id": 2}, {"id": 3}]
        alignment = [
            {"objective_id": 1, "is_addressed": True},
            {"objective_id": 1, "is_addressed": True},
            {"objective_id": 2, "is_addressed": True},
            {"objective_id": 3, "is_addressed": True},
        ]
        result = curriculum_alignment.compute(objectives, alignment, "curriculum text")
        assert result.aligned == 3
        assert result.pct == 100.0

    def test_unknown_objective_id_ignored(self) -> None:
        objectives = [{"id": 1}, {"id": 2}]
        alignment = [
            {"objective_id": 1, "is_addressed": True},
            {"objective_id": 99, "is_addressed": True},  # hallucinated id
        ]
        result = curriculum_alignment.compute(objectives, alignment, "curriculum text")
        assert result.aligned == 1  # 99 does not count
        assert result.score == 3  # 1/2 = 50%

    def test_no_objectives_scores_one(self) -> None:
        result = curriculum_alignment.compute([], [], "curriculum text")
        assert result.score == 1
        assert result.pct is None

    def test_curriculum_text_carried_through(self) -> None:
        result = curriculum_alignment.compute([{"id": 1}], [], "Course: Foo\n\nBar")
        assert result.curriculum_text == "Course: Foo\n\nBar"


class TestEvaluateAgainstCurriculum:
    class FakeClient:
        def __init__(self, payload: dict[str, Any] | None = None) -> None:
            self.payload = payload
            self.calls: list[str] = []

        def generate(self, prompt: str, **_: object) -> str:
            self.calls.append(prompt)
            if self.payload is None:
                raise RuntimeError("simulated LLM failure")
            return json.dumps(self.payload)

    def test_empty_objectives_returns_none_without_calling_llm(self) -> None:
        client = self.FakeClient({"alignment": []})
        result = curriculum_alignment.evaluate_against_curriculum(
            client, [], "curriculum text"
        )
        assert result is None
        assert client.calls == []

    def test_empty_curriculum_text_returns_none_without_calling_llm(self) -> None:
        client = self.FakeClient({"alignment": []})
        result = curriculum_alignment.evaluate_against_curriculum(
            client, [{"id": 1}], "   "
        )
        assert result is None
        assert client.calls == []

    def test_llm_failure_returns_none_not_raises(self) -> None:
        client = self.FakeClient(payload=None)  # simulates client.generate() raising
        result = curriculum_alignment.evaluate_against_curriculum(
            client, [{"id": 1}], "curriculum text"
        )
        assert result is None

    def test_malformed_json_returns_none_not_raises(self) -> None:
        class BadJsonClient:
            def generate(self, prompt: str, **_: object) -> str:
                return "not valid json"

        result = curriculum_alignment.evaluate_against_curriculum(
            BadJsonClient(), [{"id": 1}], "curriculum text"
        )
        assert result is None

    def test_happy_path_returns_result(self) -> None:
        client = self.FakeClient(
            {
                "alignment": [
                    {"objective_id": 1, "is_addressed": True, "evidence": "quote"},
                ]
            }
        )
        result = curriculum_alignment.evaluate_against_curriculum(
            client, [{"id": 1, "text": "obj"}], "curriculum text"
        )
        assert result is not None
        assert result.aligned == 1
        assert result.score == 4
        assert len(client.calls) == 1
