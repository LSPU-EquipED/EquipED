"""Prompt builder and budget management for SME evaluation envelopes."""

from __future__ import annotations

import json
from typing import Any

from equiped_harness.contracts import (
    CountBandConfig,
    CriterionDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)
from equiped_harness.runtime.prompts import AgentPrompt, PromptEnvelopeBuilder
from equiped_harness.sme.source_selection import select_source_text


def _criterion_prompt_block(criterion: CriterionDefinition) -> str:
    lines = [
        f"CRITERION: {criterion.criterion_code}",
        f"Title: {criterion.title}",
        f"Description: {criterion.description}",
    ]
    if criterion.scoring_rule:
        lines.append(f"Scoring Rule: {criterion.scoring_rule}")

    config = criterion.strategy_config
    if isinstance(config, LlmRubricGuidanceConfig):
        lines.append("Strategy: LLM Rubric Guidance")
        lines.append(f"Guidance: {config.guidance}")
        if config.level_descriptors:
            lines.append("Level Descriptors:")
            for desc in sorted(config.level_descriptors, key=lambda d: d.score):
                lines.append(f"  - Score {desc.score}: {desc.descriptor}")
        lines.append(
            "Instructions: Assign an integer score from 1 to 4 and provide an "
            "exact, verbatim evidence quote substring from the source text with "
            "finding='present', or follow the absence contract above."
        )
    elif isinstance(config, CountBandConfig):
        lines.append("Strategy: Grounded Count")
        lines.append(
            "Instructions: Extract all distinct, genuine matching instances from "
            "the source text. For each instance found, 'excerpt' must be an exact "
            "verbatim quote substring from the source text. If NO matching "
            "instances exist in the document, set 'instances' to an empty list []. "
            "Do NOT fabricate or describe an excerpt. Do NOT assign a score."
        )
    elif isinstance(config, RatioBandConfig):
        lines.append("Strategy: Qualifying Coverage Ratio")
        lines.append(
            "Instructions: Extract all units from the source text into total_units. "
            'For each unit, assign a distinct unique unit_id (e.g. "u1", "u2") '
            "and provide an exact verbatim evidence quote substring from the "
            "source text. List the unit_ids of all qualifying units in "
            "qualifying_unit_ids. Set has_measurable_content to true whenever "
            "total_units is not empty (set to false ONLY if the document has no "
            "content to measure, in which case total_units and "
            "qualifying_unit_ids must both be empty []). Do NOT assign a score."
        )

    return "\n".join(lines)


def _example_measurement(criterion: CriterionDefinition) -> dict[str, Any]:
    config = criterion.strategy_config
    if isinstance(config, LlmRubricGuidanceConfig):
        return {
            "criterion_id": criterion.criterion_code,
            "criterion_title": criterion.title,
            "score": 3,
            "finding": "present",
            "evidence": (
                "Exact verbatim quote from the source text supporting the score."
            ),
            "reasoning": (
                "Brief explanation of how the evidence aligns with the rubric guidance."
            ),
        }
    elif isinstance(config, CountBandConfig):
        return {
            "criterion_id": criterion.criterion_code,
            "criterion_title": criterion.title,
            "instances": [
                {
                    "excerpt": "Exact verbatim excerpt from the source text.",
                    "explanation": "Brief explanation of this instance.",
                }
            ],
            "summary": "Overview of extracted instances.",
        }
    elif isinstance(config, RatioBandConfig):
        return {
            "criterion_id": criterion.criterion_code,
            "total_units": [
                {
                    "unit_id": "u1",
                    "evidence": "Exact verbatim quote from the source text for unit 1.",
                    "label": "Unit 1 label",
                },
                {
                    "unit_id": "u2",
                    "evidence": "Exact verbatim quote from the source text for unit 2.",
                    "label": "Unit 2 label",
                },
            ],
            "qualifying_unit_ids": ["u1"],
            "has_measurable_content": True,
            "summary": "Overview of evaluated units.",
        }
    return {"criterion_id": criterion.criterion_code}


_SME_PREAMBLE_BASE = (
    "You are the Subject Matter Expert (SME) evaluation agent for Student "
    "Learning Materials (SLM).\n"
    "Evaluate the criteria below strictly and impartially against the "
    "provided UNTRUSTED source text.\n"
    "- Ground all extractions: every evidence and excerpt MUST be an exact, "
    "verbatim substring of the source text.\n"
    "- For rubric-guidance criteria, if required content is not found in the "
    "supplied passages, use finding='absent', evidence=null and nonblank reasoning "
    "explaining what is missing. Score using the rubric descriptors; never "
    "invent a quote or change the score just to supply evidence. Absence applies "
    "only to the supplied text, not omitted portions of the document.\n"
    "- Return a single JSON object with 'summary' and "
    "'criterion_measurements'.\n"
    "- 'criterion_measurements' must contain exactly one object per "
    "criterion in the exact order listed below."
)

_NO_SELF_SCORE_FOR_COUNT_RATIO = (
    "\n- Do NOT calculate or return final numeric scores for count or ratio "
    "strategies; emit only the required measurement structure."
)


def _build_sme_preamble(criteria: tuple[CriterionDefinition, ...]) -> str:
    """SME's preamble, only warning against self-scoring if this envelope
    actually contains a count/ratio criterion -- for an all-llm_rubric_
    guidance envelope, that warning would directly contradict the per-
    criterion "assign an integer score" instruction."""
    has_calculator_criterion = any(
        isinstance(c.strategy_config, (CountBandConfig, RatioBandConfig))
        for c in criteria
    )
    if has_calculator_criterion:
        return _SME_PREAMBLE_BASE + _NO_SELF_SCORE_FOR_COUNT_RATIO
    return _SME_PREAMBLE_BASE


_GAP_MARKER_WARNING = (
    "The source text may contain '[...]' markers where document sections were "
    "omitted to fit the budget; do NOT quote across a '[...]' marker and do NOT "
    "fabricate text to fill omitted sections. Passages are selected using section "
    "and rubric-vocabulary hints; selection is not a complete-document review. "
    "Do not infer whole-document absence, counts, ratios, or topic continuity "
    "from incomplete coverage. Unrecognized headings do not prove absence."
)


def build_envelope_prompt_and_source(
    criteria: tuple[CriterionDefinition, ...],
    canonical_source_text: str,
    prompt_budget: int,
    prompt_preamble: str | None = None,
) -> tuple[AgentPrompt, str]:
    """Construct role-separated prompt reserving repair budget.

    The system instruction carries the SME preamble, criterion blocks, JSON
    schema example, and gap-marker warning. The user context carries the
    rubric-selected untrusted source passages. Selection runs in memory and
    adds no inference requests or persistent document state.
    """
    criteria_blocks = "\n\n".join(_criterion_prompt_block(c) for c in criteria)
    example = {
        "summary": "Brief summary of evaluation findings for these criteria.",
        "criterion_measurements": [_example_measurement(c) for c in criteria],
    }
    example_json = json.dumps(example, indent=2, ensure_ascii=False)
    builder = PromptEnvelopeBuilder(
        evaluator_preamble=_build_sme_preamble(criteria),
        criteria_blocks=criteria_blocks,
        example_json=example_json,
        total_budget=prompt_budget,
        reserved_repair_chars=600,
        gap_marker_warning=_GAP_MARKER_WARNING,
    )
    prompt, source_packet = builder.build(
        canonical_source_text,
        managed_prompt=prompt_preamble,
    )
    # Reuse the builder's exact source allowance, including fixed instructions
    # and its repair reservation. Only SME replaces the uniform sample.
    selected_source = select_source_text(
        canonical_source_text, criteria, budget=len(source_packet)
    )
    if selected_source != source_packet:
        prompt = AgentPrompt(
            system_instruction=prompt.system_instruction,
            user_context=(
                f"=== UNTRUSTED SOURCE TEXT ===\n{selected_source}\n"
                "=== END UNTRUSTED SOURCE TEXT ==="
            ),
        )
        source_packet = selected_source
    return prompt, source_packet


__all__ = ["build_envelope_prompt_and_source"]
