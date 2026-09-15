"""Prompt builder and budget management for SME evaluation envelopes."""

from __future__ import annotations

import json
from typing import Any

from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)

from ..runtime.prompts import AgentPrompt, PromptEnvelopeBuilder

REPAIR_SUFFIX = (
    "\n\nVALIDATOR_FAILURE category=SME_INVALID path=criterion_measurements. "
    "Regenerate ONLY the complete JSON response; do not include commentary."
)


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
            "exact, verbatim evidence quote substring from the source text."
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


SME_PREAMBLE = (
    "You are the Subject Matter Expert (SME) evaluation agent for Student "
    "Learning Materials (SLM).\n"
    "Evaluate the criteria below strictly and impartially against the "
    "provided UNTRUSTED source text.\n"
    "- Ground all extractions: every evidence and excerpt MUST be an exact, "
    "verbatim substring of the source text.\n"
    "- Return a single JSON object with 'summary' and "
    "'criterion_measurements'.\n"
    "- 'criterion_measurements' must contain exactly one object per "
    "criterion in the exact order listed below.\n"
    "- Do NOT calculate or return final numeric scores for count or ratio "
    "strategies; emit only the required measurement structure."
)

_GAP_MARKER_WARNING = (
    "The source text may contain '[...]' markers where document sections were "
    "omitted to fit the budget; do NOT quote across a '[...]' marker and do NOT "
    "fabricate text to fill omitted sections."
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
    downsampled untrusted source text.
    """
    criteria_blocks = "\n\n".join(_criterion_prompt_block(c) for c in criteria)
    example = {
        "summary": "Brief summary of evaluation findings for these criteria.",
        "criterion_measurements": [_example_measurement(c) for c in criteria],
    }
    example_json = json.dumps(example, indent=2, ensure_ascii=False)
    builder = PromptEnvelopeBuilder(
        evaluator_preamble=SME_PREAMBLE,
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
    return prompt, source_packet


__all__ = [
    "REPAIR_SUFFIX",
    "SME_PREAMBLE",
    "build_envelope_prompt_and_source",
]
