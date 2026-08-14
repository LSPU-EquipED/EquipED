# SME Scoring Redesign & DPO Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SME's deterministic `compute()`/`bands.py` engine with direct LLM scoring in 3 grouped calls (down from today's 6 extraction baskets), and extend the ITSO-pattern reviewer-correction/DPO loop (`PreferenceLog`, review modal, per-criterion feedback endpoint, JSONL export) to SME's 10 criteria.

**Architecture:** Three new grouped-scoring modules (`groups.py`, `grouped_prompt.py`, `grouped_response.py`, `grouped_execution.py`) live alongside SME's existing engine code and mirror ITSO's proven prompt→execute→parse shape. A new `EngineScoredAgent._run_full_llm_scoring()` method is added *additively* to `sme/pipeline.py` — every method Coordinator calls (`_resolve_full_text`, `_rubric_titles`, `_score_via_engine`, `_run_full_engine_scoring`) is untouched, so Coordinator's behavior cannot regress. `SME.run()` switches to the new method; `registry.run_criterion` (the existing per-criterion extraction fallback) is kept as-is and reused when a grouped call fails outright. DPO capture reuses `PreferenceLog`/`CriterionFeedbackCreate` as-is (widened to accept `agent_name="sme"`), and the review-modal/export patterns already built for ITSO are generalized rather than duplicated.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (server/Python 3.12), React + TanStack Query (client), pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-13-sme-dpo-scoring-design.md`

## Global Constraints

- Coordinator is not touched: no shared method on `EngineScoredAgent` used by `Coordinator` (`_resolve_full_text`, `_rubric_titles`, `_score_via_engine`, `_run_full_engine_scoring`) may change signature or behavior.
- GAD is untouched.
- No change to `synthesis/matrix.py`'s `AGENT_WEIGHTS` or the synthesized-score formula.
- No training trigger, job queue, or serving-stack code — training and adapter loading stay manual/out-of-repo, mirroring ITSO.
- Every new Alembic migration's `down_revision` must chain from the current single head (`20260811_0004` as of this plan — confirm with the "get chain heads" command in Task 7 before writing the migration, in case other work has landed since).
- `bands.py`'s `ratio_band`/`count_band`/`mean_band` and the per-criterion `compute()` functions (`objective_alignment.py`, `varied_assessment.py`, etc.) are **not deleted** — they remain the per-criterion fallback path's scoring logic via `registry.run_criterion`/`run_grouped`, unchanged.

---

## File Structure

```
server/modules/agents/sme/
  groups.py                # NEW: group->codes map, code->group map, per-group text slicer
  grouped_prompt.py         # NEW: build_group_prompt() — JSON prompt per group
  grouped_response.py       # NEW: schema + parse_group_response() + group_criterion_scores()
  grouped_execution.py      # NEW: execute_group() — LLM call + repair-once + parse
  pipeline.py                # MODIFY: add _run_full_llm_scoring() to EngineScoredAgent (additive)
  agent.py                   # MODIFY: SME.run() calls _run_full_llm_scoring()
server/modules/synthesis/
  models.py                  # MODIFY: AgentResult gets group_prompts JSON column
  service.py                  # MODIFY: persist group_prompts; generalize reviewer_correction to sme
server/modules/feedback/
  schemas.py                  # MODIFY: CriterionFeedbackCreate.agent_name widened to itso|sme
server/alembic/versions/
  20260814_0001_add_agent_result_group_prompts.py   # NEW migration
server/scripts/
  export_sme_dpo_pairs.py    # NEW: per-group DPO export for SME
client/src/features/evaluation/
  components/AgentReviewModal.tsx   # RENAMED from ItsoReviewModal.tsx, parameterized by agentName
  components/Scorecard.tsx           # MODIFY: Review Scores button/modal for both itso and sme
  types.ts                            # MODIFY: CriterionFeedbackRequest.agent_name widened
server/tests/agents/sme/
  test_groups.py
  test_grouped_response.py
  test_grouped_prompt.py
  test_grouped_execution.py
  test_sme_llm_scoring.py            # _run_full_llm_scoring() + SME.run() wiring
server/tests/synthesis/
  test_service.py                     # MODIFY: extend with group_prompts + sme reviewer_correction
server/tests/scripts/
  test_export_sme_dpo_pairs.py
```

---

## Task 1: Group definitions and text slicing

**Files:**
- Create: `server/modules/agents/sme/groups.py`
- Test: `server/tests/agents/sme/test_groups.py`

**Interfaces:**
- Produces: `GROUP_CODES: dict[str, tuple[str, ...]]` (group name -> criterion codes, fixed order), `CODE_TO_GROUP: dict[str, str]` (reverse map), `slice_for_group(group: str, text: str) -> str`, `GROUP_NAMES: tuple[str, ...]` (`("assessment_alignment", "task_execution", "document_wide")`).

The three groups are chosen by **existing, already-validated text-slicing scope**, not a fresh guess: `assessment_alignment` reuses the exact head+Performance-Tasks-body slice basket A1 already uses (`extraction.slice_for_basket_a1`); `task_execution` reuses the bottom-section-only slice baskets A2, A3, and A4 already use identically (`extraction.slice_for_basket_a2` — A3's own `slice_for_basket_a3` calls the same underlying `_slice_bottom_section(body=9000)` helper, so reusing A2's public function for A-03 too changes no behavior); `document_wide` reuses the whole-document downsample baskets B1 and B2 already use identically (`extraction.slice_for_basket_b1`). All 10 registered codes are covered across the three groups (2 + 5 + 3 = 10). No new slicing logic is invented — this task only regroups criteria that already share a validated slice function.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/agents/sme/test_groups.py
from __future__ import annotations

from server.modules.agents.sme import groups
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
    assert groups.GROUP_CODES["task_execution"] == ("A-01", "A-03", "OP-02", "OP-03", "OP-05")


def test_document_wide_group_codes():
    assert groups.GROUP_CODES["document_wide"] == ("OP-01", "OP-04", "A-04")


def test_slice_for_group_delegates_to_validated_basket_slicers():
    text = "x" * 20000
    from server.modules.agents.sme import extraction

    assert groups.slice_for_group("assessment_alignment", text) == (
        extraction.slice_for_basket_a1(text)
    )
    assert groups.slice_for_group("task_execution", text) == (
        extraction.slice_for_basket_a2(text)
    )
    assert groups.slice_for_group("document_wide", text) == (
        extraction.slice_for_basket_b1(text)
    )


def test_slice_for_group_rejects_unknown_group():
    import pytest

    with pytest.raises(KeyError):
        groups.slice_for_group("not-a-group", "text")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/agents/sme/test_groups.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.agents.sme.groups'`

- [ ] **Step 3: Write minimal implementation**

```python
# server/modules/agents/sme/groups.py
"""Grouping for SME's LLM-direct-scoring calls.

Each group's text slice reuses an EXISTING, already-validated basket slicer
from ``extraction.py`` -- these groups only re-package criteria that already
share an identical slicing scope, so no new slicing behavior is introduced.
See ``docs/superpowers/specs/2026-08-13-sme-dpo-scoring-design.md``.
"""

from __future__ import annotations

from . import extraction

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

_SLICERS = {
    "assessment_alignment": extraction.slice_for_basket_a1,
    "task_execution": extraction.slice_for_basket_a2,
    "document_wide": extraction.slice_for_basket_b1,
}


def slice_for_group(group: str, text: str) -> str:
    return _SLICERS[group](text)


__all__ = ["GROUP_CODES", "GROUP_NAMES", "CODE_TO_GROUP", "slice_for_group"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/agents/sme/test_groups.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/agents/sme/groups.py server/tests/agents/sme/test_groups.py
git commit -m "feat(sme): add LLM-scoring group definitions"
```

---

## Task 2: Grouped response schema and parsing

**Files:**
- Create: `server/modules/agents/sme/grouped_response.py`
- Test: `server/tests/agents/sme/test_grouped_response.py`

**Interfaces:**
- Consumes: `groups.GROUP_CODES` (Task 1).
- Produces: `build_group_response_schema(codes: tuple[str, ...], titles: dict[str, str]) -> dict[str, Any]`, `parse_group_response(raw: str, codes: tuple[str, ...], titles: dict[str, str]) -> dict[str, Any]`, `group_criterion_scores(parsed: dict, codes: tuple[str, ...], titles: dict[str, str]) -> tuple[CriterionScore, ...]`. Response shape per criterion: `{criterion_id, criterion_title, score, justification, evidence}` — no `chunk_ids` (SME scores from the full canonical SLM text, not retrieved chunks, so there is no chunk-citation concept here).

This mirrors `itso/response.py` exactly, minus chunk handling.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/agents/sme/test_grouped_response.py
from __future__ import annotations

import json

import pytest
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.sme.grouped_response import (
    build_group_response_schema,
    group_criterion_scores,
    parse_group_response,
)

CODES = ("A-02", "A-05")
TITLES = {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"}


def _payload(score=3, **overrides):
    entries = []
    for code in CODES:
        entries.append(
            {
                "criterion_id": code,
                "criterion_title": TITLES[code],
                "score": score,
                "justification": "justification text",
                "evidence": ["evidence quote"],
                **overrides,
            }
        )
    return json.dumps({"summary": "ok", "criterion_scores": entries})


def test_build_schema_has_one_entry_per_code():
    schema = build_group_response_schema(CODES, TITLES)
    prefix_items = schema["properties"]["criterion_scores"]["prefixItems"]
    assert [item["properties"]["criterion_id"]["const"] for item in prefix_items] == list(
        CODES
    )
    for item in prefix_items:
        assert "chunk_ids" not in item["properties"]


def test_parse_accepts_valid_payload():
    parsed = parse_group_response(_payload(), CODES, TITLES)
    assert parsed["summary"] == "ok"


def test_parse_rejects_non_json():
    with pytest.raises(AgentExecutionError):
        parse_group_response("not json", CODES, TITLES)


def test_group_criterion_scores_returns_one_per_code_in_order():
    parsed = parse_group_response(_payload(score=4), CODES, TITLES)
    scores = group_criterion_scores(parsed, CODES, TITLES)
    assert [s.criterion_id for s in scores] == list(CODES)
    assert all(s.score == 4 for s in scores)
    assert scores[0].chunk_ids == ()


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


def test_group_criterion_scores_rejects_out_of_range_score():
    parsed = parse_group_response(_payload(score=4), CODES, TITLES)
    parsed["criterion_scores"][0]["score"] = 5
    with pytest.raises(AgentExecutionError):
        group_criterion_scores(parsed, CODES, TITLES)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/agents/sme/test_grouped_response.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# server/modules/agents/sme/grouped_response.py
"""Response schema and parsing for SME's grouped LLM-scoring calls.

Mirrors ``itso/response.py`` exactly, minus chunk-citation handling -- SME
scores from the full canonical SLM text (see
``EngineScoredAgent._resolve_full_text``), not retrieved chunks, so there is
no known-chunk-id set to validate citations against.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError

SME_TEXT_MAX = 2000


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
                    "maxLength": SME_TEXT_MAX,
                },
                "evidence": {
                    "type": "array",
                    "maxItems": 8,
                    "items": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": SME_TEXT_MAX,
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
    raw: str, codes: tuple[str, ...], titles: dict[str, str]
) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise _failure("SMEGroupResponseTypeError", type(raw).__name__)
    payload = raw.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", payload, flags=re.I | re.S)
    if match:
        payload = match.group(1).strip()
    elif not payload.startswith("{"):
        raise _failure("SMEGroupInvalidJSON", raw)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise _failure("SMEGroupInvalidJSON", raw) from exc
    if (
        not isinstance(parsed, dict)
        or set(parsed) != {"summary", "criterion_scores"}
        or not isinstance(parsed.get("summary"), str)
        or not 1 <= len(parsed["summary"]) <= 2000
    ):
        raise _failure("SMEGroupInvalidResponse", type(parsed).__name__)
    group_criterion_scores(parsed, codes, titles)
    return parsed


def group_criterion_scores(
    parsed: dict[str, Any], codes: tuple[str, ...], titles: dict[str, str]
) -> tuple[CriterionScore, ...]:
    entries = parsed.get("criterion_scores")
    if not isinstance(entries, list) or len(entries) != len(codes):
        raise _failure("SMEGroupInvalidCriterionScores", "shape")
    seen: set[str] = set()
    result: list[CriterionScore] = []
    for index, (item, expected_code) in enumerate(zip(entries, codes, strict=True)):
        if (
            not isinstance(item, dict)
            or item.get("criterion_id") != expected_code
            or expected_code in seen
            or set(item) != {"criterion_id", "criterion_title", "score", "justification", "evidence"}
        ):
            raise _failure("SMEGroupInvalidCriterion", index)
        if item.get("criterion_title") != titles.get(expected_code):
            raise _failure("SMEGroupInvalidCriterionTitle", index)
        seen.add(expected_code)
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 4:
            raise _failure("SMEGroupInvalidScore", index)
        justification = item.get("justification")
        if (
            not isinstance(justification, str)
            or not justification
            or len(justification) > SME_TEXT_MAX
        ):
            raise _failure("SMEGroupInvalidJustification", index)
        evidence = item.get("evidence")
        if (
            not isinstance(evidence, list)
            or len(evidence) > 8
            or any(
                not isinstance(e, str) or not e or len(e) > SME_TEXT_MAX
                for e in evidence
            )
        ):
            raise _failure("SMEGroupInvalidEvidence", index)
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

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/agents/sme/test_grouped_response.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/agents/sme/grouped_response.py server/tests/agents/sme/test_grouped_response.py
git commit -m "feat(sme): add grouped LLM-scoring response schema and parser"
```

---

## Task 3: Grouped prompt construction

**Files:**
- Create: `server/modules/agents/sme/grouped_prompt.py`
- Test: `server/tests/agents/sme/test_grouped_prompt.py`

**Interfaces:**
- Consumes: `groups.slice_for_group` (Task 1).
- Produces: `build_group_prompt(group: str, codes: tuple[str, ...], titles: dict[str, str], full_text: str, *, prompt_preamble: str | None = None) -> str`.

Folds each criterion's retired `compute()`/`bands.py` threshold rule into fixed instruction text per code (`_SCORING_RULES`), so the LLM anchors on the same numeric bands the deterministic functions used — copied verbatim from `registry._render()`'s justification templates, which is the single source of truth for what each threshold actually is today.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/agents/sme/test_grouped_prompt.py
from __future__ import annotations

import json

from server.modules.agents.sme.grouped_prompt import build_group_prompt

CODES = ("A-02", "A-05")
TITLES = {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"}


def test_build_group_prompt_is_valid_json_with_expected_keys():
    prompt = build_group_prompt("assessment_alignment", CODES, TITLES, "some SLM text")
    payload = json.loads(prompt)
    assert payload["agent"] == "sme"
    assert payload["group"] == "assessment_alignment"
    assert set(payload["criteria"]) == {"A-02", "A-05"}
    assert "document_text" in payload


def test_build_group_prompt_includes_scoring_rule_per_code():
    prompt = build_group_prompt("assessment_alignment", CODES, TITLES, "text")
    payload = json.loads(prompt)
    assert "5+" in payload["criteria"]["A-02"]["scoring_rule"]
    assert "moderate scale" in payload["criteria"]["A-05"]["scoring_rule"].lower() or (
        "80" in payload["criteria"]["A-05"]["scoring_rule"]
    )


def test_build_group_prompt_prepends_preamble():
    without = build_group_prompt("assessment_alignment", CODES, TITLES, "text")
    with_preamble = build_group_prompt(
        "assessment_alignment", CODES, TITLES, "text", prompt_preamble="SYSTEM RULES"
    )
    assert with_preamble.startswith("SYSTEM RULES")
    assert without != with_preamble


def test_build_group_prompt_slices_long_text():
    long_text = "x" * 50000
    prompt = build_group_prompt("task_execution", ("A-01",), {"A-01": "Learner Transformation"}, long_text)
    payload = json.loads(prompt)
    assert len(payload["document_text"]) < len(long_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/agents/sme/test_grouped_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# server/modules/agents/sme/grouped_prompt.py
"""Prompt construction for SME's grouped LLM-scoring calls.

Each criterion's scoring rule text is copied verbatim from
``registry._render()``'s justification templates -- the single source of
truth for the threshold each retired ``compute()`` function used -- so the
LLM is anchored to the same numeric bands, not asked to invent its own scale.
"""

from __future__ import annotations

import json
from typing import Any

from .groups import slice_for_group

_DESCRIPTIONS: dict[str, str] = {
    "A-01": "Students are engaged in transforming what they learn.",
    "A-02": "Teachers can easily assess students' progress by using varied assessment tools.",
    "A-03": "The material keeps an on-going record of students' progress and allows the teacher to monitor student performance.",
    "A-04": "Positive, meaningful feedback, and prescriptive guides for interventions are provided.",
    "A-05": "Objectives are gauged effectively.",
    "OP-01": "Topics are coherent from Unit to Chapter.",
    "OP-02": "Material is interactive in each lesson which makes life-long learning easier.",
    "OP-03": "Directions are clear and complete enough for students to perform required tasks.",
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
        "Score the percentage of stated objectives that are measured by a "
        "real assessment on the moderate scale: 4 if >=80%, 3 if >=50%, "
        "2 if >=20%, else 1. No objectives found -> 1."
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
        "Score the percentage of topic-to-topic transitions that are "
        "coherent (each topic logically follows the last) on the moderate "
        "scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
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
        "Return exactly one criterion for each criterion, in this exact order "
        "and with these exact titles: "
        + "; ".join(f"{code} = {titles[code]}" for code in codes),
        "Each criterion score must be between 1 and 4.",
        "Follow each criterion's scoring_rule exactly -- state the count or "
        "percentage you found in the justification so the score is auditable.",
        "Ground all claims in the provided document_text.",
    ]
    payload = {
        "agent": "sme",
        "group": group,
        "document_text": document_text,
        "criteria": criteria,
        "instructions": instructions,
    }
    body = json.dumps(payload, ensure_ascii=False)
    return (prompt_preamble.rstrip() + "\n\n" + body) if prompt_preamble else body


__all__ = ["build_group_prompt"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/agents/sme/test_grouped_prompt.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/agents/sme/grouped_prompt.py server/tests/agents/sme/test_grouped_prompt.py
git commit -m "feat(sme): add grouped LLM-scoring prompt builder"
```

---

## Task 4: Grouped call execution with repair-once

**Files:**
- Create: `server/modules/agents/sme/grouped_execution.py`
- Test: `server/tests/agents/sme/test_grouped_execution.py`

**Interfaces:**
- Consumes: `build_group_prompt` (Task 3), `parse_group_response`/`group_criterion_scores` (Task 2), `RunLLMClient` (`server/modules/agents/runtime/llm.py`, already exists).
- Produces: `execute_group(group: str, codes: tuple[str, ...], titles: dict[str, str], client: RunLLMClient, full_text: str, *, prompt_preamble: str | None = None) -> tuple[tuple[CriterionScore, ...], str]` — returns `(scores, prompt_text)`. Raises `AgentExecutionError` if both the initial call and the one repair attempt fail to parse.

Mirrors `itso/execution.py`'s repair-once-on-parse-failure shape.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/agents/sme/test_grouped_execution.py
from __future__ import annotations

import json

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.runtime.llm import RunLLMClient
from server.modules.agents.sme.grouped_execution import execute_group

CODES = ("A-02", "A-05")
TITLES = {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"}


class _LLM:
    model = "primary"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def generate_result(self, prompt, *, temperature, max_new_tokens, deadline, response_contract):
        self.prompts.append(prompt)
        return CompletionResult(next(self.responses), "primary", 10, 20, 30, "stop", attempts=1)


def _response(score=3):
    entries = [
        {
            "criterion_id": code,
            "criterion_title": TITLES[code],
            "score": score,
            "justification": "justification",
            "evidence": ["evidence"],
        }
        for code in CODES
    ]
    return json.dumps({"summary": "ok", "criterion_scores": entries})


def test_execute_group_returns_scores_and_prompt_text():
    client = RunLLMClient(_LLM([_response(4)]), "sme")
    scores, prompt_text = execute_group(
        "assessment_alignment", CODES, TITLES, client, "some SLM text"
    )
    assert [s.criterion_id for s in scores] == list(CODES)
    assert all(s.score == 4 for s in scores)
    assert '"group": "assessment_alignment"' in prompt_text


def test_execute_group_repairs_once_on_bad_json():
    llm = _LLM(["{broken", _response(3)])
    client = RunLLMClient(llm, "sme")
    scores, _ = execute_group("assessment_alignment", CODES, TITLES, client, "text")
    assert len(llm.prompts) == 2
    assert all(s.score == 3 for s in scores)


def test_execute_group_raises_after_repair_also_fails():
    llm = _LLM(["{broken", "{still broken"])
    client = RunLLMClient(llm, "sme")
    with pytest.raises(AgentExecutionError):
        execute_group("assessment_alignment", CODES, TITLES, client, "text")
    assert len(llm.prompts) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/agents/sme/test_grouped_execution.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# server/modules/agents/sme/grouped_execution.py
"""LLM transport for one SME grouped-scoring call, with repair-once on a
parse failure. Mirrors ``itso/execution.py``'s repair shape.
"""

from __future__ import annotations

import time

from server.core.config import get_settings
from server.core.llm import ResponseContract

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError
from ..runtime.llm import RunLLMClient
from .grouped_prompt import build_group_prompt
from .grouped_response import (
    build_group_response_schema,
    group_criterion_scores,
    parse_group_response,
)

_REPAIR_SUFFIX = (
    "\n\nVALIDATOR_FAILURE category=SME_GROUP_INVALID path=criterion_scores. "
    "Regenerate ONLY the complete JSON response; do not include commentary."
)


def execute_group(
    group: str,
    codes: tuple[str, ...],
    titles: dict[str, str],
    client: RunLLMClient,
    full_text: str,
    *,
    prompt_preamble: str | None = None,
) -> tuple[tuple[CriterionScore, ...], str]:
    settings = get_settings()
    prompt = build_group_prompt(
        group, codes, titles, full_text, prompt_preamble=prompt_preamble
    )
    if settings.llm_response_mode == "json_schema":
        contract = ResponseContract.json_schema(
            build_group_response_schema(codes, titles),
            name=f"sme_group_{group}",
        )
    else:
        contract = ResponseContract.json_object()
    temperature = settings.get_agent_temperature("sme")
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
        parsed = parse_group_response(completion.content, codes, titles)
    except AgentExecutionError:
        repaired = client.generate_result(
            prompt + _REPAIR_SUFFIX,
            temperature=temperature,
            max_new_tokens=settings.llm_max_new_tokens,
            deadline=deadline,
            response_contract=contract,
        )
        parsed = parse_group_response(repaired.content, codes, titles)
    scores = group_criterion_scores(parsed, codes, titles)
    return scores, prompt


__all__ = ["execute_group"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/agents/sme/test_grouped_execution.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/agents/sme/grouped_execution.py server/tests/agents/sme/test_grouped_execution.py
git commit -m "feat(sme): add grouped LLM-scoring call execution with repair-once"
```

---

## Task 5: `_run_full_llm_scoring()` on `EngineScoredAgent`

**Files:**
- Modify: `server/modules/agents/sme/pipeline.py`
- Test: `server/tests/agents/sme/test_sme_llm_scoring.py`

**Interfaces:**
- Consumes: `groups.GROUP_CODES`/`GROUP_NAMES` (Task 1), `grouped_execution.execute_group` (Task 4), `registry.run_criterion` (existing, unchanged — the per-criterion fallback).
- Produces: `EngineScoredAgent._run_full_llm_scoring(self, *, evaluation_id, document_id, chunk_infos, context_text, prompt_version_id, db, canonical_source_text=None, llm_client=None, prompt_preamble=None) -> AgentEvaluationResult`. `AgentEvaluationResult.metadata["group_prompts"]` is a `dict[str, str]` (group name -> that group's exact prompt), populated only for groups whose LLM call succeeded (a group that fell back to per-criterion scoring has no single prompt to snapshot for that group).

This method is **new**, added alongside `_run_full_engine_scoring`/`_score_via_engine` — neither existing method is modified, so `Coordinator` (which calls `_resolve_full_text`, `_rubric_titles`, and `_run_full_engine_scoring`/`_score_via_engine` via its own `run()`) is unaffected.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/agents/sme/test_sme_llm_scoring.py
from __future__ import annotations

import json
import uuid

from server.core.llm import CompletionResult
from server.modules.agents.sme.agent import SME


class _LLM:
    model = "primary"

    def __init__(self, group_payloads: dict[str, str]):
        self.group_payloads = group_payloads
        self.prompts: list[str] = []

    def generate_result(self, prompt, *, temperature, max_new_tokens, deadline, response_contract):
        self.prompts.append(prompt)
        payload = json.loads(prompt.split("\n\n", 1)[-1]) if "\n\n" in prompt else json.loads(prompt)
        group = payload["group"]
        return CompletionResult(
            self.group_payloads[group], "primary", 10, 20, 30, "stop", attempts=1
        )


def _all_group_payload(score: int) -> dict[str, str]:
    from server.modules.agents.sme import groups
    from server.modules.agents.sme.pipeline import EngineScoredAgent

    titles = EngineScoredAgent()._rubric_titles(None) if False else {}
    # Titles are resolved inside the agent from the rubric service; the fake
    # LLM only needs to answer with the codes it was asked about, so pull
    # the codes straight from groups.GROUP_CODES and use registry titles
    # directly (identical to what get_active_rubric_criteria returns for the
    # default seeded rubric).
    from server.modules.agents.sme.registry import REGISTERED_CODES  # noqa: F401

    result = {}
    for group_name, codes in groups.GROUP_CODES.items():
        entries = [
            {
                "criterion_id": code,
                "criterion_title": _TITLE_FIXTURE[code],
                "score": score,
                "justification": "justification",
                "evidence": ["evidence"],
            }
            for code in codes
        ]
        result[group_name] = json.dumps({"summary": "ok", "criterion_scores": entries})
    return result


_TITLE_FIXTURE = {
    "A-01": "Learner Transformation",
    "A-02": "Varied Assessment Tools",
    "A-03": "Progress Monitoring",
    "A-04": "Prescriptive Feedback",
    "A-05": "Objective Gauging",
    "OP-01": "Topic Coherence",
    "OP-02": "Interactivity",
    "OP-03": "Clear Directions",
    "OP-04": "Accurate Sections",
    "OP-05": "Enhancement Activities",
}


def test_sme_run_scores_all_ten_criteria_via_llm(monkeypatch):
    from server.modules.agents.sme import pipeline

    monkeypatch.setattr(
        pipeline.EngineScoredAgent, "_rubric_titles", lambda self, db: _TITLE_FIXTURE
    )
    sme = SME()
    llm = _LLM(_all_group_payload(3))
    result = sme.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=[{"chunk_id": "c1", "text": "x"}],
        canonical_source_text="clean SLM text " * 50,
        llm_client=llm,
    )
    assert result.success is True
    assert len(result.criterion_scores) == 10
    assert all(s.score == 3 for s in result.criterion_scores)
    assert set(result.metadata["group_prompts"]) == {
        "assessment_alignment",
        "task_execution",
        "document_wide",
    }


def test_sme_run_falls_back_to_per_criterion_when_one_group_fails(monkeypatch):
    from server.modules.agents.sme import pipeline

    monkeypatch.setattr(
        pipeline.EngineScoredAgent, "_rubric_titles", lambda self, db: _TITLE_FIXTURE
    )
    payloads = _all_group_payload(3)
    payloads["assessment_alignment"] = "{not valid json"

    class _FailOnceLLM(_LLM):
        def generate_result(self, prompt, **kwargs):
            self.prompts.append(prompt)
            payload = json.loads(prompt)
            group = payload["group"]
            if group == "assessment_alignment":
                return CompletionResult(
                    "{still not valid", "primary", 5, 5, 10, "stop", attempts=1
                )
            return CompletionResult(
                self.group_payloads[group], "primary", 10, 20, 30, "stop", attempts=1
            )

    sme = SME()
    llm = _FailOnceLLM(payloads)
    result = sme.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=[{"chunk_id": "c1", "text": "x"}],
        canonical_source_text="clean SLM text " * 50,
        llm_client=llm,
    )
    assert result.success is True
    assert len(result.criterion_scores) == 10
    # assessment_alignment's codes fell back to the per-criterion engine path,
    # so that group has no snapshot-able single prompt.
    assert "assessment_alignment" not in result.metadata["group_prompts"]
    assert "task_execution" in result.metadata["group_prompts"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/agents/sme/test_sme_llm_scoring.py -v`
Expected: FAIL — `SME.run()` still calls `_run_full_engine_scoring`, and `_run_full_llm_scoring` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add to `server/modules/agents/sme/pipeline.py` (after `_run_full_engine_scoring`, before `__all__`):

```python
    def _run_full_llm_scoring(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None,
        prompt_version_id: uuid.UUID | None,
        db: Any | None,
        canonical_source_text: str | None = None,
        llm_client: Any | None = None,
        prompt_preamble: str | None = None,
    ) -> AgentEvaluationResult:
        """Score every criterion via 3 grouped direct-LLM-scoring calls
        (``groups.GROUP_CODES``), falling back to the existing per-criterion
        engine path (``registry.run_criterion``) for any group whose call
        fails outright. Additive: does not modify ``_score_via_engine`` or
        ``_run_full_engine_scoring``, which Coordinator still uses unchanged.
        """
        from ..runtime.llm import error_reference
        from . import groups
        from .grouped_execution import execute_group

        full_text = self._resolve_full_text(
            document_id, context_text, chunk_infos, canonical_source_text
        )
        if not full_text.strip():
            raise AgentExecutionError("no document text available for evaluation")

        start = time.perf_counter()
        primary_client = llm_client or self._default_llm_client or get_llm_client()
        client = (
            primary_client
            if isinstance(primary_client, RunLLMClient)
            else RunLLMClient(
                primary_client,
                self.agent_name,
                requested_model=(
                    getattr(primary_client, "model", None) or get_llm_model_name()
                ),
                default_response_contract=ResponseContract.json_object(),
            )
        )
        titles = self._rubric_titles(db)

        all_scores: dict[str, CriterionScore] = {}
        group_prompts: dict[str, str] = {}
        fallback_calls = 0

        for group_name in groups.GROUP_NAMES:
            codes = groups.GROUP_CODES[group_name]
            group_titles = {code: titles.get(code, code) for code in codes}
            try:
                scores, prompt_text = execute_group(
                    group_name,
                    codes,
                    group_titles,
                    client,
                    full_text,
                    prompt_preamble=prompt_preamble,
                )
                for score in scores:
                    all_scores[score.criterion_id] = score
                group_prompts[group_name] = prompt_text
            except Exception as exc:
                logger.warning(
                    "[SME_LLM_SCORING] group=%s failed, falling back to "
                    "per-criterion engine path: category=%s | reference=%s",
                    group_name,
                    type(exc).__name__,
                    error_reference(exc),
                )
                for code in codes:
                    fallback_calls += 1
                    try:
                        band, justification, evidence = registry.run_criterion(
                            code, client, full_text, prompt_preamble=prompt_preamble
                        )
                    except Exception as fallback_exc:
                        raise AgentExecutionError(
                            f"{self.agent_name} criterion {code} failed in both "
                            "the grouped LLM-scoring path and the per-criterion "
                            f"engine fallback (category={type(fallback_exc).__name__}, "
                            f"reference={error_reference(fallback_exc)})"
                        ) from fallback_exc
                    all_scores[code] = CriterionScore(
                        criterion_id=code,
                        criterion_title=titles.get(code, code),
                        score=band,
                        justification=justification,
                        chunk_ids=(),
                        evidence=evidence,
                    )

        criterion_scores = tuple(
            all_scores[code] for code in sorted(all_scores)
        )
        subtotal = sum(s.score for s in criterion_scores) / len(criterion_scores)
        total_seconds = time.perf_counter() - start
        actual_model = (
            client.actual_model
            if client.actual_model != "unknown"
            else client.requested_model
        )

        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=criterion_scores,
            summary="",
            model_name=actual_model,
            processing_seconds=total_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=prompt_version_id,
            success=True,
            metadata={"group_prompts": group_prompts},
            provenance={
                "requested_model": client.requested_model,
                "actual_model": actual_model,
                "fallback_occurred": client.fallback_occurred,
                "criterion_fallback_calls": fallback_calls,
                "logical_calls": client.telemetry["call_count"],
            },
        )
```

Then update `server/modules/agents/sme/agent.py`'s `SME.run()` to call the new method instead of `_run_full_engine_scoring`:

```python
        result = self._run_full_llm_scoring(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=chunk_infos,
            context_text=context_text,
            prompt_version_id=consumed_prompt_id,
            db=db,
            llm_client=llm_client,
            canonical_source_text=kwargs.get("canonical_source_text"),
            prompt_preamble=prompt_text,
        )
```

(This replaces the existing `self._run_full_engine_scoring(...)` call — same keyword arguments, same call site, only the method name changes.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/agents/sme/test_sme_llm_scoring.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full SME test suite to confirm nothing else broke**

Run: `uv run --project server pytest server/tests/agents/sme server/tests/agents/coordinator -v`
Expected: Existing engine tests (`test_scoring_bands.py`, `test_scoring_criteria.py`, `test_scoring_skeleton.py`, `test_sme_hardening.py`, `test_sme_isolation.py`, `test_sme_oracle_contracts.py`, `test_sme_telemetry_contract.py`) still exercise `registry`/`bands.py`/`_score_via_engine` directly and must still pass unchanged — they test the retained engine/fallback machinery, not `SME.run()`'s call site. `test_sme_run.py` tests `SME.run()` directly and WILL need updating to expect the new LLM-scoring call shape instead of the engine call shape — update its fakes to match the `_LLM` pattern in `test_sme_llm_scoring.py` above rather than deleting coverage. All Coordinator tests must pass with zero changes, confirming the additive-only claim.

- [ ] **Step 6: Commit**

```bash
git add server/modules/agents/sme/pipeline.py server/modules/agents/sme/agent.py server/tests/agents/sme/test_sme_llm_scoring.py server/tests/agents/sme/test_sme_run.py
git commit -m "feat(sme): score all criteria via grouped LLM calls, retiring the engine as primary scorer"
```

---

## Task 6: Persist `group_prompts` on `AgentResult`

**Files:**
- Create: `server/alembic/versions/20260814_0001_add_agent_result_group_prompts.py`
- Modify: `server/modules/synthesis/models.py`
- Modify: `server/modules/synthesis/service.py`
- Test: `server/tests/synthesis/test_service.py`

**Interfaces:**
- Produces: `AgentResult.group_prompts: Mapped[dict | None]` (JSON column). `persist_agent_outputs` sets `group_prompts=agent_result.metadata.get("group_prompts")` on both `AgentResult(...)` construction sites (success and failure branches, `synthesis/service.py:82-121`).

- [ ] **Step 1: Confirm the current migration chain head before writing down_revision**

Run:
```bash
uv run --project server python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
cfg = Config('server/alembic.ini')
cfg.set_main_option('script_location', 'server/alembic')
print(ScriptDirectory.from_config(cfg).get_heads())
"
```
Expected: `['20260811_0004']` (as of this plan's writing). If it differs, use whatever single head this prints as `down_revision` below instead.

- [ ] **Step 2: Write the failing test**

```python
# server/tests/synthesis/test_service.py — add to existing file
def test_persist_agent_outputs_stores_group_prompts(db_session, evaluation_job, document):
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
    from server.modules.synthesis.models import AgentResult
    from server.modules.synthesis.service import persist_agent_outputs

    result = AgentEvaluationResult(
        agent_name="sme",
        evaluation_id=evaluation_job.evaluation_id,
        document_id=document.document_id,
        subtotal=3.0,
        criterion_scores=(
            CriterionScore(
                criterion_id="A-01",
                criterion_title="Learner Transformation",
                score=3,
                justification="j",
                evidence=(),
            ),
        ),
        summary="",
        model_name="test-model",
        processing_seconds=1.0,
        token_count=10,
        metadata={"group_prompts": {"task_execution": "prompt text"}},
    )
    persist_agent_outputs(
        db_session, evaluation_job.evaluation_id, document.document_id, [result]
    )
    row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=evaluation_job.evaluation_id, agent_name="sme")
        .one()
    )
    assert row.group_prompts == {"task_execution": "prompt text"}
```

(Adapt `db_session`/`evaluation_job`/`document` to whatever fixtures the existing tests in this file already use — check the top of `server/tests/synthesis/test_service.py` for the current fixture names before adding this test, since fixture naming in this file predates this plan.)

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/synthesis/test_service.py -k group_prompts -v`
Expected: FAIL — `AgentResult` has no `group_prompts` column yet.

- [ ] **Step 4: Write the migration**

```python
# server/alembic/versions/20260814_0001_add_agent_result_group_prompts.py
"""add group_prompts to agent_results

Revision ID: 20260814_0001
Revises: 20260811_0004
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260814_0001"
down_revision = "20260811_0004"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if _has_column("agent_results", "group_prompts"):
        return
    op.add_column("agent_results", sa.Column("group_prompts", sa.JSON(), nullable=True))


def downgrade() -> None:
    if not _has_column("agent_results", "group_prompts"):
        return
    op.drop_column("agent_results", "group_prompts")
```

- [ ] **Step 5: Add the column to the model**

In `server/modules/synthesis/models.py`, add to `AgentResult` right after `prompt_text`:

```python
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_prompts: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
```

- [ ] **Step 6: Persist it in `persist_agent_outputs`**

In `server/modules/synthesis/service.py`, add `group_prompts=agent_result.metadata.get("group_prompts")` to **both** `AgentResult(...)` constructions (the failure branch at line ~82 and the success branch at line ~104), immediately after the `prompt_text=agent_result.prompt_text,` line in each.

- [ ] **Step 7: Run the migration and re-run the test**

Run: `uv run --project server alembic -c server/alembic.ini upgrade head`
Run: `uv run --project server pytest server/tests/synthesis/test_service.py -k group_prompts -v`
Expected: PASS

- [ ] **Step 8: Run the migration guard test to confirm the chain is still single-headed**

Run: `uv run --project server pytest server/tests/migrations/test_curriculum_map_migration.py -v`
Expected: FAIL on `CHAIN_HEAD_REV` — update `server/tests/migrations/test_curriculum_map_migration.py`'s `CHAIN_HEAD_REV` constant (and its preceding comment) to `"20260814_0001"`, then re-run. Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add server/alembic/versions/20260814_0001_add_agent_result_group_prompts.py server/modules/synthesis/models.py server/modules/synthesis/service.py server/tests/synthesis/test_service.py server/tests/migrations/test_curriculum_map_migration.py
git commit -m "feat(synthesis): persist SME's per-group prompt snapshots on AgentResult"
```

---

## Task 7: Widen feedback to accept SME, generalize reviewer-correction surfacing

**Files:**
- Modify: `server/modules/feedback/schemas.py`
- Modify: `server/modules/synthesis/service.py`
- Test: `server/tests/feedback/test_router.py` (existing file — extend)
- Test: `server/tests/synthesis/test_service.py` (existing file — extend)

**Interfaces:**
- Produces: `CriterionFeedbackCreate.agent_name: Literal["itso", "sme"]`. `get_evaluation_results()` surfaces `reviewer_correction` for `agent_name in ("itso", "sme")`, not just `"itso"`.

- [ ] **Step 1: Write the failing test (schema)**

```python
# server/tests/feedback/test_router.py — add to existing file
def test_criterion_feedback_accepts_sme_agent_name(client, auth_headers, evaluation_with_sme_result):
    response = client.post(
        f"/feedback/{evaluation_with_sme_result.evaluation_id}/criteria/A-01",
        json={"agent_name": "sme", "action": "ACCEPT"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["agent_name"] == "sme"
```

(Adapt `client`/`auth_headers`/`evaluation_with_sme_result` to the existing fixtures already used elsewhere in `server/tests/feedback/test_router.py` and `server/tests/feedback/conftest.py` — check that file's existing tests, e.g. the equivalent ITSO ACCEPT test, for the exact fixture names before writing this.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/feedback/test_router.py -k sme_agent_name -v`
Expected: FAIL with 422 (Pydantic rejects `agent_name="sme"` against `Literal["itso"]`).

- [ ] **Step 3: Widen the schema**

In `server/modules/feedback/schemas.py`:

```python
class CriterionFeedbackCreate(BaseModel):
    """Request body for POST /feedback/{evaluation_id}/criteria/{criterion_id}.

    ``agent_name`` is restricted to agents whose score+justification come
    from a single LLM generation and can therefore produce a coherent DPO
    pair: "itso" (one call scores all 5 criteria) and "sme" (3 grouped calls
    score all 10 criteria — see
    docs/superpowers/specs/2026-08-13-sme-dpo-scoring-design.md). Coordinator
    and GAD are not included: Coordinator's non-A-05 scores are copied from
    SME (corrections against those belong to "sme"), and GAD's score is
    still code-computed from extracted facts.
    """

    agent_name: Literal["itso", "sme"]
```

(Update the docstring; the `Literal` change is the only field-level edit.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/feedback/test_router.py -k sme_agent_name -v`
Expected: PASS

- [ ] **Step 5: Write the failing test (reviewer_correction surfacing)**

```python
# server/tests/synthesis/test_service.py — add to existing file
def test_get_evaluation_results_surfaces_sme_reviewer_correction(
    db_session, evaluation_job, document, sme_agent_result_with_criterion_scores
):
    from server.modules.feedback.models import PreferenceLog
    from server.modules.synthesis.service import get_evaluation_results

    log = PreferenceLog(
        evaluation_id=evaluation_job.evaluation_id,
        user_id=evaluation_job.submitted_by,
        agent_name="sme",
        criterion_id="A-01",
        action="EDIT",
        edited_json={"score": 4, "justification": "corrected"},
    )
    db_session.add(log)
    db_session.commit()

    response = get_evaluation_results(
        evaluation_job.evaluation_id, evaluation_job.submitted_by, db_session
    )
    sme_criteria = {c["criterion_id"]: c for c in response.domain_scores["sme"]["criteria"]}
    assert sme_criteria["A-01"]["reviewer_correction"] == {
        "action": "EDIT",
        "score": 4,
        "justification": "corrected",
    }
```

(Adapt fixture names to whatever this file already establishes for an SME `AgentResult` + `CriterionScore` row — mirror the existing ITSO equivalent test in this file.)

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/synthesis/test_service.py -k sme_reviewer_correction -v`
Expected: FAIL — `reviewer_correction` is `None` because `get_evaluation_results` only looks up `agent_name == "itso"`.

- [ ] **Step 7: Generalize the surfacing logic**

In `server/modules/synthesis/service.py`, rename the ITSO-specific lookup to cover both agents:

```python
    # Latest reviewer correction per (agent, criterion) for every agent whose
    # score comes from a single/grouped LLM generation and can therefore
    # produce a coherent DPO pair (itso, sme). ACCEPT is excluded -- it
    # carries no score/justification and nothing in the UI sends it anymore.
    reviewable_agents = ("itso", "sme")
    corrections: dict[tuple[str, str], PreferenceLog] = {}
    for log in (
        db.query(PreferenceLog)
        .filter(
            PreferenceLog.evaluation_id == evaluation_id,
            PreferenceLog.agent_name.in_(reviewable_agents),
            PreferenceLog.action.in_(["EDIT", "REJECT"]),
        )
        .order_by(PreferenceLog.created_at.desc())
        .all()
    ):
        corrections.setdefault((log.agent_name, log.criterion_id), log)
```

Then in the `domain_scores` dict comprehension, replace:

```python
                    "reviewer_correction": (
                        _reviewer_correction_payload(
                            itso_corrections.get(score.criterion_id)
                        )
                        if result.agent_name == "itso"
                        else None
                    ),
```

with:

```python
                    "reviewer_correction": (
                        _reviewer_correction_payload(
                            corrections.get((result.agent_name, score.criterion_id))
                        )
                        if result.agent_name in reviewable_agents
                        else None
                    ),
```

- [ ] **Step 8: Run test to verify it passes, and confirm the ITSO test still passes**

Run: `uv run --project server pytest server/tests/synthesis/test_service.py -v`
Expected: All PASS, including the pre-existing ITSO reviewer-correction test (confirms the rename didn't regress ITSO's behavior).

- [ ] **Step 9: Commit**

```bash
git add server/modules/feedback/schemas.py server/modules/synthesis/service.py server/tests/feedback/test_router.py server/tests/synthesis/test_service.py
git commit -m "feat(feedback): accept SME criterion feedback, surface SME reviewer corrections"
```

---

## Task 8: SME DPO export script

**Files:**
- Create: `server/scripts/export_sme_dpo_pairs.py`
- Test: `server/tests/scripts/test_export_sme_dpo_pairs.py`

**Interfaces:**
- Consumes: `groups.CODE_TO_GROUP`, `groups.GROUP_CODES` (Task 1), `AgentResult.group_prompts` (Task 6).
- Produces: `export_sme_dpo_pairs(db) -> Iterator[SmeDpoPair]` where `SmeDpoPair` has `group: str, prompt: str, chosen: str, rejected: str, evaluation_id, document_id, reviewer_ids: frozenset`. One pair per `(evaluation_id, group)` with at least one real correction in that group — never a synthetic all-10-criteria pair, per the design doc.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/scripts/test_export_sme_dpo_pairs.py
from __future__ import annotations

from server.scripts.export_sme_dpo_pairs import export_sme_dpo_pairs


def test_export_yields_one_pair_per_group_with_a_real_correction(
    db_session, sme_evaluation_with_group_prompts_and_edit
):
    pairs = list(export_sme_dpo_pairs(db_session))
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.group == "task_execution"
    assert pair.prompt == "task_execution prompt text"
    import json

    chosen = json.loads(pair.chosen)["criterion_scores"]
    rejected = json.loads(pair.rejected)["criterion_scores"]
    assert set(chosen) == {"A-01", "OP-02", "OP-03", "OP-05"}
    assert chosen["A-01"]["score"] == 4  # corrected
    assert rejected["A-01"]["score"] == 3  # AI original


def test_export_skips_groups_with_no_group_prompts_snapshot(
    db_session, sme_evaluation_missing_group_prompts_with_edit
):
    pairs = list(export_sme_dpo_pairs(db_session))
    assert pairs == []


def test_export_skips_evaluations_with_no_real_change(
    db_session, sme_evaluation_with_degenerate_edit
):
    pairs = list(export_sme_dpo_pairs(db_session))
    assert pairs == []
```

(These fixtures build an `EvaluationJob`, an `AgentResult(agent_name="sme", group_prompts={...})`, matching `CriterionScore` rows for all 10 codes, and a `PreferenceLog(agent_name="sme", action="EDIT", ...)` row — mirror the fixture-building style already used in `server/tests/scripts/test_export_dpo_pairs.py` and `server/tests/scripts/conftest.py` for the ITSO equivalent, adapting agent_name/criterion set.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/scripts/test_export_sme_dpo_pairs.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# server/scripts/export_sme_dpo_pairs.py
"""Export DPO training pairs from SME reviewer EDIT feedback.

SME scores via 3 grouped LLM calls (see
``server/modules/agents/sme/groups.py``), so -- unlike ITSO's single-call
export -- pairs are keyed per (evaluation, group), not per evaluation. A
group with no corrected criteria yields no row: no real SME call ever spans
all 10 criteria at once, so a synthetic "all criteria in one prompt" pair
would train on a shape the model never sees at inference time.

See docs/superpowers/specs/2026-08-13-sme-dpo-scoring-design.md and
server/scripts/export_dpo_pairs.py (the ITSO equivalent this mirrors).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from server.modules.agents.sme.groups import CODE_TO_GROUP, GROUP_CODES
from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentResult, CriterionScore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmeDpoPair:
    group: str
    prompt: str
    chosen: str
    rejected: str
    evaluation_id: Any
    document_id: Any
    reviewer_ids: frozenset[Any]


def _is_real_change(
    edited_json: dict[str, Any] | None, original_score: CriterionScore
) -> bool:
    if not edited_json:
        return False
    edited_score = edited_json.get("score")
    edited_justification = str(edited_json.get("justification") or "").strip()
    original_justification = (original_score.justification or "").strip()
    return not (
        edited_score == original_score.score
        and edited_justification == original_justification
    )


def export_sme_dpo_pairs(db: Any) -> Iterator[SmeDpoPair]:
    """Yield one SmeDpoPair per (evaluation, group) with >=1 real correction."""

    edit_rows = (
        db.query(PreferenceLog)
        .filter(PreferenceLog.agent_name == "sme", PreferenceLog.action == "EDIT")
        .order_by(PreferenceLog.created_at.desc())
        .all()
    )

    latest_edit: dict[tuple[Any, str], PreferenceLog] = {}
    for log in edit_rows:
        grain = (log.evaluation_id, log.criterion_id)
        latest_edit.setdefault(grain, log)

    edits_by_evaluation: dict[Any, dict[str, PreferenceLog]] = defaultdict(dict)
    for (evaluation_id, criterion_id), log in latest_edit.items():
        edits_by_evaluation[evaluation_id][criterion_id] = log

    for evaluation_id, criterion_edits in edits_by_evaluation.items():
        agent_result = (
            db.query(AgentResult)
            .filter(
                AgentResult.evaluation_id == evaluation_id,
                AgentResult.agent_name == "sme",
            )
            .first()
        )
        if agent_result is None or not agent_result.group_prompts:
            logger.warning(
                "Skipping evaluation %s: no group_prompts snapshot (agent_result "
                "missing or predates group-prompt snapshotting).",
                evaluation_id,
            )
            continue

        original_scores = {
            score.criterion_id: score
            for score in (
                db.query(CriterionScore)
                .filter(CriterionScore.agent_result_id == agent_result.agent_result_id)
                .all()
            )
        }
        if not original_scores:
            logger.warning(
                "Skipping evaluation %s: no CriterionScore rows for its SME "
                "agent_result.",
                evaluation_id,
            )
            continue

        edits_by_group: dict[str, dict[str, PreferenceLog]] = defaultdict(dict)
        for criterion_id, log in criterion_edits.items():
            group = CODE_TO_GROUP.get(criterion_id)
            if group is None:
                logger.warning(
                    "Preference log %s: criterion_id %s is not a registered "
                    "SME code; ignored.",
                    log.log_id,
                    criterion_id,
                )
                continue
            edits_by_group[group][criterion_id] = log

        for group, group_edits in edits_by_group.items():
            group_prompt = agent_result.group_prompts.get(group)
            if not group_prompt:
                logger.warning(
                    "Skipping evaluation %s group %s: no prompt snapshot for "
                    "this group (it may have fallen back to per-criterion "
                    "scoring for this evaluation).",
                    evaluation_id,
                    group,
                )
                continue

            group_codes = GROUP_CODES[group]
            if any(code not in original_scores for code in group_codes):
                logger.warning(
                    "Skipping evaluation %s group %s: missing CriterionScore "
                    "row(s) for this group's codes.",
                    evaluation_id,
                    group,
                )
                continue

            chosen_map: dict[str, dict[str, Any]] = {}
            rejected_map: dict[str, dict[str, Any]] = {}
            reviewer_ids: set[Any] = set()

            for code in group_codes:
                score_row = original_scores[code]
                original_entry = {
                    "score": score_row.score,
                    "justification": score_row.justification,
                }
                rejected_map[code] = original_entry
                log = group_edits.get(code)
                if log is None or not _is_real_change(log.edited_json, score_row):
                    chosen_map[code] = original_entry
                    continue
                chosen_map[code] = {
                    "score": log.edited_json.get("score"),
                    "justification": log.edited_json.get("justification"),
                }
                reviewer_ids.add(log.user_id)

            if chosen_map == rejected_map:
                logger.warning(
                    "Skipping evaluation %s group %s: no criterion had a "
                    "real correction survive.",
                    evaluation_id,
                    group,
                )
                continue

            yield SmeDpoPair(
                group=group,
                prompt=group_prompt,
                chosen=json.dumps({"criterion_scores": chosen_map}, ensure_ascii=False),
                rejected=json.dumps(
                    {"criterion_scores": rejected_map}, ensure_ascii=False
                ),
                evaluation_id=evaluation_id,
                document_id=agent_result.document_id,
                reviewer_ids=frozenset(reviewer_ids),
            )


def main() -> None:
    import argparse

    from server.core.database import get_session_factory

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", help="Path to write the JSONL export to, e.g. sme_dpo_pairs.jsonl"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    session = get_session_factory()()
    try:
        count = 0
        evaluations: set[Any] = set()
        reviewers: set[Any] = set()
        with open(args.output, "w", encoding="utf-8") as f:
            for pair in export_sme_dpo_pairs(session):
                f.write(
                    json.dumps(
                        {
                            "prompt": pair.prompt,
                            "chosen": pair.chosen,
                            "rejected": pair.rejected,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                count += 1
                evaluations.add(pair.evaluation_id)
                reviewers.update(pair.reviewer_ids)
        logger.info(
            "Wrote %d SME DPO pairs across %d evaluations, %d reviewers to %s",
            count,
            len(evaluations),
            len(reviewers),
            args.output,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/scripts/test_export_sme_dpo_pairs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/scripts/export_sme_dpo_pairs.py server/tests/scripts/test_export_sme_dpo_pairs.py
git commit -m "feat(scripts): add per-group SME DPO pair export"
```

---

## Task 9: Widen frontend feedback types

**Files:**
- Modify: `client/src/features/evaluation/types.ts`
- Test: `client/src/features/evaluation/hooks/__tests__/useSubmitFeedback.test.tsx` (existing — extend)

**Interfaces:**
- Produces: `CriterionFeedbackRequest.agent_name: 'itso' | 'sme'`.

- [ ] **Step 1: Write the failing test**

```tsx
// client/src/features/evaluation/hooks/__tests__/useSubmitFeedback.test.tsx — add
it('accepts agent_name "sme" in the request body', () => {
  const body: import('../../types').CriterionFeedbackRequest = {
    agent_name: 'sme',
    action: 'ACCEPT',
  };
  expect(body.agent_name).toBe('sme');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd client && pnpm vitest run src/features/evaluation/hooks/__tests__/useSubmitFeedback.test.tsx`
Expected: FAIL — TypeScript compile error, `agent_name: 'sme'` not assignable to `'itso'`.

- [ ] **Step 3: Widen the type**

In `client/src/features/evaluation/types.ts`:

```typescript
export interface CriterionFeedbackRequest {
  agent_name: 'itso' | 'sme';
  action: CriterionFeedbackAction;
  score?: number;
  justification?: string;
  notes?: string;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd client && pnpm vitest run src/features/evaluation/hooks/__tests__/useSubmitFeedback.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/features/evaluation/types.ts client/src/features/evaluation/hooks/__tests__/useSubmitFeedback.test.tsx
git commit -m "feat(evaluation): widen CriterionFeedbackRequest to accept sme"
```

---

## Task 10: Generalize the review modal for SME, wire it into Scorecard

**Files:**
- Rename+Modify: `client/src/features/evaluation/components/ItsoReviewModal.tsx` -> `client/src/features/evaluation/components/AgentReviewModal.tsx`
- Modify: `client/src/features/evaluation/components/Scorecard.tsx`

**Interfaces:**
- Consumes: `CriterionFeedbackRequest.agent_name` (Task 9).
- Produces: `AgentReviewModal({ agentName, evaluationId, criteria, onClose })` — same component, one added prop (`agentName: 'itso' | 'sme'`) threaded into the `mutation.mutateAsync` body instead of the hardcoded `'itso' as const` literal.

This is a rename + parameterize, not a rewrite: every existing behavior (baseline/edited-diff logic, retry-all-on-partial-failure, locked-REJECT toggle) stays byte-identical except the two `agent_name: 'itso' as const` literals become `agent_name: agentName`.

- [ ] **Step 1: Rename the file and add the prop**

```bash
git mv client/src/features/evaluation/components/ItsoReviewModal.tsx client/src/features/evaluation/components/AgentReviewModal.tsx
```

Edit `AgentReviewModal.tsx`:

```typescript
type AgentReviewModalProps = {
  readonly agentName: 'itso' | 'sme';
  readonly evaluationId: string;
  readonly criteria: readonly CriterionScoreItem[];
  readonly onClose: () => void;
};
```

```typescript
export function AgentReviewModal({ agentName, evaluationId, criteria, onClose }: AgentReviewModalProps) {
```

Replace the two `agent_name: 'itso' as const` occurrences inside `handleSubmit`'s `actions` builder with `agent_name: agentName,` (drop `as const` — the prop's own union type already narrows it).

Replace the header text `Review ITSO Scores` with a computed label:

```typescript
  const agentLabel = agentName === 'itso' ? 'ITSO' : 'SME';
```

```tsx
              Review {agentLabel} Scores
```

- [ ] **Step 2: Update `Scorecard.tsx` to render the generalized modal for both domains**

```typescript
import { AgentReviewModal } from './AgentReviewModal';
```

```typescript
  const [reviewModalAgent, setReviewModalAgent] = useState<'itso' | 'sme' | null>(null);
```

(Remove the old `isItsoReviewOpen` state.)

In the domain-header row, replace:

```tsx
                              {domain === 'itso' && (
                                <button
                                  type="button"
                                  className="shrink-0 rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/5 px-2 py-1 text-[9px] font-bold normal-case tracking-wide text-[#1b3b87] hover:bg-[#1b3b87]/10"
                                  onClick={() => setIsItsoReviewOpen(true)}
                                >
                                  Review Scores
                                </button>
                              )}
```

with:

```tsx
                              {(domain === 'itso' || domain === 'sme') && (
                                <button
                                  type="button"
                                  className="shrink-0 rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/5 px-2 py-1 text-[9px] font-bold normal-case tracking-wide text-[#1b3b87] hover:bg-[#1b3b87]/10"
                                  onClick={() => setReviewModalAgent(domain)}
                                >
                                  Review Scores
                                </button>
                              )}
```

At the bottom, replace:

```tsx
            {isItsoReviewOpen && results.domain_scores.itso && (
              <ItsoReviewModal
                evaluationId={evaluation.evaluation_id}
                criteria={results.domain_scores.itso.criteria}
                onClose={() => setIsItsoReviewOpen(false)}
              />
            )}
```

with:

```tsx
            {reviewModalAgent && results.domain_scores[reviewModalAgent] && (
              <AgentReviewModal
                agentName={reviewModalAgent}
                evaluationId={evaluation.evaluation_id}
                criteria={results.domain_scores[reviewModalAgent].criteria}
                onClose={() => setReviewModalAgent(null)}
              />
            )}
```

- [ ] **Step 3: Type-check and run the client test suite**

Run: `cd client && pnpm build` (runs `tsc` first — will fail on any leftover `ItsoReviewModal` import or `isItsoReviewOpen` reference)
Expected: Clean build. Fix any remaining reference the search-and-replace above missed (grep the client tree for `ItsoReviewModal` and `isItsoReviewOpen` to confirm zero remaining hits before considering this done).

Run: `cd client && pnpm vitest run`
Expected: All existing tests still PASS (no test directly imports `ItsoReviewModal` by name per the earlier file read — only `Scorecard.tsx` did).

- [ ] **Step 4: Manual verification in the browser**

Start the dev server (`cd client && pnpm dev`) and the backend, run an evaluation through to completion, and confirm on the Scorecard page: both the SME and ITSO domain rows show a "Review Scores" button; opening SME's shows all 10 SME criteria with the same Accept/Reject/Edit affordances ITSO's modal has; submitting an SME EDIT persists and reopening the modal shows it as the new baseline (mirrors ITSO's existing "prior correction" behavior, unchanged by this task).

- [ ] **Step 5: Commit**

```bash
git add client/src/features/evaluation/components/AgentReviewModal.tsx client/src/features/evaluation/components/Scorecard.tsx
git commit -m "feat(evaluation): generalize the ITSO review modal to cover SME's 10 criteria"
```

---

## Self-Review Notes

- **Spec coverage:** "Call structure" (Tasks 1-5), "Output shape" (Task 2), "Fallback path" (Task 5), "DPO Correction Capture & Review UI" (Tasks 7, 9, 10), "DPO Export" (Task 8), "Fine-tuning & Deployment" (explicitly out of scope for this plan per the spec's own deferral to a manual, out-of-repo process — no task implements adapter loading, matching Non-goals). Coordinator/GAD non-goals are enforced structurally (Task 5's additive-only method, no other file touches `coordinator/` or `gad/`).
- **Grouping choice:** the 3 groups in Task 1 are derived from already-validated slicing scope (not a fresh domain guess), but the spec itself flags "validate the specific grouping against the oracle before shipping" as a condition of accepting the 2-3-call risk — that oracle-parity validation is a manual QA step to run against real SLMs before this ships to production, not a repo-testable unit, so it is called out here rather than as a task: run the existing oracle test fixtures (`server/tests/agents/sme/test_sme_oracle_contracts.py`'s validated documents) through `SME.run()` post-Task-5 and compare each criterion's LLM-scored band against the oracle's expected band before merging this branch.
