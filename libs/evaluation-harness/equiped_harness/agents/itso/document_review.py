"""Bounded, traceable context for the document-review ITSO envelope."""

from __future__ import annotations

import re
from bisect import bisect_left
from collections.abc import Mapping
from typing import Any, Literal

from equiped_harness.exceptions import AgentExecutionError

_REVIEW_TERMS = re.compile(
    r"\b(?:copyright|ownership|owned|author|permission|licen[cs]e|consent|"
    r"confidential|privacy|personal\s+(?:data|information)|student\s+(?:id|"
    r"number|records?|grades?)|publish|waiv\w*|reproduc\w*|attribution|"
    r"prepared\s+by|learning\s+resources|acknowledg\w*)\b",
    re.IGNORECASE,
)
_CLAUSE_TERMS = re.compile(
    r"\b(?:copyright|ownership|permission|licen[cs]e|consent|confidential|"
    r"privacy|personal\s+(?:data|information)|student\s+(?:id|number|"
    r"records?|grades?)|publish|waiv\w*|reproduc\w*|prepared\s+by)\b",
    re.IGNORECASE,
)


def unquoted_review_status(
    criterion: Any, score: int
) -> Literal["no_concern_detected", "rights_unverified"] | None:
    """Classify narrowly allowed empty-evidence findings for presentation.

    This does not validate evidence, change a score, or imply legal clearance.
    Callers must independently confirm adapter 3, empty evidence, and a
    non-empty justification before using the classification.
    """
    if not getattr(criterion, "scoring_rule", None):
        return None
    code = getattr(criterion, "criterion_code", None)
    if code == "ITSO-04" and score == 4:
        return "no_concern_detected"
    if code == "ITSO-05" and score == 3:
        return "rights_unverified"
    return None


def review_chunks(chunk_infos: tuple[Any, ...], *, excerpt_chars: int) -> tuple:
    """Prefer relevant exact windows, including clauses after a chunk's prefix.

    This is context selection, not a PII detector or a finding of absence.
    The normal prompt budget still decides the final reviewed coverage.
    """
    selected = []
    for raw in chunk_infos:
        chunk = dict(raw)
        text = str(chunk.get("text", ""))
        matches = list(_REVIEW_TERMS.finditer(text))
        clauses = [m.start() for m in _CLAUSE_TERMS.finditer(text)]
        start = 0
        if matches and len(text) > excerpt_chars:
            # Select the window containing the most review terms; stable ties
            # prefer earlier content. Never concatenate disjoint quotations.
            starts = {max(0, m.start() - excerpt_chars // 4) for m in matches}
            positions = [m.start() for m in matches]
            start = max(
                sorted(starts),
                key=lambda s: (
                    bisect_left(clauses, s + excerpt_chars) - bisect_left(clauses, s),
                    bisect_left(positions, s + excerpt_chars)
                    - bisect_left(positions, s),
                ),
            )
        chunk["text"] = text[start : start + excerpt_chars]
        selected.append((bool(clauses), bool(matches), chunk))
    return tuple(
        chunk for _, _, chunk in sorted(selected, key=lambda item: (-item[0], -item[1]))
    )


def review_coverage(context: Any, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe the actual excerpts sent, relative to supplied extracted text."""
    original = {str(c["chunk_id"]): str(c.get("text", "")) for c in context.chunk_infos}
    reviewed = 0
    for chunk in chunks:
        text = str(chunk.get("text", ""))
        source = original.get(str(chunk["chunk_id"]), "")
        if text not in source and text.endswith("..."):
            text = text[:-3].rstrip()
        if text not in source:
            raise AgentExecutionError("ITSO review excerpt is not supplied source text")
        reviewed += len(text)
    supplied = sum(len(text) for text in original.values())
    full = len(chunks) == len(original) and all(
        str(c.get("text", "")) == original.get(str(c["chunk_id"])) for c in chunks
    )
    return {
        "supplied_chunk_count": len(original),
        "reviewed_chunk_count": len(chunks),
        "supplied_text_characters": supplied,
        "reviewed_text_characters": reviewed,
        "all_supplied_text_reviewed": full,
        "scope": (
            "extracted text only; images and extraction omissions are not assessed"
        ),
    }


def policy_context(policy: Mapping[str, Any], codes: set[str]) -> dict[str, Any]:
    """Accept only the existing residency-gated snapshot shape, with tight caps."""
    result: dict[str, Any] = {}
    if policy.get("delivery_state") != "enabled":
        return result
    criteria = policy.get("criteria", {})
    if not isinstance(criteria, Mapping):
        return result
    for code in sorted(codes & {"ITSO-03", "ITSO-04", "ITSO-05"}):
        row = criteria.get(code, {})
        if not isinstance(row, Mapping) or row.get("status") != "available":
            continue
        clauses = []
        for chunk in row.get("chunks", ())[:2]:
            if isinstance(chunk, Mapping) and isinstance(chunk.get("text"), str):
                clauses.append(
                    {
                        "text": chunk["text"][:500],
                        "page_number": chunk.get("page_number"),
                    }
                )
        if clauses:
            result[code] = {"policy_area": row.get("policy_area"), "clauses": clauses}
    return result


def evidence_options(chunks: list[dict[str, Any]], codes: set[str]) -> dict[str, list]:
    """Offer short exact passages, not generated assertions or assigned scores."""
    options: dict[str, list] = {}
    patterns = {
        "ITSO-02": r"\b(?:learning\s+resources|references|bibliography)\b",
        "ITSO-03": r"\b(?:prepared\s+by|copyright|ownership)\b",
    }
    for code in sorted(codes):
        candidates = (
            sorted(
                chunks,
                key=lambda c: (
                    not re.search(r"\bprepared\s+by\b", str(c.get("text", "")), re.I)
                ),
            )
            if code == "ITSO-03"
            else chunks
        )
        for chunk in candidates:
            text = str(chunk.get("text", ""))
            match = (
                (
                    re.search(r"\bprepared\s+by\b", text, re.I)
                    if code == "ITSO-03"
                    else None
                )
                or re.search(patterns[code], text, re.IGNORECASE)
                if code in patterns
                else None
            )
            if code != "ITSO-01" and match is None:
                continue
            start = match.start() if match else 0
            quote = text[start : start + 220].strip()
            if quote.endswith("..."):
                quote = quote[:-3].rstrip()
            if quote:
                options.setdefault(code, []).append(
                    {"chunk_id": chunk["chunk_id"], "quote": quote}
                )
            if len(options.get(code, [])) == 2:
                break
    return options


def validate_review_evidence(
    parsed: dict[str, Any],
    criteria: tuple[Any, ...],
    *,
    packed_chunk_map: dict[str, str] | None = None,
) -> None:
    """Require quotations for decisive document findings under defined rules.

    Empty evidence supports a provisional 3 for ownership/rights, or the
    rubric's scoped no-concern 4 for confidentiality. Historical forms without
    scoring rules retain their original contract.
    """
    definitions = {c.criterion_code: c for c in criteria if c.scoring_rule}
    if not definitions:
        return
    options = evidence_options(
        [
            {"chunk_id": cid, "text": text}
            for cid, text in (packed_chunk_map or {}).items()
        ],
        set(definitions),
    )
    rows = parsed["criterion_scores"]
    if isinstance(rows, dict):
        rows = [
            {**(row if isinstance(row, dict) else {"score": row}), "criterion_id": code}
            for code, row in rows.items()
        ]
    for row in rows:
        code = row["criterion_id"]
        if code not in definitions:
            continue
        if (
            not isinstance(row.get("justification"), str)
            or not row["justification"].strip()
        ):
            error = AgentExecutionError(
                "ITSOInvalidJustification: criterion reasoning is required"
            )
            error.itso_diagnostic_category = "ITSOInvalidJustification"
            raise error
        if (
            code == "ITSO-01"
            and row["score"] == 4
            and re.search(
                r"\boriginality\s+(?:(?:remains?|is|was)\s+)?"
                r"(?:unverified|not\s+(?:verified|established))\b",
                row["justification"],
                re.I,
            )
        ):
            error = AgentExecutionError(
                "ITSOInvalidScore: top band contradicts stated originality uncertainty"
            )
            error.itso_diagnostic_category = "ITSOInvalidScore"
            error.itso_criterion_id = code
            error.itso_reason = "unverified_top_score"
            raise error
        needs_quote = (
            code == "ITSO-01"
            or code in {"ITSO-02", "ITSO-03"}
            and bool(options.get(code))
            or code == "ITSO-04"
            and row["score"] < 4
            or code in {"ITSO-03", "ITSO-05"}
            and row["score"] != 3
        )
        if needs_quote and not row.get("evidence"):
            error = AgentExecutionError(
                "ITSOInvalidEvidence: document finding requires a quotation"
            )
            error.itso_diagnostic_category = "ITSOInvalidEvidence"
            error.itso_criterion_id = code
            error.itso_reason = "missing_review_evidence"
            raise error
