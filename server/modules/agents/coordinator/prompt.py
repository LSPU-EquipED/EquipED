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

from ..exceptions import AgentExecutionError
from .slicing import downsample

REPAIR_SUFFIX = (
    "\n\nVALIDATOR_FAILURE category=COORDINATOR_INVALID path=criterion_measurements. "
    "Regenerate ONLY the complete JSON response; do not include commentary."
)

COORDINATOR_PREAMBLE = (
    "You are the Program Coordinator evaluation agent for Student Learning\n"
    "Materials (SLM). You judge each criterion the same way the Subject Matter\n"
    "Expert does, but from a curriculum-alignment perspective: your role is to\n"
    "confirm the material serves the confirmed course curriculum. For the\n"
    "curriculum-alignment criterion you are given a CURRICULUM CONTEXT block —\n"
    "every alignment claim you make about it must quote it verbatim."
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
            "Instructions: Extract all units from the source text into total_units. "
            "For each unit, assign a unique unit_id and provide an exact verbatim "
            "evidence quote substring from the source text. List the unit_ids of "
            "all qualifying units in qualifying_unit_ids. Set has_measurable_content "
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
                    "unit_id": "u1",
                    "evidence": "Exact verbatim quote from the source text for unit 1.",
                    "label": "Unit 1 label",
                }
            ],
            "qualifying_unit_ids": ["u1"],
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
                    "reasoning": (
                        "Why the curriculum span addresses this objective."
                    ),
                }
            ],
            "summary": "Overview of objective-curriculum alignment.",
        }
    return {"criterion_id": criterion.criterion_code}


def build_envelope_prompt(
    criteria: tuple[CriterionDefinition, ...],
    source_text: str,
    curriculum_context: str,
    prompt_preamble: str | None = None,
) -> str:
    criteria_blocks = "\n\n".join(_criterion_prompt_block(c) for c in criteria)
    example = {
        "summary": "Brief summary of evaluation findings for these criteria.",
        "criterion_measurements": [_example_measurement(c) for c in criteria],
    }
    example_json = json.dumps(example, indent=2, ensure_ascii=False)

    instructions = [
        "=== EVALUATOR INSTRUCTIONS ===",
        COORDINATOR_PREAMBLE,
        "CRITERIA TO EVALUATE:",
        criteria_blocks,
        "REQUIRED JSON OUTPUT STRUCTURE:",
        example_json,
        "=== END EVALUATOR INSTRUCTIONS ===",
        "",
        "=== UNTRUSTED SOURCE TEXT ===",
        source_text,
        "=== END SOURCE TEXT ===",
    ]

    if any(isinstance(c.strategy_config, CurriculumAlignmentConfig) for c in criteria):
        instructions.extend(
            [
                "=== CURRICULUM CONTEXT ===",
                curriculum_context,
                "=== END CURRICULUM CONTEXT ===",
            ]
        )

    body = "\n\n".join(instructions)
    if prompt_preamble and prompt_preamble.strip():
        return prompt_preamble.strip() + "\n\n" + body
    return body


def build_envelope_prompt_and_source(
    criteria: tuple[CriterionDefinition, ...],
    canonical_source_text: str,
    curriculum_context: str,
    prompt_budget: int,
    prompt_preamble: str | None = None,
) -> tuple[str, str]:
    """Construct prompt reserving REPAIR_SUFFIX and downsampling source text."""
    template_without_source = build_envelope_prompt(
        criteria,
        source_text="",
        curriculum_context=curriculum_context,
        prompt_preamble=prompt_preamble,
    )
    available_for_source = (
        prompt_budget - len(template_without_source) - len(REPAIR_SUFFIX)
    )
    if available_for_source <= 0:
        raise AgentExecutionError(
            "Coordinator prompt instructions exceed total prompt budget"
        )

    source_packet = downsample(
        canonical_source_text, budget=available_for_source, windows=6
    )
    # slicing.downsample joins windows with GAP_MARKER and can slightly exceed
    # the byte budget; clamp so the assembled prompt stays within prompt_budget.
    if len(source_packet) > available_for_source:
        source_packet = source_packet[:available_for_source]
    prompt = build_envelope_prompt(
        criteria,
        source_text=source_packet,
        curriculum_context=curriculum_context,
        prompt_preamble=prompt_preamble,
    )
    if len(prompt) + len(REPAIR_SUFFIX) > prompt_budget:
        raise AgentExecutionError("Coordinator prompt exceeds total prompt budget")

    return prompt, source_packet


__all__ = [
    "REPAIR_SUFFIX",
    "build_envelope_prompt",
    "build_envelope_prompt_and_source",
]
