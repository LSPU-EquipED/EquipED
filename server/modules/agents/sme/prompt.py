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

from ..exceptions import AgentExecutionError
from .slicing import GAP_MARKER

REPAIR_SUFFIX = (
    "\n\nVALIDATOR_FAILURE category=SME_INVALID path=criterion_measurements. "
    "Regenerate ONLY the complete JSON response; do not include commentary."
)


def downsample_source_text(text: str, budget: int, windows: int = 6) -> str:
    """Sample evenly-spaced windows spanning the entire document.

    Ensures the final length is strictly <= budget and the last window is
    anchored to the true tail of the document.
    """
    if len(text) <= budget:
        return text
    if budget <= len(GAP_MARKER):
        raise AgentExecutionError("SME source budget cannot mark omitted content")

    total_gaps_len = (windows - 1) * len(GAP_MARKER)
    if budget <= total_gaps_len + windows:
        raise AgentExecutionError("SME source budget cannot mark omitted content")

    chunk_size = max(1, (budget - total_gaps_len) // windows)
    chunks: list[str] = []
    for i in range(windows):
        if i == windows - 1:
            start = max(0, len(text) - chunk_size)  # True tail
        else:
            start = (i * len(text)) // windows
        chunks.append(text[start : start + chunk_size])

    sampled = GAP_MARKER.join(chunks)
    if len(sampled) > budget:
        sampled = sampled[:budget]
    return sampled


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
    return {"criterion_id": criterion.criterion_code}


def build_envelope_prompt(
    criteria: tuple[CriterionDefinition, ...],
    source_text: str,
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
        (
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
        ),
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

    body = "\n\n".join(instructions)
    if prompt_preamble and prompt_preamble.strip():
        return prompt_preamble.strip() + "\n\n" + body
    return body


def build_envelope_prompt_and_source(
    criteria: tuple[CriterionDefinition, ...],
    canonical_source_text: str,
    prompt_budget: int,
    prompt_preamble: str | None = None,
) -> tuple[str, str]:
    """Construct prompt reserving REPAIR_SUFFIX and downsampling source text."""
    template_without_source = build_envelope_prompt(
        criteria, source_text="", prompt_preamble=prompt_preamble
    )
    available_for_source = (
        prompt_budget - len(template_without_source) - len(REPAIR_SUFFIX)
    )
    if available_for_source <= 0:
        raise AgentExecutionError("SME prompt instructions exceed total prompt budget")

    source_packet = downsample_source_text(
        canonical_source_text, budget=available_for_source, windows=6
    )
    prompt = build_envelope_prompt(
        criteria, source_text=source_packet, prompt_preamble=prompt_preamble
    )
    if len(prompt) + len(REPAIR_SUFFIX) > prompt_budget:
        raise AgentExecutionError("SME prompt exceeds total prompt budget")

    return prompt, source_packet


__all__ = [
    "REPAIR_SUFFIX",
    "build_envelope_prompt",
    "build_envelope_prompt_and_source",
    "downsample_source_text",
]
