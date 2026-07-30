"""Single-call LLM check: is each mapped curriculum objective addressed by
the SLM, and at what observed I/E/D depth?

One call for the whole set of mapped objectives per run -- never one call
per objective (shared token/minute budget across SME/Coordinator/GAD/ITSO).
Independent of SME's objective extraction: this pipeline reads the SLM
content fresh rather than reusing any prior agent's extracted objectives.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

PROMPT = """You are checking a Self-Paced Learning Module (SLM) against a
list of curriculum objectives it is expected to address.

Your job is to extract facts only. Do NOT assign any score or I/E/D label
yourself except for the observed depth described below.

For EACH objective below, decide:
1. is_addressed: does the SLM content address this objective at all? Use
   this STRICT rule: the SLM must directly cover the same knowledge/skill
   named in the objective (matching topic and intent). A generic or
   unrelated mention does NOT count. If unsure, mark is_addressed = false.
2. observed_level: if addressed, classify the DEPTH at which the SLM
   engages this objective, using the same three tiers as the curriculum
   map itself:
   - "I" (Introductory): the objective is merely introduced or mentioned.
   - "E" (Enabling): the SLM has students practice or apply it.
   - "D" (Demonstrative): the SLM requires students to independently
     demonstrate mastery of it (e.g. an assessed project, case study, or
     capstone-style task).
   If not addressed, observed_level must be null.
3. evidence: for every objective you mark is_addressed = true, quote the
   exact SLM text that supports it. If you cannot quote real content, mark
   is_addressed = false and evidence = null.

Return ONLY valid JSON in exactly this shape:
{{
  "results": [
    {{
      "objective_code": "IT08",
      "is_addressed": true,
      "observed_level": "I",
      "evidence": "exact quote or null"
    }}
  ]
}}

CURRICULUM OBJECTIVES FOR THIS COURSE:
{objectives}

SLM CONTENT:
{content}
"""


def run_alignment_llm(
    client: Any,
    mapped_objectives: list[dict[str, Any]],
    slm_text: str,
) -> list[dict[str, Any]]:
    """Return per-objective alignment facts, filtered to requested codes.

    Returns an empty list on any failure (bad JSON, LLM error, no mapped
    objectives) so the caller can short-circuit cleanly rather than
    crashing the whole check.
    """
    if not mapped_objectives:
        return []

    valid_codes = {obj["code"] for obj in mapped_objectives}
    try:
        raw = client.generate(
            PROMPT.format(
                objectives=json.dumps(mapped_objectives, ensure_ascii=False),
                content=slm_text,
            ),
            temperature=0.0,
            max_new_tokens=1800,
        )
        data = json.loads(raw)
        raw_results = list(data.get("results", []))
    except Exception as exc:
        logger.warning(
            "Curriculum alignment LLM check failed: %s",
            str(exc)[:200],
        )
        return []

    filtered: list[dict[str, Any]] = []
    for item in raw_results:
        code = item.get("objective_code")
        if code not in valid_codes:
            continue
        filtered.append(
            {
                "objective_code": code,
                "is_addressed": bool(item.get("is_addressed", False)),
                "observed_level": item.get("observed_level"),
                "evidence": item.get("evidence"),
            }
        )
    return filtered


__all__ = ["run_alignment_llm", "PROMPT"]
