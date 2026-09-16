"""Tests for GAD combined prompt rendering of llm_rubric_guidance criteria."""

from __future__ import annotations

import uuid

from server.modules.agents.gad.prompt import build_combined_prompt
from server.modules.rubrics.contracts import (
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    LlmScoreDescriptor,
)
from server.modules.rubrics.snapshot_contracts import build_evaluation_form_snapshot

_CHUNKS = [{"chunk_id": "chunk_1", "text": "Sample document text."}]


def _snapshot():
    crit = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="GAD-01",
        title="Free from Stereotypes",
        description="Judge freedom from gender stereotypes.",
        display_order=1,
        strategy_config=LlmRubricGuidanceConfig(
            guidance="Judge how free the material is from gender stereotypes.",
            level_descriptors=(
                LlmScoreDescriptor(score=4, descriptor="No stereotypes found."),
                LlmScoreDescriptor(
                    score=3,
                    descriptor=(
                        "At most one isolated instance of gender stereotyping or bias."
                    ),
                ),
                LlmScoreDescriptor(
                    score=2,
                    descriptor=(
                        "A few instances of gender stereotyping or bias, but "
                        "not pervasive."
                    ),
                ),
                LlmScoreDescriptor(score=1, descriptor="Frequent or pervasive."),
            ),
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="GAD Rubric v2",
        version_number=2,
        adapter_key="gad",
        adapter_version=2,
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="GAD",
                title="Inclusivity & Gender Sensitivity",
                display_order=1,
                criteria=(crit,),
            ),
        ),
    )
    return build_evaluation_form_snapshot(uuid.uuid4(), form)


def test_prompt_renders_guidance_and_level_descriptors() -> None:
    prompt = build_combined_prompt(packed_chunks=_CHUNKS, form_snapshot=_snapshot())
    system_text = prompt.system_instruction
    assert "Judge how free the material is from gender stereotypes." in system_text
    assert "Score 4: No stereotypes found." in system_text
    assert "Score 1: Frequent or pervasive." in system_text
    assert '"score"' in system_text
    assert '"chunk_id"' in system_text


def test_prompt_omits_do_not_include_score_when_all_llm_rubric_guidance() -> None:
    """Regression test for the final-review finding: for an all-
    llm_rubric_guidance envelope, the CRITICAL RULES block must not tell the
    model to omit 'score' while the per-criterion instructions (asserted in
    test_prompt_renders_guidance_and_level_descriptors above) simultaneously
    require one. The original version of this test asserted against the
    literal substring "Do not assign scores", which never appeared in either
    branch of the code and so passed regardless of whether the contradictory
    "Do NOT include 'score', 'criterion_score', 'band', ..." CRITICAL RULES
    bullet was actually excluded -- it let the real bug ship undetected."""
    prompt = build_combined_prompt(packed_chunks=_CHUNKS, form_snapshot=_snapshot())
    system_text = prompt.system_instruction
    assert "Do NOT include 'score'" not in system_text
    assert "do NOT include 'score'" not in system_text
    assert "FACT-ONLY EXTRACTION INSTRUCTIONS" not in system_text
    # The per-criterion "score" requirement must still be present and
    # uncontradicted.
    assert '"score": an integer from 1 to 4' in system_text
