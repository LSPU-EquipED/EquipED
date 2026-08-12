"""Combined GAD extraction and repair prompt builders."""

from __future__ import annotations

import json
from typing import Any

from . import registry
from .grounding import MAX_INSTANCES_PER_CRITERION

# ---------------------------------------------------------------------------
# 2.1 — Combined prompt builder (GAD-local, reuses runtime transport)
# ---------------------------------------------------------------------------


def build_combined_prompt(
    *,
    packed_chunks: list[dict[str, Any]],
    prompt_version: str | None,
    gad_managed_prompt: str | None = None,
) -> str:
    """Build one combined fact-only extraction prompt.

    ``gad_managed_prompt`` is the active managed GAD prompt text (fact-only
    revision). When provided it is embedded as the primary instruction.
    ``packed_chunks`` are the only factual source — syllabus/curriculum
    reference context is excluded.

    The returned JSON string is ready for total-budget enforcement and LLM
    transport. This is a GAD-local pipeline that does not use ITSO execution's
    score-shaped prompt template.
    """
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
        if definition.balance:
            criterion_details.append(
                f"  {definition.criterion_id} ({definition.title}):\n"
                f"    - Count meaningful female ('female_count') and male "
                f"('male_count') representations.\n"
                f"    - A meaningful representation includes: named individuals, "
                f"characters, illustrations depicting people, examples or case "
                f"studies involving people, explicit gender references (e.g., "
                f"woman, man, girl, boy, female, male), and gender-specific "
                f"pronouns (e.g., she, her, he, him).\n"
                f"    - If a list, table, or paragraph labels people as female "
                f"or male, count each listed person/name in the matching gender "
                f"count.\n"
                f"    - Count each representation once within the same discussion, "
                f"example, or case study. If the same individual appears in "
                f"different examples, count each appearance separately.\n"
                f"    - Do NOT infer gender when ambiguous. Ignore gender-neutral "
                f"references.\n"
                f"    - Include a non-empty 'summary' (1-2 sentences).\n"
                f"    - Do NOT include 'instances', 'instance_count', or any "
                f"numeric score fields."
            )
        else:
            criterion_details.append(
                f"  {definition.criterion_id} ({definition.title}):\n"
                f"    - Count instances with non-negative integer "
                f"'instance_count'.\n"
                f"    - List each unique instance with exact 'excerpt' "
                f"and 'chunk_id' from document_chunks.\n"
                f"    - Max {MAX_INSTANCES_PER_CRITERION} instances.\n"
                f"    - Include a non-empty 'summary' (1-2 sentences).\n"
                f"    - Do NOT include numeric score fields."
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
