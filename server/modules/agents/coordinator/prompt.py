"""Prompt builder and budget management for Coordinator evaluation envelopes."""

from __future__ import annotations

import json
from typing import Any

from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)

from ..runtime.prompts import AgentPrompt, PromptEnvelopeBuilder
from ..runtime.slicing import GAP_MARKER

REPAIR_SUFFIX = (
    "\n\nVALIDATOR_FAILURE category=COORDINATOR_INVALID path=criterion_measurements. "
    "Regenerate ONLY the complete JSON response matching the required schema, "
    "criteria order, and exact field set: no extra or missing fields. "
    "Evidence, excerpts, and objective_text MUST each be an exact verbatim "
    "substring of the SOURCE TEXT; assessment_excerpt MUST be an exact verbatim "
    "substring of the CURRICULUM CONTEXT. "
    "Emit each repeated identical fact only once. "
    "Duplicate ratio units must use one consistent qualifies boolean. "
    "Do not include commentary."
)


COORDINATOR_PREAMBLE = (
    "You are the Program Coordinator evaluation agent for Student Learning\n"
    "Materials (SLM). You judge each criterion the same way the Subject Matter\n"
    "Expert does, but from a curriculum-alignment perspective: your role is to\n"
    "confirm the material serves the confirmed course curriculum. For the\n"
    "curriculum-alignment criterion you are given a CURRICULUM CONTEXT block —\n"
    "every alignment claim you make about it must quote it verbatim.\n"
    "- Ground all extractions: every evidence and excerpt MUST be an exact, "
    "verbatim substring of the source text.\n"
    "- The source text may contain '[...]' markers where document sections were "
    "omitted to fit the budget; do NOT quote across a '[...]' marker and do NOT "
    "fabricate text to fill omitted sections.\n"
    "- Return a single JSON object with 'summary' and 'criterion_measurements'.\n"
    "- 'criterion_measurements' must contain exactly one object per criterion, "
    "in the exact order listed below.\n"
    "- Do NOT calculate or return final numeric scores for count or ratio "
    "strategies; emit only the required measurement structure."
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
            "the source text. For each instance, provide an exact verbatim "
            "excerpt substring from the source text. Do NOT assign a score."
        )
    elif isinstance(config, RatioBandConfig):
        lines.append("Strategy: Qualifying Coverage Ratio")
        lines.append(
            "Instructions: Extract all units from the source text into total_units "
            "in document order. For each unit, provide an exact verbatim evidence "
            "quote substring from the source text and a qualifies boolean (true "
            "for qualifying units, false otherwise). You may include an optional "
            "label and location per unit. Do NOT emit unit_id or "
            "qualifying_unit_ids; units are linked by document order. "
            "Set has_measurable_content "
            "to true (or false if the document has no relevant content to measure). "
            "Do NOT assign a score."
        )
    elif isinstance(config, CurriculumAlignmentConfig):
        lines.append("Strategy: Curriculum Objective Alignment")
        lines.append(
            "Instructions: Extract every learning objective STATED IN THE SLM as an "
            "exact verbatim substring of the source text. For each objective, decide "
            "whether the CURRICULUM CONTEXT addresses it. If addressed, copy the exact "
            "verbatim span from CURRICULUM CONTEXT that supports it into "
            "assessment_excerpt; if not, set is_aligned false and leave "
            "assessment_excerpt null. Do NOT assign a score."
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
            "criterion_title": criterion.title,
            "total_units": [
                {
                    "evidence": "Exact verbatim quote from the source text for unit 1.",
                    "qualifies": True,
                    "label": "Unit 1 label",
                }
            ],
            "has_measurable_content": True,
            "summary": "Overview of evaluated units.",
        }
    elif isinstance(config, CurriculumAlignmentConfig):
        return {
            "criterion_id": criterion.criterion_code,
            "criterion_title": criterion.title,
            "alignments": [
                {
                    "objective_text": "Exact verbatim objective excerpt from the SLM.",
                    "is_aligned": True,
                    "assessment_excerpt": (
                        "Exact verbatim span from the curriculum context."
                    ),
                    "reasoning": ("Why the curriculum span addresses this objective."),
                }
            ],
            "summary": "Overview of objective-curriculum alignment.",
        }
    return {"criterion_id": criterion.criterion_code}


_GAP_MARKER_WARNING = (
    "The source text may contain '[...]' markers where document sections were "
    "omitted to fit the budget; do NOT quote across a '[...]' marker and do NOT "
    "fabricate text to fill omitted sections."
)


def build_envelope_prompt_and_source(
    criteria: tuple[CriterionDefinition, ...],
    canonical_source_text: str,
    curriculum_context: str,
    prompt_budget: int,
    prompt_preamble: str | None = None,
) -> tuple[AgentPrompt, str]:
    """Construct role-separated prompt reserving repair budget.

    The system instruction carries the evaluator preamble, criterion blocks,
    JSON schema example, and gap-marker warning. The user context carries the
    downsampled untrusted source text plus the curriculum context for
    curriculum-alignment envelopes.
    """
    criteria_blocks = "\n\n".join(_criterion_prompt_block(c) for c in criteria)
    example = {
        "summary": "Brief summary of evaluation findings for these criteria.",
        "criterion_measurements": [_example_measurement(c) for c in criteria],
    }
    example_json = json.dumps(example, indent=2, ensure_ascii=False)
    builder = PromptEnvelopeBuilder(
        evaluator_preamble=COORDINATOR_PREAMBLE,
        criteria_blocks=criteria_blocks,
        example_json=example_json,
        total_budget=prompt_budget,
        reserved_repair_chars=600,
        gap_marker_warning=_GAP_MARKER_WARNING,
    )
    has_curriculum = any(
        isinstance(c.strategy_config, CurriculumAlignmentConfig) for c in criteria
    )
    prompt, source_packet = builder.build(
        canonical_source_text,
        reference_context=curriculum_context if has_curriculum else None,
        reference_heading="CURRICULUM CONTEXT",
        managed_prompt=prompt_preamble,
    )
    return prompt, source_packet


__all__ = [
    "COORDINATOR_PREAMBLE",
    "GAP_MARKER",
    "REPAIR_SUFFIX",
    "build_envelope_prompt_and_source",
]
