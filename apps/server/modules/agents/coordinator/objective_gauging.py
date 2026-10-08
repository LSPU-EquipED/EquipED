"""Coordinator v3 source inventory, evidence validation, and coverage scoring.

This deliberately accepts a bounded text format, not arbitrary PDF layouts.
The scoring response cannot add, omit, or merge source objectives.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..exceptions import AgentExecutionError
from ..runtime.bands import ratio_band
from ..runtime.slicing import GAP_MARKER

_OBJECTIVE_HEADINGS = frozenset(
    {
        "objectives",
        "learning objectives",
        "course objectives",
        "lesson objectives",
        "learning outcomes",
        "intended learning outcomes",
    }
)
_ASSESSMENT_HEADINGS = frozenset(
    {
        "assessment",
        "assessments",
        "assessment tasks",
        "self-assessment",
        "self assessment",
        "self-check",
        "self check",
        "quiz",
        "test",
        "pre-test",
        "post-test",
        "activities",
        "activity",
        "exercises",
        "exercise",
        "practice",
    }
)
_OTHER_HEADINGS = frozenset(
    {
        "introduction",
        "content",
        "lesson content",
        "discussion",
        "references",
        "summary",
        "conclusion",
        "lesson",
        "overview",
        "resources",
    }
)
_ENTRY = re.compile(r"^\s*(?:(?P<number>\d+)[.)]|[-*•])\s+(?P<text>\S.*)$")
_HEADING_PREFIX = re.compile(r"^\s*(?:#{1,6}\s+|[A-ZIVX]+[.)]\s+)")
_UNIT_HEADING = re.compile(r"^(?:lesson|unit|module)\s+\d+(?:\s*[:.-].*)?$", re.I)


@dataclass(frozen=True, slots=True)
class Objective:
    objective_id: str
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ObjectiveSource:
    objectives: tuple[Objective, ...]
    assessment_sections: tuple[str, ...]


def _heading(line: str) -> str | None:
    if _ENTRY.fullmatch(line):
        return None
    clean = _HEADING_PREFIX.sub("", line.strip()).rstrip(":").strip().casefold()
    if clean in _OBJECTIVE_HEADINGS | _ASSESSMENT_HEADINGS | _OTHER_HEADINGS:
        return clean
    if _UNIT_HEADING.fullmatch(clean):
        return "lesson"
    # An explicit unknown heading must not silently become an objective continuation.
    if (
        line.lstrip().startswith("#")
        or line.strip().endswith(":")
        or (line.strip() and line.strip().isupper() and len(line.strip()) < 100)
    ):
        return "unknown"
    if len(clean) < 80 and re.search(r"\b(objectives?|outcomes?)\b", clean):
        return "unknown"
    return None


def inventory_source(source: str, *, max_chars: int = 200_000) -> ObjectiveSource:
    if not isinstance(source, str) or not source.strip():
        raise AgentExecutionError("Coordinator objective source is empty")
    if len(source) > max_chars or GAP_MARKER.strip() in source:
        raise AgentExecutionError(
            "Coordinator objective source exceeds limits or is truncated"
        )
    objectives: list[Objective] = []
    assessments: list[str] = []
    section: str | None = None
    start: int | None = None
    end = 0
    assessment_start = 0
    offset = 0
    section_count = 0
    entry_indent: int | None = None
    numbered: bool | None = None
    next_number = 1
    seen: set[str] = set()

    def flush_objective() -> None:
        nonlocal start
        if start is None:
            return
        raw = source[start:end]
        text = raw.strip()
        span_end = end - (len(raw) - len(raw.rstrip()))
        normalized = " ".join(text.split()).casefold()
        if not text or normalized in seen:
            raise AgentExecutionError(
                "Coordinator objective inventory is empty or duplicated"
            )
        if len(text) > 4_000 or len(objectives) >= 100:
            raise AgentExecutionError(
                "Coordinator objective inventory exceeds supported limits"
            )
        seen.add(normalized)
        objectives.append(
            Objective(f"OBJ-{len(objectives) + 1:04d}", text, start, span_end)
        )
        start = None

    for line in source.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        heading = _heading(content)
        if heading is not None:
            if section == "objectives":
                flush_objective()
                if len(objectives) == section_count:
                    raise AgentExecutionError("Coordinator objective section is empty")
                if heading == "unknown":
                    raise AgentExecutionError(
                        "Coordinator objective section has an ambiguous heading"
                    )
            elif section == "assessment":
                assessments.append(source[assessment_start:offset].strip())
                if heading in _OBJECTIVE_HEADINGS:
                    raise AgentExecutionError(
                        "Objectives nested in assessment material are ambiguous"
                    )
            if heading in _OBJECTIVE_HEADINGS:
                section = "objectives"
                section_count = len(objectives)
                entry_indent = None
                numbered = None
                next_number = 1
            elif heading in _ASSESSMENT_HEADINGS:
                section = "assessment"
                assessment_start = offset + len(line)
            else:
                section = None
                if heading == "unknown" and re.search(
                    r"\b(objectives?|outcomes?)\b", content, re.I
                ):
                    raise AgentExecutionError("Unrecognized objective heading")
        elif section == "objectives" and content.strip():
            match = _ENTRY.fullmatch(content)
            if match:
                indent = len(content.expandtabs()) - len(content.expandtabs().lstrip())
                is_numbered = match.group("number") is not None
                if entry_indent is None:
                    entry_indent = indent
                    numbered = is_numbered
                if indent != entry_indent or numbered != is_numbered:
                    raise AgentExecutionError(
                        "Nested or mixed objective lists are ambiguous"
                    )
                if is_numbered:
                    if int(match.group("number")) != next_number:
                        raise AgentExecutionError(
                            "Objective numbering is incomplete or ambiguous"
                        )
                    next_number += 1
                flush_objective()
                start = offset + match.start("text")
                end = offset + len(content)
            elif start is not None and content[0].isspace():
                end = offset + len(content)
            else:
                raise AgentExecutionError(
                    "Objective entries must be numbered/bulleted "
                    "with indented continuations"
                )
        offset += len(line)
    if section == "objectives":
        flush_objective()
        if len(objectives) == section_count:
            raise AgentExecutionError("Coordinator objective section is empty")
    elif section == "assessment":
        assessments.append(source[assessment_start:].strip())
    if not objectives:
        raise AgentExecutionError("No supported explicit objective inventory")
    return ObjectiveSource(tuple(objectives), tuple(s for s in assessments if s))


def coverage_score(matched: int, total: int) -> int:
    if (
        type(matched) is not int
        or type(total) is not int
        or total <= 0
        or not 0 <= matched <= total
    ):
        raise ValueError("coverage counts are invalid")
    return ratio_band(matched, total, scale="moderate").band


def validate_matches(
    raw: str, inventory: ObjectiveSource, curriculum: str
) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise AgentExecutionError("Coordinator objective response is not JSON") from exc
    if not isinstance(data, dict) or set(data) != {"objective_matches"}:
        raise AgentExecutionError(
            "Coordinator objective response requires only objective_matches"
        )
    rows = data["objective_matches"]
    if not isinstance(rows, list) or len(rows) != len(inventory.objectives):
        raise AgentExecutionError(
            "Coordinator response must include every inventoried objective"
        )
    expected = {o.objective_id: o for o in inventory.objectives}
    validated: dict[str, dict[str, Any]] = {}
    keys = {
        "objective_id",
        "assessment_matched",
        "assessment_excerpt",
        "curriculum_matched",
        "curriculum_excerpt",
    }
    for row in rows:
        if not isinstance(row, dict) or set(row) != keys:
            raise AgentExecutionError("Coordinator objective row has invalid fields")
        oid = row["objective_id"]
        if not isinstance(oid, str) or oid not in expected or oid in validated:
            raise AgentExecutionError(
                "Coordinator response has unknown or duplicate objective IDs"
            )
        result: dict[str, Any] = {
            "objective_id": oid,
            "objective_text": expected[oid].text,
        }
        for dimension, sources in (
            ("assessment", inventory.assessment_sections),
            ("curriculum", (curriculum,)),
        ):
            matched = row[f"{dimension}_matched"]
            excerpt = row[f"{dimension}_excerpt"]
            if (
                type(matched) is not bool
                or not isinstance(excerpt, str)
                or len(excerpt) > 4_000
            ):
                raise AgentExecutionError(
                    "Coordinator matches require booleans and bounded excerpt strings"
                )
            excerpt = excerpt.strip()
            supported = bool(excerpt) and any(excerpt in s for s in sources)
            if dimension == "assessment" and any(
                excerpt and excerpt in o.text for o in inventory.objectives
            ):
                supported = False
            result[f"{dimension}_matched"] = matched and supported
            result[f"{dimension}_excerpt"] = excerpt if matched and supported else ""
            result[f"{dimension}_rejected"] = matched and not supported
        validated[oid] = result
    return {
        "objective_matches": [validated[o.objective_id] for o in inventory.objectives]
    }


def score_dimension(
    rows: list[dict[str, Any]], dimension: str
) -> tuple[int, str, tuple[str, ...]]:
    matched = sum(r[f"{dimension}_matched"] for r in rows)
    rejected = sum(r[f"{dimension}_rejected"] for r in rows)
    score = coverage_score(matched, len(rows))
    title = "Objective gauging" if dimension == "assessment" else "Curriculum alignment"
    summary = (
        f"{title}: {matched}/{len(rows)} objectives supported "
        f"({matched * 100 / len(rows):.1f}%). "
        f"{rejected} unsupported claims rejected. Score {score}."
    )
    supported_ids = ", ".join(
        r["objective_id"] for r in rows if r[f"{dimension}_matched"]
    )
    unmatched_ids = ", ".join(
        r["objective_id"] for r in rows if not r[f"{dimension}_matched"]
    )
    label = "Measured" if dimension == "assessment" else "Aligned"
    unmatched_label = "Unmeasured" if dimension == "assessment" else "Unaligned"
    summary += (
        f" {label} objectives: {supported_ids or 'none'}."
        f" {unmatched_label} objectives: {unmatched_ids or 'none'}."
    )
    evidence = tuple(
        r[f"{dimension}_excerpt"] for r in rows if r[f"{dimension}_matched"]
    )
    return score, summary, evidence
