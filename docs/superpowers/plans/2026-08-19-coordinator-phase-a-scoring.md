# Coordinator Phase A: Grouped-LLM Scoring Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Coordinator.run()` score all 10 rubric criteria itself, via
3 grouped direct-LLM-scoring calls, replacing the current single-call
A-05-only extract-then-compute path — with no dependency on
`feat/sme-dpo-scoring`.

**Architecture:** Four new Coordinator-only modules
(`groups.py`, `grouped_prompt.py`, `grouped_response.py`,
`grouped_execution.py`) copy-adapted from SME's equivalents but fully
independent (no imports from `sme.*` business logic — only the existing
shared `EngineScoredAgent` base stays shared). `Coordinator.run()` calls
these three grouped calls directly; `extraction.py`, `curriculum.py`, and
`reconciliation.py::merge_with_sme()` are deleted, along with the
orchestrator's post-hoc reconciliation step.

**Tech Stack:** Python 3.12, FastAPI modules under `server/modules/agents/`,
pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-coordinator-dpo-scoring-design.md`
(Phase A only — do not implement anything marked `*(Phase B)*` in that doc:
no `group_prompts` persistence beyond building the in-memory dict, no DPO
export script, no frontend/`feedback` schema changes, no adapters work).

## Global Constraints

- Ruff-enforced (E, F, I, UP), line length 88, Python 3.12
  (`uv run --project server ruff check server`).
- Run tests from repo root: `uv run --project server pytest <path>`.
- No shared modules between Coordinator's new grouped-scoring code and
  `server/modules/agents/sme/*` — copy-adapt, do not import, except the
  existing `EngineScoredAgent` base (`sme/pipeline.py`) for
  `_resolve_full_text`/`_rubric_titles`/`__init__` only (unchanged, already
  the case today).
- `REQUIRES_CURRICULUM_EVIDENCE: frozenset[str] = frozenset({"A-05"})` is
  the only criterion enforcing verbatim-quote groundedness against
  `curriculum_context`; do not add ad-hoc groundedness checks elsewhere.
- Hard-fail, no engine fallback: a group that fails validation twice
  (original attempt + one repair retry) is omitted from the result, not
  covered by any fallback path. If every group fails, the whole `run()`
  raises `AgentExecutionError`.
- Do not touch `server/modules/synthesis/service.py`,
  `server/modules/feedback/*`, any file under `client/`, or the DB
  migrations directory — all Phase B, out of scope here.

---

## File Structure

- Create: `server/modules/agents/coordinator/groups.py` — group→codes
  mapping, `REQUIRES_CURRICULUM_EVIDENCE`, and Coordinator's own text
  slicers (adapted from SME's `extraction.py` slicers, since Coordinator
  has no basket-extraction module to import them from).
- Create: `server/modules/agents/coordinator/grouped_prompt.py` — builds
  each group's JSON prompt payload (criteria descriptions/scoring
  rules/document slice/`curriculum_context`).
- Create: `server/modules/agents/coordinator/grouped_response.py` —
  response JSON schema, parsing, shape validation, and the
  `REQUIRES_CURRICULUM_EVIDENCE` groundedness check.
- Create: `server/modules/agents/coordinator/grouped_execution.py` — one
  group's LLM transport with repair-once retry.
- Modify: `server/modules/agents/coordinator/agent.py` — rewrite
  `Coordinator.run()` to drive the 3 grouped calls instead of
  `extraction.extract()` + `curriculum.compute()`.
- Delete: `server/modules/agents/coordinator/extraction.py`
- Delete: `server/modules/agents/coordinator/curriculum.py`
- Delete: `server/modules/agents/coordinator/reconciliation.py`
- Delete: `server/modules/agents/coordinator/summary.py` (its only
  consumer, `_build_alignment_summary`, is retired along with the
  A-05-only result it summarized).
- Modify: `server/modules/evaluations/orchestrator.py` — remove the
  `merge_with_sme` import, the `_reconcile_coordinator_result()` call
  site, and the function definition itself.
- Delete: `server/tests/agents/coordinator/test_coordinator_contract.py`,
  `test_coordinator_isolation.py`, `test_coordinator_roadmap.py`,
  `test_curriculum_alignment.py` — all import the retired modules
  (`extraction`/`curriculum`/`reconciliation`) and are already failing on
  `main` today (confirmed via `pytest server/tests/agents/coordinator/ -q`:
  36 failed / 24 passed before this plan's changes — pre-existing breakage
  from an earlier refactor, not caused by this work).
- Modify: `server/tests/agents/coordinator/test_coordinator_run.py` —
  replace entirely with tests for the new `run()`.
- Delete: `server/tests/evaluations/test_orchestrator_reconciliation.py` —
  tests `_reconcile_coordinator_result`, which no longer exists.
- Modify: `server/tests/evaluations/test_orchestrator.py` — remove the two
  `monkeypatch.setattr(evaluation_orchestrator, "_reconcile_coordinator_result", ...)`
  lines (the attribute won't exist anymore).
- Create: `server/tests/agents/coordinator/test_groups.py`,
  `test_grouped_prompt.py`, `test_grouped_response.py`,
  `test_grouped_execution.py`.

**Interfaces produced by this plan** (for reference across tasks):

```python
# groups.py
GROUP_CODES: dict[str, tuple[str, ...]]   # {"assessment_alignment": ("A-02","A-05"), ...}
GROUP_NAMES: tuple[str, ...]
CODE_TO_GROUP: dict[str, str]
REQUIRES_CURRICULUM_EVIDENCE: frozenset[str]   # {"A-05"}
def slice_for_group(group: str, text: str) -> str: ...

# grouped_prompt.py
def build_group_prompt(
    group: str, codes: tuple[str, ...], titles: dict[str, str],
    full_text: str, curriculum_context: str, *, prompt_preamble: str | None = None,
) -> str: ...

# grouped_response.py
def build_group_response_schema(codes: tuple[str, ...], titles: dict[str, str]) -> dict: ...
def parse_group_response(
    raw: str, codes: tuple[str, ...], titles: dict[str, str], curriculum_context: str,
) -> dict: ...
def group_criterion_scores(
    parsed: dict, codes: tuple[str, ...], titles: dict[str, str],
) -> tuple[CriterionScore, ...]: ...

# grouped_execution.py
def execute_group(
    group: str, codes: tuple[str, ...], titles: dict[str, str],
    client: RunLLMClient, full_text: str, curriculum_context: str,
    *, prompt_preamble: str | None = None,
) -> tuple[tuple[CriterionScore, ...], str]: ...
```

---

## Task 1: `coordinator/groups.py` — grouping, groundedness config, text slicing

**Files:**
- Create: `server/modules/agents/coordinator/groups.py`
- Test: `server/tests/agents/coordinator/test_groups.py`

**Interfaces:**
- Produces: `GROUP_CODES`, `GROUP_NAMES`, `CODE_TO_GROUP`,
  `REQUIRES_CURRICULUM_EVIDENCE`, `slice_for_group(group, text) -> str`
  (see File Structure interfaces above).

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/agents/coordinator/test_groups.py
from __future__ import annotations

import pytest
from server.modules.agents.coordinator import groups
from server.modules.agents.sme.registry import REGISTERED_CODES


def test_group_codes_cover_every_registered_code_exactly_once():
    seen = []
    for codes in groups.GROUP_CODES.values():
        seen.extend(codes)
    assert sorted(seen) == sorted(REGISTERED_CODES)
    assert len(seen) == len(set(seen))


def test_code_to_group_is_the_exact_inverse_of_group_codes():
    for group_name, codes in groups.GROUP_CODES.items():
        for code in codes:
            assert groups.CODE_TO_GROUP[code] == group_name


def test_group_names_matches_group_codes_keys():
    assert set(groups.GROUP_NAMES) == set(groups.GROUP_CODES)


def test_assessment_alignment_group_codes():
    assert groups.GROUP_CODES["assessment_alignment"] == ("A-02", "A-05")


def test_task_execution_group_codes():
    assert groups.GROUP_CODES["task_execution"] == (
        "A-01", "A-03", "OP-02", "OP-03", "OP-05",
    )


def test_document_wide_group_codes():
    assert groups.GROUP_CODES["document_wide"] == ("OP-01", "OP-04", "A-04")


def test_requires_curriculum_evidence_contains_only_a05():
    assert groups.REQUIRES_CURRICULUM_EVIDENCE == frozenset({"A-05"})
    # every code in the set must be a real, currently-registered code
    assert groups.REQUIRES_CURRICULUM_EVIDENCE <= REGISTERED_CODES


def test_slice_for_group_rejects_unknown_group():
    with pytest.raises(KeyError):
        groups.slice_for_group("not-a-group", "text")


def test_slice_for_group_assessment_alignment_short_text_returned_whole():
    text = "short SLM text"
    assert groups.slice_for_group("assessment_alignment", text) == text


def test_slice_for_group_task_execution_anchors_to_performance_task_section():
    prefix = "lecture body " * 2000
    tail = "Performance Task 1: build a widget."
    text = prefix + tail
    sliced = groups.slice_for_group("task_execution", text)
    assert tail in sliced
    assert len(sliced) < len(text)


def test_slice_for_group_document_wide_downsamples_long_text():
    text = "x" * 50000
    sliced = groups.slice_for_group("document_wide", text)
    assert len(sliced) < len(text)
    assert "[...]" in sliced


def test_slice_for_group_document_wide_short_text_returned_whole():
    text = "short text"
    assert groups.slice_for_group("document_wide", text) == text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_groups.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named
'server.modules.agents.coordinator.groups'`

- [ ] **Step 3: Write `groups.py`**

```python
"""Grouping for Coordinator's LLM-direct-scoring calls.

Coordinator's rubric is identical in shape to SME's (same 10 codes -- see
server/data/rubrics/rubrics.json) but is scored through an independent,
curriculum-alignment lens instead of SME's content-accuracy lens. This
module is copy-adapted from server/modules/agents/sme/groups.py and
server/modules/agents/sme/extraction.py's text slicers, NOT imported from
them -- see
docs/superpowers/specs/2026-08-18-coordinator-dpo-scoring-design.md
("Code sharing: fully separate, not shared machinery"). Coordinator has no
basket-extraction module of its own to slice against, so its slicers are
defined here directly instead of split into a separate extraction module.
"""

from __future__ import annotations

GROUP_CODES: dict[str, tuple[str, ...]] = {
    "assessment_alignment": ("A-02", "A-05"),
    "task_execution": ("A-01", "A-03", "OP-02", "OP-03", "OP-05"),
    "document_wide": ("OP-01", "OP-04", "A-04"),
}

GROUP_NAMES: tuple[str, ...] = tuple(GROUP_CODES)

CODE_TO_GROUP: dict[str, str] = {
    code: group_name
    for group_name, codes in GROUP_CODES.items()
    for code in codes
}

# Only A-05 (Objective Gauging) has a literal, quotable claim against
# curriculum_context ("this objective is addressed by the curriculum").
# The other 9 criteria judge the document's own internal qualities
# (interactivity, clarity, feedback quality) that curriculum text has
# nothing to verify against -- see the design doc's "Groundedness
# enforcement" section for the full rationale.
REQUIRES_CURRICULUM_EVIDENCE: frozenset[str] = frozenset({"A-05"})

# Real student-facing tasks live in a "Performance Task(s)" section near
# the bottom of the PDF, not scattered activity words in the lecture body
# (see server/modules/agents/sme/extraction.py's SECTION_ANCHORS for the
# same finding on SME's side).
_SECTION_ANCHORS: tuple[str, ...] = (
    "performance task",
    "performance tasks",
    "learning tasks",
    "enrichment activit",
    "enhancement activit",
    "assessment task",
    "questions for reflection",
)

_GAP_MARKER = "\n\n[...]\n\n"


def _find_section_start(text: str, *, after: int = 0) -> int | None:
    """Earliest _SECTION_ANCHORS match at or after ``after``, or None."""
    lower = text.lower()
    start: int | None = None
    for anchor in _SECTION_ANCHORS:
        idx = lower.find(anchor, after)
        if idx != -1 and (start is None or idx < start):
            start = idx
    return start


def _slice_head_and_tail(text: str, *, head: int = 4000, body: int = 7000) -> str:
    """Objectives head + the bottom Performance-Tasks section.

    Objectives are typically stated early; A-02/A-05 need both the stated
    objectives and the assessments/alignment evidence near the bottom.
    """
    if len(text) <= head + body:
        return text
    head_part = text[:head]
    start = _find_section_start(text, after=head)
    body_part = text[-body:] if start is None else text[start : start + body]
    return head_part + "\n\n[...lecture body omitted...]\n\n" + body_part


def _slice_bottom_section(text: str, *, body: int = 9000) -> str:
    """The bottom Performance-Tasks section only, tail-anchored fallback."""
    if len(text) <= body:
        return text
    start = _find_section_start(text)
    if start is None:
        return text[-body:]
    return text[start : start + body]


def _downsample(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample ``windows`` evenly-spaced chunks spanning the whole document.

    Criteria that judge the full lesson sequence (OP-01 coherence, OP-04
    section accuracy) need visibility into late topics a single window
    would miss -- see server/modules/agents/sme/slicing.py's ``downsample``
    for the same technique on SME's side (this is a direct, independent
    copy so Coordinator has no import-time dependency on the sme package
    beyond EngineScoredAgent).
    """
    if len(text) <= budget:
        return text
    chunk_size = max(budget // windows, 1)
    chunks: list[str] = []
    for i in range(windows):
        if i == windows - 1:
            start = max(0, len(text) - chunk_size)
        else:
            start = (i * len(text)) // windows
        chunks.append(text[start : start + chunk_size])
    return _GAP_MARKER.join(chunks)


def slice_for_group(group: str, text: str) -> str:
    if group == "assessment_alignment":
        return _slice_head_and_tail(text)
    if group == "task_execution":
        return _slice_bottom_section(text)
    if group == "document_wide":
        return _downsample(text)
    raise KeyError(group)


__all__ = [
    "GROUP_CODES",
    "GROUP_NAMES",
    "CODE_TO_GROUP",
    "REQUIRES_CURRICULUM_EVIDENCE",
    "slice_for_group",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_groups.py -v`
Expected: PASS (all 11 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/agents/coordinator/groups.py server/tests/agents/coordinator/test_groups.py
git commit -m "feat(coordinator): add grouping, groundedness config, and text slicers"
```

---

## Task 2: `coordinator/grouped_prompt.py` — prompt construction

**Files:**
- Create: `server/modules/agents/coordinator/grouped_prompt.py`
- Test: `server/tests/agents/coordinator/test_grouped_prompt.py`

**Interfaces:**
- Consumes: `groups.slice_for_group` (Task 1).
- Produces: `build_group_prompt(group, codes, titles, full_text,
  curriculum_context, *, prompt_preamble=None) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/agents/coordinator/test_grouped_prompt.py
from __future__ import annotations

import json

from server.modules.agents.coordinator.grouped_prompt import build_group_prompt

CODES = ("A-02", "A-05")
TITLES = {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"}


def test_build_group_prompt_includes_group_name_and_codes():
    prompt = build_group_prompt(
        "assessment_alignment", CODES, TITLES, "some SLM text", "curriculum text"
    )
    payload = json.loads(prompt)
    assert payload["group"] == "assessment_alignment"
    assert payload["agent"] == "coordinator"
    assert list(payload["criteria"]) == list(CODES)


def test_build_group_prompt_includes_curriculum_context_for_every_group():
    for group, codes in (
        ("assessment_alignment", CODES),
        ("task_execution", ("A-01",)),
        ("document_wide", ("OP-01",)),
    ):
        prompt = build_group_prompt(
            group, codes, {c: c for c in codes}, "text", "MY CURRICULUM TEXT"
        )
        assert "MY CURRICULUM TEXT" in prompt


def test_a05_scoring_rule_instructs_curriculum_grounding():
    prompt = build_group_prompt(
        "assessment_alignment", CODES, TITLES, "text", "curriculum text"
    )
    payload = json.loads(prompt)
    assert "curriculum" in payload["criteria"]["A-05"]["scoring_rule"].lower()


def test_non_a05_scoring_rule_does_not_require_curriculum_grounding():
    prompt = build_group_prompt(
        "assessment_alignment", CODES, TITLES, "text", "curriculum text"
    )
    payload = json.loads(prompt)
    assert "curriculum" not in payload["criteria"]["A-02"]["scoring_rule"].lower()


def test_prompt_preamble_is_prepended():
    prompt = build_group_prompt(
        "assessment_alignment",
        CODES,
        TITLES,
        "text",
        "curriculum text",
        prompt_preamble="SYSTEM NOTE",
    )
    assert prompt.startswith("SYSTEM NOTE")


def test_document_text_is_sliced_per_group():
    long_text = "x" * 50000
    prompt = build_group_prompt(
        "document_wide", ("OP-01",), {"OP-01": "Topic Coherence"}, long_text, "c"
    )
    payload = json.loads(prompt)
    assert len(payload["document_text"]) < len(long_text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_grouped_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `grouped_prompt.py`**

```python
"""Prompt construction for Coordinator's grouped LLM-scoring calls.

Every criterion's title/description is copied verbatim from
server/data/rubrics/rubrics.json (Coordinator's rubric set is byte-identical
to SME's). The scoring_rule text for the 9 non-A-05 criteria mirrors SME's
_SCORING_RULES (same document-internal judgment, same numeric bands) -- see
docs/superpowers/specs/2026-08-18-coordinator-dpo-scoring-design.md
("Curriculum-alignment scoring: where it happens"). A-05's scoring_rule is
the one rewritten to instruct curriculum-grounded evidence instead of
SLM-internal evidence.
"""

from __future__ import annotations

import json
from typing import Any

from .groups import slice_for_group

_DESCRIPTIONS: dict[str, str] = {
    "A-01": "Students are engaged in transforming what they learn.",
    "A-02": (
        "Teachers can easily assess students' progress by using varied "
        "assessment tools."
    ),
    "A-03": (
        "The material keeps an on-going record of students' progress and "
        "allows the teacher to monitor student performance."
    ),
    "A-04": (
        "Positive, meaningful feedback, and prescriptive guides for "
        "interventions are provided."
    ),
    "A-05": "Objectives are gauged effectively.",
    "OP-01": "Topics are coherent from Unit to Chapter.",
    "OP-02": (
        "Material is interactive in each lesson which makes life-long "
        "learning easier."
    ),
    "OP-03": (
        "Directions are clear and complete enough for students to perform "
        "required tasks."
    ),
    "OP-04": "Paragraphs and sections have clear and accurate information.",
    "OP-05": "Enhancement activities for students are provided.",
}

_SCORING_RULES: dict[str, str] = {
    "A-01": (
        "Score the percentage of tasks that engage higher-order thinking "
        "(apply/analyze/evaluate/create, not just remember/understand) on "
        "the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. "
        "No tasks found -> 1."
    ),
    "A-02": (
        "Count distinct assessment TYPES used (objective test, written, "
        "reflection, performance task, project, oral, self-assessment). "
        "Score: 5+ types -> 4, 3-4 types -> 3, 2 types -> 2, <=1 type -> 1."
    ),
    "A-05": (
        "Score the percentage of the SLM's stated objectives that are "
        "ADDRESSED BY THE CURRICULUM (not by the SLM's own assessments) on "
        "the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. "
        "An objective counts as addressed only if curriculum_context "
        "contains a verbatim quote supporting it -- copy that exact quote "
        "into evidence, do not paraphrase. No objectives found, or none "
        "addressed by the curriculum -> 1."
    ),
    "OP-02": (
        "Count genuine interactive elements with real task content (not "
        "just a label like 'Activity 1' with no actual task). Score: "
        "4+ elements -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
    "OP-03": (
        "Score the percentage of tasks with clear, complete directions on "
        "the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "OP-05": (
        "Count genuine enhancement activities beyond the core lesson "
        "content. Score: 3+ activities -> 4, 2 -> 3, 1 -> 2, 0 -> 1."
    ),
    "OP-01": (
        "If there are fewer than 4 topic-to-topic transitions total, score "
        "by issue count instead (a short module with 0 issues is coherent, "
        "not deficient): 0 issues -> 4, 1 -> 3, 2 -> 2, 3+ issues -> 1. "
        "Otherwise (4+ transitions), score the percentage of transitions "
        "that are coherent (each topic logically follows the last) on the "
        "moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. No "
        "topics at all -> 1."
    ),
    "OP-04": (
        "Score the percentage of sections that are clear and internally "
        "consistent (no contradictions or garbled content) on the moderate "
        "scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "A-04": (
        "Count distinct feedback/intervention mechanism TYPES (answer key, "
        "rubric, remediation referral, positive reinforcement). Score: "
        "3-4 types -> 4, 2 types -> 3, 1 type -> 2, 0 types -> 1."
    ),
    "A-03": (
        "Count genuine progress-monitoring mechanisms, spanning up to 4 "
        "types (checkpoint, self-assessment, reflection, cumulative). "
        "Score: 4+ mechanisms -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
}


def build_group_prompt(
    group: str,
    codes: tuple[str, ...],
    titles: dict[str, str],
    full_text: str,
    curriculum_context: str,
    *,
    prompt_preamble: str | None = None,
) -> str:
    document_text = slice_for_group(group, full_text)
    criteria: dict[str, Any] = {
        code: {
            "title": titles[code],
            "description": _DESCRIPTIONS[code],
            "scoring_rule": _SCORING_RULES[code],
        }
        for code in codes
    }
    instructions = [
        "Return JSON with summary and criterion_scores only.",
        "Return exactly one entry for each criterion, in this exact order "
        "and with these exact titles: "
        + "; ".join(f"{code} = {titles[code]}" for code in codes),
        "Each criterion score must be between 1 and 4.",
        "Follow each criterion's scoring_rule exactly -- state the count or "
        "percentage you found in the justification so the score is auditable.",
        "Ground non-curriculum claims in the provided document_text. For "
        "any criterion whose scoring_rule requires curriculum grounding, "
        "evidence must be an exact, verbatim quote from curriculum_context.",
    ]
    payload = {
        "agent": "coordinator",
        "group": group,
        "document_text": document_text,
        "curriculum_context": curriculum_context,
        "criteria": criteria,
        "instructions": instructions,
    }
    body = json.dumps(payload, ensure_ascii=False)
    return (prompt_preamble.rstrip() + "\n\n" + body) if prompt_preamble else body


__all__ = ["build_group_prompt"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_grouped_prompt.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/agents/coordinator/grouped_prompt.py server/tests/agents/coordinator/test_grouped_prompt.py
git commit -m "feat(coordinator): add grouped-scoring prompt construction"
```

---

## Task 3: `coordinator/grouped_response.py` — schema, parsing, groundedness

**Files:**
- Create: `server/modules/agents/coordinator/grouped_response.py`
- Test: `server/tests/agents/coordinator/test_grouped_response.py`

**Interfaces:**
- Consumes: `groups.REQUIRES_CURRICULUM_EVIDENCE` (Task 1),
  `CriterionScore` (`..contracts`), `AgentExecutionError` (`..exceptions`).
- Produces: `build_group_response_schema(codes, titles) -> dict`,
  `parse_group_response(raw, codes, titles, curriculum_context) -> dict`,
  `group_criterion_scores(parsed, codes, titles) -> tuple[CriterionScore, ...]`.

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/agents/coordinator/test_grouped_response.py
from __future__ import annotations

import json

import pytest
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.coordinator.grouped_response import (
    build_group_response_schema,
    group_criterion_scores,
    parse_group_response,
)

CODES = ("A-02", "A-05")
TITLES = {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"}
CURRICULUM = "This course covers algorithms and data structures in depth."


def _payload(*, a05_evidence=None, score=3):
    a05_evidence = (
        [CURRICULUM.split(".")[0] + "."] if a05_evidence is None else a05_evidence
    )
    entries = [
        {
            "criterion_id": "A-02",
            "criterion_title": TITLES["A-02"],
            "score": score,
            "justification": "justification text",
            "evidence": ["evidence quote"],
        },
        {
            "criterion_id": "A-05",
            "criterion_title": TITLES["A-05"],
            "score": score,
            "justification": "justification text",
            "evidence": a05_evidence,
        },
    ]
    return json.dumps({"summary": "ok", "criterion_scores": entries})


def test_build_schema_has_one_entry_per_code():
    schema = build_group_response_schema(CODES, TITLES)
    prefix_items = schema["properties"]["criterion_scores"]["prefixItems"]
    ids = [item["properties"]["criterion_id"]["const"] for item in prefix_items]
    assert ids == list(CODES)


def test_parse_accepts_valid_payload_with_grounded_a05_evidence():
    parsed = parse_group_response(_payload(), CODES, TITLES, CURRICULUM)
    assert parsed["summary"] == "ok"


def test_parse_rejects_non_json():
    with pytest.raises(AgentExecutionError):
        parse_group_response("not json", CODES, TITLES, CURRICULUM)


def test_parse_rejects_a05_evidence_not_verbatim_in_curriculum():
    payload = _payload(a05_evidence=["a fabricated quote"])
    with pytest.raises(AgentExecutionError):
        parse_group_response(payload, CODES, TITLES, CURRICULUM)


def test_parse_allows_a05_empty_evidence():
    payload = _payload(a05_evidence=[])
    parsed = parse_group_response(payload, CODES, TITLES, CURRICULUM)
    assert parsed["summary"] == "ok"


def test_parse_does_not_check_groundedness_for_non_a05_criteria():
    # A-02's evidence is "evidence quote", never in CURRICULUM -- must pass.
    parsed = parse_group_response(_payload(), CODES, TITLES, CURRICULUM)
    scores = group_criterion_scores(parsed, CODES, TITLES)
    a02 = next(s for s in scores if s.criterion_id == "A-02")
    assert a02.evidence == ("evidence quote",)


def test_group_criterion_scores_returns_one_per_code_in_order():
    parsed = parse_group_response(_payload(score=4), CODES, TITLES, CURRICULUM)
    scores = group_criterion_scores(parsed, CODES, TITLES)
    assert [s.criterion_id for s in scores] == list(CODES)
    assert all(s.score == 4 for s in scores)
    assert scores[0].chunk_ids == ()


def test_group_criterion_scores_rejects_out_of_range_score():
    parsed = parse_group_response(_payload(score=4), CODES, TITLES, CURRICULUM)
    parsed["criterion_scores"][0]["score"] = 5
    with pytest.raises(AgentExecutionError):
        group_criterion_scores(parsed, CODES, TITLES)


def test_group_criterion_scores_rejects_wrong_code_order():
    entries = [
        {
            "criterion_id": "A-05",
            "criterion_title": "Objective Gauging",
            "score": 3,
            "justification": "j",
            "evidence": [],
        },
        {
            "criterion_id": "A-02",
            "criterion_title": "Varied Assessment Tools",
            "score": 3,
            "justification": "j",
            "evidence": [],
        },
    ]
    parsed = {"summary": "ok", "criterion_scores": entries}
    with pytest.raises(AgentExecutionError):
        group_criterion_scores(parsed, CODES, TITLES)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_grouped_response.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `grouped_response.py`**

```python
"""Response schema and parsing for Coordinator's grouped LLM-scoring calls.

Copy-adapted from server/modules/agents/sme/grouped_response.py -- same
shape validation, plus one addition: a groundedness check, run only for
criteria in groups.REQUIRES_CURRICULUM_EVIDENCE, that mirrors the exact
substring check the retired extraction.py used to run in Python
(``evidence.strip() in curriculum_text``). See
docs/superpowers/specs/2026-08-18-coordinator-dpo-scoring-design.md
("Groundedness enforcement: config-driven, not universal").
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError
from .groups import REQUIRES_CURRICULUM_EVIDENCE

COORD_TEXT_MAX = 2000

_CRITERION_ITEM_KEYS = {
    "criterion_id",
    "criterion_title",
    "score",
    "justification",
    "evidence",
}


def _failure(category: str, value: Any) -> AgentExecutionError:
    reference = hashlib.sha256(str(value).encode()).hexdigest()[:16]
    return AgentExecutionError(f"{category} (reference: {reference})")


def build_group_response_schema(
    codes: tuple[str, ...], titles: dict[str, str]
) -> dict[str, Any]:
    def _entry(code: str) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "criterion_id",
                "criterion_title",
                "score",
                "justification",
                "evidence",
            ],
            "properties": {
                "criterion_id": {"const": code},
                "criterion_title": {"const": titles[code]},
                "score": {"type": "integer", "minimum": 1, "maximum": 4},
                "justification": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": COORD_TEXT_MAX,
                },
                "evidence": {
                    "type": "array",
                    "maxItems": 8,
                    "items": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": COORD_TEXT_MAX,
                    },
                },
            },
        }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "criterion_scores"],
        "properties": {
            "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
            "criterion_scores": {
                "type": "array",
                "minItems": len(codes),
                "maxItems": len(codes),
                "prefixItems": [_entry(code) for code in codes],
                "items": _entry(codes[0]) if codes else {"type": "object"},
            },
        },
    }


def parse_group_response(
    raw: str, codes: tuple[str, ...], titles: dict[str, str], curriculum_context: str
) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise _failure("CoordinatorGroupResponseTypeError", type(raw).__name__)
    payload = raw.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", payload, flags=re.I | re.S)
    if match:
        payload = match.group(1).strip()
    elif not payload.startswith("{"):
        raise _failure("CoordinatorGroupInvalidJSON", raw)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise _failure("CoordinatorGroupInvalidJSON", raw) from exc
    if (
        not isinstance(parsed, dict)
        or set(parsed) != {"summary", "criterion_scores"}
        or not isinstance(parsed.get("summary"), str)
        or not 1 <= len(parsed["summary"]) <= 2000
    ):
        raise _failure("CoordinatorGroupInvalidResponse", type(parsed).__name__)
    group_criterion_scores(parsed, codes, titles)
    _check_groundedness(parsed, codes, curriculum_context)
    return parsed


def _check_groundedness(
    parsed: dict[str, Any], codes: tuple[str, ...], curriculum_context: str
) -> None:
    entries = parsed["criterion_scores"]
    for code, entry in zip(codes, entries, strict=True):
        if code not in REQUIRES_CURRICULUM_EVIDENCE:
            continue
        for evidence in entry.get("evidence", []):
            if evidence.strip() not in curriculum_context:
                raise _failure("CoordinatorGroupUngroundedEvidence", code)


def group_criterion_scores(
    parsed: dict[str, Any], codes: tuple[str, ...], titles: dict[str, str]
) -> tuple[CriterionScore, ...]:
    entries = parsed.get("criterion_scores")
    if not isinstance(entries, list) or len(entries) != len(codes):
        raise _failure("CoordinatorGroupInvalidCriterionScores", "shape")
    seen: set[str] = set()
    result: list[CriterionScore] = []
    for index, (item, expected_code) in enumerate(zip(entries, codes, strict=True)):
        if (
            not isinstance(item, dict)
            or item.get("criterion_id") != expected_code
            or expected_code in seen
            or set(item) != _CRITERION_ITEM_KEYS
        ):
            raise _failure("CoordinatorGroupInvalidCriterion", index)
        if item.get("criterion_title") != titles.get(expected_code):
            raise _failure("CoordinatorGroupInvalidCriterionTitle", index)
        seen.add(expected_code)
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 4:
            raise _failure("CoordinatorGroupInvalidScore", index)
        justification = item.get("justification")
        if (
            not isinstance(justification, str)
            or not justification
            or len(justification) > COORD_TEXT_MAX
        ):
            raise _failure("CoordinatorGroupInvalidJustification", index)
        evidence = item.get("evidence")
        if (
            not isinstance(evidence, list)
            or len(evidence) > 8
            or any(
                not isinstance(e, str) or not e or len(e) > COORD_TEXT_MAX
                for e in evidence
            )
        ):
            raise _failure("CoordinatorGroupInvalidEvidence", index)
        result.append(
            CriterionScore(
                criterion_id=expected_code,
                criterion_title=item["criterion_title"],
                score=score,
                justification=justification,
                chunk_ids=(),
                evidence=tuple(evidence),
            )
        )
    return tuple(result)


__all__ = [
    "build_group_response_schema",
    "parse_group_response",
    "group_criterion_scores",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_grouped_response.py -v`
Expected: PASS (all 9 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/agents/coordinator/grouped_response.py server/tests/agents/coordinator/test_grouped_response.py
git commit -m "feat(coordinator): add grouped-scoring response schema, parsing, groundedness"
```

---

## Task 4: `coordinator/grouped_execution.py` — LLM transport with repair-once

**Files:**
- Create: `server/modules/agents/coordinator/grouped_execution.py`
- Test: `server/tests/agents/coordinator/test_grouped_execution.py`

**Interfaces:**
- Consumes: `grouped_prompt.build_group_prompt`,
  `grouped_response.build_group_response_schema`,
  `grouped_response.parse_group_response`,
  `grouped_response.group_criterion_scores` (Tasks 2-3),
  `RunLLMClient` (`..runtime.llm`), `AgentExecutionError` (`..exceptions`).
- Produces: `execute_group(group, codes, titles, client, full_text,
  curriculum_context, *, prompt_preamble=None) -> tuple[tuple[CriterionScore, ...], str]`.

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/agents/coordinator/test_grouped_execution.py
from __future__ import annotations

import json

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.runtime.llm import RunLLMClient
from server.modules.agents.coordinator.grouped_execution import execute_group

CODES = ("A-02", "A-05")
TITLES = {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"}
CURRICULUM = "This course covers algorithms in depth."


class _LLM:
    model = "primary"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def generate_result(
        self, prompt, *, temperature, max_new_tokens, deadline, response_contract
    ):
        self.prompts.append(prompt)
        return CompletionResult(
            next(self.responses), "primary", 10, 20, 30, "stop", attempts=1
        )


def _response(score=3, a05_evidence=None):
    a05_evidence = [] if a05_evidence is None else a05_evidence
    entries = [
        {
            "criterion_id": "A-02",
            "criterion_title": TITLES["A-02"],
            "score": score,
            "justification": "justification",
            "evidence": ["evidence"],
        },
        {
            "criterion_id": "A-05",
            "criterion_title": TITLES["A-05"],
            "score": score,
            "justification": "justification",
            "evidence": a05_evidence,
        },
    ]
    return json.dumps({"summary": "ok", "criterion_scores": entries})


def test_execute_group_returns_scores_and_prompt_text():
    client = RunLLMClient(_LLM([_response(4)]), "coordinator")
    scores, prompt_text = execute_group(
        "assessment_alignment", CODES, TITLES, client, "some SLM text", CURRICULUM
    )
    assert [s.criterion_id for s in scores] == list(CODES)
    assert all(s.score == 4 for s in scores)
    assert '"group": "assessment_alignment"' in prompt_text


def test_execute_group_repairs_once_on_bad_json():
    llm = _LLM(["{broken", _response(3)])
    client = RunLLMClient(llm, "coordinator")
    scores, _ = execute_group(
        "assessment_alignment", CODES, TITLES, client, "text", CURRICULUM
    )
    assert len(llm.prompts) == 2
    assert all(s.score == 3 for s in scores)


def test_execute_group_repairs_once_on_ungrounded_a05_evidence():
    llm = _LLM([_response(3, a05_evidence=["fabricated"]), _response(3)])
    client = RunLLMClient(llm, "coordinator")
    scores, _ = execute_group(
        "assessment_alignment", CODES, TITLES, client, "text", CURRICULUM
    )
    assert len(llm.prompts) == 2


def test_execute_group_raises_after_repair_also_fails():
    llm = _LLM(["{broken", "{still broken"])
    client = RunLLMClient(llm, "coordinator")
    with pytest.raises(AgentExecutionError):
        execute_group("assessment_alignment", CODES, TITLES, client, "text", CURRICULUM)
    assert len(llm.prompts) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_grouped_execution.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `grouped_execution.py`**

```python
"""LLM transport for one Coordinator grouped-scoring call, with
repair-once on a parse/groundedness failure. Copy-adapted from
server/modules/agents/sme/grouped_execution.py -- unlike SME's version,
a second failure here is NOT caught by a caller-side engine fallback; it
propagates as AgentExecutionError. See
docs/superpowers/specs/2026-08-18-coordinator-dpo-scoring-design.md
("Failure handling: hard-fail, no engine fallback").
"""

from __future__ import annotations

import time

from server.core.config import get_settings
from server.core.llm import ResponseContract

from ..contracts import CriterionScore
from ..runtime.llm import RunLLMClient
from .grouped_prompt import build_group_prompt
from .grouped_response import (
    build_group_response_schema,
    group_criterion_scores,
    parse_group_response,
)

_REPAIR_SUFFIX = (
    "\n\nVALIDATOR_FAILURE category=COORDINATOR_GROUP_INVALID "
    "path=criterion_scores. Regenerate ONLY the complete JSON response; "
    "do not include commentary."
)


def execute_group(
    group: str,
    codes: tuple[str, ...],
    titles: dict[str, str],
    client: RunLLMClient,
    full_text: str,
    curriculum_context: str,
    *,
    prompt_preamble: str | None = None,
) -> tuple[tuple[CriterionScore, ...], str]:
    settings = get_settings()
    prompt = build_group_prompt(
        group,
        codes,
        titles,
        full_text,
        curriculum_context,
        prompt_preamble=prompt_preamble,
    )
    if settings.llm_response_mode == "json_schema":
        contract = ResponseContract.json_schema(
            build_group_response_schema(codes, titles),
            name=f"coordinator_group_{group}",
        )
    else:
        contract = ResponseContract.json_object()
    temperature = settings.get_agent_temperature("coordinator")
    deadline = time.monotonic() + float(
        getattr(settings, "llm_request_timeout_seconds", 120)
    )
    completion = client.generate_result(
        prompt,
        temperature=temperature,
        max_new_tokens=settings.llm_max_new_tokens,
        deadline=deadline,
        response_contract=contract,
    )
    try:
        parsed = parse_group_response(
            completion.content, codes, titles, curriculum_context
        )
    except Exception:
        repaired = client.generate_result(
            prompt + _REPAIR_SUFFIX,
            temperature=temperature,
            max_new_tokens=settings.llm_max_new_tokens,
            deadline=deadline,
            response_contract=contract,
        )
        parsed = parse_group_response(
            repaired.content, codes, titles, curriculum_context
        )
    scores = group_criterion_scores(parsed, codes, titles)
    return scores, prompt


__all__ = ["execute_group"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_grouped_execution.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/agents/coordinator/grouped_execution.py server/tests/agents/coordinator/test_grouped_execution.py
git commit -m "feat(coordinator): add grouped-scoring LLM transport with repair-once retry"
```

---

## Task 5: Rewrite `Coordinator.run()` to drive the 3 grouped calls

**Files:**
- Modify: `server/modules/agents/coordinator/agent.py`
- Modify: `server/tests/agents/coordinator/test_coordinator_run.py` (full
  replacement)

**Interfaces:**
- Consumes: `groups.GROUP_NAMES`, `groups.GROUP_CODES` (Task 1),
  `grouped_execution.execute_group` (Task 4), `EngineScoredAgent`
  (`..sme.pipeline`, unchanged), `error_reference` (`..runtime.llm`).
- Produces: `Coordinator.run(...) -> AgentEvaluationResult` with
  `criterion_scores` covering up to 10 codes and
  `metadata={"group_prompts": {...}}` (values only used by Phase B later;
  harmless on `main` today since `AgentResult` has no `group_prompts`
  column to persist into — confirmed via
  `server/modules/synthesis/service.py`, which does not read
  `agent_result.metadata` at all on `main`).

- [ ] **Step 1: Replace `test_coordinator_run.py` with tests for the new `run()`**

```python
# server/tests/agents/coordinator/test_coordinator_run.py
"""Tests for Coordinator's grouped-LLM-scoring run().

Coordinator now scores all 10 criteria itself via 3 grouped calls (see
docs/superpowers/specs/2026-08-18-coordinator-dpo-scoring-design.md),
independent of SME. No merge/reconciliation step exists any more.
"""

from __future__ import annotations

import json
import uuid

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.coordinator.agent import Coordinator
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.sme.registry import REGISTERED_CODES

_CHUNK_INFOS = [{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}]
_CURRICULUM_TEXT = "This course covers algorithms in depth."
_TITLES = {code: f"{code} Title" for code in REGISTERED_CODES}


def _group_response(codes, score=3):
    entries = [
        {
            "criterion_id": code,
            "criterion_title": _TITLES[code],
            "score": score,
            "justification": "justification",
            "evidence": [],
        }
        for code in codes
    ]
    return json.dumps({"summary": "ok", "criterion_scores": entries})


class _SequencedClient:
    model = "coord-model"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_result(
        self, prompt, *, temperature, max_new_tokens, deadline, response_contract
    ):
        if self.calls >= len(self.responses):
            raise AssertionError("called more times than expected")
        payload = self.responses[self.calls]
        self.calls += 1
        if payload is None:
            raise RuntimeError("configured to fail")
        return CompletionResult(payload, self.model, "stop")


def _make_agent(monkeypatch, client) -> Coordinator:
    agent = Coordinator(llm_client=client)
    monkeypatch.setattr(
        "server.modules.agents.sme.pipeline.get_active_rubric_criteria",
        lambda agent_id, db=None: _TITLES,
    )
    return agent


def _all_group_responses(score=3):
    from server.modules.agents.coordinator import groups

    return [
        _group_response(groups.GROUP_CODES[name], score=score)
        for name in groups.GROUP_NAMES
    ]


def test_scores_all_ten_criteria_via_three_calls(monkeypatch):
    client = _SequencedClient(_all_group_responses())
    agent = _make_agent(monkeypatch, client)

    result = agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="full slm text",
        canonical_source_text="full slm text",
        curriculum_id=uuid.uuid4(),
        curriculum_context=_CURRICULUM_TEXT,
    )

    assert client.calls == 3
    assert {s.criterion_id for s in result.criterion_scores} == REGISTERED_CODES
    assert result.success is True
    assert set(result.metadata["group_prompts"]) == {
        "assessment_alignment", "task_execution", "document_wide",
    }


def test_requires_curriculum_context(monkeypatch):
    client = _SequencedClient(_all_group_responses())
    agent = _make_agent(monkeypatch, client)

    with pytest.raises(AgentExecutionError):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
            canonical_source_text="full slm text",
            curriculum_id=None,
            curriculum_context=None,
        )
    assert client.calls == 0


def test_one_group_failing_twice_omits_only_its_criteria(monkeypatch):
    from server.modules.agents.coordinator import groups

    responses = []
    for name in groups.GROUP_NAMES:
        if name == "task_execution":
            responses += ["{broken", "{still broken"]  # repair also fails
        else:
            responses.append(_group_response(groups.GROUP_CODES[name]))
    client = _SequencedClient(responses)
    agent = _make_agent(monkeypatch, client)

    result = agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="full slm text",
        canonical_source_text="full slm text",
        curriculum_id=uuid.uuid4(),
        curriculum_context=_CURRICULUM_TEXT,
    )

    missing = set(groups.GROUP_CODES["task_execution"])
    scored = {s.criterion_id for s in result.criterion_scores}
    assert scored == REGISTERED_CODES - missing
    assert result.success is True


def test_all_groups_failing_raises(monkeypatch):
    client = _SequencedClient(["{broken"] * 6)  # 3 groups x (try + repair)
    agent = _make_agent(monkeypatch, client)

    with pytest.raises(AgentExecutionError):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
            canonical_source_text="full slm text",
            curriculum_id=uuid.uuid4(),
            curriculum_context=_CURRICULUM_TEXT,
        )


def test_raises_when_no_chunk_infos(monkeypatch):
    agent = _make_agent(monkeypatch, _SequencedClient([]))

    with pytest.raises(AgentExecutionError):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=[],
            context_text="full slm text",
            curriculum_id=uuid.uuid4(),
            curriculum_context=_CURRICULUM_TEXT,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_run.py -v`
Expected: FAIL (old `run()` still single-call/A-05-only; import errors for
`groups` module usage inside the test are fine since Task 1-4 already
created it — the failures here should be assertion failures, e.g.
`client.calls == 1` not `3`, or `AttributeError` if `agent.py` doesn't yet
import what the test expects indirectly)

- [ ] **Step 3: Rewrite `agent.py`**

```python
"""Program coordinator domain agent.

Coordinator's rubric is byte-identical to SME's (see
server/data/rubrics/rubrics.json), but Coordinator scores all 10 criteria
independently, through a curriculum-alignment lens, via 3 grouped
direct-LLM-scoring calls (mirrors SME's own grouped-scoring pattern, but
fully separate code -- see
docs/superpowers/specs/2026-08-18-coordinator-dpo-scoring-design.md).
There is no reliance on SME's result and no engine fallback: a group that
fails validation twice (original attempt + one repair retry) is simply
omitted from the result.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from server.core.llm import get_llm_model_name

from ..contracts import AgentEvaluationResult, CriterionScore
from ..exceptions import AgentExecutionError
from ..runtime.llm import RunLLMClient, error_reference
from ..sme.pipeline import EngineScoredAgent
from . import groups
from .grouped_execution import execute_group

logger = logging.getLogger(__name__)


class Coordinator(EngineScoredAgent):
    agent_name = "coordinator"
    rubric_source_type = "rubric_coord"
    reference_source_types = ("syllabus",)
    domain_keywords = (
        "program",
        "outcomes",
        "objectives",
        "curriculum",
        "alignment",
        "competencies",
        "learning outcomes",
        "course",
        "standards",
        "assessment",
        "goals",
    )

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        db: Any | None = None,
        llm_client: Any | None = None,
        reference_document_ids: dict[str, Any] | None = None,
        roadmap_context: dict[str, Any] | None = None,
        canonical_source_text: str | None = None,
        curriculum_id: uuid.UUID | None = None,
        curriculum_context: str | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Score all 10 criteria via 3 grouped direct-LLM-scoring calls."""
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        start = time.perf_counter()
        full_text = self._resolve_full_text(
            document_id, context_text, chunk_infos, canonical_source_text
        )
        if not full_text.strip():
            raise AgentExecutionError("no document text available for evaluation")

        curriculum_id = curriculum_id or (reference_document_ids or {}).get(
            "curriculum"
        )
        if (
            curriculum_id is None
            or not isinstance(curriculum_context, str)
            or not curriculum_context.strip()
        ):
            raise AgentExecutionError(
                "Coordinator requires curriculum_id and authoritative "
                "curriculum context"
            )
        curriculum_text = curriculum_context.strip()

        client = llm_client or self._default_llm_client
        if client is None:
            raise AgentExecutionError("Coordinator requires an assigned LLM client")
        adapter = (
            client
            if isinstance(client, RunLLMClient)
            else RunLLMClient(
                client,
                self.agent_name,
                requested_model=(
                    getattr(client, "model", None) or get_llm_model_name()
                ),
            )
        )

        titles = self._rubric_titles(db)
        all_scores: dict[str, CriterionScore] = {}
        group_prompts: dict[str, str] = {}
        failed_groups: list[str] = []

        for group_name in groups.GROUP_NAMES:
            codes = groups.GROUP_CODES[group_name]
            group_titles = {code: titles.get(code, code) for code in codes}
            try:
                scores, prompt_text = execute_group(
                    group_name,
                    codes,
                    group_titles,
                    adapter,
                    full_text,
                    curriculum_text,
                )
            except Exception as exc:
                logger.warning(
                    "[COORDINATOR_LLM_SCORING] group=%s failed with no "
                    "fallback: category=%s | reference=%s",
                    group_name,
                    type(exc).__name__,
                    error_reference(exc),
                )
                failed_groups.append(group_name)
                continue
            for score in scores:
                all_scores[score.criterion_id] = score
            group_prompts[group_name] = prompt_text

        if not all_scores:
            raise AgentExecutionError(
                "Coordinator scoring failed for every group; no criteria scored"
            )

        criterion_scores = tuple(all_scores[code] for code in sorted(all_scores))
        subtotal = sum(s.score for s in criterion_scores) / len(criterion_scores)
        total_seconds = time.perf_counter() - start

        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=criterion_scores,
            summary="",
            model_name=adapter.actual_model or adapter.requested_model,
            processing_seconds=total_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=None,
            success=True,
            metadata={"group_prompts": group_prompts},
            provenance={
                "requested_model": adapter.requested_model,
                "actual_model": adapter.actual_model,
                "fallback_occurred": adapter.fallback_occurred,
                "grouped_calls": len(group_prompts),
                "failed_groups": failed_groups,
            },
        )


__all__ = ["Coordinator"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_run.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/agents/coordinator/agent.py server/tests/agents/coordinator/test_coordinator_run.py
git commit -m "feat(coordinator): score all 10 criteria via 3 grouped LLM calls"
```

---

## Task 6: Retire `extraction.py`, `curriculum.py`, `reconciliation.py`, `summary.py`, and the orchestrator's reconciliation step

**Files:**
- Delete: `server/modules/agents/coordinator/extraction.py`
- Delete: `server/modules/agents/coordinator/curriculum.py`
- Delete: `server/modules/agents/coordinator/reconciliation.py`
- Delete: `server/modules/agents/coordinator/summary.py`
- Modify: `server/modules/evaluations/orchestrator.py`
- Delete: `server/tests/agents/coordinator/test_coordinator_contract.py`
- Delete: `server/tests/agents/coordinator/test_coordinator_isolation.py`
- Delete: `server/tests/agents/coordinator/test_coordinator_roadmap.py`
- Delete: `server/tests/agents/coordinator/test_curriculum_alignment.py`
- Delete: `server/tests/evaluations/test_orchestrator_reconciliation.py`
- Modify: `server/tests/evaluations/test_orchestrator.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `evaluations/orchestrator.py` no longer imports
  `merge_with_sme` or defines `_reconcile_coordinator_result`;
  `supervisor_result.agent_results` is used directly (Coordinator's own
  `run()` result is already the complete 10-criterion result).

- [ ] **Step 1: Delete the four retired Coordinator modules**

```bash
git rm server/modules/agents/coordinator/extraction.py
git rm server/modules/agents/coordinator/curriculum.py
git rm server/modules/agents/coordinator/reconciliation.py
git rm server/modules/agents/coordinator/summary.py
```

- [ ] **Step 2: Delete the four stale Coordinator test files**

These import the modules just deleted and were already failing on `main`
before this plan (36 failed / 24 passed, confirmed via
`uv run --project server pytest server/tests/agents/coordinator/ -q`
before Task 1 started).

```bash
git rm server/tests/agents/coordinator/test_coordinator_contract.py
git rm server/tests/agents/coordinator/test_coordinator_isolation.py
git rm server/tests/agents/coordinator/test_coordinator_roadmap.py
git rm server/tests/agents/coordinator/test_curriculum_alignment.py
```

- [ ] **Step 3: Remove the reconciliation call site and function from `orchestrator.py`**

Remove the import (near the top of the file):

```python
from server.modules.agents.coordinator.reconciliation import merge_with_sme
```

Replace this block (the reconciliation call site, roughly where
`supervisor_result.agent_results = _reconcile_coordinator_result(...)`
appears):

```python
            # Coordinator's own run() (dispatched in parallel with SME by
            # Supervisor, unchanged) only computes A-05 -- splice in SME's
            # other 9 scores now that both have finished, or fall back to
            # Coordinator's full independent pass if SME failed. See
            # coordinator.py's module docstring for why.
            supervisor_result.agent_results = _reconcile_coordinator_result(
                supervisor_result.agent_results
            )
```

with nothing (delete the block entirely) — `supervisor_result.agent_results`
already contains Coordinator's complete, independent 10-criterion result
now, so no post-processing step is needed.

Delete the `_reconcile_coordinator_result` function definition entirely
(from its `def _reconcile_coordinator_result(` line through its final
`return [failed if r is coordinator_result else r for r in agent_results]`
line — the whole function, including the module-level docstring comment
directly above it).

- [ ] **Step 4: Delete the reconciliation-specific orchestrator test file**

```bash
git rm server/tests/evaluations/test_orchestrator_reconciliation.py
```

- [ ] **Step 5: Remove the two dead monkeypatches in `test_orchestrator.py`**

Find both occurrences of this block in
`server/tests/evaluations/test_orchestrator.py` (one around line 187, one
around line 365) and delete each entirely — `_reconcile_coordinator_result`
no longer exists, so `monkeypatch.setattr` on it would raise
`AttributeError`:

```python
    monkeypatch.setattr(
        evaluation_orchestrator,
        "_reconcile_coordinator_result",
        lambda results, **kwargs: results,
    )
```

- [ ] **Step 6: Run the full coordinator + orchestrator + evaluations test suites**

Run:
```bash
uv run --project server pytest server/tests/agents/coordinator/ server/tests/evaluations/ -v
```
Expected: PASS for every test in `server/tests/agents/coordinator/` (the
new Task 1-5 files) and every remaining test in
`server/tests/evaluations/test_orchestrator.py` (the two edited tests
should now pass without the dead monkeypatch calls, since Coordinator's
`run()` — invoked through `Supervisor.run_evaluation`, which these tests
already fake — needs no reconciliation step to reach `COMPLETED`).

If any `test_orchestrator.py` test still fails after removing the
monkeypatch, check whether it also constructed a fake `AgentEvaluationResult`
for `"coordinator"` with only a single `A-05` criterion (the old
single-call shape) — update any such fixture to return all 10 criteria
directly, matching Coordinator's new complete-result contract.

- [ ] **Step 7: Ruff check the whole coordinator package and orchestrator**

Run: `uv run --project server ruff check server/modules/agents/coordinator server/modules/evaluations/orchestrator.py server/tests/agents/coordinator server/tests/evaluations`
Expected: no errors (fix any import-order/unused-import findings, e.g. a
leftover `merge_with_sme` import or now-unused `AgentEvaluationResult`
import in `orchestrator.py` if nothing else in the file still uses it —
check before removing).

- [ ] **Step 8: Commit**

```bash
git add -A server/modules/agents/coordinator server/modules/evaluations/orchestrator.py server/tests/agents/coordinator server/tests/evaluations
git commit -m "refactor(coordinator): retire extraction/curriculum/reconciliation and the orchestrator merge step"
```

---

## Task 7: Full verification pass

**Files:** none (verification only).

- [ ] **Step 1: Run the complete server test suite**

Run: `uv run --project server pytest server -q`
Expected: no new failures introduced by this plan's changes. Compare
against the pre-existing baseline: before this plan, only
`server/tests/agents/coordinator/` had failures (36 failed / 24 passed,
all now deleted or fixed by Tasks 1-6) — the rest of the suite should be
unaffected, since Phase A does not touch `sme/*`, `itso/*`, `gad/*`,
`synthesis/*`, or `feedback/*`.

- [ ] **Step 2: Run ruff across the whole server package**

Run: `uv run --project server ruff check server`
Expected: no errors.

- [ ] **Step 3: Confirm no accidental Phase B scope crept in**

Run:
```bash
git diff main --stat
```
Expected: only files under `server/modules/agents/coordinator/`,
`server/modules/evaluations/orchestrator.py`,
`server/tests/agents/coordinator/`, `server/tests/evaluations/`, and this
plan/spec's own docs — nothing under `server/modules/synthesis/service.py`,
`server/modules/feedback/`, `client/`, or `server/db/alembic/versions/`.

- [ ] **Step 4: Commit any final cleanup, if needed**

If Steps 1-3 required fixes, commit them:

```bash
git add -A
git commit -m "fix(coordinator): address full-suite verification findings"
```

If no fixes were needed, skip this step — nothing to commit.
