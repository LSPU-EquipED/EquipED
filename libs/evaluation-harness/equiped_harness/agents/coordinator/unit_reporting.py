"""Source-grounded reporting for Coordinator v3 unit and objective checks."""

from __future__ import annotations

import re
from typing import Any

MAX_FINDING = 1200
MAX_LIMITATION = 500
MAX_QUOTE = 700
MAX_EVIDENCE = 3

_UNAVAILABLE = "Reasoning unavailable—review required."


def _source_text(entry: Any) -> str | None:
    if isinstance(entry, dict):
        value = entry.get("text")
    else:
        value = getattr(entry, "text", None)
    return value if isinstance(value, str) else None


def validate_unit_explanation(
    value: Any, catalog: dict[str, Any], allowed_ids: set[str]
) -> dict[str, Any]:
    """Validate a v3 explanation with whole, exact source quotations."""
    if not isinstance(value, dict) or set(value) != {
        "finding",
        "limitation",
        "evidence",
    }:
        raise ValueError("explanation fields are invalid")
    finding, limitation, evidence = (
        value["finding"],
        value["limitation"],
        value["evidence"],
    )
    if (
        not isinstance(finding, str)
        or finding != finding.strip()
        or not finding
        or len(finding) > MAX_FINDING
    ):
        raise ValueError(
            "explanation finding must be nonempty, trimmed, and at most 1200 characters"
        )
    if (
        not isinstance(limitation, str)
        or limitation != limitation.strip()
        or len(limitation) > MAX_LIMITATION
    ):
        raise ValueError(
            "explanation limitation must be trimmed and at most 500 characters"
        )
    if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE:
        raise ValueError("explanation evidence must be an array of at most 3 quotes")
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
            or not quote.strip()
            or len(quote) > MAX_QUOTE
        ):
            raise ValueError(
                "quote must be nonempty, trimmed, and at most 700 characters"
            )
        source_text = _source_text(catalog[source_id])
        if source_text is None:
            raise ValueError("explanation quote is not an exact source substring")
        if quote not in source_text:
            pattern = r"\s+".join(re.escape(word) for word in quote.split())
            match = re.search(pattern, source_text)
            if match is None or len(match.group()) > MAX_QUOTE:
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


def _sentences(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    value = " ".join(value.split())
    # Keep sentence boundaries, including common abbreviations conservatively.
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", value) if part.strip()]


def _unique_sentences(*groups: list[str], limit: int = 3) -> list[str]:
    chosen: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for sentence in group:
            key = sentence.casefold()
            if key not in seen:
                chosen.append(sentence)
                seen.add(key)
                if len(chosen) == limit:
                    return chosen
    return chosen


def _bounded_finding(sentences: list[str]) -> str:
    kept: list[str] = []
    for sentence in sentences:
        candidate = " ".join((*kept, sentence))
        if len(candidate) <= MAX_FINDING:
            kept.append(sentence)
    return " ".join(kept) or _UNAVAILABLE


def _reasons(packet_explanations: list[dict[str, Any]]) -> list[str]:
    return [
        sentence
        for row in packet_explanations
        if isinstance(row, dict)
        for sentence in _sentences(row.get("finding"))
    ]


def _decision_reasons(
    review_decisions: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    positives, negatives, rejected = [], [], []
    for decision in review_decisions:
        if not isinstance(decision, dict):
            continue
        reason = _sentences(decision.get("reason"))
        target = decision.get("decision")
        if target == "qualifies":
            positives.extend(reason)
        elif target == "does_not_qualify":
            negatives.extend(reason)
        elif target == "not_a_unit":
            rejected.extend(reason)
    return positives, negatives, rejected


def _evidence_for_items(
    items: list[dict[str, Any]], catalog: dict[str, Any], allowed_ids: set[str]
) -> list[dict[str, str]]:
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            continue
        source_id, quote = item.get("source_id"), item.get("quote")
        if (
            source_id not in allowed_ids
            or source_id not in catalog
            or not isinstance(quote, str)
        ):
            continue
        text = _source_text(catalog[source_id])
        if (
            text is None
            or not quote.strip()
            or quote not in text
            or len(quote) > MAX_QUOTE
        ):
            continue
        pair = source_id, quote
        if pair not in seen:
            result.append({"source_id": source_id, "quote": quote})
            seen.add(pair)
        if len(result) == MAX_EVIDENCE:
            break
    return result


def build_unit_explanation(
    *,
    criterion_title: str,
    fact: dict[str, Any],
    packet_explanations: list[dict[str, Any]],
    unavailable_packets: int,
    review_decisions: list[dict[str, Any]],
    proposed_items: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    positives, negatives, rejected = _decision_reasons(review_decisions)
    accepted = [
        item
        for item in proposed_items
        if isinstance(item, dict) and item.get("qualifies") is True
    ]
    declined = [
        item
        for item in proposed_items
        if isinstance(item, dict) and item.get("qualifies") is False
    ]
    rejected_ids = {
        row.get("item_id")
        for row in review_decisions
        if isinstance(row, dict) and row.get("decision") == "not_a_unit"
    }
    rejected_items = [
        item
        for item in proposed_items
        if isinstance(item, dict) and item.get("item_id") in rejected_ids
    ]
    packet_reasons = _reasons(packet_explanations)
    verifier_reasons = positives + negatives + rejected
    selected = (
        _unique_sentences(
            positives[:1],
            (negatives or rejected)[:1],
            positives[1:],
            negatives[1:],
            rejected[1:],
            limit=3,
        )
        if verifier_reasons
        else _unique_sentences(packet_reasons, limit=3)
    )
    if not selected:
        selected = [_UNAVAILABLE]
    finding = _bounded_finding(selected)
    if not proposed_items and not unavailable_packets:
        label = fact.get("unit_label") or "applicable learner practices"
        finding = (
            f"No {label} were identified in the reviewed text. "
            f"The extracted material did not demonstrate {criterion_title.lower()}."
        )
    limitation = ""
    status = "complete"
    if unavailable_packets:
        limitation = (
            f"Explanation unavailable for {unavailable_packets} evidence packet(s); "
            "measured results remain valid."
        )
        status = "partial"
    rejected_item_ids = {item.get("item_id") for item in rejected_items}
    genuine_near_misses = [
        item for item in declined if item.get("item_id") not in rejected_item_ids
    ]
    evidence_items = (
        accepted[:2]
        + genuine_near_misses[:1]
        + rejected_items[:1]
        + accepted[2:]
        + genuine_near_misses[1:]
        + rejected_items[1:]
    )
    # Unit proposals have already passed exact quote validation upstream.
    evidence, seen_quotes = [], set()
    packet_items = [
        item
        for row in packet_explanations
        if isinstance(row, dict) and isinstance(row.get("evidence"), list)
        for item in row["evidence"]
    ]
    for item in evidence_items + packet_items:
        source_id, quote = item.get("source_id"), item.get("quote")
        if (
            isinstance(source_id, str)
            and isinstance(quote, str)
            and quote.strip()
            and len(quote) <= MAX_QUOTE
        ):
            pair = source_id, quote
            if pair not in seen_quotes:
                evidence.append({"source_id": source_id, "quote": quote})
                seen_quotes.add(pair)
        if len(evidence) == MAX_EVIDENCE:
            break
    has_available_reason = bool(verifier_reasons or packet_reasons)
    if unavailable_packets and not has_available_reason:
        finding = _UNAVAILABLE
        limitation = (
            "Explanation unavailable because some evidence packets could not be "
            "reviewed; measured results remain valid."
        )
        status = "partial"
        evidence = []
    categories = fact.get("categories")
    if isinstance(categories, list) and categories:
        labels = sorted(
            {
                str(category).replace("_", " ")
                for category in categories
                if isinstance(category, str)
            }
        )
        if labels:
            category_sentence = (
                "Identified categories include " + ", ".join(labels[:6]) + "."
            )
            finding = _bounded_finding(
                _unique_sentences(_sentences(finding), [category_sentence], limit=3)
            )
    return {"finding": finding, "limitation": limitation, "evidence": evidence}, status


def build_objective_explanation(
    *,
    objectives: tuple[dict[str, Any], ...],
    rows: list[dict[str, Any]],
    packet_explanations: list[dict[str, Any]],
    unavailable_packets: int,
    catalog: dict[str, Any],
    kind: str = "objective",
) -> tuple[dict[str, Any], str]:
    if kind not in {"objective", "curriculum"}:
        raise ValueError("unsupported objective explanation kind")
    objective_by_id = {
        row.get("objective_id"): row for row in objectives if isinstance(row, dict)
    }
    matched = [row for row in rows if isinstance(row, dict) and row.get("source_ids")]
    unsupported = [
        row for row in rows if isinstance(row, dict) and not row.get("source_ids")
    ]
    reasons = _unique_sentences(
        [
            s
            for row in packet_explanations
            if isinstance(row, dict)
            for s in _sentences(row.get("finding"))
        ],
        limit=3,
    )
    examples = []
    for row in unsupported[:2]:
        oid = row.get("objective_id")
        objective = objective_by_id.get(oid, {})
        label = objective.get("text") or objective.get("title") or oid
        if isinstance(label, str) and label.strip():
            row_reasons = _sentences(row.get("reason"))
            examples.extend(
                row_reasons[:1]
                or [f"No supporting {kind} passage was mapped for “{label.strip()}.”"]
            )
    support_reasons = [
        sentence for row in matched for sentence in _sentences(row.get("reason"))
    ]
    # Per-objective reasons describe the reviewed mappings. A primary packet's
    # prose may still describe a proposal that the independent check rejected.
    has_row_reasons = any(row.get("reason") for row in rows)
    reasons = _unique_sentences(
        support_reasons, [] if has_row_reasons else reasons, limit=3
    )
    if not reasons and not examples:
        reasons = [_UNAVAILABLE]
    finding = _bounded_finding(
        _unique_sentences(reasons[:1], examples[:1], reasons[1:], examples[1:], limit=3)
    )
    source_ids = {
        source_id
        for row in matched
        for source_id in row.get("source_ids", [])
        if isinstance(source_id, str)
    }
    evidence = []
    seen_evidence: set[tuple[str, str]] = set()
    for row in matched:
        for match in row.get("matches", []):
            if not isinstance(match, dict):
                continue
            for item in _evidence_for_items([match], catalog, source_ids):
                key = (item["source_id"], item["quote"])
                if key not in seen_evidence:
                    evidence.append(item)
                    seen_evidence.add(key)
            if len(evidence) >= MAX_EVIDENCE:
                break
        if len(evidence) >= MAX_EVIDENCE:
            break
    limitation, status = "", "complete"
    if unavailable_packets:
        limitation = (
            f"Explanation unavailable for {unavailable_packets} evidence packet(s); "
            "measured objective coverage remains valid."
        )
        status = "partial"
    if not evidence and not limitation:
        limitation = (
            "No matched source passage was available to quote for this finding."
        )
    if (
        unavailable_packets
        and not packet_explanations
        and not matched
        and not unsupported
    ):
        finding = _UNAVAILABLE
        limitation = (
            "Explanation unavailable because evidence packets could not be reviewed; "
            "measured objective coverage remains valid."
        )
        status = "partial"
    finding = _bounded_finding(_sentences(finding))
    explanation = {"finding": finding, "limitation": limitation, "evidence": evidence}
    return validate_unit_explanation(
        explanation, catalog, source_ids if evidence else set()
    ), status


def render_unit_justification(
    explanation: dict[str, Any],
    fact: dict[str, Any],
    score: int,
    *,
    kind: str | None = None,
) -> str:
    kind = kind or fact.get("kind")
    prefix = explanation["finding"]
    if explanation.get("limitation"):
        prefix += f" Limitation: {explanation['limitation']}"
    if kind == "count":
        count = fact.get("count", 0)
        label = str(fact.get("unit_label") or "qualifying unit").replace("_", " ")
        rule = (
            f"{count} {label}{'' if count == 1 or label.endswith('s') else 's'} "
            f"were identified; the rubric assigns {score}/4."
        )
    elif kind == "ratio":
        total, qualifying = fact.get("total", 0), fact.get("qualifying", 0)
        label = str(fact.get("unit_label") or "unit").replace("_", " ")
        short_sample = fact.get("scoring_config", {}).get("short_sample")
        if short_sample and 0 < total < short_sample["min_units"]:
            issues = total - qualifying
            rule = (
                f"In this short sample, {issues} of {total} reviewed {label} "
                f"fell short. The rubric's short-sample issue rule assigns {score}/4."
            )
            return f"{prefix} {rule}"
        pct = qualifying / total * 100 if total else 0.0
        rule = (
            f"{qualifying} of {total} reviewed "
            f"{label}{'' if total == 1 or label.endswith('s') else 's'} met the "
            f"criterion ({pct:.1f}%); the rubric assigns {score}/4."
        )
    elif kind == "guidance":
        rule = f"Guidance was identified; the rubric assigns {score}/4."
    elif kind in {"objective", "curriculum"}:
        rows = fact.get("rows", [])
        matched = sum(
            bool(row.get("source_ids")) for row in rows if isinstance(row, dict)
        )
        pct = matched / len(rows) * 100 if rows else 0.0
        label = "curriculum outcomes" if kind == "curriculum" else "assessment tasks"
        rule = (
            f"{label.capitalize()} support {matched} of {len(rows)} learning "
            f"objectives ({pct:.1f}%); the rubric assigns {score}/4."
        )
    else:
        raise ValueError("unsupported unit justification kind")
    return f"{prefix} {rule}"


def build_unit_summary(
    scores: list[Any],
    explanations: dict[str, dict[str, Any]],
    reasoning_statuses: dict[str, str],
) -> str:
    rows = []
    for score in scores:
        code = getattr(score, "criterion_id", None) or (
            score.get("criterion_id") if isinstance(score, dict) else None
        )
        value = (
            getattr(score, "score", None)
            if not isinstance(score, dict)
            else score.get("score")
        )
        if code:
            rows.append(
                (
                    str(code),
                    value,
                    explanations.get(str(code), {}),
                    reasoning_statuses.get(str(code), "complete"),
                )
            )
    weak = [row for row in rows if isinstance(row[1], (int, float)) and row[1] <= 2]
    strong = [row for row in rows if isinstance(row[1], (int, float)) and row[1] >= 3]
    selected = weak[:2] + strong[:1]
    # Always surface material A-05 findings and packet limitations.
    for row in rows:
        if row[0] == "A-05" or row[3] in {"partial", "unavailable"}:
            if row not in selected:
                selected.append(row)
    parts = []
    for code, _, explanation, status in selected:
        finding = explanation.get("finding") if isinstance(explanation, dict) else None
        if isinstance(finding, str) and finding:
            parts.append(f"{code}: {finding}")
        if status in {"partial", "unavailable"}:
            parts.append(
                f"{code}: some explanation was unavailable; measured results "
                "remain valid."
            )
    return " ".join(_unique_sentences(parts, limit=12))
