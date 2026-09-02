"""Provenance schema enforcement — allowlist-based sanitizer.

Ensures provenance dicts only contain documented scalar/list fields
and never leak raw text, secrets, or arbitrary caller keys.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Allowlist of all documented provenance keys (Phase-1 + Phase-2).
# Any key not in this set is silently dropped during serialization.
# ---------------------------------------------------------------------------

PROVENANCE_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Phase 1 — frozen before dispatch
        "precheck_version",
        "precheck_result_hash",
        "bibliography_found",
        "reference_count",
        "intext_citation_count",
        "doi_count",
        "coverage_ratio",
        "chunk_ids_ordered",
        "chunk_id_count",
        "chunk_ids_hash",
        # Phase 1 — policy evidence (opaque metadata only, no raw text/IDs)
        "policy_delivery_state",
        "policy_evidence",
        "policy_retrieval_version",
        "policy_trimmed",
        # Phase 2 — recorded after execution
        "requested_model",
        "actual_model",
        "requested_temperature",
        "fallback_occurred",
        "response_format_downgraded",
        "summary_requested_model",
        "summary_actual_model",
        "summary_fallback_occurred",
        "repair_occurred",
        "prompt_trimmed",
        "reference_context_dropped",
        # Phase 2 — GAD single-pass extraction (3.3)
        "extraction_schema_version",
        "registry_version",
        "evidence_candidates",
        "evidence_accepted",
        "evidence_rejected",
        # Phase 2 — GAD timing (3.4)
        "gad_extraction_seconds",
        "gad_validation_seconds",
        "gad_scoring_seconds",
        "llm_attempts",
        "llm_prompt_tokens",
        "llm_completion_tokens",
        "llm_total_tokens",
        "llm_wall_seconds",
        "llm_call_count",
        "llm_cap_hit_count",
        "llm_usage_available",
        "llm_served_model",
        # SME bounded transport telemetry (flat scalar fields only)
        "logical_calls",
        "physical_attempts",
        "input_tokens",
        "output_tokens",
        "truncation_count",
        "cap_hit_count",
        "criterion_fallback_calls",
        "grouped_calls",
        "fallback_calls",
        "provider_seconds_ms",
        "trim_count",
        "grounding_rejected_count",
    }
)

# Scalar type constraint per key for optional runtime validation.
# Keys not listed accept any type supported by JSON.
_PROVENANCE_TYPES: dict[str, type | tuple[type, type]] = {
    "precheck_version": str,
    "precheck_result_hash": str,
    "bibliography_found": bool,
    "reference_count": int,
    "intext_citation_count": int,
    "doi_count": int,
    "coverage_ratio": float,
    "chunk_ids_ordered": list,
    "chunk_id_count": int,
    "chunk_ids_hash": str,
    "policy_delivery_state": str,
    "policy_evidence": dict,
    "policy_retrieval_version": str,
    "policy_trimmed": bool,
    "requested_model": str,
    "actual_model": str,
    "requested_temperature": (int, float),
    "fallback_occurred": bool,
    "response_format_downgraded": bool,
    "summary_requested_model": str,
    "summary_actual_model": str,
    "summary_fallback_occurred": bool,
    "repair_occurred": bool,
    "prompt_trimmed": bool,
    "reference_context_dropped": int,
    "extraction_schema_version": str,
    "registry_version": int,
    "evidence_candidates": int,
    "evidence_accepted": int,
    "evidence_rejected": int,
    "gad_extraction_seconds": (int, float),
    "gad_validation_seconds": (int, float),
    "gad_scoring_seconds": (int, float),
    "llm_attempts": int,
    "llm_prompt_tokens": int,
    "llm_completion_tokens": int,
    "llm_total_tokens": int,
    "llm_wall_seconds": (int, float),
    "llm_call_count": int,
    "llm_cap_hit_count": int,
    "llm_usage_available": bool,
    "llm_served_model": str,
    "logical_calls": int,
    "physical_attempts": int,
    "input_tokens": int,
    "output_tokens": int,
    "truncation_count": int,
    "cap_hit_count": int,
    "criterion_fallback_calls": int,
    "grouped_calls": int,
    "fallback_calls": int,
    "provider_seconds_ms": int,
    "trim_count": int,
    "grounding_rejected_count": int,
}

# Bounded string/list value caps per key.
_PROVENANCE_MAX_LEN: dict[str, int] = {
    "precheck_version": 10,
    "precheck_result_hash": 128,
    "chunk_ids_hash": 128,
    "requested_model": 200,
    "actual_model": 200,
    "summary_requested_model": 200,
    "summary_actual_model": 200,
    "llm_served_model": 200,
    "chunk_ids_ordered": 64,
    "policy_delivery_state": 20,
    "policy_retrieval_version": 10,
    "extraction_schema_version": 10,
}
_BOUNDED_INTEGER_KEYS = frozenset(
    {
        "reference_context_dropped",
        "registry_version",
        "evidence_candidates",
        "evidence_accepted",
        "evidence_rejected",
        "llm_attempts",
        "llm_prompt_tokens",
        "llm_completion_tokens",
        "llm_total_tokens",
        "llm_call_count",
        "llm_cap_hit_count",
        "logical_calls",
        "physical_attempts",
        "input_tokens",
        "output_tokens",
        "truncation_count",
        "cap_hit_count",
        "criterion_fallback_calls",
        "grouped_calls",
        "fallback_calls",
        "provider_seconds_ms",
        "trim_count",
        "grounding_rejected_count",
    }
)

_SENSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "api-key",
    "secret",
    "password",
    "token",
    "credential",
)

_CHUNK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_POLICY_CRITERIA = frozenset({"ITSO-03", "ITSO-04", "ITSO-05"})
_POLICY_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def sanitize_provenance(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a provenance dict containing only allowlisted keys.

    - Drops any key not in ``PROVENANCE_ALLOWLIST``.
    - Truncates bounded string fields to their max length.
    - Capped list fields are preserved at most to their max length.
    - Drops the entire provenance if any value matches a sensitive
      substring pattern after coercion to lower-case string.
    - Returns ``None`` when ``raw`` is None or empty.

    The result is safe for persistence and API exposure.
    """
    if not raw:
        return None

    sanitized: dict[str, Any] = {}

    for key, value in raw.items():
        if key not in PROVENANCE_ALLOWLIST:
            continue

        # Type check: skip values that don't match expected type.
        expected_type = _PROVENANCE_TYPES.get(key)
        if expected_type is not None:
            if (
                not isinstance(value, expected_type)
                or key
                in {
                    "logical_calls",
                    "physical_attempts",
                    "input_tokens",
                    "output_tokens",
                    "truncation_count",
                    "cap_hit_count",
                    "criterion_fallback_calls",
                }
                and isinstance(value, bool)
            ):
                continue
        if key in _BOUNDED_INTEGER_KEYS and (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= 10_000_000
        ):
            continue

        if key == "chunk_ids_ordered":
            if not all(
                isinstance(chunk_id, str) and _CHUNK_ID_PATTERN.fullmatch(chunk_id)
                for chunk_id in value
            ):
                continue

        if key == "policy_evidence":
            if set(value) != _POLICY_CRITERIA or any(
                not isinstance(entry, dict)
                or set(entry) != {"status", "chunk_count", "provenance_hash"}
                or entry["status"] not in {"available", "unavailable"}
                or isinstance(entry["chunk_count"], bool)
                or not isinstance(entry["chunk_count"], int)
                or not 0 <= entry["chunk_count"] <= 64
                or not isinstance(entry["provenance_hash"], str)
                or not _POLICY_HASH_PATTERN.fullmatch(entry["provenance_hash"])
                for entry in value.values()
            ):
                continue
            value = {
                criterion: {
                    "status": value[criterion]["status"],
                    "chunk_count": value[criterion]["chunk_count"],
                    "provenance_hash": value[criterion]["provenance_hash"],
                }
                for criterion in _POLICY_CRITERIA
            }

        # Bounded string length.
        max_len = _PROVENANCE_MAX_LEN.get(key)
        if max_len is not None and isinstance(value, str):
            value = value[:max_len]

        # Bounded list length.
        if max_len is not None and isinstance(value, list):
            value = value[:max_len]

        sanitized[key] = value

    # Scan all values for sensitive substrings (redaction check).
    for value in sanitized.values():
        if isinstance(value, str):
            lower = value.lower()
            for sensitive in _SENSITIVE_SUBSTRINGS:
                if sensitive in lower:
                    return None

    return sanitized if sanitized else None


__all__ = [
    "PROVENANCE_ALLOWLIST",
    "sanitize_provenance",
]
