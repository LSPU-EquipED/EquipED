"""Bounded, source-grounded explanations and deterministic report wording."""

from __future__ import annotations

import re
from typing import Any

from equiped_harness.agents.coordinator.catalog import CatalogItem

CONTRACT_V2 = "coordinator_current.v2"

_MAX_FINDING = 400
_MAX_LIMITATION = 200
_MAX_QUOTE = 240
_MAX_EVIDENCE = 2


def unavailable_explanation() -> dict[str, Any]:
    """Return the deterministic explanation used when model reasoning fails."""
    return {
        "finding": "Reasoning unavailable—review required.",
        "limitation": (
            "Measurements passed validation, but the model explanation could not "
            "be verified after repair."
        ),
        "evidence": [],
    }


def selected_source_ids(fact: dict[str, Any], *, kind: str) -> set[str]:
    """Return evidence source IDs selected by a deterministic measurement fact."""
    if kind == "guidance":
        value = fact.get("evidence_id")
        return {value} if isinstance(value, str) else set()
    if kind == "count":
        values = fact.get("instance_ids", [])
    elif kind == "ratio":
        values = fact.get("unit_ids", [])
    elif kind in {"objective", "curriculum"}:
        values = [
            source_id
            for row in fact.get("rows", [])
            if isinstance(row, dict)
            for source_id in row.get("source_ids", [])
        ]
    else:
        raise ValueError("unsupported explanation selection kind")
    return (
        set(values)
        if isinstance(values, list) and all(isinstance(i, str) for i in values)
        else set()
    )


def validate_explanation(
    value: Any,
    catalog: dict[str, CatalogItem],
    allowed_ids: set[str],
) -> dict[str, Any]:
    """Validate an explanation and return a plain normalized mapping.

    Errors intentionally describe contract failures only; they never include source
    text or model supplied content.
    """
    if not isinstance(value, dict) or set(value) != {
        "finding",
        "limitation",
        "evidence",
    }:
        raise ValueError("explanation fields are invalid")
    finding = value["finding"]
    limitation = value["limitation"]
    evidence = value["evidence"]
    if (
        not isinstance(finding, str)
        or finding != finding.strip()
        or not finding
        or len(finding) > _MAX_FINDING
    ):
        raise ValueError(
            "explanation finding must be nonempty, trimmed, and at most 400 characters"
        )
    if (
        not isinstance(limitation, str)
        or limitation != limitation.strip()
        or len(limitation) > _MAX_LIMITATION
    ):
        raise ValueError(
            "explanation limitation must be trimmed and at most 200 characters"
        )
    if not isinstance(evidence, list) or len(evidence) > _MAX_EVIDENCE:
        raise ValueError("explanation evidence must be an array of at most 2 quotes")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"source_id", "quote"}:
            raise ValueError("explanation evidence item is invalid")
        source_id, quote = item["source_id"], item["quote"]
        if (
            not isinstance(source_id, str)
            or source_id not in allowed_ids
            or source_id not in catalog
        ):
            raise ValueError(
                "quote source_id must be selected in results and reference a "
                "known source"
            )
        if (
            not isinstance(quote, str)
            or quote != quote.strip()
            or not quote
            or len(quote) > _MAX_QUOTE
        ):
            raise ValueError(
                "quote must be nonempty, trimmed, and at most 240 characters"
            )
        source = catalog[source_id]
        source_text = (
            source.text if isinstance(source, CatalogItem) else source.get("text")
        )
        if not isinstance(source_text, str):
            raise ValueError("explanation quote is not an exact source substring")
        if quote not in source_text:
            # PDF line wraps may be rendered as spaces by the model. Match the
            # entire quote, preserving every word and punctuation mark, then
            # retain the original source slice. Never accept a partial phrase.
            pattern = r"\s+".join(re.escape(word) for word in quote.split())
            match = re.search(pattern, source_text)
            if match is None or len(match.group()) > _MAX_QUOTE:
                raise ValueError("explanation quote is not an exact source substring")
            quote = match.group()
        pair = (source_id, quote)
        if pair in seen:
            raise ValueError("duplicate explanation evidence is invalid")
        seen.add(pair)
        normalized.append({"source_id": source_id, "quote": quote})
    if allowed_ids and not normalized:
        raise ValueError("explanation requires source evidence")
    if not allowed_ids and (normalized or not limitation):
        raise ValueError("unsupported finding requires a limitation")
    return {"finding": finding, "limitation": limitation, "evidence": normalized}


def evidence_quotes(explanation: dict[str, Any]) -> tuple[str, ...]:
    """Return normalized quotes in their supplied order."""
    return tuple(item["quote"] for item in explanation["evidence"])


def render_justification(
    explanation: dict[str, Any], fact: dict[str, Any], score: int, *, kind: str
) -> str:
    """Render bounded model explanation followed by computed measurement wording."""
    finding = explanation["finding"]
    limitation = explanation["limitation"]
    prefix = finding if not limitation else f"{finding} Limitation: {limitation}"
    if kind == "guidance":
        rule = f"This corresponds to a rubric score of {score}/4."
    elif kind == "count":
        count = len(fact.get("instance_ids", []))
        rule = (
            f"{count} supporting passage(s) were identified. "
            f"The rubric assigns {score}/4."
        )
    elif kind == "ratio":
        total = len(fact.get("unit_ids", []))
        qualifying = len(fact.get("qualifying_unit_ids", []))
        pct = qualifying / total * 100 if total else 0.0
        rule = (
            f"{qualifying} of {total} reviewed passages met the criterion "
            f"({pct:.1f}%). The rubric assigns {score}/4."
        )
    elif kind == "objective":
        rows = fact.get("rows", [])
        matched = sum(bool(row.get("source_ids")) for row in rows)
        if fact.get("assessment_available") is False:
            rule = (
                "Objective assessment coverage could not be established; "
                "the rubric assigns 1/4."
            )
        else:
            pct = matched / len(rows) * 100 if rows else 0.0
            rule = (
                f"Assessment tasks support {matched} of {len(rows)} learning "
                f"objectives ({pct:.1f}%), giving {score}/4."
            )
    elif kind == "curriculum":
        rows = fact.get("rows", [])
        matched = sum(bool(row.get("source_ids")) for row in rows)
        pct = matched / len(rows) * 100 if rows else 0.0
        rule = (
            f"Curriculum outcomes support {matched} of {len(rows)} learning "
            f"objectives ({pct:.1f}%), giving {score}/4."
        )
    else:
        raise ValueError("unsupported explanation rendering kind")
    return f"{prefix} {rule}"
