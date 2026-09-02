"""Tests for the Coordinator envelope prompt builder."""

from __future__ import annotations

import uuid

import pytest
from server.modules.agents.coordinator.prompt import (
    REPAIR_SUFFIX,
    build_envelope_prompt_and_source,
)
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)

CURRICULUM = "Curriculum topic: photosynthesis converts light to chemical energy."


def make_criterion(
    code: str, *, strategy: str, scoring_rule: str | None = None
) -> CriterionDefinition:
    """Local builder standing in for the absent shared test helper."""
    if strategy == "ratio_band":
        config = RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        )
    elif strategy == "count_band":
        config = CountBandConfig(
            mode="minimum_count", threshold_4=4, threshold_3=2, threshold_2=1
        )
    elif strategy == "curriculum_alignment":
        config = CurriculumAlignmentConfig()
    elif strategy == "llm_rubric_guidance":
        config = LlmRubricGuidanceConfig(guidance="Evaluate.")
    else:  # pragma: no cover - guard for typos
        raise ValueError(f"unknown strategy {strategy!r}")

    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=f"{code} title",
        description=f"{code} description",
        scoring_rule=scoring_rule,
        display_order=0,
        strategy_config=config,
    )


def test_curriculum_block_only_present_for_a05_envelope():
    op_env = (make_criterion("OP-02", strategy="count_band"),)
    a_env = (make_criterion("A-05", strategy="curriculum_alignment"),)

    op_prompt, _ = build_envelope_prompt_and_source(
        op_env, "doc text", CURRICULUM, prompt_budget=32000
    )
    a_prompt, _ = build_envelope_prompt_and_source(
        a_env, "doc text", CURRICULUM, prompt_budget=32000
    )
    # The delimited context block is injected only for the A-05 envelope.
    # (The Coordinator preamble mentions the phrase in both, so assert on the
    # block delimiter rather than the bare substring.)
    assert "=== CURRICULUM CONTEXT ===" not in op_prompt
    assert "=== CURRICULUM CONTEXT ===" in a_prompt
    assert CURRICULUM in a_prompt


def test_preamble_and_repair_reservation():
    env = (make_criterion("A-01", strategy="ratio_band"),)
    prompt, _ = build_envelope_prompt_and_source(
        env,
        "doc text",
        CURRICULUM,
        prompt_budget=32000,
        prompt_preamble="Program roadmap context (advisory): Course code: CHEM1",
    )
    assert "Program Coordinator evaluation agent" in prompt
    assert "Program roadmap context (advisory)" in prompt
    assert len(prompt) + len(REPAIR_SUFFIX) <= 32000


def test_preamble_carries_output_contract_rules():
    env = (make_criterion("A-05", strategy="curriculum_alignment"),)
    prompt, _ = build_envelope_prompt_and_source(
        env, "doc text", CURRICULUM, prompt_budget=32000
    )
    assert "exactly one object per criterion" in prompt
    assert "verbatim substring of the source text" in prompt
    assert "single JSON object with 'summary' and 'criterion_measurements'" in prompt
    assert "Do NOT calculate or return final numeric scores" in prompt


def test_stored_scoring_rule_is_injected_into_the_criterion_block():
    env = (
        make_criterion(
            "OP-02",
            strategy="count_band",
            scoring_rule="Count interactive elements; 4+ -> 4, 2-3 -> 3.",
        ),
    )
    prompt, _ = build_envelope_prompt_and_source(
        env, "doc text", CURRICULUM, prompt_budget=32000
    )
    assert "Scoring Rule: Count interactive elements; 4+ -> 4, 2-3 -> 3." in prompt


def test_missing_scoring_rule_omits_the_line():
    env = (make_criterion("OP-02", strategy="count_band"),)
    prompt, _ = build_envelope_prompt_and_source(
        env, "doc text", CURRICULUM, prompt_budget=32000
    )
    assert "Scoring Rule:" not in prompt


def test_oversized_source_is_downsampled():
    env = (make_criterion("OP-01", strategy="ratio_band"),)
    big = "sentence. " * 20000
    _, packet = build_envelope_prompt_and_source(
        env, big, CURRICULUM, prompt_budget=6000
    )
    assert len(packet) < len(big)


def test_instructions_exceeding_budget_raise():
    env = (make_criterion("A-01", strategy="ratio_band"),)
    with pytest.raises(AgentExecutionError):
        build_envelope_prompt_and_source(env, "doc", CURRICULUM, prompt_budget=200)
