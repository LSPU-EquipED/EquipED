"""Single-pass GAD combined extraction, validation, and repair.

Task 1.1-3.4 implementation: one combined fact-only LLM call replaces
five sequential criterion-level extraction calls. The model extracts
facts only; final numeric scoring remains deterministic in the registry.
"""

from __future__ import annotations

import json
import logging
import re
from collections import OrderedDict
from typing import Any

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError
from . import registry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1.1 — Extraction schema version (single source for envelope)
# Registry version lives in registry.REGISTRY_VERSION — DO NOT duplicate
# ---------------------------------------------------------------------------

EXTRACTION_SCHEMA_VERSION = "1.0.0"
"""Version of the combined extraction envelope schema."""

MAX_INSTANCES_PER_CRITERION = 10
"""Hard cap on evidence instances per criterion to bound output size."""

# ---------------------------------------------------------------------------
# Canonical section keys — the ONLY accepted top-level envelope keys.
# ---------------------------------------------------------------------------

CANONICAL_SECTION_KEYS: frozenset[str] = frozenset({
    "gad-01",
    "gad-02",
    "gad-03",
    "gad-04",
    "gad-05",
})

_INSTANCE_SECTION_KEYS: frozenset[str] = frozenset({
    "gad-01",
    "gad-03",
    "gad-04",
    "gad-05",
})

_BALANCE_SECTION_KEYS: frozenset[str] = frozenset({"gad-02"})

# ---------------------------------------------------------------------------
# Numeric-score blocklist — every known alias that assigns scores.
# ---------------------------------------------------------------------------

_SCORE_BLOCKLIST: frozenset[str] = frozenset({
    "score",
    "criterion_score",
    "numeric_score",
    "band",
    "score_band",
    "final_score",
    "subtotal",
    "rating",
    "grade",
    "mark",
    "points",
    "value",
    "result",
    "level",
})

# ---------------------------------------------------------------------------
# 1.2 — Strict combined response parsing with object_pairs_hook
# ---------------------------------------------------------------------------


def _hook_detect_duplicate_keys(pairs: list[tuple[str, Any]]) -> OrderedDict:
    """``object_pairs_hook`` that raises on duplicate keys within the SAME
    JSON object (per-object scope, not global).
    """
    seen: dict[str, str] = {}
    for key, _val in pairs:
        lower = key.strip().lower()
        if lower in seen:
            raise ValueError(
                f"duplicate key (case-insensitive): '{key}' "
                f"(first occurrence as '{seen[lower]}')"
            )
        seen[lower] = key
    return OrderedDict(pairs)


def parse_combined_response(raw_response: str) -> dict[str, Any]:
    """Parse and strictly validate the combined GAD extraction envelope.

    * Uses ``object_pairs_hook`` to catch exact/case-insensitive duplicates
      **before** JSON construction.
    * Normalises all keys to canonical lower-case (``gad-01``…``gad-05``).
    * Rejects **any** key not in ``CANONICAL_SECTION_KEYS``.
    * Rejects any section containing a numeric-score blocklist field.
    * Validates each section's strict schema (field types, presence,
      non-empty summaries, prohibition of cross-type fields).
    * Returns a dict with exactly the five canonical keys.

    Raises ``AgentExecutionError`` on any violation — never defaults ``{}``.
    """
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise AgentExecutionError("GAD combined response is empty or non-string")

    payload = raw_response.strip()
    fenced = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$",
        payload,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        payload = fenced.group(1).strip()
    elif not payload.startswith("{"):
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start : end + 1]

    try:
        parsed = json.loads(payload, object_pairs_hook=_hook_detect_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        msg = str(exc)
        if "duplicate key" in msg.lower():
            raise AgentExecutionError(
                f"GAD combined response has {msg}"
            ) from exc
        raise AgentExecutionError(
            f"GAD combined response is invalid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, (dict, OrderedDict)):
        raise AgentExecutionError("GAD combined response must be a JSON object")

    # --- Normalise keys to canonical lower-case ---
    normalised: dict[str, Any] = {}
    for raw_key, val in parsed.items():
        canonical_key = raw_key.strip().lower()
        normalised[canonical_key] = val

    # --- Reject unknown sections ---
    unknown = set(normalised) - CANONICAL_SECTION_KEYS
    if unknown:
        raise AgentExecutionError(
            f"GAD combined response contains unknown section(s): "
            f"{sorted(unknown)}"
        )

    # --- Reject missing required sections ---
    missing = CANONICAL_SECTION_KEYS - set(normalised)
    if missing:
        raise AgentExecutionError(
            f"GAD combined response missing required sections: {sorted(missing)}"
        )

    # --- Reject numeric-score fields at every level ---
    _reject_score_fields(normalised)

    # --- Validate each section's strict schema ---
    for section_key in CANONICAL_SECTION_KEYS:
        section_val = normalised[section_key]
        if not isinstance(section_val, dict):
            raise AgentExecutionError(
                f"GAD section '{section_key}' must be a JSON object, "
                f"got {type(section_val).__name__}"
            )
        _validate_section(section_key, section_val)

    return normalised


# ---------------------------------------------------------------------------
# Recursive score-field rejection
# ---------------------------------------------------------------------------


def _reject_score_fields(obj: Any, path: str = "") -> None:
    """Recursively reject any dict containing a blocklisted numeric-score key.

    Raises ``AgentExecutionError`` immediately on first prohibited field.
    """
    if isinstance(obj, dict):
        for key, val in obj.items():
            lower_key = key.strip().lower()
            if lower_key in _SCORE_BLOCKLIST:
                raise AgentExecutionError(
                    f"GAD combined response contains prohibited numeric-score "
                    f"field '{key}' at {path or 'root'}"
                )
            _reject_score_fields(val, f"{path}.{key}" if path else key)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _reject_score_fields(item, f"{path}[{idx}]")


# ---------------------------------------------------------------------------
# Per-section strict schema validation
# ---------------------------------------------------------------------------

_ALLOWED_BALANCE_FIELDS: frozenset[str] = frozenset({
    "criterion",
    "female_count",
    "male_count",
    "summary",
})

_ALLOWED_INSTANCE_FIELDS: frozenset[str] = frozenset({
    "criterion",
    "instance_count",
    "instances",
    "summary",
})

_ALLOWED_INSTANCE_ITEM_FIELDS: frozenset[str] = frozenset({
    "excerpt",
    "chunk_id",
    "explanation",
})


def _validate_section(section_key: str, section_val: dict[str, Any]) -> None:
    """Validate a single criterion section's structure, field types, and allowlist."""
    lower_key = section_key.strip().lower()

    if lower_key in _BALANCE_SECTION_KEYS:
        # GAD-02: female_count, male_count, summary — reject any extra field
        extra = set(section_val) - _ALLOWED_BALANCE_FIELDS
        if extra:
            raise AgentExecutionError(
                f"GAD section '{section_key}' has unapproved field(s): "
                f"{sorted(extra)}"
            )
        for field in ("female_count", "male_count"):
            val = section_val.get(field)
            if not isinstance(val, int) or isinstance(val, bool) or val < 0:
                raise AgentExecutionError(
                    f"GAD section '{section_key}' field '{field}' must be "
                    f"a non-negative integer, got {type(val).__name__}: {val}"
                )
        summary = section_val.get("summary", "")
        if not isinstance(summary, str) or not summary.strip():
            raise AgentExecutionError(
                f"GAD section '{section_key}' requires a non-empty summary"
            )
        # Reject instance-specific fields
        for banned in ("instances", "instance_count"):
            if banned in section_val:
                raise AgentExecutionError(
                    f"GAD section '{section_key}' (balance) must not contain "
                    f"field '{banned}'"
                )

    elif lower_key in _INSTANCE_SECTION_KEYS:
        # GAD-01/03/04/05: instance_count, instances, summary — reject extra fields
        extra = set(section_val) - _ALLOWED_INSTANCE_FIELDS
        if extra:
            raise AgentExecutionError(
                f"GAD section '{section_key}' has unapproved field(s): "
                f"{sorted(extra)}"
            )
        instance_count = section_val.get("instance_count")
        if not isinstance(instance_count, int) or isinstance(
            instance_count, bool
        ) or instance_count < 0:
            raise AgentExecutionError(
                f"GAD section '{section_key}' field 'instance_count' must be "
                f"a non-negative integer"
            )
        raw_instances = section_val.get("instances", [])
        if not isinstance(raw_instances, list):
            raise AgentExecutionError(
                f"GAD section '{section_key}' field 'instances' must be a list"
            )
        summary = section_val.get("summary", "")
        if not isinstance(summary, str) or not summary.strip():
            raise AgentExecutionError(
                f"GAD section '{section_key}' requires a non-empty summary"
            )
        max_instances = MAX_INSTANCES_PER_CRITERION
        if len(raw_instances) > max_instances:
            logger.info(
                "GAD section '%s' returned %d instances, capping at %d",
                section_key,
                len(raw_instances),
                max_instances,
            )
        for idx, inst in enumerate(raw_instances[:max_instances]):
            if not isinstance(inst, dict):
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] must be a JSON object"
                )
            extra_inst = set(inst) - _ALLOWED_INSTANCE_ITEM_FIELDS
            if extra_inst:
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] has unapproved "
                    f"field(s): {sorted(extra_inst)}"
                )
            excerpt = inst.get("excerpt", "")
            if not isinstance(excerpt, str) or not excerpt.strip():
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] requires "
                    f"a non-empty 'excerpt'"
                )
            chunk_id = inst.get("chunk_id", "")
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] requires "
                    f"a non-empty 'chunk_id'"
                )


# ---------------------------------------------------------------------------
# 1.3 — Evidence grounding and entry limits
# ---------------------------------------------------------------------------


def ground_instances(
    section_key: str,
    instances: list[dict[str, Any]],
    packed_chunks: list[dict[str, Any]],
) -> tuple[list[str], list[str], int]:
    """Validate instance excerpts and chunk_ids against frozen packed chunks.

    Returns (accepted_excerpts, accepted_chunk_ids, rejected_count).
    * Unknown chunk_ids, malformed references, duplicate normalised excerpts,
      and excerpts absent from their cited chunk are rejected.
    * Accepted excerpts are the **canonical source text** (not normalised).
    * Chunk IDs are deduplicated per chunk.
    """
    chunk_map: dict[str, str] = {}
    for chunk in packed_chunks:
        cid = str(chunk.get("chunk_id", "")).strip()
        text = str(chunk.get("text", ""))
        if cid:
            chunk_map[cid] = text

    def _normalized(text: str) -> str:
        return " ".join(text.casefold().split())

    normalized_chunks = {
        cid: _normalized(text) for cid, text in chunk_map.items()
    }

    seen_excerpts: set[str] = set()
    accepted_excerpts: list[str] = []
    accepted_chunk_ids: list[str] = []
    rejected = 0

    for inst in instances:
        if not isinstance(inst, dict):
            rejected += 1
            continue
        excerpt = str(inst.get("excerpt", "")).strip()
        chunk_id = str(inst.get("chunk_id", "")).strip()

        if not excerpt or not chunk_id:
            rejected += 1
            continue

        # Duplicate check (normalised) — case-fold, whitespace-normalise
        norm_excerpt = _normalized(excerpt)
        if not norm_excerpt or norm_excerpt in seen_excerpts:
            rejected += 1
            continue

        # Chunk ID must be known
        if chunk_id not in normalized_chunks:
            rejected += 1
            continue

        # Excerpt must be present in the cited chunk's normalised text
        if norm_excerpt not in normalized_chunks[chunk_id]:
            rejected += 1
            continue

        seen_excerpts.add(norm_excerpt)
        # Persist the canonical source excerpt (as provided by model)
        accepted_excerpts.append(excerpt)
        if chunk_id not in accepted_chunk_ids:
            accepted_chunk_ids.append(chunk_id)

    return accepted_excerpts, accepted_chunk_ids, rejected


# ---------------------------------------------------------------------------
# 2.1 — Combined prompt builder (GAD-local, reuses BaseAgent transport)
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
    transport. This is a GAD-local pipeline that does NOT use BaseAgent's
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
    "Prior response:\n{partial}\n\n"
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
    as the initial call, plus the parse error and the prior (partial) response.
    The model never sees a reduced or altered context.
    """
    max_partial_chars = 4000
    partial = partial_response or ""
    if len(partial) > max_partial_chars:
        partial = partial[: max_partial_chars - 3].rstrip() + "..."

    return _REPAIR_COMBINED_TEMPLATE.format(
        full_context=full_prompt_context,
        error=error_detail[:500],
        partial=partial,
    )


# ---------------------------------------------------------------------------
# Score adapter — translates combined sections into registry scores
# ---------------------------------------------------------------------------


def score_from_combined(
    combined: dict[str, Any],
    packed_chunks: list[dict[str, Any]],
) -> tuple[list[CriterionScore], int, int, int]:
    """Adapt validated combined sections into registry ``CriterionScore`` values.

    Returns (scores, evidence_candidates, evidence_accepted, evidence_rejected).
    Each criterion section is passed to the corresponding registry scorer
    after grounding evidence. GAD-02 bypasses grounding (counts only).

    ``combined`` MUST already have passed ``parse_combined_response`` so that
    all keys are canonical, all schemas validated, and no numeric-score fields
    remain. This function never defaults ``{}`` for a missing section.
    """
    scores: list[CriterionScore] = []
    evidence_candidates = 0
    evidence_accepted = 0
    evidence_rejected = 0

    for definition in registry.CRITERIA:
        section_key = definition.criterion_id.lower()
        section = combined.get(section_key)
        if section is None or not isinstance(section, dict):
            raise AgentExecutionError(
                f"Missing or invalid section for {definition.criterion_id}: "
                f"section must be present and a dict after parsing"
            )

        if definition.balance:
            # GAD-02: counts only, no grounding
            female_count = int(section.get("female_count", 0))
            male_count = int(section.get("male_count", 0))
            band = definition.score(female_count, male_count)
            difference = abs(female_count - male_count)
            summary = str(section.get("summary", "")).strip()
            justification = (
                f"Female representations: {female_count}; male representations: "
                f"{male_count}; absolute difference: {difference}. {summary}"
            )
            scores.append(
                CriterionScore(
                    criterion_id=definition.criterion_id,
                    criterion_title=definition.title,
                    score=band,
                    justification=justification,
                    chunk_ids=(),
                    evidence=(),
                )
            )
        else:
            # GAD-01/03/04/05: grounded instances
            raw_instances = section.get("instances", [])
            if not isinstance(raw_instances, list):
                raw_instances = []
            # Blocker 2: enforce hard per-criterion instance cap before any
            # scoring/persistence — truncate both the local list AND the
            # combined dict so the persisted raw_response reflects the cap.
            if len(raw_instances) > MAX_INSTANCES_PER_CRITERION:
                raw_instances = raw_instances[:MAX_INSTANCES_PER_CRITERION]
                section["instances"] = raw_instances
                logger.info(
                    "GAD section '%s' truncated to %d instances",
                    definition.criterion_id,
                    MAX_INSTANCES_PER_CRITERION,
                )
            claimed_count = int(section.get("instance_count", 0))
            evidence_candidates += len(raw_instances)

            accepted_excerpts, accepted_ids, rejected = ground_instances(
                section_key, raw_instances, packed_chunks
            )
            evidence_accepted += len(accepted_excerpts)
            evidence_rejected += rejected

            grounded_count = len(accepted_excerpts)
            band = definition.score(grounded_count)
            summary = str(section.get("summary", "")).strip()
            justification = (
                f"Grounded unique instances: {grounded_count} "
                f"(model reported {claimed_count}; {rejected} unsupported "
                f"or invalid instance(s) excluded). {summary}"
            )
            scores.append(
                CriterionScore(
                    criterion_id=definition.criterion_id,
                    criterion_title=definition.title,
                    score=band,
                    justification=justification,
                    chunk_ids=tuple(accepted_ids),
                    evidence=tuple(accepted_excerpts),
                )
            )

    return scores, evidence_candidates, evidence_accepted, evidence_rejected


__all__ = [
    "CANONICAL_SECTION_KEYS",
    "EXTRACTION_SCHEMA_VERSION",
    "MAX_INSTANCES_PER_CRITERION",
    "build_combined_prompt",
    "build_combined_repair_prompt",
    "ground_instances",
    "parse_combined_response",
    "score_from_combined",
]
