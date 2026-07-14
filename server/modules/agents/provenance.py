"""Provenance schema enforcement — allowlist-based sanitizer.

Ensures provenance dicts only contain documented scalar/list fields
and never leak raw text, secrets, or arbitrary caller keys.
"""

from __future__ import annotations

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
        "repair_occurred",
        "prompt_trimmed",
        "reference_context_dropped",
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
    "repair_occurred": bool,
    "prompt_trimmed": bool,
    "reference_context_dropped": int,
}

# Bounded string/list value caps per key.
_PROVENANCE_MAX_LEN: dict[str, int] = {
    "precheck_version": 10,
    "precheck_result_hash": 128,
    "chunk_ids_hash": 128,
    "requested_model": 200,
    "actual_model": 200,
    "chunk_ids_ordered": 64,
    "policy_delivery_state": 20,
    "policy_retrieval_version": 10,
}

_SENSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "api-key",
    "secret",
    "password",
    "token",
    "credential",
)


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
            if not isinstance(value, expected_type):
                continue

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
