"""Validation and merging for source-grounded Coordinator objective matches."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from equiped_harness.exceptions import AgentExecutionError

_MAX_MATCHES = 2
_MAX_QUOTE = 700
_MAX_REASON = 500


def objective_quote_catalog(catalog: Mapping[str, Any]) -> list[dict[str, str]]:
    """Number complete bounded source slices so models select, rather than recopy."""
    options = []
    for source_id, entry in catalog.items():
        text = _text(entry)
        if text is None:
            raise AgentExecutionError("Objective source text is invalid")
        cursor = 0
        index = 0
        while cursor < len(text):
            end = min(cursor + 500, len(text))
            if end < len(text):
                boundary = text.rfind(" ", cursor + 250, end)
                newline = text.rfind("\n", cursor + 250, end)
                if max(boundary, newline) > cursor:
                    end = max(boundary, newline) + 1
            quote = text[cursor:end].strip()
            cursor = end
            if not quote:
                continue
            index += 1
            options.append(
                {
                    "source_id": source_id,
                    "source": _source(entry),
                    "quote_id": f"{source_id}:q{index:03d}",
                    "text": quote,
                }
            )
    return options


def _text(entry: Any) -> str | None:
    value = (
        entry.get("text")
        if isinstance(entry, Mapping)
        else getattr(entry, "text", None)
    )
    return value if isinstance(value, str) else None


def _source(entry: Any) -> str | None:
    value = (
        entry.get("source")
        if isinstance(entry, Mapping)
        else getattr(entry, "source", None)
    )
    return value if isinstance(value, str) else None


def _canonical_quote(quote: Any, source_text: str) -> str:
    if not isinstance(quote, str) or not quote or len(quote) > _MAX_QUOTE:
        raise AgentExecutionError(
            "Objective quote must be nonempty and at most 700 characters"
        )
    # Match whitespace flexibly while retaining the precise source slice.
    words = quote.split()
    if not words:
        raise AgentExecutionError("Objective quote must contain source text")
    pattern = r"\s+".join(re.escape(word) for word in words)
    matches = list(re.finditer(pattern, source_text))
    if not matches:
        raise AgentExecutionError("Objective quote is not an exact source substring")
    # Repeated appearances of the same quote remain grounded; the first source
    # slice is canonical and preserves line wraps and spacing from the document.
    canonical = matches[0].group()
    if len(canonical) > _MAX_QUOTE:
        raise AgentExecutionError("Canonical objective quote exceeds 700 characters")
    return canonical


def validate_objective_rows(
    rows: Any,
    objectives: tuple[dict[str, str], ...],
    catalog: Mapping[str, Any],
    namespace: str,
) -> list[dict[str, Any]]:
    """Validate complete, ordered objective results and canonicalize quotations."""
    if namespace not in {"assessment", "curriculum"}:
        raise AgentExecutionError("Objective source namespace is invalid")
    if not isinstance(rows, (list, tuple)) or len(rows) != len(objectives):
        raise AgentExecutionError("Objective rows must cover every objective")
    expected_ids = [obj.get("objective_id") for obj in objectives]
    if any(not isinstance(oid, str) or not oid for oid in expected_ids) or len(
        set(expected_ids)
    ) != len(expected_ids):
        raise AgentExecutionError("Objective inventory is invalid")

    normalized: list[dict[str, Any]] = []
    quote_options = {
        item["quote_id"]: item for item in objective_quote_catalog(catalog)
    }
    for row, objective in zip(rows, objectives, strict=True):
        if not isinstance(row, Mapping):
            raise AgentExecutionError("Objective row is invalid")
        oid = objective["objective_id"]
        if row.get("objective_id") != oid:
            raise AgentExecutionError("Objective rows are missing or out of order")
        if set(row) not in (
            {"objective_id", "matches", "reason"},
            {"objective_id", "matches", "source_ids", "reason"},
        ):
            raise AgentExecutionError("Objective row fields are invalid")
        matches = row["matches"]
        reason = row["reason"]
        if not isinstance(matches, (list, tuple)) or len(matches) > _MAX_MATCHES:
            raise AgentExecutionError(
                "Objective matches must contain at most two quotes"
            )
        if (
            not isinstance(reason, str)
            or not reason.strip()
            or len(reason) > _MAX_REASON
        ):
            raise AgentExecutionError(
                "Objective reason must be nonempty and at most 500 characters"
            )

        objective_text = " ".join(str(objective.get("text", "")).split()).casefold()
        validated_matches: list[dict[str, str]] = []
        source_ids: list[str] = []
        seen: set[tuple[str, str]] = set()
        for match in matches:
            if isinstance(match, Mapping) and set(match) == {"quote_id"}:
                quote_id = match["quote_id"]
                option = (
                    quote_options.get(quote_id) if isinstance(quote_id, str) else None
                )
                if option is None:
                    raise AgentExecutionError("Objective quote_id is unknown")
                match = {"source_id": option["source_id"], "quote": option["text"]}
            if not isinstance(match, Mapping) or set(match) != {"source_id", "quote"}:
                raise AgentExecutionError("Objective match fields are invalid")
            source_id = match["source_id"]
            if not isinstance(source_id, str) or source_id not in catalog:
                raise AgentExecutionError("Objective match source is unknown")
            entry = catalog[source_id]
            source_text = _text(entry)
            if _source(entry) != namespace or source_text is None:
                raise AgentExecutionError(
                    "Objective match source is outside its namespace"
                )
            quote = _canonical_quote(match["quote"], source_text)
            if (
                namespace == "assessment"
                and " ".join(quote.split()).casefold() == objective_text
            ):
                raise AgentExecutionError(
                    "Objective match cannot quote the objective itself"
                )
            key = (source_id, quote)
            if key in seen:
                raise AgentExecutionError("Duplicate objective match is invalid")
            seen.add(key)
            validated_matches.append({"source_id": source_id, "quote": quote})
            if source_id not in source_ids:
                source_ids.append(source_id)
        if "source_ids" in row and row["source_ids"] != source_ids:
            raise AgentExecutionError(
                "Objective source_ids do not match grounded quotes"
            )
        normalized.append(
            {
                "objective_id": oid,
                "matches": validated_matches,
                "source_ids": source_ids,
                "reason": reason.strip(),
            }
        )
    return normalized


def combine_objective_rows(
    parts: list[list[dict[str, Any]]],
    objectives: tuple[dict[str, str], ...],
    catalog: Mapping[str, Any],
    namespace: str,
) -> list[dict[str, Any]]:
    """Merge per-task objective evidence, retaining at most two grounded quotes."""
    if not parts:
        raise AgentExecutionError("Objective results are missing")
    objective_by_id = {item["objective_id"]: item for item in objectives}
    if len(objective_by_id) != len(objectives):
        raise AgentExecutionError("Objective inventory is invalid")
    objective_order = {
        item["objective_id"]: index for index, item in enumerate(objectives)
    }
    validated: list[dict[str, dict[str, Any]]] = []
    covered: set[str] = set()
    for part in parts:
        if not isinstance(part, list) or not part:
            raise AgentExecutionError("Objective task result is empty or invalid")
        part_ids = [
            row.get("objective_id") if isinstance(row, Mapping) else None
            for row in part
        ]
        if (
            any(
                not isinstance(oid, str) or oid not in objective_by_id
                for oid in part_ids
            )
            or part_ids != sorted(part_ids, key=objective_order.__getitem__)
            or len(set(part_ids)) != len(part_ids)
        ):
            raise AgentExecutionError(
                "Objective task groups are unknown, unordered, or overlapping"
            )
        subset = tuple(objective_by_id[oid] for oid in part_ids)
        normalized = validate_objective_rows(part, subset, catalog, namespace)
        validated.append({row["objective_id"]: row for row in normalized})
        covered.update(part_ids)
    if covered != set(objective_by_id):
        raise AgentExecutionError("Objective task groups do not cover every objective")
    result: list[dict[str, Any]] = []
    for index, objective in enumerate(objectives):
        matches: list[dict[str, str]] = []
        reasons: list[str] = []
        seen_matches: set[tuple[str, str]] = set()
        seen_reasons: set[str] = set()
        for part in validated:
            row = part.get(objective["objective_id"])
            if row is None:
                continue
            reason = row["reason"].strip()
            if reason.casefold() not in seen_reasons:
                reasons.append(reason)
                seen_reasons.add(reason.casefold())
            for match in row["matches"]:
                key = (match["source_id"], match["quote"])
                if key not in seen_matches and len(matches) < _MAX_MATCHES:
                    matches.append(match)
                    seen_matches.add(key)
        # Evidence-backed reasons explain a positive match. When no part has
        # evidence, retain the unique gap reasons to describe the absence.
        if matches:
            reasons = [
                row["reason"]
                for part in validated
                if (row := part.get(objective["objective_id"])) is not None
                and row["matches"]
            ]
        reason = _joined_reason(_unique(reasons))
        source_ids = list(dict.fromkeys(match["source_id"] for match in matches))
        result.append(
            {
                "objective_id": objective["objective_id"],
                "matches": matches,
                "source_ids": source_ids,
                "reason": reason,
            }
        )
    return result


def _joined_reason(reasons: list[str]) -> str:
    """Return unique concise rationale text within the persisted field limit."""
    output = ""
    for reason in reasons:
        candidate = f"{output} {reason}".strip()
        if len(candidate) <= _MAX_REASON:
            output = candidate
        elif not output:
            output = reason[:_MAX_REASON].rstrip()
            break
    return output or "No supported objective evidence was identified."


def _unique(reasons: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        key = reason.casefold()
        if key not in seen:
            result.append(reason)
            seen.add(key)
    return result
