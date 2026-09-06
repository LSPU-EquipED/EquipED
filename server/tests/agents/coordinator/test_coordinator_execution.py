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
from server.modules.agents.runtime.slicing import GAP_MARKER, downsample_source_text
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    RatioBandConfig,
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


def test_execute_envelope_grounds_against_raw_large_curriculum_context() -> None:
    crit = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="A-05",
        title="A-05 title",
        description="A-05 description",
        display_order=0,
        strategy_config=CurriculumAlignmentConfig(),
    )
    excerpt = "Exact curriculum evidence beyond the sampled prompt window."
    curriculum = "x" * 3000 + excerpt + "y" * 21000
    assert excerpt not in downsample_source_text(curriculum, budget=12000)
    payload = {
        "summary": "Coordinator evaluation summary.",
        "criterion_measurements": [
            {
                "criterion_id": "A-05",
                "criterion_title": crit.title,
                "alignments": [
                    {
                        "objective_text": "Activity one is a quiz",
                        "is_aligned": True,
                        "assessment_excerpt": excerpt,
                    }
                ],
            }
        ],
    }

    _scores, _prompt, parsed, repaired = execute_envelope(
        0, (crit,), _client([payload]), SOURCE, curriculum, temperature=0.0
    )

    alignment = parsed["criterion_measurements"][0]["alignments"][0]
    assert repaired is False
    assert alignment["is_aligned"] is True
    assert alignment["assessment_excerpt"] == excerpt


def test_execute_envelope_second_failure_raises() -> None:
    crit = _make_count_criterion()
    client = _client([_invalid_payload(), _invalid_payload()])

    with pytest.raises(AgentExecutionError):
        execute_envelope(0, (crit,), client, SOURCE, CURRICULUM, temperature=0.0)


def _make_ratio_criterion(code: str = "OP-01") -> CriterionDefinition:
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=f"{code} title",
        description=f"{code} description",
        display_order=0,
        strategy_config=RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        ),
    )


def test_execute_envelope_ratio_qualifies_flags_canonicalize_and_score() -> None:
    crit = _make_ratio_criterion()
    payload = {
        "summary": "Coordinator evaluation summary.",
        "criterion_measurements": [
            {
                "criterion_id": crit.criterion_code,
                "criterion_title": crit.title,
                "total_units": [
                    {"evidence": "Activity one is a quiz", "qualifies": True},
                    {"evidence": "Activity two is an essay", "qualifies": True},
                ],
                "has_measurable_content": True,
                "summary": "Two units extracted.",
            }
        ],
    }
    client = _client([payload])

    scores, _prompt, parsed, repair_occurred = execute_envelope(
        0, (crit,), client, SOURCE, CURRICULUM, temperature=0.0
    )

    assert repair_occurred is False
    measurement = parsed["criterion_measurements"][0]
    assert [u["unit_id"] for u in measurement["total_units"]] == ["u1", "u2"]
    assert all("qualifies" not in u for u in measurement["total_units"])
    assert measurement["qualifying_unit_ids"] == ["u1", "u2"]
    assert len(scores) == 1
    assert scores[0].criterion_id == "OP-01"
    assert scores[0].score == 4


class _RecordingFake(SequencedFakeClient):
    """Sequenced fake that also captures each prompt sent to the model."""

    def __init__(self, payloads: list[dict | None]) -> None:
        super().__init__(payloads)
        self.prompts: list[str] = []

    def generate(self, prompt: str, **kwargs: object) -> str:
        self.prompts.append(prompt)
        return super().generate(prompt, **kwargs)


def test_execute_envelope_count_duplicate_succeeds_first_try_scores_unique() -> None:
    """Duplicate grounded excerpts dedupe first try, emit once, score unique."""
    crit = _make_count_criterion()
    payload = {
        "summary": "Coordinator evaluation summary.",
        "criterion_measurements": [
            {
                "criterion_id": crit.criterion_code,
                "criterion_title": crit.title,
                "instances": [
                    {"excerpt": "Activity one is a quiz"},
                    {"excerpt": "Activity one is a quiz"},
                ],
            }
        ],
    }
    fake = _RecordingFake([payload])
    fake.model = get_llm_model_name()
    client = RunLLMClient(fake, "coordinator", requested_model="test-model")

    scores, _prompt, parsed, repair_occurred = execute_envelope(
        0, (crit,), client, SOURCE, CURRICULUM, temperature=0.0
    )

    assert repair_occurred is False
    instances = parsed["criterion_measurements"][0]["instances"]
    assert len(instances) == 1
    assert instances[0]["excerpt"] == "Activity one is a quiz"
    assert len(scores) == 1
    assert scores[0].score == 2


def test_execute_envelope_ratio_conflict_repairs_with_static_guidance() -> None:
    """True ratio conflict retries once with fixed guidance and no content echo."""
    crit = _make_ratio_criterion()
    raw_marker = "UNIQUE_CONFLICT_MARKER_should_not_echo_abc123"
    conflict_payload = {
        "summary": raw_marker,
        "criterion_measurements": [
            {
                "criterion_id": crit.criterion_code,
                "criterion_title": crit.title,
                "total_units": [
                    {"evidence": "Activity one is a quiz", "qualifies": True},
                    {"evidence": "Activity one is a quiz", "qualifies": False},
                ],
                "has_measurable_content": True,
            }
        ],
    }
    valid_payload = {
        "summary": "Coordinator evaluation summary.",
        "criterion_measurements": [
            {
                "criterion_id": crit.criterion_code,
                "criterion_title": crit.title,
                "total_units": [
                    {"evidence": "Activity one is a quiz", "qualifies": True},
                ],
                "has_measurable_content": True,
            }
        ],
    }
    fake = _RecordingFake([conflict_payload, valid_payload])
    fake.model = get_llm_model_name()
    client = RunLLMClient(fake, "coordinator", requested_model="test-model")

    scores, prompt_text, parsed, repair_occurred = execute_envelope(
        0, (crit,), client, SOURCE, CURRICULUM, temperature=0.0
    )

    assert repair_occurred is True
    assert fake.calls == 2
    assert len(fake.prompts) == 2
    repair_prompt = fake.prompts[1]
    assert repair_prompt.startswith(fake.prompts[0])
    assert "VALIDATOR_FAILURE category=COORDINATOR_INVALID" in repair_prompt
    assert "consistent qualifies" in repair_prompt
    assert "only once" in repair_prompt
    assert "substring of the SOURCE TEXT" in repair_prompt
    assert "substring of the CURRICULUM CONTEXT" in repair_prompt
    assert raw_marker not in repair_prompt
    # Diagnostic suffix names the exact validation failure for the model.
    assert "conflicting qualifies" in repair_prompt
    assert len(scores) == 1
    assert scores[0].score == 4
    measurement = parsed["criterion_measurements"][0]
    assert [u["unit_id"] for u in measurement["total_units"]] == ["u1"]
    assert measurement["qualifying_unit_ids"] == ["u1"]


def test_long_document_multiunit_a01_succeeds_with_full_envelope_budget() -> None:
    """60k-char SLM with head+tail A-01 units grounds cleanly in Envelope 1."""
    crit = _make_ratio_criterion(code="A-01")
    head_sentence = "HEAD START assessment unit alpha grounding anchor sentence."
    tail_sentence = "TRUE TAIL END assessment unit omega grounding anchor sentence."
    filler = "Supporting instructional filler content for budget pressure. "
    # ~60k chars with distinctive head and tail units at opposite ends.
    long_doc = head_sentence + " " + filler * 1100 + " " + tail_sentence
    assert len(long_doc) >= 60000

    payload = {
        "summary": "Coordinator evaluation summary.",
        "criterion_measurements": [
            {
                "criterion_id": "A-01",
                "criterion_title": crit.title,
                "total_units": [
                    {"evidence": head_sentence, "qualifies": True},
                    {"evidence": tail_sentence, "qualifies": False},
                ],
                "has_measurable_content": True,
            }
        ],
    }
    client = _client([payload])
    budget = get_settings().agent_total_prompt_budget_chars

    scores, prompt_text, parsed, repair_occurred = execute_envelope(
        1, (crit,), client, long_doc, CURRICULUM, temperature=0.0
    )

    assert repair_occurred is False
    assert len(prompt_text) + len(REPAIR_SUFFIX) <= budget
    # Both head and tail units survive downsampling with full envelope budget.
    assert head_sentence in prompt_text
    assert tail_sentence in prompt_text
    assert GAP_MARKER in prompt_text
    measurement = parsed["criterion_measurements"][0]
    assert [u["unit_id"] for u in measurement["total_units"]] == ["u1", "u2"]
    assert measurement["qualifying_unit_ids"] == ["u1"]
    assert scores[0].criterion_id == "A-01"
