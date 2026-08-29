"""Combined GAD extraction and repair prompt builders."""

from __future__ import annotations

import json
from typing import Any

from . import registry
from .grounding import MAX_INSTANCES_PER_CRITERION

# ---------------------------------------------------------------------------
# Canonical fallback counting rules per criterion
# ---------------------------------------------------------------------------

FALLBACK_GAD_INSTRUCTIONS = {
    "GAD-01": (
        "Count each unique instance of gender stereotypes or gender-biased "
        "representations — content that reinforces stereotypes about gender "
        "roles, abilities, behaviors, occupations, or characteristics, or that "
        "explicitly or implicitly portrays one gender using stereotypical "
        "assumptions. Do NOT count discussions of gender stereotypes presented "
        "for educational, analytical, historical, or critical purposes, or "
        "gender-neutral content. Count each unique instance once."
    ),
    "GAD-02": (
        "Count meaningful female and male representations: named individuals, "
        "names listed under a gender-labeled group or heading, characters, "
        "illustrations depicting people, examples or case studies involving "
        "people, explicit gender references (woman, man, girl, boy, female, "
        "male), and gender-specific pronouns (she, her, he, him). Count each "
        "meaningful representation once within the same discussion, example, or "
        "scenario; if the same individual appears in different examples, count "
        "each appearance separately. Do NOT infer gender when it is ambiguous, "
        "and ignore gender-neutral references."
    ),
    "GAD-03": (
        "Count each unique instance that portrays one gender as less capable, "
        "less respected, less deserving, or as having fewer opportunities than "
        "another. Do NOT count discussions of discrimination presented for "
        "educational, analytical, historical, or critical purposes. Count each "
        "unique instance once."
    ),
    "GAD-04": (
        "Count each unique instance where the material excludes one gender's "
        "experiences, disproportionately favors one gender's experiences, or "
        "assumes that activities, roles, responsibilities, interests, or "
        "aspirations belong primarily to one gender. Do NOT count "
        "gender-neutral examples or discussions presented for educational, "
        "analytical, historical, or critical purposes. Count each unique "
        "instance once."
    ),
    "GAD-05": (
        "Count each unique instance of discriminatory, prejudicial, "
        "exclusionary, or inequality-promoting content related to gender, race, "
        "social class, disability, religion, sexual orientation, or ethnic "
        "background. Do NOT count historical, educational, analytical, or "
        "critical discussions of discrimination. Count each unique instance "
        "once."
    ),
}

# ---------------------------------------------------------------------------
# 2.1 — Combined prompt builder (GAD-local, reuses runtime transport)
# ---------------------------------------------------------------------------


def build_combined_prompt(
    *,
    packed_chunks: list[dict[str, Any]],
    prompt_version: str | None,
    gad_managed_prompt: str | None = None,
    scoring_rules: dict[str, str] | None = None,
) -> str:
    """Build one combined fact-only extraction prompt.

    ``gad_managed_prompt`` is the active managed GAD prompt text (fact-only
    revision). When provided it is embedded as the primary instruction.
    ``packed_chunks`` are the only factual source — syllabus/curriculum
    reference context is excluded. ``scoring_rules`` is an optional dict
    mapping criterion codes to semantic counting guidance text; missing or
    blank entries fall back to ``FALLBACK_GAD_INSTRUCTIONS``.

    The returned JSON string is ready for total-budget enforcement and LLM
    transport. This is a GAD-local pipeline that does not use ITSO execution's
    score-shaped prompt template.
    """
    rules = scoring_rules or {}

    def _rule(code: str) -> str:
        supplied = rules.get(code)
        if supplied and supplied.strip():
            return supplied.strip()
        return FALLBACK_GAD_INSTRUCTIONS[code]

    instruction_parts: list[str] = []

    if gad_managed_prompt:
        instruction_parts.append(gad_managed_prompt)
    else:
        instruction_parts.append(
            "You are a GAD fact extractor. Examine the provided document "
            "chunks and extract specific factual observations for each "
            "GAD criterion below. Do not assign scores, do not make "
            "recommendations beyond the required summary."
        )

    instruction_parts.append(
        "\n\nFACT-ONLY EXTRACTION INSTRUCTIONS:\n"
        "You MUST extract facts ONLY from the 'document_chunks' provided "
        "below. Do not use external knowledge, syllabus, curriculum, or "
        "reference materials as factual sources.\n\n"
        "For each criterion, return exactly one section. The combined "
        "response must be a single JSON object with five keys: "
        "'gad-01', 'gad-02', 'gad-03', 'gad-04', 'gad-05'.\n\n"
    )

    # Per-criterion extraction details
    criterion_details: list[str] = []
    for definition in registry.CRITERIA:
        code = definition.criterion_id
        header = f"  {code} ({definition.title}):\n    {_rule(code)}\n"
        if definition.balance:
            criterion_details.append(
                header
                + "    Return a JSON object for this section with EXACTLY "
                "these fields and no others:\n"
                "    - \"female_count\": a non-negative integer.\n"
                "    - \"male_count\": a non-negative integer.\n"
                "    - \"summary\": a non-empty string, 1-2 sentences.\n"
                "    Do not include \"instances\", \"instance_count\", a score, "
                "or any other field."
            )
        else:
            criterion_details.append(
                header
                + "    Return a JSON object for this section with EXACTLY "
                "these fields and no others:\n"
                "    - \"instance_count\": a non-negative integer — the "
                "number of unique instances found; use 0 if none.\n"
                "    - \"instances\": an array (may be empty) of objects, each "
                "with exactly \"excerpt\" (an exact substring of a chunk's "
                "text) and \"chunk_id\" (matching a document_chunks id); at "
                f"most {MAX_INSTANCES_PER_CRITERION}.\n"
                "    - \"summary\": a non-empty string, 1-2 sentences.\n"
                "    Do not include a score, band, rating, or any other field."
            )

    instruction_parts.append("PER-CRITERION DETAILS:\n" + "\n".join(criterion_details))

    instruction_parts.append(
        "\n\nCRITICAL RULES:\n"
        "- Every excerpt must be an exact substring from a chunk's 'text' field.\n"
        "- Every 'chunk_id' must exactly match a chunk_id from document_chunks.\n"
        "- Return ONLY valid JSON. No markdown fences, no commentary.\n"
        "- Do NOT include 'score', 'criterion_score', 'band', 'rating', "
        "'grade', or any numeric score fields.\n"
        "- All 'instance_count', 'female_count', 'male_count' must be "
        "non-negative integers.\n"
        "- All summaries must be non-empty strings (1-2 sentences)."
    )

    instructions = "\n\n".join(instruction_parts)

    payload: dict[str, Any] = {
        "agent": "gad",
        "prompt_version": prompt_version,
        "document_chunks": packed_chunks,
        "instructions": [instructions],
    }

    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 3.1 — Whole-envelope fact-only repair prompt (SAME frozen context)
# ---------------------------------------------------------------------------

_REPAIR_COMBINED_TEMPLATE = (
    "{full_context}\n\n"
    "Your previous GAD extraction response was incomplete or malformed. "
    "Review the error below, then return a COMPLETE corrected JSON object "
    "with ALL FIVE required sections (gad-01 through gad-05). "
    "Follow the same fact-only extraction rules as above.\n\n"
    "Do NOT change factual content beyond what is needed to fix the error. "
    "Do NOT add numeric score fields.\n\n"
    "Error: {error}\n\n"
    "Return ONLY the complete corrected JSON object."
)


def build_combined_repair_prompt(
    *,
    full_prompt_context: str,
    partial_response: str,
    error_detail: str,
) -> str:
    """Build a whole-envelope repair prompt that includes the SAME frozen context.

    The repair receives the identical packed chunks and fact-only instructions
    as the initial call, plus only a bounded error category/path. Rejected
    output is never echoed back to the model.
    The model never sees a reduced or altered context.
    """
    return _REPAIR_COMBINED_TEMPLATE.format(
        full_context=full_prompt_context,
        error=error_detail[:500],
    )


__all__ = [
    "FALLBACK_GAD_INSTRUCTIONS",
    "build_combined_prompt",
    "build_combined_repair_prompt",
]
