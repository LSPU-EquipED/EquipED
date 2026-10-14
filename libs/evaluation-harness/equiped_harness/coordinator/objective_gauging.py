"""Coordinator v3 source inventory, evidence validation, and coverage scoring.

This deliberately accepts a bounded text format, not arbitrary PDF layouts.
The scoring response cannot add, omit, or merge source objectives.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.runtime.bands import ratio_band
from equiped_harness.runtime.slicing import GAP_MARKER

_OBJECTIVE_HEADINGS = frozenset(
    {
        "objectives",
        "learning objectives",
        "course objectives",
        "lesson objectives",
        "learning outcomes",
        "intended learning outcomes",
        "lesson learning outcomes",
        "targets/ objectives",
        "targets/objectives",
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
        "student learning strategies",
        "online activities",
        "online activities (synchronous/ asynchronous)",
        "online activities (synchronous/asynchronous)",
    }
)
_ENTRY = re.compile(r"^\s*(?:(?P<number>\d+)[.)]|[-*•·])\s+(?P<text>\S.*)$")
_SPLIT_ENTRY = re.compile(r"^\s*(?P<marker>(?:\d+[.)]|[-*•·]))\s*$")
_LEARNER_LEAD_IN = re.compile(
    r"^(?:at the end of (?:this|the) (?:lesson|module|course)|"
    r"after completing (?:this|the) (?:lesson|module|course)),\s*"
    r"(?:the )?(?:students|learners)\s+(?:should|will)\s+be able to:?$",
    re.I,
)
# Only word-boundary prefixes of these exact lead-ins can be buffered.
_LEAD_INS = tuple(
    f"{opening} {determiner} {unit}, {learner} {modal} be able to"
    for opening in ("at the end of", "after completing")
    for determiner in ("this", "the")
    for unit in ("lesson", "module", "course")
    for learner in ("students", "learners", "the students", "the learners")
    for modal in ("should", "will")
)
_UNFINISHED = re.compile(
    r"(?:,|\b(?:and|or|with|by|to|of|for|between|such as|including))\s*$", re.I
)
# The actual template has a list conjunction after a completed semicolon clause,
# and a title-cased noun phrase wrapping after "in the". Neither is generic prose.
_LIST_CONJUNCTION = re.compile(r";\s+and\s*$", re.I)
_TITLE_WRAP_PREFIX = re.compile(r"\bin the\s*$", re.I)
# Confirmed wrap: a three-word title phrase whose first word is a -tion noun.
# Do not accept generic capitalized sentences or unmarked imperative objectives.
_TITLE_WRAP = re.compile(r"[A-Z][a-z]+tion(?: [A-Z][a-z]+){2}")
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


def _recognition_space(text: str) -> str:
    return " ".join(text.split())


def _heading(line: str) -> str | None:
    recognized_line = _recognition_space(line)
    if _ENTRY.fullmatch(recognized_line) or _SPLIT_ENTRY.fullmatch(recognized_line):
        return None
    clean = (
        _HEADING_PREFIX.sub("", recognized_line.strip()).rstrip(":").strip().casefold()
    )
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
    # The actual discussion contains a wrapped sentence with a singular
    # objective subject and "has ... to" predicate, not a plural list heading.
    # Explicit heading cues above still fail closed; this cannot start an entry.
    singular_prose = re.match(
        r"^(?:The|the) (?:main )?objective\b.+\bhas\b.+\bto\b", recognized_line
    )
    if (
        len(clean) < 80
        and re.search(r"\b(objectives?|outcomes?)\b", clean)
        and not singular_prose
    ):
        return "unknown"
    return None


def _structural_lines(source: str) -> Iterator[tuple[str, str]]:
    """Join only complete finite known headings over at most three adjacent lines.

    Raw lines are retained for offsets. No blank, marker, or unknown prose may
    be swallowed, and a partial extension of a complete heading is ambiguous.
    """
    lines = source.splitlines(keepends=True)
    known = _OBJECTIVE_HEADINGS | _ASSESSMENT_HEADINGS | _OTHER_HEADINGS
    index = 0
    while index < len(lines):
        first = lines[index].rstrip("\r\n")
        candidate = _recognition_space(first)
        best = 1 if _heading(first) in known else 0
        clean = _HEADING_PREFIX.sub("", candidate).casefold()
        initial_prefix = any(h.startswith(clean + " ") for h in known)
        consumed = 1
        for following in lines[index + 1 : index + 3]:
            clean = _HEADING_PREFIX.sub("", candidate).casefold()
            if not any(h.startswith(clean + " ") for h in known):
                break
            fragment = _recognition_space(following)
            if not fragment:
                break
            extended = candidate + " " + fragment
            recognized = _heading(extended)
            clean_extension = _HEADING_PREFIX.sub("", extended).casefold()
            prefix = any(h.startswith(clean_extension + " ") for h in known)
            if recognized not in known and not prefix:
                if consumed > best and best:
                    raise AgentExecutionError("Wrapped section heading is incomplete")
                break
            candidate = extended
            consumed += 1
            if recognized in known:
                best = consumed
        following = lines[index + 1] if index + 1 < len(lines) else ""
        # A single prefix cannot orphan an adjacent marked target or end at a
        # blank/EOF. Unrelated body prose is not a wrapped-heading candidate.
        previous_marker = index > 0 and _SPLIT_ENTRY.fullmatch(
            lines[index - 1].rstrip("\r\n")
        )
        orphan_prefix = (
            initial_prefix
            and not previous_marker
            and (
                not following.strip()
                or _ENTRY.fullmatch(following.rstrip("\r\n"))
                or _SPLIT_ENTRY.fullmatch(following.rstrip("\r\n"))
            )
        )
        if consumed > best and (best or consumed > 1 or orphan_prefix):
            raise AgentExecutionError("Wrapped section heading is incomplete")
        if best > 1:
            yield "".join(lines[index : index + best]), candidate
            index += best
        else:
            yield lines[index], first
            index += 1


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
    split_marker: str | None = None
    split_indent: int | None = None
    preface_lines: list[str] = []
    preface_complete = False
    unindented_wrap = False
    next_number = 1
    seen: set[str] = set()

    def flush_objective(*, bounded: bool = True, list_boundary: bool = False) -> None:
        nonlocal start, unindented_wrap
        if start is None:
            return
        raw = source[start:end]
        unfinished = bool(
            _UNFINISHED.search(raw.rstrip()) or _TITLE_WRAP_PREFIX.search(raw.rstrip())
        )
        if (unfinished and not (list_boundary and _LIST_CONJUNCTION.search(raw))) or (
            unindented_wrap and not bounded
        ):
            raise AgentExecutionError(
                "Objective continuation is incomplete or unbounded"
            )
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
        unindented_wrap = False

    for line, content in _structural_lines(source):
        if (
            section == "objectives"
            and not content.strip()
            and (
                preface_lines
                and not preface_complete
                or split_marker is not None
                or start is not None
                and (
                    _UNFINISHED.search(source[start:end].rstrip())
                    or _TITLE_WRAP_PREFIX.search(source[start:end].rstrip())
                )
            )
        ):
            raise AgentExecutionError(
                "Objective structural fragment crosses a blank line"
            )
        if section == "objectives" and content.strip() and start is None:
            candidate = _recognition_space(
                " ".join(preface_lines + [content.strip()])
            ).casefold()
            complete = bool(_LEARNER_LEAD_IN.fullmatch(candidate))
            prefix = any(lead.startswith(candidate + " ") for lead in _LEAD_INS)
            if (preface_lines and not preface_complete) or complete or prefix:
                if (
                    entry_indent is not None
                    or split_marker is not None
                    or preface_complete
                    or len(preface_lines) >= 3
                    or not (complete or prefix)
                ):
                    raise AgentExecutionError("Objective learner lead-in is ambiguous")
                preface_lines.append(content.strip())
                preface_complete = complete
                offset += len(line)
                continue
        heading = _heading(content)
        if heading is not None:
            if section == "objectives":
                if preface_lines and (
                    not preface_complete
                    or len(objectives) == section_count
                    and start is None
                ):
                    raise AgentExecutionError(
                        "Objective learner lead-in has no entries"
                    )
                if split_marker is not None:
                    raise AgentExecutionError("Objective list marker is incomplete")
                flush_objective()
                if (
                    len(objectives) == section_count
                    and heading not in _OBJECTIVE_HEADINGS
                ):
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
                if section == "objectives" and len(objectives) == section_count:
                    offset += len(line)
                    continue
                section = "objectives"
                section_count = len(objectives)
                entry_indent = None
                numbered = None
                next_number = 1
                preface_lines = []
                preface_complete = False
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
            split = _SPLIT_ENTRY.fullmatch(content)
            if split:
                if split_marker is not None:
                    raise AgentExecutionError("Objective list marker is ambiguous")
                flush_objective(list_boundary=True)
                split_marker = split.group("marker")
                split_indent = len(content.expandtabs()) - len(
                    content.expandtabs().lstrip()
                )
            elif split_marker is not None:
                if match:
                    raise AgentExecutionError(
                        "Objective list marker is followed by another marker"
                    )
                is_numbered = split_marker[0].isdigit()
                indent = len(content.expandtabs()) - len(content.expandtabs().lstrip())
                if split_indent != indent:
                    raise AgentExecutionError(
                        "Nested or mixed objective lists are ambiguous"
                    )
                if entry_indent is None:
                    entry_indent = indent
                    numbered = is_numbered
                if entry_indent != indent or numbered != is_numbered:
                    raise AgentExecutionError(
                        "Nested or mixed objective lists are ambiguous"
                    )
                if is_numbered:
                    number = int(split_marker[:-1])
                    if number != next_number:
                        raise AgentExecutionError(
                            "Objective numbering is incomplete or ambiguous"
                        )
                    next_number += 1
                start = offset + len(content) - len(content.lstrip())
                end = offset + len(content)
                split_marker = None
                split_indent = None
            elif match:
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
                flush_objective(list_boundary=True)
                start = offset + match.start("text")
                end = offset + len(content)
            elif start is not None and content[0].isspace():
                end = offset + len(content)
            elif start is not None and (
                _UNFINISHED.search(source[start:end].rstrip())
                and content[0].islower()
                or _TITLE_WRAP_PREFIX.search(source[start:end].rstrip())
                and _TITLE_WRAP.fullmatch(content.strip())
            ):
                end = offset + len(content)
                unindented_wrap = True
            else:
                raise AgentExecutionError(
                    "Objective entries must be numbered/bulleted "
                    "with indented continuations"
                )
        offset += len(line)
    if section == "objectives":
        if preface_lines and not preface_complete:
            raise AgentExecutionError("Objective learner lead-in is incomplete")
        flush_objective(bounded=False)
        if split_marker is not None:
            raise AgentExecutionError("Objective list marker is incomplete")
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
