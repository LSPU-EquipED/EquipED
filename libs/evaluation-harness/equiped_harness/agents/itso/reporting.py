"""ITSO evidence interpretation and concise reporting, independent of storage."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

from equiped_harness.agents.itso.document_review import unquoted_review_status
from equiped_harness.agents.itso.prompt import reference_limit_notice
from equiped_harness.contracts import CriterionDefinition

_ITSO_SOURCE_MARKER = re.compile(r"\[\s*source\s+([1-9][0-9]*)\s*\]", re.I)
_ITSO_RECEIPT_MARKERS = (
    "Tool-derived public reference verification (",
    " Reviewed extracted-text coverage:",
)


def usable_source(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    if str(row.get("status", "")).strip().casefold() not in {
        "matched",
        "ambiguous",
        "mismatch",
        "mismatched",
    }:
        return False
    url = row.get("source_url")
    excerpt = row.get("excerpt")
    if (
        not isinstance(url, str)
        or not url
        or not isinstance(excerpt, str)
        or not excerpt.strip()
    ):
        return False
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme.casefold() == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def public_sources(
    report: dict | None, model_justification: str
) -> list[dict[str, Any]]:
    """Project only cited, usable passages, preserving report position numbers."""
    if report is None:
        return []
    refs = report.get("references")
    if not isinstance(refs, list):
        return []
    cited = {int(value) for value in _ITSO_SOURCE_MARKER.findall(model_justification)}
    cited.update(
        index
        for index, row in enumerate(refs, 1)
        if isinstance(row, dict)
        and isinstance(row.get("source_url"), str)
        and cites_public_source(model_justification, row["source_url"])
    )
    projected: list[dict[str, Any]] = []
    for number in sorted(cited):
        if number < 1 or number > len(refs) or len(projected) >= 5:
            continue
        row = refs[number - 1]
        if not usable_source(row):
            continue
        title = row.get("title")
        projected.append(
            {
                "number": number,
                "title": title[:300] if isinstance(title, str) else None,
                "url": row["source_url"],
                "excerpt": row["excerpt"].strip()[:700],
            }
        )
    return projected


def pre_receipt_justification(justification: str) -> str:
    positions = [
        position
        for marker in _ITSO_RECEIPT_MARKERS
        if (position := justification.find(marker)) >= 0
    ]
    return justification[: min(positions)].rstrip() if positions else justification


def has_saved_items(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        if not value.strip():
            return False
        try:
            decoded = json.loads(value)
        except ValueError:
            return True
        return bool(decoded) if isinstance(decoded, list) else bool(decoded)
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(value)


def result_evidence_status(
    criterion: CriterionDefinition,
    *,
    score: int,
    evidence: Any,
    chunk_ids: Any,
    justification: str,
    is_itso_v3: bool,
) -> str | None:
    if (
        not is_itso_v3
        or criterion.criterion_code not in {"ITSO-04", "ITSO-05"}
        or not justification.strip()
        or has_saved_items(evidence)
        or has_saved_items(chunk_ids)
    ):
        return None
    return unquoted_review_status(criterion, score)


def reference_check_note(report: dict | None) -> str | None:
    if report is None:
        return None
    rows = report.get("references")
    if not isinstance(rows, list):
        return None
    usable_count = sum(usable_source(row) for row in rows)
    searched_count = len(rows)
    if not searched_count:
        return None
    sentence = (
        f"Readable source text was found for {usable_count} of {searched_count} "
        f"searched reference{'s' if searched_count != 1 else ''}."
    )
    coverage = report.get("coverage")
    skipped = coverage.get("skipped") if isinstance(coverage, dict) else None
    if type(skipped) is int and skipped > 0:
        verb = "was" if skipped == 1 else "were"
        sentence += (
            f" {skipped} additional reference{'s' if skipped != 1 else ''} "
            f"{verb} not searched."
        )
    fields = {
        field
        for row in rows
        if isinstance(row, dict)
        for field in (row.get("unverified_fields") or [])
        if field in {"author", "year"}
    }
    if fields:
        names = " and ".join(name for name in ("author", "year") if name in fields)
        sentence += f" {names.capitalize()} details remain unconfirmed."
    return sentence


def review_summary(report: dict | None, payload: dict | None) -> str | None:
    """Build readable presentation from the complete saved v3 review facts."""
    coverage = payload.get("document_review_coverage") if payload else None
    local_status = payload.get("local_policy_status") if payload else None
    rows = report.get("references") if report else None
    if (
        not isinstance(coverage, dict)
        or not isinstance(rows, list)
        or local_status not in {"available", "unavailable"}
    ):
        return None
    reviewed = coverage.get("reviewed_chunk_count")
    supplied = coverage.get("supplied_chunk_count")
    reviewed_chars = coverage.get("reviewed_text_characters")
    supplied_chars = coverage.get("supplied_text_characters")
    if not all(
        type(value) is int and value >= 0
        for value in (reviewed, supplied, reviewed_chars, supplied_chars)
    ):
        return None
    parts = []
    searched = len(rows)
    usable = sum(usable_source(row) for row in rows)
    parts.append(
        f"Public reference checks found readable source text for {usable} of "
        f"{searched} searched references."
    )
    report_coverage = report.get("coverage")
    skipped = (
        report_coverage.get("skipped") if isinstance(report_coverage, dict) else None
    )
    if type(skipped) is int and skipped > 0:
        parts.append(
            f"{skipped} additional detected reference"
            f"{' was' if skipped == 1 else 's were'} not searched."
        )
    unverified = {
        field
        for row in rows
        if isinstance(row, dict)
        for field in (row.get("unverified_fields") or [])
        if field in {"author", "year"}
    }
    if unverified:
        names = " and ".join(name for name in ("author", "year") if name in unverified)
        parts.append(f"{names.capitalize()} details remain unconfirmed.")
    parts.append(
        f"Document review covered {reviewed} of {supplied} text sections "
        f"({reviewed_chars} of {supplied_chars} characters). Images and "
        "missing extracted text were not assessed."
    )
    parts.append(
        "Institutional policy text was "
        f"{local_status}; ownership and permissions require human review."
    )
    return " ".join(parts)


def clean_justification(
    justification: str, *, strip_reference: bool, strip_coverage: bool
) -> str:
    markers = ((_ITSO_RECEIPT_MARKERS[0],) if strip_reference else ()) + (
        (_ITSO_RECEIPT_MARKERS[1],) if strip_coverage else ()
    )
    positions = [
        position for marker in markers if (position := justification.find(marker)) >= 0
    ]
    if positions:
        justification = justification[: min(positions)]
    return justification.rstrip()


def _v3_reference_summary(report_text: str) -> str:
    """Summarize trusted reference coverage in concise, readable language."""
    report = json.loads(report_text)
    usable_count = 0
    for row in report["references"]:
        status = row["status"].strip().casefold()
        url, excerpt = row["source_url"], row["excerpt"]
        usable_count += int(
            status in {"matched", "ambiguous", "mismatch", "mismatched"}
            and bool(url and excerpt and excerpt.strip())
        )

    summary = (
        f"Readable public source text was found for {usable_count} of "
        f"{len(report['references'])} references."
    )
    counts = report.get("coverage", {})
    if isinstance(counts, dict):
        if type(counts.get("skipped")) is int and counts["skipped"] >= 0:
            skipped = counts["skipped"]
            if skipped:
                summary += (
                    f" {skipped} additional detected reference"
                    f"{' was' if skipped == 1 else 's were'} not searched."
                )
    if report.get("bibliography_status") == "not_detected":
        summary += " No bibliography was found in the supplied text."

    return summary


def readable_reference_justification(justification: str, report: dict[str, Any]) -> str:
    """Separate the exact captured limit notice from an otherwise useful finding."""
    notice = reference_limit_notice(report)
    if not notice:
        return justification
    concise = re.sub(
        r"\s+", " ", re.sub(re.escape(notice), "", justification, flags=re.I)
    ).strip(" \t\r\n;")
    words = re.sub(r"\[\s*source\s+[1-9][0-9]*\s*\]", " ", concise, flags=re.I)
    words = re.sub(r"https://\S+", " ", words, flags=re.I)
    words = re.sub(r"[\W_]+", " ", words, flags=re.UNICODE)
    return concise if re.search(r"[^\W\d_]{2,}", words) else justification


def cites_public_source(justification: str, url: str) -> bool:
    tokens = re.findall(r"https://[^\s<>\"'`]+", justification)
    if any(
        token.startswith(url) and not token[len(url) :].strip(".,;:!?)]}")
        for token in tokens
    ):
        return True
    homepage = re.fullmatch(r"https://([^/?#]+)/?", url)
    if homepage is None:
        return False
    # A homepage's exact hostname identifies the retrieved resource without
    # requiring prose to repeat the scheme or root slash. Page paths still
    # require the complete URL, so a shared publisher host is insufficient.
    host = re.escape(homepage.group(1))
    return bool(
        host
        and re.search(
            rf"(?<![\w@./-])(?:https://)?{host}/?"
            rf"(?=$|[\s\)\]\}}]|[.,;:!?]+(?=$|[\s\)\]\}}]))",
            justification,
            flags=re.IGNORECASE,
        )
    )


def captured_context(
    generations: list[dict[str, Any]],
) -> tuple[dict | None, dict | None]:
    """Combine saved source-check and document-review facts from user JSON."""
    report = None
    presentation_payload: dict[str, Any] = {}
    for generation in generations:
        if generation.get("agent_id") != "itso" or not isinstance(
            generation.get("prompt_messages"), list
        ):
            continue
        for message in generation.get("prompt_messages"):
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content")
            if not isinstance(content, str):
                continue
            try:
                payload = json.loads(content)
            except (TypeError, ValueError):
                continue
            candidate_report = (
                payload.get("public_reference_verification")
                if isinstance(payload, dict)
                else None
            )
            if (
                report is None
                and isinstance(candidate_report, dict)
                and isinstance(candidate_report.get("references"), list)
            ):
                report = candidate_report
            if isinstance(payload, dict):
                if isinstance(payload.get("document_review_coverage"), dict):
                    presentation_payload["document_review_coverage"] = payload[
                        "document_review_coverage"
                    ]
                if payload.get("local_policy_status") in {"available", "unavailable"}:
                    presentation_payload["local_policy_status"] = payload[
                        "local_policy_status"
                    ]
    return report, presentation_payload if presentation_payload else None


def captured_criterion_justification(
    generations: list[dict[str, Any]], criterion_id: str, saved_justification: str
) -> str:
    """Return this criterion's original model rationale, never its receipt."""
    found_response_shape = False
    for generation in generations:
        response = generation.get("response_json")
        if not isinstance(response, dict):
            continue
        rows = response.get("criterion_scores")
        if isinstance(rows, dict):
            found_response_shape = True
            row = rows.get(criterion_id)
            if row is None:
                continue
        elif isinstance(rows, list):
            found_response_shape = True
            row = next(
                (
                    item
                    for item in rows
                    if isinstance(item, dict)
                    and item.get("criterion_id") == criterion_id
                ),
                None,
            )
            if row is None:
                continue
        else:
            continue
        return (
            row["justification"]
            if isinstance(row, dict) and isinstance(row.get("justification"), str)
            else ""
        )
    # Captures predating the criterion response shape can still be read safely:
    # only rationale preceding the known appended receipt markers is eligible.
    return (
        "" if found_response_shape else pre_receipt_justification(saved_justification)
    )


def present_justification(
    justification: str,
    *,
    criterion_id: str,
    report: dict | None,
    sources: list[dict],
    has_coverage: bool,
    reference_note: str | None,
) -> str:
    """Keep saved audit receipts when their supporting capture is unavailable."""
    has_receipt = any(marker in justification for marker in _ITSO_RECEIPT_MARKERS[:1])
    if has_receipt and not sources:
        return justification
    justification = clean_justification(
        justification,
        strip_reference=bool(sources),
        strip_coverage=has_coverage,
    )
    if criterion_id == "ITSO-02" and reference_note and report:
        justification = readable_reference_justification(justification, report)
    leading = re.match(
        r"^\s*\[\s*source\s+([1-9][0-9]*)\s*\]\s*:?\s*", justification, re.I
    )
    if leading and int(leading.group(1)) in {source["number"] for source in sources}:
        justification = justification[leading.end() :]
    return justification
