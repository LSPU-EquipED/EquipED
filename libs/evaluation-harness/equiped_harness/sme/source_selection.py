"""Local, rubric-guided source selection for SME. No storage or model calls.

Section labels are hints, never proof that content is absent. Every returned
passage is an unchanged source span, in document order, with explicit gaps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from equiped_harness.contracts import CriterionDefinition, LlmRubricGuidanceConfig
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.runtime.slicing import GAP_MARKER

# Recognize document roles, not rubric codes or fixed page positions.
_HEADINGS = (
    (
        "metadata",
        r"(?:intellectual property|copyright|cover page|module information"
        r"|course information)",
    ),
    (
        "objectives",
        r"(?:(?:intended )?learning (?:outcomes?|objectives?)"
        r"|objectives?|targets/?|layunin)",
    ),
    (
        "rubric",
        r"(?:rubrics?|scoring guide|grading criteria|assessment criteria)(?:\s+.*)?",
    ),
    (
        "monitoring",
        r"(?:self[- ]assessment|checkpoints?|progress checks?|reflection)(?:\s+.*)?",
    ),
    ("feedback", r"(?:answer keys?|feedback|remediation|interventions?)(?:\s+.*)?"),
    ("enhancement", r"(?:enhancement|enrichment|extension|further practice)(?:\s+.*)?"),
    (
        "assessment",
        r"(?:assessments?|quizzes|quiz|post[- ]test|pre[- ]test"
        r"|evaluation tasks?|examinations?)(?:\s+.*)?",
    ),
    (
        "activity",
        r"(?:activities|activity(?:\s+\d+)?|learning tasks?"
        r"|learning experience(?:\s+\d+)?|practice tasks?|performance tasks?"
        r"|laboratory(?:\s*#?\s*\d+)?|lab\s*#?\s*\d+|gawain|pagsasanay)"
        r"(?:\s*[|:–—-].*)?",
    ),
    (
        "support",
        r"(?:student learning strategies|learning strategies"
        r"|post[- ]class follow[- ]up)(?:\s*.*)?",
    ),
    (
        "references",
        r"(?:references|bibliography|learning resources|web resources"
        r"|books?\(s\)|sources)",
    ),
    (
        "lesson",
        r"(?:module content|learning contents?|lesson content|lesson proper"
        r"|discussion|introduction)(?:\s+.*)?",
    ),
)
_HEADING_PATTERNS = tuple(
    (kind, re.compile(pattern, re.I)) for kind, pattern in _HEADINGS
)
_NEEDS = (
    (
        r"objectiv|outcome|gaug|measur",
        ("objectives", "activity", "assessment", "rubric"),
    ),
    (r"assess|evaluat|quiz|test", ("activity", "assessment", "rubric")),
    (
        r"interactiv|activit|task|direction|instruction|transform|higher.order",
        ("activity", "assessment"),
    ),
    (r"enhanc|enrich|extension", ("enhancement", "activity", "support")),
    (
        r"progress|monitor|checkpoint|reflection|self.assess",
        ("monitoring", "support", "assessment"),
    ),
    (r"feedback|intervention|remediat|answer.key", ("feedback", "rubric", "support")),
    (r"coheren|logical|flow|topic|paragraph|section|consisten|accura", ("lesson",)),
    (r"reference|bibliograph|citation|acknowledg", ("references",)),
    (
        r"metadata|copyright|cover|course code|academic year|author|title page",
        ("metadata",),
    ),
)
_STOP_WORDS = frozenset(
    "the and for with from this that these those are have has how all some most "
    "few none only score judge criterion review requirement material module "
    "students student provided using nearly whether content".split()
)


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    kind: str


def _heading_kind(line: str) -> str | None:
    label = re.sub(r"\s+", " ", line.strip()).rstrip(":").strip()
    label = re.sub(r"^(?:\d+(?:\.\d+)*[.)]|[A-Z][.)])\s+", "", label)
    if len(label) > 140 or len(label.split()) > 20:
        return None
    for kind, pattern in _HEADING_PATTERNS:
        if pattern.fullmatch(label):
            return kind
    return None


def _sections(text: str) -> list[_Span]:
    headings: list[tuple[int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        kind = _heading_kind(line)
        current = headings[-1][1] if headings else None
        # These are children of a task, not a new global objectives section.
        if (
            kind == "objectives"
            and current in {"activity", "assessment", "enhancement"}
            and re.fullmatch(r"\s*(?:objectives?|layunin):?\s*", line, re.I)
        ):
            kind = None
        if re.fullmatch(r"\s*Instructions?:?\s*", line, re.I) and current not in {
            "activity",
            "assessment",
            "enhancement",
            "rubric",
        }:
            kind = "activity"
        if kind and not (
            headings and kind == current and offset - headings[-1][0] < 120
        ):
            headings.append((offset, kind))
        offset += len(line)
    if not headings:
        return [_Span(0, len(text), "unclassified")]
    if headings[0][0] > 0:
        prefix = text[: headings[0][0]]
        kind = (
            "metadata"
            if re.search(r"self.paced\s+learning\s+module", prefix, re.I)
            else "unclassified"
        )
        headings.insert(0, (0, kind))
    return [
        _Span(start, headings[i + 1][0] if i + 1 < len(headings) else len(text), kind)
        for i, (start, kind) in enumerate(headings)
    ]


def _units(text: str, section: _Span, limit: int) -> list[_Span]:
    """Split long sections on original line/word boundaries, never rewrite text."""
    result = []
    start = section.start
    while start < section.end:
        while start < section.end and text[start].isspace():
            start += 1
        if start == section.end:
            break
        end = min(section.end, start + limit)
        if end < section.end:
            boundary = text.rfind("\n", start + limit // 2, end + 1)
            if boundary < 0:
                boundary = next(
                    (i for i in range(end, start, -1) if text[i].isspace()), -1
                )
            if boundary < 0:
                # An indivisible token cannot be included within this budget.
                next_space = re.search(r"\s", text[end : section.end])
                start = end + next_space.end() if next_space else section.end
                continue
            end = boundary
        result.append(_Span(start, end, section.kind))
        start = end
    return result


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", text.casefold())) - _STOP_WORDS


def _requirements(
    criteria: tuple[CriterionDefinition, ...],
) -> tuple[set[str], set[str]]:
    descriptions = []
    for criterion in criteria:
        descriptions.extend(
            (criterion.title, criterion.description, criterion.scoring_rule or "")
        )
        config = criterion.strategy_config
        if isinstance(config, LlmRubricGuidanceConfig):
            descriptions.append(config.guidance)
            descriptions.extend(d.descriptor for d in config.level_descriptors or ())
    query = " ".join(descriptions).casefold()
    kinds = {
        kind for pattern, group in _NEEDS if re.search(pattern, query) for kind in group
    }
    return kinds, _tokens(query)


def _render(text: str, spans: list[_Span]) -> str:
    merged: list[tuple[int, int]] = []
    for span in sorted(spans, key=lambda s: s.start):
        if merged and not text[merged[-1][1] : span.start].strip():
            merged[-1] = (merged[-1][0], span.end)
        else:
            merged.append((span.start, span.end))
    return GAP_MARKER.join(text[start:end].strip() for start, end in merged)


def select_source_text(
    text: str, criteria: tuple[CriterionDefinition, ...], *, budget: int
) -> str:
    """Select bounded source spans using section hints and current rubric wording.

    Unknown headings remain searchable by rubric vocabulary. With no matching
    roles or vocabulary, retain distributed original passages conservatively.
    Neither successful detection nor selection guarantees full coverage.
    """
    if budget < 1:
        raise AgentExecutionError("SME source budget must be positive")
    if len(text) <= budget:
        return text
    sections = _sections(text)
    kinds, terms = _requirements(criteria)
    units = [u for s in sections for u in _units(text, s, max(120, budget // 3))]
    lexical = {u: len(_tokens(text[u.start : u.end]) & terms) for u in units}
    # A front-matter hint must not permanently hide relevant prose under an
    # unfamiliar heading. Lexical matches can recover such passages.
    eligible = [
        u
        for u in units
        if u.kind != "metadata" or "metadata" in kinds or lexical[u] > 0
    ]
    if not eligible:
        eligible = units
    ranked = sorted(eligible, key=lambda u: (-(u.kind in kinds), -lexical[u], u.start))
    selected: list[_Span] = []

    def add(span: _Span) -> bool:
        if span in selected or len(_render(text, selected + [span])) > budget:
            return False
        selected.append(span)
        return True

    # Give each requested section role a chance before filling with more of
    # one abundant kind (usually explanatory lesson content).
    for kind in (
        "objectives",
        "activity",
        "assessment",
        "rubric",
        "monitoring",
        "feedback",
        "enhancement",
        "support",
        "lesson",
        "references",
        "metadata",
    ):
        if kind in kinds:
            for unit in ranked:
                if unit.kind == kind and add(unit):
                    break

    if not selected and not any(lexical[u] for u in eligible):
        # Unknown layout: distribute passage coverage instead of guessing roles.
        for i in dict.fromkeys((0, len(eligible) // 2, len(eligible) - 1)):
            if eligible:
                add(eligible[i])
    for span in ranked:
        add(span)
    if not selected:
        raise AgentExecutionError(
            "SME source budget cannot fit a complete source passage"
        )
    return _render(text, selected)


__all__ = ["select_source_text"]
