"""Tests for the Coordinator envelope execution + repair transport."""

from __future__ import annotations

import uuid

import pytest
from server.core.config import get_settings
from server.core.llm import get_llm_model_name
from server.modules.agents.coordinator.execution import execute_envelope
from server.modules.agents.coordinator.prompt import REPAIR_SUFFIX
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.runtime.llm import RunLLMClient
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
)
from server.tests.agents.helpers import SequencedFakeClient

SOURCE = (
    "The material includes several activities. Activity one is a quiz. "
    "Activity two is an essay. Activity three is a debate."
)
CURRICULUM = "Unit 2 covers photosynthesis and light reactions in detail."


def _make_count_criterion(code: str = "OP-02") -> CriterionDefinition:
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=f"{code} title",
        description=f"{code} description",
        display_order=0,
        strategy_config=CountBandConfig(
            mode="minimum_count", threshold_4=4, threshold_3=2, threshold_2=1
        ),
    )


def _valid_payload(crit: CriterionDefinition) -> dict:
    return {
        "summary": "Coordinator evaluation summary.",
        "criterion_measurements": [
            {
                "criterion_id": crit.criterion_code,
                "criterion_title": crit.title,
                "instances": [
                    {"excerpt": "Activity one is a quiz"},
                    {"excerpt": "Activity two is an essay"},
                ],
            }
        ],
    }


def _invalid_payload() -> dict:
    return {
        "summary": "bad",
        "criterion_measurements": [
            {"criterion_id": "X-99", "criterion_title": "wrong", "instances": []}
        ],
    }


def _client(payloads: list[dict | None]) -> RunLLMClient:
    fake = SequencedFakeClient(payloads)
    fake.model = get_llm_model_name()
    return RunLLMClient(fake, "coordinator", requested_model="test-model")


def test_execute_envelope_success_first_try() -> None:
    crit = _make_count_criterion()
    client = _client([_valid_payload(crit)])

    scores, prompt_text, parsed, repair_occurred = execute_envelope(
        0, (crit,), client, SOURCE, CURRICULUM, temperature=0.0
    )

    assert repair_occurred is False
    assert len(scores) == 1
    assert scores[0].criterion_id == "OP-02"
    assert scores[0].score == 3
    assert "criterion_measurements" in parsed
    assert isinstance(prompt_text, str) and prompt_text


def test_execute_envelope_repairs_once_then_succeeds() -> None:
    crit = _make_count_criterion()
    client = _client([_invalid_payload(), _valid_payload(crit)])

    scores, _prompt, _parsed, repair_occurred = execute_envelope(
        0, (crit,), client, SOURCE, CURRICULUM, temperature=0.0
    )

    assert repair_occurred is True
    assert scores[0].score == 3


def test_execute_envelope_bounds_large_curriculum_context() -> None:
    crit = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="A-05",
        title="A-05 title",
        description="A-05 description",
        display_order=0,
        strategy_config=CurriculumAlignmentConfig(),
    )
    payload = {
        "summary": "Coordinator evaluation summary.",
        "criterion_measurements": [
            {
                "criterion_id": "A-05",
                "criterion_title": crit.title,
                "alignments": [
                    {
                        "objective_text": "Activity one is a quiz",
                        "is_aligned": False,
                        "assessment_excerpt": None,
                    }
                ],
            }
        ],
    }
    huge_curriculum = "Curriculum topic sentence. " * 1600  # ~43k chars
    assert len(huge_curriculum) > 40000
    client = _client([payload])

    scores, prompt_text, _parsed, repaired = execute_envelope(
        0, (crit,), client, SOURCE, huge_curriculum, temperature=0.0
    )

    assert repaired is False
    assert scores[0].criterion_id == "A-05"
    budget = get_settings().agent_total_prompt_budget_chars
    assert len(prompt_text) + len(REPAIR_SUFFIX) <= budget


def test_execute_envelope_second_failure_raises() -> None:
    crit = _make_count_criterion()
    client = _client([_invalid_payload(), _invalid_payload()])

    with pytest.raises(AgentExecutionError):
        execute_envelope(0, (crit,), client, SOURCE, CURRICULUM, temperature=0.0)
