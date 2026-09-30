# Adapter Validation House-Rule Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `apps/server/scripts/seed_house_rule_edits.py`, a safe, removable script that turns the stored answers of REAL SME evaluations into a DPO dataset teaching one invented rule (raise the score of the odd-numbered criteria by 1), so an adapter trained on it can be checked for "did it learn the rule".

**Architecture:** The script never touches evaluations, generations or documents. It reads them, decides per criterion what to correct, prints a report (dry run is the default), and only with explicit confirmation writes small `PreferenceLog` correction rows (`{"score": N}`, no justification) under a dedicated user, tagged with a run id. The existing exporter and projector already turn such rows into `chosen`/`rejected` pairs, so nothing else changes. Cleanup deletes exactly the tagged rows.

**Tech Stack:** Python 3.12, SQLAlchemy 2, argparse, pytest (SQLite in memory), ruff. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-26-adapter-validation-house-rule-design.md` (approved 2026-09-30, updated for per-agent adapters; safeguard chosen: option A, a written rule only).

**Branch:** create `feat/house-rule-validation-script` from `origin/main` before Task 1 (`git switch -c feat/house-rule-validation-script origin/main`). The work does not depend on `feat/per-agent-adapter-publishing`.

## Global Constraints

- Backend modules use absolute `server.*` imports. Run everything from `apps/`: `cd apps && uv run --project server pytest <path>`; test paths look like `server/tests/scripts/...`. Run the script as `cd apps && uv run --project server python -m server.scripts.seed_house_rule_edits ...`.
- Ruff rules E, F, I, UP; line length 88; Python 3.12. After writing code run `uv run --project server ruff check --fix <files>` and `ruff format <files>` and accept its import ordering (the import blocks below are grouped by meaning, not by the repo's isort config). Do not reformat unrelated files.
- No new dependencies. Business rules stay in `modules/*`; this is a one-off script under `server/scripts/`, like `seed_synthetic_dpo_pairs.py`.
- **The safety rails are mandatory** (the target is the shared Neon dev database): nothing is written without BOTH `--confirm SEED` and a matching `--confirm-target`; only evaluations the admin lists are touched; a criterion that already has ANY `PreferenceLog` row for `(evaluation, sme, criterion)` is skipped so a real reviewer decision is never overridden; every written row is tagged `house-rule-seed:<run-id>` and is removable; production environments are refused.
- **The correction is score-only:** `edited_json == {"score": N}` exactly (no `justification` key), so the model's own reasoning stays identical in the chosen and rejected answers.
- **The script never modifies real evaluations, generations, documents or snapshots.** It only reads them and inserts/deletes its own tagged `PreferenceLog` rows and one dedicated user.
- Only SME generations with `envelope_status == "ok"` and contract `criterion_measurements.v1` v1 count (the exporter ignores `repaired` and `fallback` generations; real data has some).
- The user commits per task: the "hand off" steps say what to commit; do not add `Co-Authored-By` or `Claude-Session` trailers.

## Review Focus

Failure modes the spec implies but a happy-path test would miss. Each is pinned by a test in the task named.

1. **Old synthetic pairs contaminate the dataset.** The exporter builds pairs from EVERY SME correction in the database, and 25 synthetic pairs from an earlier seeding run (`synthetic-dpo-seed:32f54b7b-1122-4d70-a869-e86eba03cb42`, lowering scores and rewriting reasoning) are there now. The report must show the existing exportable pair count and warn when it is above zero. (Task 4)
2. **One criterion in two generations of the same evaluation.** A correction is keyed by `(evaluation, agent, criterion)`, so one row cannot fit two different scores; such a criterion must be skipped as `criterion_in_multiple_generations`. (Task 2)
3. **Generations that are not `ok`.** Real data has `repaired` and `fallback` generations (4 of 20). They must be ignored, and an evaluation whose only generations are not `ok` must abort the whole run. (Task 2)
4. **Held-out contamination.** The same evaluation id twice or in both lists, or the same document in both the train and reference lists, must abort with nothing written. A typo'd `--edit-criteria` code that no listed evaluation contains must also abort. (Task 2)
5. **Cleanup after a later decision or a wrong-agent row.** Cleanup must restore the earlier effective correction, and must abort without deleting anything if a tagged row is not for the SME agent. (Task 7)

## Reconciliation Notes (spec vs code/data; the controller rules)

- **R1 (data):** the database already holds 25 exportable SME pairs, all synthetic. Proposed: the report prints the baseline count and a warning; the runbook (Task 8) makes "remove them first with the synthetic seeder's `--cleanup`" Phase 0.
- **R2 (data):** every real SME prompt at the code default budget is about 14.4k-15.8k characters (about 3,600-3,950 tokens by chars/4), so 100% are above the notebook's 1,536-token limit, and even `MAX_SEQ_LENGTH = 2048` cannot hold one prompt. The report suggests `max_prompt_length` and `MAX_SEQ_LENGTH` values (Task 3); expect roughly 4352-4608 and 5888-6144, to be confirmed by a T4 smoke run. **Important (measured 2026-09-30):** the prompt size depends on `SME_TOTAL_PROMPT_BUDGET_CHARS`. The code default (and minimum) is 15000, but the developer `.env` sets 28000, which gives ~27.4k-char prompts (~6,850 tokens) for a long SLM and far more `repaired` answers. At 15000 a long and a short SLM give the SAME prompt size (14,394 chars) because the source is downsampled, and 8/8 envelope runs on a long SLM came out `ok`. The whole experiment (data collection, training and the validation benchmarks) must run with `SME_TOTAL_PROMPT_BUDGET_CHARS=15000`; the runbook (Task 8) says so.
- **R3 (data):** a real SME evaluation stores 2 generations (`envelope_0` = OP-01..05, `envelope_1` = A-01..05), so it yields at most 2 pairs, not 2-3. About 100 pairs needs about 50 evaluations.
- **R4 (data):** only 4 distinct real SLMs with readable text exist locally (`uploads/sample_slm`), plus 2 scanned ones, not 10. Repeated runs of the same SLM give near-duplicate pairs, so the dataset is thin and generalization evidence rests on 1-2 held-out SLMs. Recorded in the runbook; no code change.
- **R9 (data, found 2026-09-30):** the user's six SLMs with history are the faculty-uploaded 6-page `BSIT_CMSC313_SLM1/5/10/11/12/100` (files local, stored prompts 15.7k-15.85k chars = the budget-15000 era). Four of them (SLM1, SLM11, SLM12, SLM100) already have about 15 stored base-model `ok` SME generations from 7+1+1+1 COMPLETED SME evaluations (free "rejected" answers); SLM5 and SLM10 have none, so they make natural held-out SLMs. Some stored evaluations were scored with an adapter applied (`evaluation_jobs.adapter_resolution`, e.g. SLM1 on 2026-09-29 with `sme-v1`), which must not count as base answers: `plan_evaluation` aborts on them (Task 2). `adapter_resolution` exists only on the per-agent adapter branch, so the check uses `getattr` and its test is skipped where the column is absent.
- **R5 (spec wording):** the expected-scores CSV is one row per (SLM, criterion), not per (evaluation, criterion), because the "base reference" averages the runs of one SLM and is what the admin types into Model Validation once per SLM.
- **R6 (spec wording):** the spec says to reuse the synthetic-user helper, but `_get_or_create_synthetic_user` hardcodes another email and is private. Proposed: a small own `get_or_create_house_user` (email `house-rule-seed@local.test`) so cleanup can match by user AND tag.
- **R7 (design choice):** the environment check runs in every mode; the database-target check and both confirmations run only for write and cleanup, so a read-only dry run does not need the fingerprint allowlist. The dry run prints the value to pass as `--confirm-target`.
- **R8 (design choice):** `_is_score_shaped` in the projector is private and unchanged; the script keeps its own copy and a test pins that both agree.

## File Structure

| File | Responsibility |
|---|---|
| `apps/server/scripts/seed_house_rule_edits.py` (new) | Rule, planning, report, CSV, write, cleanup, CLI |
| `apps/server/tests/scripts/test_seed_house_rule_edits.py` (new) | All tests for the script |
| `training/house-rule-validation.md` (new) | The runbook: phases, notebook limits, rules, cleanup |

---

### Task 1: Rule, constants and plan types (pure code)

**Files:**
- Create: `apps/server/scripts/seed_house_rule_edits.py`
- Create: `apps/server/tests/scripts/test_seed_house_rule_edits.py`

**Interfaces:**
- Produces: constants `AGENT_ID`, `RUN_NOTE_PREFIX`, `HOUSE_USER_EMAIL`, `DEFAULT_EDIT_CRITERIA`, `PROMPT_TOKEN_LIMIT`, `CHARS_PER_TOKEN`, `CONTRACT_KEY`, `CONTRACT_VERSION`; `IneligibleRunError`; `apply_rule(score) -> tuple[int | None, str | None]`; `is_score_shaped(measurement) -> bool`; `base_reference(scores) -> int`; `expected_score(role, reference) -> int`; `normalize_codes(raw) -> tuple[str, ...]`; `format_note(run_id) -> str`; frozen dataclasses `CriterionPlan`, `GenerationInfo`, `EvaluationPlan` (property `writes`), `RunPlan` (properties `writes`, `pair_generation_ids`, method `skip_counts()`).

- [ ] **Step 1: Write the failing tests**

Create `apps/server/tests/scripts/test_seed_house_rule_edits.py`:

```python
"""Tests for the house-rule correction script (adapter validation)."""

from __future__ import annotations

import uuid

import pytest
from server.modules.training_data.projectors import _is_score_shaped
from server.scripts import seed_house_rule_edits as tool


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1, (2, None)),
        (2, (3, None)),
        (3, (4, None)),
        (4, (None, "already_max")),
        (0, (None, "invalid_score")),
        (5, (None, "invalid_score")),
        (True, (None, "invalid_score")),
        ("3", (None, "invalid_score")),
        (None, (None, "invalid_score")),
        (3.0, (4, None)),
        (2.5, (None, "invalid_score")),
    ],
)
def test_apply_rule_raises_by_one_and_skips_the_ceiling(score, expected):
    assert tool.apply_rule(score) == expected


@pytest.mark.parametrize(
    "measurement",
    [
        {"criterion_id": "OP-01", "score": 2, "reasoning": "r"},
        {"criterion_id": "OP-01", "score": 2, "instances": []},
        {"criterion_id": "OP-01", "score": 2, "total_units": 3},
        {"criterion_id": "OP-01", "instances": []},
        {"criterion_id": "OP-01"},
    ],
)
def test_is_score_shaped_agrees_with_the_projector(measurement):
    assert tool.is_score_shaped(measurement) == _is_score_shaped(measurement)


@pytest.mark.parametrize(
    ("scores", "expected"),
    [([2, 3], 3), ([2, 2, 3], 2), ([3, 4], 4), ([1], 1), ([2, 2], 2)],
)
def test_base_reference_is_the_mean_rounded_half_up(scores, expected):
    assert tool.base_reference(scores) == expected


@pytest.mark.parametrize(
    ("role", "reference", "expected"),
    [("edited", 4, 4), ("edited", 2, 3), ("control", 2, 2), ("control", 4, 4)],
)
def test_expected_score_applies_the_rule_only_to_edited(role, reference, expected):
    assert tool.expected_score(role, reference) == expected


def test_normalize_codes_uppercases_dedupes_and_keeps_order():
    assert tool.normalize_codes([" op-01", "A-03 ", "", "OP-01"]) == ("OP-01", "A-03")


def test_default_edit_set_is_the_six_odd_numbered_criteria():
    assert tool.DEFAULT_EDIT_CRITERIA == (
        "OP-01",
        "OP-03",
        "OP-05",
        "A-01",
        "A-03",
        "A-05",
    )


def test_format_note_tags_the_run():
    run_id = uuid.uuid4()
    assert tool.format_note(run_id) == f"house-rule-seed:{run_id}"


def _criterion(code, *, role="edited", generation=None, new=None, skip=None):
    return tool.CriterionPlan(
        evaluation_id=uuid.UUID(int=1),
        generation_id=generation or uuid.UUID(int=2),
        criterion_code=code,
        role=role,
        base_score=2,
        new_score=new,
        skip_reason=skip,
    )


def _evaluation(group, criteria):
    return tool.EvaluationPlan(
        evaluation_id=uuid.UUID(int=1),
        document_id=uuid.UUID(int=3),
        document_title="Doc",
        group=group,
        generations=(),
        criteria=tuple(criteria),
    )


def test_only_train_plans_write_and_pair_generations_are_counted():
    gen_a, gen_b = uuid.UUID(int=10), uuid.UUID(int=11)
    train = _evaluation(
        "train",
        [
            _criterion("OP-01", generation=gen_a, new=3),
            _criterion("OP-03", generation=gen_a, new=4),
            _criterion("A-01", generation=gen_b, new=2),
            _criterion("A-03", generation=gen_b, skip="already_max"),
            _criterion("OP-02", role="control"),
        ],
    )
    reference = _evaluation("reference", [_criterion("OP-01", new=3)])
    run = tool.RunPlan(plans=(train, reference), edit_codes=("OP-01",))

    assert len(train.writes) == 3
    assert reference.writes == ()
    assert len(run.writes) == 3
    assert run.pair_generation_ids == frozenset({gen_a, gen_b})
    assert run.skip_counts() == {"already_max": 1}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v`
Expected: FAIL (`ModuleNotFoundError: server.scripts.seed_house_rule_edits`).

- [ ] **Step 3: Write the minimal implementation**

Create `apps/server/scripts/seed_house_rule_edits.py`:

```python
"""House-rule DPO corrections on REAL SME evaluations (adapter validation).

Teaches one invented, easy-to-measure rule to an SME adapter: for each *edited*
criterion the score is raised by 1 (capped at 4); every other criterion is a
*control* and is never corrected. The script reads the stored answers of real,
COMPLETED SME evaluations and, only with explicit confirmation, inserts small
score-only ``PreferenceLog`` corrections. The existing exporter turns those into
DPO pairs, so the exporter, projectors and training flow are unchanged.

It never modifies evaluations, generations, documents or snapshots. Every row it
writes is tagged ``house-rule-seed:<run-id>`` and can be removed with --cleanup.

DEV/TEST/LOCAL ONLY. The adapter trained on these corrections teaches an INVENTED
rule: it is a validation artifact and must never be published.

Usage (from apps/):
    # 1. Read-only report (the default):
    uv run --project server python -m server.scripts.seed_house_rule_edits \
        --train-evaluations-file train_ids.txt \
        --reference-evaluations-file heldout_ids.txt --verify-export \
        --report-csv expected_scores.csv

    # 2. Write the corrections (both flags are required):
    uv run --project server python -m server.scripts.seed_house_rule_edits \
        --train-evaluations-file train_ids.txt \
        --reference-evaluations-file heldout_ids.txt --verify-export \
        --confirm SEED --confirm-target <LOCAL or fingerprint>

    # 3. Remove them when the validation is done:
    uv run --project server python -m server.scripts.seed_house_rule_edits \
        --cleanup --run-id <UUID> --confirm CLEANUP --confirm-target <T>
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

AGENT_ID = "sme"
RUN_NOTE_PREFIX = "house-rule-seed"
HOUSE_USER_EMAIL = "house-rule-seed@local.test"
DEFAULT_EDIT_CRITERIA = ("OP-01", "OP-03", "OP-05", "A-01", "A-03", "A-05")
# The Colab notebook trains with max_prompt_length = 1536 tokens.
PROMPT_TOKEN_LIMIT = 1536
CHARS_PER_TOKEN = 4
CONTRACT_KEY = "criterion_measurements.v1"
CONTRACT_VERSION = 1

Group = Literal["train", "reference"]
Role = Literal["edited", "control"]


class IneligibleRunError(Exception):
    """The run cannot proceed; nothing was written."""


def _as_score(value: object) -> int | None:
    """A valid 1-4 integer score, else None. Booleans and strings are invalid."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    else:
        return None
    return number if 1 <= number <= 4 else None


def apply_rule(score: object) -> tuple[int | None, str | None]:
    """The house rule: (new_score, skip_reason). Raise by 1, capped at 4."""
    current = _as_score(score)
    if current is None:
        return None, "invalid_score"
    if current >= 4:
        return None, "already_max"
    return current + 1, None


def is_score_shaped(measurement: dict[str, Any]) -> bool:
    """True only for an llm_rubric_guidance measurement (same test as the
    projector's private helper; a test pins that they agree)."""
    return (
        "score" in measurement
        and "instances" not in measurement
        and "total_units" not in measurement
    )


def base_reference(scores: Sequence[int]) -> int:
    """Mean of an SLM's runs, rounded half up (2.5 -> 3)."""
    return int(sum(scores) / len(scores) + 0.5)


def expected_score(role: Role, reference: int) -> int:
    """What the adapter should score if it learned the rule."""
    return min(4, reference + 1) if role == "edited" else reference


def normalize_codes(raw: Sequence[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for item in raw:
        code = item.strip().upper()
        if code:
            seen.setdefault(code, None)
    return tuple(seen)


def format_note(run_id: uuid.UUID) -> str:
    return f"{RUN_NOTE_PREFIX}:{run_id}"


@dataclass(frozen=True, slots=True)
class CriterionPlan:
    evaluation_id: uuid.UUID
    generation_id: uuid.UUID
    criterion_code: str
    role: Role
    base_score: int | None
    new_score: int | None
    skip_reason: str | None


@dataclass(frozen=True, slots=True)
class GenerationInfo:
    generation_id: uuid.UUID
    unit_key: str
    prompt_chars: int
    criterion_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationPlan:
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    group: Group
    generations: tuple[GenerationInfo, ...]
    criteria: tuple[CriterionPlan, ...]

    @property
    def writes(self) -> tuple[CriterionPlan, ...]:
        """Corrections to write. Reference (held-out) plans never write."""
        if self.group != "train":
            return ()
        return tuple(c for c in self.criteria if c.new_score is not None)


@dataclass(frozen=True, slots=True)
class RunPlan:
    plans: tuple[EvaluationPlan, ...]
    edit_codes: tuple[str, ...]

    @property
    def writes(self) -> tuple[CriterionPlan, ...]:
        return tuple(c for plan in self.plans for c in plan.writes)

    @property
    def pair_generation_ids(self) -> frozenset[uuid.UUID]:
        """Generations that will produce a DPO pair (>= 1 correction each)."""
        return frozenset(c.generation_id for c in self.writes)

    def skip_counts(self) -> Counter[str]:
        return Counter(
            c.skip_reason
            for plan in self.plans
            for c in plan.criteria
            if c.skip_reason
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v`
Expected: PASS (all parametrized cases).

- [ ] **Step 5: Lint and hand off for commit**

Run: `cd apps && uv run --project server ruff check --fix server/scripts/seed_house_rule_edits.py server/tests/scripts/test_seed_house_rule_edits.py && uv run --project server ruff format server/scripts/seed_house_rule_edits.py server/tests/scripts/test_seed_house_rule_edits.py`
Suggested commit: `feat(scripts): house-rule scoring core and plan types`

---

### Task 2: Reading evaluations, eligibility and the run plan (read-only)

**Files:**
- Modify: `apps/server/scripts/seed_house_rule_edits.py`
- Modify: `apps/server/tests/scripts/test_seed_house_rule_edits.py`

**Interfaces:**
- Consumes: Task 1 types and `apply_rule`, `is_score_shaped`, `normalize_codes`; `load_verified_agent_snapshot`, `SnapshotIntegrityError`, `LlmRubricGuidanceConfig`.
- Produces: `_decide(role, code, measurement, strategy, existing, duplicated) -> tuple[int | None, str | None]`; `plan_evaluation(session, evaluation_id, *, group, edit_codes) -> EvaluationPlan`; `plan_run(session, *, train_ids, reference_ids, edit_codes) -> RunPlan`. Skip reasons used: `not_in_snapshot`, `not_llm_rubric_guidance`, `not_score_shaped`, `criterion_in_multiple_generations`, `existing_log`, `already_max`, `invalid_score`.

- [ ] **Step 1: Write the failing tests**

Append to `apps/server/tests/scripts/test_seed_house_rule_edits.py` (add the imports at the top of the file):

```python
import hashlib
import json
from datetime import UTC, datetime

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.modules.synthesis.models import AgentGeneration, AgentResult

# Re-exported fixture: seeds the active SME rubric (OP-01..05, A-01..05, all
# llm_rubric_guidance) into the in-memory test database.
from server.tests.scripts.test_seed_synthetic_dpo_pairs import (  # noqa: F401
    seeded_sme_rubric,
)


@pytest.fixture()
def user(db_session):
    account = create_user(
        db_session,
        name="Tester",
        email="tester@local.test",
        password=uuid.uuid4().hex,
        role=UserRole.FACULTY,
    )
    db_session.flush()
    return account


def measurement(code, score, reasoning="because"):
    return {
        "criterion_id": code,
        "criterion_title": code,
        "score": score,
        "reasoning": reasoning,
        "evidence": "e",
    }


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_evaluation(
    session,
    user,
    generations,
    *,
    status="COMPLETED",
    title="Test SLM",
    envelope_status="ok",
    document_id=None,
    prompt_chars=200,
):
    """A stored SME evaluation with one generation per list in `generations`."""
    document_id = document_id or uuid.uuid4()
    if session.get(Document, document_id) is None:
        session.add(
            Document(
                document_id=document_id,
                title=title,
                source_type="slm",
                file_path=f"uploads/{document_id}.pdf",
                uploaded_by=user.user_id,
                uploaded_at=datetime.now(UTC),
                page_count=1,
                has_ocr_pages=False,
                processing_status="PROCESSED",
            )
        )
    evaluation_id = uuid.uuid4()
    session.add(
        EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            submitted_by=user.user_id,
            status=status,
            target_agent="sme",
        )
    )
    session.flush()
    resolve_or_reuse_evaluation_snapshots(session, evaluation_id, ("sme",))
    agent_result_id = uuid.uuid4()
    session.add(
        AgentResult(
            agent_result_id=agent_result_id,
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_name="sme",
            model_name="gemma-3-4b-it",
            success=True,
            envelope_status={"envelope_0": "ok"},
        )
    )
    session.flush()
    generation_ids = []
    for index, measurements in enumerate(generations):
        response = {"summary": "s", "criterion_measurements": measurements}
        response_text = json.dumps(response)
        prompt = ("PROMPT-%d-" % index).ljust(prompt_chars, "x")
        generation_id = uuid.uuid4()
        session.add(
            AgentGeneration(
                generation_id=generation_id,
                agent_result_id=agent_result_id,
                evaluation_id=evaluation_id,
                document_id=document_id,
                agent_id="sme",
                unit_key=f"envelope_{index}",
                criterion_ids=[m["criterion_id"] for m in measurements],
                prompt_text=prompt,
                response_text=response_text,
                response_json=response,
                response_contract_key="criterion_measurements.v1",
                response_contract_version=1,
                model_name="gemma-3-4b-it",
                envelope_status=envelope_status,
                prompt_sha256=_sha(prompt),
                response_sha256=_sha(response_text),
            )
        )
        generation_ids.append(generation_id)
    session.commit()
    return evaluation_id, generation_ids


FULL_ANSWER = [
    [
        measurement("OP-01", 2),
        measurement("OP-02", 3),
        measurement("OP-03", 4),
        measurement("OP-04", 1),
        measurement("OP-05", 3),
    ],
    [
        measurement("A-01", 1),
        measurement("A-02", 2),
        measurement("A-03", 3),
        measurement("A-04", 4),
        measurement("A-05", 2),
    ],
]


def test_plan_evaluation_applies_the_rule_and_never_touches_controls(
    db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)

    plan = tool.plan_evaluation(
        db_session,
        evaluation_id,
        group="train",
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )

    by_code = {c.criterion_code: c for c in plan.criteria}
    assert by_code["OP-01"].new_score == 3
    assert by_code["OP-03"].new_score is None
    assert by_code["OP-03"].skip_reason == "already_max"
    assert by_code["OP-05"].new_score == 4
    assert (by_code["A-01"].new_score, by_code["A-03"].new_score) == (2, 4)
    assert by_code["A-05"].new_score == 3
    for code in ("OP-02", "OP-04", "A-02", "A-04"):
        assert by_code[code].role == "control"
        assert by_code[code].new_score is None
        assert by_code[code].skip_reason is None
    assert len(plan.generations) == 2
    assert len(plan.writes) == 5
    assert plan.document_title == "Test SLM"


def test_reference_plans_compute_but_never_write(db_session, user, seeded_sme_rubric):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    plan = tool.plan_evaluation(
        db_session,
        evaluation_id,
        group="reference",
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    assert plan.writes == ()
    assert {c.criterion_code for c in plan.criteria if c.role == "edited"} == set(
        tool.DEFAULT_EDIT_CRITERIA
    )


def test_missing_evaluation_aborts(db_session, seeded_sme_rubric):
    with pytest.raises(tool.IneligibleRunError, match="does not exist"):
        tool.plan_evaluation(
            db_session, uuid.uuid4(), group="train", edit_codes=("OP-01",)
        )


def test_evaluation_that_is_not_completed_aborts(db_session, user, seeded_sme_rubric):
    evaluation_id, _ = make_evaluation(
        db_session, user, FULL_ANSWER, status="EVALUATING"
    )
    with pytest.raises(tool.IneligibleRunError, match="not COMPLETED"):
        tool.plan_evaluation(
            db_session, evaluation_id, group="train", edit_codes=("OP-01",)
        )


@pytest.mark.skipif(
    not hasattr(EvaluationJob, "adapter_resolution"),
    reason="adapter_resolution exists only on the per-agent adapter branch",
)
def test_an_evaluation_scored_with_an_adapter_aborts(
    db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    job = db_session.get(EvaluationJob, evaluation_id)
    job.adapter_resolution = {
        "sme": {"requested": "sme-v1", "applied": "sme-v1", "reason": None}
    }
    db_session.commit()
    with pytest.raises(tool.IneligibleRunError, match="base-model answers only"):
        tool.plan_evaluation(
            db_session, evaluation_id, group="train", edit_codes=("OP-01",)
        )


@pytest.mark.parametrize("envelope_status", ["repaired", "fallback"])
def test_only_ok_generations_count_and_none_ok_aborts(
    db_session, user, seeded_sme_rubric, envelope_status
):
    evaluation_id, _ = make_evaluation(
        db_session, user, FULL_ANSWER, envelope_status=envelope_status
    )
    with pytest.raises(tool.IneligibleRunError, match="no usable SME generation"):
        tool.plan_evaluation(
            db_session, evaluation_id, group="train", edit_codes=("OP-01",)
        )


def test_an_existing_real_log_is_skipped_and_left_untouched(
    db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    real = PreferenceLog(
        evaluation_id=evaluation_id,
        user_id=user.user_id,
        agent_name="sme",
        criterion_id="OP-01",
        action="ACCEPT",
    )
    db_session.add(real)
    db_session.commit()

    plan = tool.plan_evaluation(
        db_session,
        evaluation_id,
        group="train",
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )

    op01 = next(c for c in plan.criteria if c.criterion_code == "OP-01")
    assert (op01.new_score, op01.skip_reason) == (None, "existing_log")
    assert db_session.query(PreferenceLog).count() == 1
    assert db_session.get(PreferenceLog, real.log_id).action == "ACCEPT"


def test_a_criterion_in_two_generations_is_skipped(db_session, user, seeded_sme_rubric):
    evaluation_id, _ = make_evaluation(
        db_session,
        user,
        [[measurement("OP-01", 2)], [measurement("OP-01", 3)]],
    )
    plan = tool.plan_evaluation(
        db_session, evaluation_id, group="train", edit_codes=("OP-01",)
    )
    assert plan.writes == ()
    assert {c.skip_reason for c in plan.criteria} == {
        "criterion_in_multiple_generations"
    }


def test_measurements_without_a_criterion_id_are_ignored(
    db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(
        db_session, user, [[{"score": 2}, measurement("OP-01", 2)]]
    )
    plan = tool.plan_evaluation(
        db_session, evaluation_id, group="train", edit_codes=("OP-01",)
    )
    assert [c.criterion_code for c in plan.criteria] == ["OP-01"]


def test_a_measurement_that_is_not_score_shaped_is_skipped(
    db_session, user, seeded_sme_rubric
):
    counted = {"criterion_id": "OP-01", "score": 2, "instances": [], "total_units": 3}
    evaluation_id, _ = make_evaluation(db_session, user, [[counted]])
    plan = tool.plan_evaluation(
        db_session, evaluation_id, group="train", edit_codes=("OP-01",)
    )
    assert plan.criteria[0].skip_reason == "not_score_shaped"
    assert plan.writes == ()


def test_decide_skip_reasons_in_priority_order():
    shaped = measurement("OP-01", 2)
    strategy = tool.LlmRubricGuidanceConfig.model_construct()
    assert tool._decide("control", "OP-02", shaped, strategy, set(), False) == (
        None,
        None,
    )
    assert tool._decide("edited", "ZZ-99", shaped, None, set(), False) == (
        None,
        "not_in_snapshot",
    )
    assert tool._decide("edited", "OP-01", shaped, object(), set(), False) == (
        None,
        "not_llm_rubric_guidance",
    )
    assert tool._decide("edited", "OP-01", shaped, strategy, set(), False) == (3, None)
    assert tool._decide("edited", "OP-01", shaped, strategy, {"OP-01"}, False) == (
        None,
        "existing_log",
    )
    assert tool._decide("edited", "OP-01", shaped, strategy, set(), True) == (
        None,
        "criterion_in_multiple_generations",
    )


def test_plan_run_reads_only_and_aborts_on_any_bad_evaluation(
    db_session, user, seeded_sme_rubric
):
    good, _ = make_evaluation(db_session, user, FULL_ANSWER)
    with pytest.raises(tool.IneligibleRunError, match="does not exist"):
        tool.plan_run(
            db_session,
            train_ids=[good, uuid.uuid4()],
            reference_ids=[],
            edit_codes=tool.DEFAULT_EDIT_CRITERIA,
        )
    assert db_session.query(PreferenceLog).count() == 0


def test_plan_run_rejects_duplicate_ids_and_ids_in_both_lists(
    db_session, user, seeded_sme_rubric
):
    first, _ = make_evaluation(db_session, user, FULL_ANSWER)
    with pytest.raises(tool.IneligibleRunError, match="more than once"):
        tool.plan_run(
            db_session,
            train_ids=[first, first],
            reference_ids=[],
            edit_codes=("OP-01",),
        )
    with pytest.raises(tool.IneligibleRunError, match="more than once"):
        tool.plan_run(
            db_session,
            train_ids=[first],
            reference_ids=[first],
            edit_codes=("OP-01",),
        )


def test_plan_run_rejects_a_document_in_both_train_and_reference(
    db_session, user, seeded_sme_rubric
):
    document_id = uuid.uuid4()
    trained, _ = make_evaluation(db_session, user, FULL_ANSWER, document_id=document_id)
    held_out, _ = make_evaluation(
        db_session, user, FULL_ANSWER, document_id=document_id
    )
    with pytest.raises(tool.IneligibleRunError, match="held-out"):
        tool.plan_run(
            db_session,
            train_ids=[trained],
            reference_ids=[held_out],
            edit_codes=("OP-01",),
        )


def test_plan_run_rejects_an_edit_code_that_no_evaluation_contains(
    db_session, user, seeded_sme_rubric
):
    first, _ = make_evaluation(db_session, user, FULL_ANSWER)
    with pytest.raises(tool.IneligibleRunError, match="never seen"):
        tool.plan_run(
            db_session, train_ids=[first], reference_ids=[], edit_codes=("ZZ-99",)
        )


def test_plan_run_collects_train_and_reference_plans(
    db_session, user, seeded_sme_rubric
):
    train, _ = make_evaluation(db_session, user, FULL_ANSWER, title="Train")
    reference, _ = make_evaluation(db_session, user, FULL_ANSWER, title="Held out")
    run = tool.plan_run(
        db_session,
        train_ids=[train],
        reference_ids=[reference],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    assert [p.group for p in run.plans] == ["train", "reference"]
    assert len(run.writes) == 5
    assert len(run.pair_generation_ids) == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v -k "plan or decide or generations or existing or completed or missing or measurements or score_shaped or edit_code"`
Expected: FAIL (`AttributeError: module ... has no attribute 'plan_evaluation'` / `_decide`).

- [ ] **Step 3: Implement**

In `apps/server/scripts/seed_house_rule_edits.py` extend the imports block at the top of the module (below the docstring; merge with the existing imports) with:

```python
import json

from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.rubrics.contracts import LlmRubricGuidanceConfig
from server.modules.rubrics.snapshot_contracts import SnapshotIntegrityError
from server.modules.rubrics.snapshots import load_verified_agent_snapshot
from server.modules.synthesis.models import AgentGeneration
from sqlalchemy import func
from sqlalchemy.orm import Session
```

Then append after the dataclasses:

```python
def _usable_generations(session: Session, evaluation_id: uuid.UUID):
    """SME generations the exporter would use: ok, criterion_measurements.v1."""
    return (
        session.query(AgentGeneration)
        .filter(
            AgentGeneration.evaluation_id == evaluation_id,
            AgentGeneration.agent_id == AGENT_ID,
            AgentGeneration.envelope_status == "ok",
            AgentGeneration.response_contract_key == CONTRACT_KEY,
            AgentGeneration.response_contract_version == CONTRACT_VERSION,
        )
        .order_by(AgentGeneration.unit_key.asc(), AgentGeneration.generation_id.asc())
        .all()
    )


def _measurements(generation: AgentGeneration) -> list[dict[str, Any]]:
    raw = generation.response_json
    if not raw and generation.response_text:
        try:
            raw = json.loads(generation.response_text)
        except (TypeError, ValueError):
            raw = None
    items = raw.get("criterion_measurements") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _measured_codes(measurements: list[dict[str, Any]]) -> list[str]:
    return [
        m["criterion_id"]
        for m in measurements
        if isinstance(m.get("criterion_id"), str) and m["criterion_id"]
    ]


def _existing_log_codes(session: Session, evaluation_id: uuid.UUID) -> set[str]:
    """Criteria that already have ANY preference log for the SME agent."""
    rows = (
        session.query(PreferenceLog.criterion_id)
        .filter(
            PreferenceLog.evaluation_id == evaluation_id,
            func.lower(PreferenceLog.agent_name) == AGENT_ID,
            PreferenceLog.criterion_id.isnot(None),
        )
        .all()
    )
    return {code for (code,) in rows}


def _decide(
    role: Role,
    code: str,
    measurement: dict[str, Any],
    strategy: object,
    existing: set[str],
    duplicated: bool,
) -> tuple[int | None, str | None]:
    """(new_score, skip_reason) for one measured criterion."""
    if role == "control":
        return None, None
    if strategy is None:
        return None, "not_in_snapshot"
    if not isinstance(strategy, LlmRubricGuidanceConfig):
        return None, "not_llm_rubric_guidance"
    if not is_score_shaped(measurement):
        return None, "not_score_shaped"
    if duplicated:
        return None, "criterion_in_multiple_generations"
    if code in existing:
        return None, "existing_log"
    return apply_rule(measurement.get("score"))


def plan_evaluation(
    session: Session,
    evaluation_id: uuid.UUID,
    *,
    group: Group,
    edit_codes: Sequence[str],
) -> EvaluationPlan:
    """Decide what to correct in one evaluation. Fails closed; reads only."""
    job = session.get(EvaluationJob, evaluation_id)
    if job is None:
        raise IneligibleRunError(f"Evaluation {evaluation_id} does not exist.")
    status = str(getattr(job.status, "value", job.status))
    if status != "COMPLETED":
        raise IneligibleRunError(
            f"Evaluation {evaluation_id} is not COMPLETED (status {status})."
        )
    # Only present on the per-agent adapter branch; absent columns mean "no adapter".
    applied = ((getattr(job, "adapter_resolution", None) or {}).get(AGENT_ID) or {}).get(
        "applied"
    )
    if applied:
        raise IneligibleRunError(
            f"Evaluation {evaluation_id} was scored with adapter {applied} applied; "
            "the experiment needs base-model answers only."
        )
    generations = _usable_generations(session, evaluation_id)
    if not generations:
        raise IneligibleRunError(
            f"Evaluation {evaluation_id} has no usable SME generation (needs "
            f"envelope_status 'ok' and contract {CONTRACT_KEY} v{CONTRACT_VERSION})."
        )
    try:
        snapshot = load_verified_agent_snapshot(session, evaluation_id, AGENT_ID)
    except SnapshotIntegrityError as exc:
        raise IneligibleRunError(
            f"Evaluation {evaluation_id} has no verified SME form snapshot: {exc}"
        ) from exc
    strategies = {
        criterion.criterion_code: criterion.strategy_config
        for domain in snapshot.snapshot_payload.form.domains
        for criterion in domain.criteria
    }
    existing = _existing_log_codes(session, evaluation_id)
    document = session.get(Document, job.document_id)
    title = (document.title if document is not None else "") or ""
    edit_set = frozenset(edit_codes)

    measured = [(g, _measurements(g)) for g in generations]
    occurrences = Counter(
        code for _, measurements in measured for code in _measured_codes(measurements)
    )
    infos: list[GenerationInfo] = []
    criteria: list[CriterionPlan] = []
    for generation, measurements in measured:
        infos.append(
            GenerationInfo(
                generation_id=generation.generation_id,
                unit_key=generation.unit_key,
                prompt_chars=len(generation.prompt_text or ""),
                criterion_codes=tuple(_measured_codes(measurements)),
            )
        )
        for measurement in measurements:
            code = measurement.get("criterion_id")
            if not isinstance(code, str) or not code:
                continue
            role: Role = "edited" if code in edit_set else "control"
            new_score, skip_reason = _decide(
                role,
                code,
                measurement,
                strategies.get(code),
                existing,
                occurrences[code] > 1,
            )
            criteria.append(
                CriterionPlan(
                    evaluation_id=evaluation_id,
                    generation_id=generation.generation_id,
                    criterion_code=code,
                    role=role,
                    base_score=_as_score(measurement.get("score")),
                    new_score=new_score,
                    skip_reason=skip_reason,
                )
            )
    return EvaluationPlan(
        evaluation_id=evaluation_id,
        document_id=job.document_id,
        document_title=title,
        group=group,
        generations=tuple(infos),
        criteria=tuple(criteria),
    )


def plan_run(
    session: Session,
    *,
    train_ids: Sequence[uuid.UUID],
    reference_ids: Sequence[uuid.UUID],
    edit_codes: Sequence[str],
) -> RunPlan:
    """Plan a whole run. Any problem aborts the run before anything is written."""
    codes = normalize_codes(edit_codes)
    if not codes:
        raise IneligibleRunError("At least one edit criterion is required.")
    all_ids = [*train_ids, *reference_ids]
    if not all_ids:
        raise IneligibleRunError("List at least one evaluation to plan.")
    duplicates = sorted(str(i) for i, n in Counter(all_ids).items() if n > 1)
    if duplicates:
        raise IneligibleRunError(
            "Evaluation id listed more than once (or in both lists): "
            + ", ".join(duplicates)
        )
    plans = [
        plan_evaluation(session, eid, group="train", edit_codes=codes)
        for eid in train_ids
    ] + [
        plan_evaluation(session, eid, group="reference", edit_codes=codes)
        for eid in reference_ids
    ]
    train_documents = {p.document_id for p in plans if p.group == "train"}
    shared = train_documents & {p.document_id for p in plans if p.group == "reference"}
    if shared:
        raise IneligibleRunError(
            "A document is in both the train and the reference list; a held-out SLM "
            "must never be trained on: " + ", ".join(sorted(str(d) for d in shared))
        )
    seen = {c.criterion_code for p in plans for c in p.criteria}
    unknown = [code for code in codes if code not in seen]
    if unknown:
        raise IneligibleRunError(
            "Edit criteria never seen in any listed evaluation: " + ", ".join(unknown)
        )
    return RunPlan(plans=tuple(plans), edit_codes=codes)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v`
Expected: PASS. If `make_evaluation` fails on a NOT NULL column of `Document`, `EvaluationJob` or `AgentGeneration`, read the model and add the missing column with a valid dummy value (the synthetic seeder `generate()` shows a working set).

- [ ] **Step 5: Lint and hand off for commit**

Run: ruff check --fix and ruff format on the two files (see Task 1 Step 5).
Suggested commit: `feat(scripts): plan house-rule corrections with fail-closed eligibility`

---

### Task 3: The dry-run report and the CLI (read-only)

**Files:**
- Modify: `apps/server/scripts/seed_house_rule_edits.py`
- Modify: `apps/server/tests/scripts/test_seed_house_rule_edits.py`

**Interfaces:**
- Consumes: Tasks 1-2.
- Produces: `parse_ids(text) -> list[uuid.UUID]`; `read_ids_file(path) -> list[uuid.UUID]`; `estimate_tokens(chars) -> int`; `suggest_limits(max_prompt_tokens) -> tuple[int, int]` (prompt limit, sequence length); `PROMPT_CHAR_LIMIT`; `REMINDERS`; `render_report(run, *, mode, baseline_pairs=None) -> str`; `build_parser()`; `main(argv=None, *, session_factory=None) -> int` (exit codes 0 ok, 2 aborted, 3 refused). In this task `main` supports the dry run only; `--confirm`, `--confirm-target` and `--cleanup` are refused with a clear message until Tasks 6 and 7.

- [ ] **Step 1: Write the failing tests**

Append to the test file:

```python
import types

from server.scripts import seed_house_rule_edits as tool  # already imported above


def test_parse_ids_accepts_commas_lines_and_comments():
    first, second = uuid.uuid4(), uuid.uuid4()
    text = f"# my run\n{first}, {second}\n\n"
    assert tool.parse_ids(text) == [first, second]
    with pytest.raises(ValueError):
        tool.parse_ids("not-a-uuid")


def test_read_ids_file(tmp_path):
    first = uuid.uuid4()
    path = tmp_path / "ids.txt"
    path.write_text(f"{first}  # trailing comment\n", encoding="utf-8")
    assert tool.read_ids_file(path) == [first]


def test_suggest_limits_rounds_up_with_a_margin():
    assert tool.estimate_tokens(15850) == 3963
    assert tool.suggest_limits(3963) == (4608, 6144)


def test_report_lists_evaluations_totals_skips_and_prompt_lengths(
    db_session, user, seeded_sme_rubric
):
    train, _ = make_evaluation(
        db_session, user, FULL_ANSWER, title="Train SLM", prompt_chars=15800
    )
    held_out, _ = make_evaluation(
        db_session, user, FULL_ANSWER, title="Held-out SLM", prompt_chars=15800
    )
    run = tool.plan_run(
        db_session,
        train_ids=[train],
        reference_ids=[held_out],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )

    text = tool.render_report(run, mode="DRY RUN")

    assert "House-rule report (DRY RUN)" in text
    assert "Edited criteria: OP-01, OP-03, OP-05, A-01, A-03, A-05" in text
    assert "[train]" in text and "[reference]" in text
    assert "Train SLM" in text and "Held-out SLM" in text
    assert "corrections planned: 5" in text
    assert "expected new pairs: 2" in text
    assert "already_max=" in text
    assert "2 of 2" in text  # generations above the notebook's prompt limit
    assert "max_prompt_length=4608" in text and "MAX_SEQ_LENGTH=6144" in text
    assert "never publish" in text.lower()
    assert "do not start another sme training job" in text.lower()


def test_report_survives_a_windows_console(db_session, user, seeded_sme_rubric):
    evaluation_id, _ = make_evaluation(
        db_session, user, FULL_ANSWER, title="Módulo – 1"
    )
    run = tool.plan_run(
        db_session,
        train_ids=[evaluation_id],
        reference_ids=[],
        edit_codes=("OP-01",),
    )
    tool.render_report(run, mode="DRY RUN").encode("cp1252")


@pytest.fixture()
def cli(monkeypatch, db_session):
    """Run main() against the in-memory database with the safety checks stubbed."""
    monkeypatch.setattr(tool, "validate_environment", lambda: "development")

    def run(*argv):
        return tool.main(list(argv), session_factory=lambda: db_session)

    return run


def test_cli_dry_run_prints_the_report_and_writes_nothing(
    cli, capsys, db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)

    code = cli("--train-evaluations", str(evaluation_id))

    out = capsys.readouterr().out
    assert code == 0
    assert "House-rule report (DRY RUN)" in out
    assert "Dry run: nothing was written" in out
    assert db_session.query(PreferenceLog).count() == 0


def test_cli_reads_ids_from_files(
    cli, capsys, tmp_path, db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    path = tmp_path / "train.txt"
    path.write_text(f"{evaluation_id}\n", encoding="utf-8")
    assert cli("--train-evaluations-file", str(path)) == 0
    assert "[train]" in capsys.readouterr().out


def test_cli_aborts_with_exit_2_and_a_message(cli, capsys, seeded_sme_rubric):
    assert cli("--train-evaluations", str(uuid.uuid4())) == 2
    assert "ABORTED" in capsys.readouterr().out
    assert cli("--train-evaluations", "nope") == 2


def test_cli_refuses_production(monkeypatch, capsys):
    def refuse():
        raise PermissionError("production refused")

    monkeypatch.setattr(tool, "validate_environment", refuse)
    assert tool.main(["--train-evaluations", str(uuid.uuid4())]) == 3
    assert "REFUSED" in capsys.readouterr().out


def test_cli_refuses_write_and_cleanup_until_they_exist(cli, capsys):
    assert cli("--train-evaluations", str(uuid.uuid4()), "--confirm", "SEED") == 3
    assert cli("--cleanup", "--run-id", str(uuid.uuid4())) == 3
    assert "not available" in capsys.readouterr().out


def test_parser_help_carries_the_publish_rule():
    assert "never be published" in tool.build_parser().format_help().lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v -k "parse_ids or read_ids or suggest or report or cli or parser"`
Expected: FAIL (missing `parse_ids`, `render_report`, `main`, ...).

- [ ] **Step 3: Implement**

Extend the imports of the script module with:

```python
import argparse
import logging
import math
from collections.abc import Callable
from pathlib import Path

from server.core.database import get_session_factory
from server.db.metadata import import_model_modules
from server.scripts.seed_synthetic_dpo_pairs import validate_environment
```

Append to the module (below `plan_run`):

```python
PROMPT_CHAR_LIMIT = PROMPT_TOKEN_LIMIT * CHARS_PER_TOKEN
# Room reserved for the model's answer when suggesting a sequence length.
RESPONSE_TOKEN_ALLOWANCE = 1536

REMINDERS = (
    "Reminders:",
    "  - The adapter trained on these corrections teaches an INVENTED rule. It is "
    "a test artifact: never publish it.",
    "  - These corrections are counted in every SME training job. Do not start "
    "another SME training job until you have run the cleanup.",
)


def estimate_tokens(chars: int) -> int:
    return math.ceil(chars / CHARS_PER_TOKEN)


def suggest_limits(max_prompt_tokens: int) -> tuple[int, int]:
    """(max_prompt_length, MAX_SEQ_LENGTH) for the notebook: the longest prompt
    plus 15%, rounded up to 256, and room for the answer on top."""
    prompt_limit = math.ceil(max_prompt_tokens * 1.15 / 256) * 256
    return prompt_limit, prompt_limit + RESPONSE_TOKEN_ALLOWANCE


def parse_ids(text: str) -> list[uuid.UUID]:
    """Evaluation ids separated by commas or newlines; '#' starts a comment."""
    ids: list[uuid.UUID] = []
    for line in text.splitlines():
        for part in line.split("#", 1)[0].split(","):
            part = part.strip()
            if part:
                ids.append(uuid.UUID(part))
    return ids


def read_ids_file(path: Path) -> list[uuid.UUID]:
    return parse_ids(path.read_text(encoding="utf-8"))


def _ascii(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


def _short(value: uuid.UUID) -> str:
    return str(value)[:8]


def render_report(
    run: RunPlan, *, mode: str, baseline_pairs: int | None = None
) -> str:
    """The printable report. ASCII only, so a Windows console cannot choke."""
    lines = [
        f"House-rule report ({mode})",
        f"Edited criteria: {', '.join(run.edit_codes)}",
        "",
        "Per evaluation:",
    ]
    for plan in run.plans:
        skips = Counter(c.skip_reason for c in plan.criteria if c.skip_reason)
        skip_text = ", ".join(f"{k}={v}" for k, v in sorted(skips.items())) or "none"
        lines.append(
            f"  {_short(plan.evaluation_id)} [{plan.group}] "
            f"{_ascii(plan.document_title)!r} generations={len(plan.generations)} "
            f"corrections={len(plan.writes)} skipped: {skip_text}"
        )
    train = [p for p in run.plans if p.group == "train"]
    reference = [p for p in run.plans if p.group == "reference"]
    lines += [
        "",
        f"Totals: train evaluations: {len(train)} | reference evaluations: "
        f"{len(reference)} | corrections planned: {len(run.writes)} | "
        f"expected new pairs: {len(run.pair_generation_ids)}",
    ]
    skip_totals = run.skip_counts()
    if skip_totals:
        lines.append(
            "Skips by reason: "
            + ", ".join(f"{k}={v}" for k, v in sorted(skip_totals.items()))
        )
    generations = [g for p in (train or run.plans) for g in p.generations]
    if generations:
        longest = max(g.prompt_chars for g in generations)
        over = sum(
            1 for g in generations if estimate_tokens(g.prompt_chars) > PROMPT_TOKEN_LIMIT
        )
        lines += [
            "",
            f"Prompt lengths over {len(generations)} generation(s): longest "
            f"{longest} chars (~{estimate_tokens(longest)} tokens, estimated as "
            f"chars/{CHARS_PER_TOKEN}).",
            f"  {over} of {len(generations)} are above the notebook's "
            f"{PROMPT_TOKEN_LIMIT}-token prompt limit (~{PROMPT_CHAR_LIMIT} chars).",
        ]
        if over:
            prompt_limit, sequence = suggest_limits(estimate_tokens(longest))
            lines.append(
                f"  Suggested notebook values: max_prompt_length={prompt_limit}, "
                f"MAX_SEQ_LENGTH={sequence} (estimates: confirm with a short T4 "
                "smoke run before the full run)."
            )
    if baseline_pairs is not None:
        lines += [
            "",
            "Existing exportable SME pairs already in the database: "
            f"{baseline_pairs}.",
        ]
        if baseline_pairs:
            lines.append(
                "  WARNING: these pairs would be trained on together with the new "
                "ones. Remove them first (see the runbook), or the adapter also "
                "learns them."
            )
    lines += ["", *REMINDERS]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Add house-rule score corrections to real SME evaluations (adapter "
            "validation). Read-only report by default. DEV/TEST/LOCAL ONLY."
        ),
        epilog=(
            "The adapter trained on these corrections teaches an invented rule and "
            "must never be published."
        ),
    )
    parser.add_argument("--train-evaluations", default="", help="Comma-separated ids.")
    parser.add_argument("--train-evaluations-file", type=Path, default=None)
    parser.add_argument(
        "--reference-evaluations", default="", help="Held-out ids (never written)."
    )
    parser.add_argument("--reference-evaluations-file", type=Path, default=None)
    parser.add_argument(
        "--edit-criteria",
        default=",".join(DEFAULT_EDIT_CRITERIA),
        help="Criteria to raise; every other SME criterion is a control.",
    )
    parser.add_argument("--report-csv", type=Path, default=None)
    parser.add_argument("--verify-export", action="store_true")
    parser.add_argument("--confirm", default=None)
    parser.add_argument("--confirm-target", default=None)
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--run-id", default=None)
    return parser


def _collect_ids(text: str, path: Path | None) -> list[uuid.UUID]:
    ids = parse_ids(text)
    if path is not None:
        ids += read_ids_file(path)
    return ids


def _run_plan(args: argparse.Namespace, session_factory: Any) -> int:
    if args.confirm is not None or args.confirm_target is not None:
        raise PermissionError("Write mode is not available yet.")
    train_ids = _collect_ids(args.train_evaluations, args.train_evaluations_file)
    reference_ids = _collect_ids(
        args.reference_evaluations, args.reference_evaluations_file
    )
    edit_codes = normalize_codes(args.edit_criteria.split(","))
    factory = session_factory if session_factory is not None else get_session_factory()
    session = factory()
    try:
        run = plan_run(
            session,
            train_ids=train_ids,
            reference_ids=reference_ids,
            edit_codes=edit_codes,
        )
        print(render_report(run, mode="DRY RUN"))
        print(
            "\nDry run: nothing was written. Add --confirm SEED --confirm-target "
            "<LOCAL or the target fingerprint> to write."
        )
        return 0
    finally:
        session.close()


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory: Callable[[], Session] | None = None,
) -> int:
    """Exit codes: 0 ok, 2 aborted (nothing written), 3 refused by a safety check."""
    import_model_modules()
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        validate_environment()
        if args.cleanup:
            raise PermissionError("Cleanup is not available yet.")
        return _run_plan(args, session_factory)
    except PermissionError as exc:
        print(f"REFUSED: {exc}")
        return 3
    except (IneligibleRunError, ValueError) as exc:
        print(f"ABORTED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: Task 3 does not use `is_local_or_test_target`, `compute_target_fingerprint` or `get_settings` yet. Do NOT import them in this task (ruff would report them unused); Task 6 adds them. Also, the test file already imports `tool` at the top, so drop the repeated `from server.scripts import seed_house_rule_edits as tool` line in the Task 3 block when you paste it.

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v`
Expected: PASS. (`test_cli_refuses_write_and_cleanup_until_they_exist` asserts the "not available" wording; Tasks 6-7 replace that test.)

- [ ] **Step 5: Lint and hand off for commit**

Suggested commit: `feat(scripts): house-rule dry-run report and CLI`

---

### Task 4: Existing-pairs check and `--verify-export`

**Files:**
- Modify: `apps/server/scripts/seed_house_rule_edits.py`
- Modify: `apps/server/tests/scripts/test_seed_house_rule_edits.py`

**Interfaces:**
- Consumes: `export_dpo_package(session, agent_id, output_dir, *, dry_run=True)` from `server.modules.training_data.exporter` (returns a manifest with `.pair_count`), the synthetic seeder's `generate` (test setup only).
- Produces: `count_exportable_pairs(session) -> int`; `--verify-export` prints the existing count (with the warning when above zero) in the dry run.

- [ ] **Step 1: Write the failing tests**

Append:

```python
from server.scripts import seed_synthetic_dpo_pairs as old_seeder


def test_count_exportable_pairs_counts_what_the_exporter_would_use(
    db_session, seeded_sme_rubric
):
    assert tool.count_exportable_pairs(db_session) == 0
    old_seeder.generate(db_session, count=2)
    assert tool.count_exportable_pairs(db_session) == 2


def test_report_warns_when_pairs_already_exist():
    run = tool.RunPlan(plans=(), edit_codes=("OP-01",))
    clean = tool.render_report(run, mode="DRY RUN", baseline_pairs=0)
    dirty = tool.render_report(run, mode="DRY RUN", baseline_pairs=25)
    assert "Existing exportable SME pairs already in the database: 0." in clean
    assert "WARNING" not in clean
    assert "already in the database: 25." in dirty
    assert "WARNING: these pairs would be trained on" in dirty


def test_cli_verify_export_flags_existing_synthetic_pairs(
    cli, capsys, db_session, user, seeded_sme_rubric
):
    old_seeder.generate(db_session, count=3)
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)

    assert cli("--train-evaluations", str(evaluation_id), "--verify-export") == 0

    out = capsys.readouterr().out
    assert "already in the database: 3." in out
    assert "WARNING" in out
    # still read-only: only the 3 synthetic corrections exist
    assert db_session.query(PreferenceLog).count() == 3
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v -k "exportable or warns_when or verify_export"`
Expected: FAIL (`count_exportable_pairs` missing; `--verify-export` prints nothing).

- [ ] **Step 3: Implement**

Add imports `import tempfile` and `from server.modules.training_data.exporter import export_dpo_package`. Append:

```python
def count_exportable_pairs(session: Session) -> int:
    """How many SME DPO pairs the exporter would produce right now (dry run)."""
    with tempfile.TemporaryDirectory() as scratch:
        manifest = export_dpo_package(
            session, AGENT_ID, Path(scratch) / "package", dry_run=True
        )
    return manifest.pair_count
```

In `_run_plan`, replace the two lines that build and print the report with:

```python
        baseline = count_exportable_pairs(session) if args.verify_export else None
        print(render_report(run, mode="DRY RUN", baseline_pairs=baseline))
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and hand off for commit**

Suggested commit: `feat(scripts): warn about SME pairs that already exist`

---

### Task 5: Expected-scores CSV

**Files:**
- Modify: `apps/server/scripts/seed_house_rule_edits.py`
- Modify: `apps/server/tests/scripts/test_seed_house_rule_edits.py`

**Interfaces:**
- Produces: `CSV_COLUMNS`; `build_expected_scores_rows(run) -> list[dict[str, str]]`; `write_expected_scores_csv(rows, path) -> None`; `--report-csv PATH` writes it in the dry run.
- CSV: one row per (SLM, criterion): `group,document_id,document_title,criterion_code,role,run_count,base_scores,base_reference,expected_score`.

- [ ] **Step 1: Write the failing tests**

Append:

```python
import csv


def _two_runs_of_one_slm(db_session, user):
    doc = uuid.uuid4()
    first, _ = make_evaluation(
        db_session,
        user,
        [[measurement("OP-01", 2), measurement("OP-02", 2)]],
        title="SLM A",
        document_id=doc,
    )
    second, _ = make_evaluation(
        db_session,
        user,
        [[measurement("OP-01", 3), measurement("OP-02", 2)]],
        title="SLM A",
        document_id=doc,
    )
    return first, second


def test_csv_rows_are_per_slm_and_criterion_with_the_rule_applied(
    db_session, user, seeded_sme_rubric
):
    first, second = _two_runs_of_one_slm(db_session, user)
    held_out, _ = make_evaluation(
        db_session,
        user,
        [[measurement("OP-01", 4), measurement("OP-02", 1)]],
        title="SLM B",
    )
    run = tool.plan_run(
        db_session,
        train_ids=[first, second],
        reference_ids=[held_out],
        edit_codes=("OP-01",),
    )

    rows = tool.build_expected_scores_rows(run)

    by_key = {(r["document_title"], r["criterion_code"]): r for r in rows}
    edited = by_key[("SLM A", "OP-01")]
    assert edited["group"] == "train" and edited["role"] == "edited"
    assert edited["run_count"] == "2"
    assert sorted(edited["base_scores"].split(";")) == ["2", "3"]
    assert edited["base_reference"] == "3"  # mean 2.5 rounds half up
    assert edited["expected_score"] == "4"
    control = by_key[("SLM A", "OP-02")]
    assert control["role"] == "control"
    assert (control["base_reference"], control["expected_score"]) == ("2", "2")
    ceiling = by_key[("SLM B", "OP-01")]
    assert ceiling["group"] == "reference"
    assert (ceiling["base_reference"], ceiling["expected_score"]) == ("4", "4")
    assert by_key[("SLM B", "OP-02")]["expected_score"] == "1"
    assert [r["group"] for r in rows] == sorted(
        (r["group"] for r in rows), key={"train": 0, "reference": 1}.get
    )


def test_cli_writes_the_csv_and_nothing_else(
    cli, tmp_path, capsys, db_session, user, seeded_sme_rubric
):
    first, second = _two_runs_of_one_slm(db_session, user)
    target = tmp_path / "out" / "expected.csv"

    code = cli(
        "--train-evaluations",
        f"{first},{second}",
        "--edit-criteria",
        "OP-01",
        "--report-csv",
        str(target),
    )

    assert code == 0
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == list(tool.CSV_COLUMNS)
    assert {r["criterion_code"] for r in rows} == {"OP-01", "OP-02"}
    assert "Expected-scores CSV written" in capsys.readouterr().out
    assert db_session.query(PreferenceLog).count() == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v -k "csv"`
Expected: FAIL (`build_expected_scores_rows` missing).

- [ ] **Step 3: Implement**

Add `import csv`. Append to the module:

```python
CSV_COLUMNS = (
    "group",
    "document_id",
    "document_title",
    "criterion_code",
    "role",
    "run_count",
    "base_scores",
    "base_reference",
    "expected_score",
)


def build_expected_scores_rows(run: RunPlan) -> list[dict[str, str]]:
    """One row per (SLM, criterion): the scores the admin types into Model
    Validation for the base model and for an adapter that learned the rule."""
    grouped: dict[tuple[str, uuid.UUID, str, str, str], list[int]] = {}
    for plan in run.plans:
        for criterion in plan.criteria:
            if criterion.base_score is None:
                continue
            key = (
                plan.group,
                plan.document_id,
                plan.document_title,
                criterion.criterion_code,
                criterion.role,
            )
            grouped.setdefault(key, []).append(criterion.base_score)
    order = {"train": 0, "reference": 1}
    rows: list[dict[str, str]] = []
    for (group, document_id, title, code, role), scores in sorted(
        grouped.items(), key=lambda kv: (order[kv[0][0]], kv[0][2], kv[0][3])
    ):
        reference = base_reference(scores)
        rows.append(
            {
                "group": group,
                "document_id": str(document_id),
                "document_title": title,
                "criterion_code": code,
                "role": role,
                "run_count": str(len(scores)),
                "base_scores": ";".join(str(s) for s in scores),
                "base_reference": str(reference),
                "expected_score": str(expected_score(role, reference)),
            }
        )
    return rows


def write_expected_scores_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
```

In `_run_plan`, after the `print(render_report(...))` line and before the "Dry run" message, add:

```python
        if args.report_csv is not None:
            write_expected_scores_csv(build_expected_scores_rows(run), args.report_csv)
            print(f"Expected-scores CSV written to {args.report_csv}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and hand off for commit**

Suggested commit: `feat(scripts): expected-scores CSV for Model Validation`

---

### Task 6: Write mode with the safety rails

**Files:**
- Modify: `apps/server/scripts/seed_house_rule_edits.py`
- Modify: `apps/server/tests/scripts/test_seed_house_rule_edits.py`

**Interfaces:**
- Consumes: `create_user` (`server.modules.auth.service`), `User`, `UserRole`, `is_local_or_test_target`, `compute_target_fingerprint`, `validate_database_target`, `CONFIRM_SEED_KEYWORD` from the synthetic seeder; `get_settings`.
- Produces: `get_or_create_house_user(session) -> User`; `write_corrections(session, run, *, run_id) -> int`; `_target_ack() -> str`; `_check_write_guards(args, *, keyword) -> None`; `_run_plan` supports `--confirm SEED --confirm-target T`.
- Note: check how `create_user` behaves (does it commit?). The synthetic seeder calls `session.flush()` right after it and relies on one later commit; do the same. If `create_user` commits internally, accept that the user row is committed even when a later step fails (it is harmless and reused).

- [ ] **Step 1: Write the failing tests**

Replace `test_cli_refuses_write_and_cleanup_until_they_exist` (delete it) and append:

```python
from server.modules.auth.models import User
from server.modules.training_data.exporter import export_dpo_package


@pytest.fixture()
def write_cli(monkeypatch, cli):
    """The CLI with the database-target checks pointed at a local target."""
    monkeypatch.setattr(
        tool,
        "get_settings",
        lambda: types.SimpleNamespace(database_url="sqlite:///:memory:"),
    )
    monkeypatch.setattr(tool, "validate_database_target", lambda: "f" * 64)
    return cli


def _eval_for_writing(db_session, user):
    return make_evaluation(db_session, user, FULL_ANSWER)[0]


def test_write_corrections_inserts_score_only_tagged_rows(
    db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    run = tool.plan_run(
        db_session,
        train_ids=[evaluation_id],
        reference_ids=[],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    run_id = uuid.uuid4()

    written = tool.write_corrections(db_session, run, run_id=run_id)

    rows = db_session.query(PreferenceLog).all()
    assert written == len(rows) == 5
    house = db_session.query(User).filter_by(email=tool.HOUSE_USER_EMAIL).one()
    for row in rows:
        assert row.action == "EDIT"
        assert row.agent_name == "sme"
        assert row.user_id == house.user_id
        assert row.notes == f"house-rule-seed:{run_id}"
        assert set(row.edited_json) == {"score"}
        assert row.generation_id is not None
    assert {r.criterion_id for r in rows} == {"OP-01", "OP-05", "A-01", "A-03", "A-05"}


def test_write_is_all_or_nothing(db_session, user, seeded_sme_rubric, monkeypatch):
    evaluation_id = _eval_for_writing(db_session, user)
    run = tool.plan_run(
        db_session,
        train_ids=[evaluation_id],
        reference_ids=[],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    real_commit = db_session.commit

    def failing_commit():
        raise RuntimeError("disk full")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    with pytest.raises(RuntimeError, match="disk full"):
        tool.write_corrections(db_session, run, run_id=uuid.uuid4())
    monkeypatch.setattr(db_session, "commit", real_commit)
    assert db_session.query(PreferenceLog).count() == 0


def test_the_exporter_turns_the_rows_into_pairs_that_differ_only_in_the_scores(
    db_session, user, seeded_sme_rubric, tmp_path
):
    evaluation_id = _eval_for_writing(db_session, user)
    run = tool.plan_run(
        db_session,
        train_ids=[evaluation_id],
        reference_ids=[],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    tool.write_corrections(db_session, run, run_id=uuid.uuid4())

    manifest = export_dpo_package(db_session, "sme", tmp_path / "package")

    assert manifest.pair_count == 2
    lines = (tmp_path / "package" / "pairs.jsonl").read_text("utf-8").splitlines()
    edited = set(tool.DEFAULT_EDIT_CRITERIA)
    for line in lines:
        pair = json.loads(line)
        chosen = json.loads(pair["chosen"])["criterion_measurements"]
        rejected = json.loads(pair["rejected"])["criterion_measurements"]
        assert len(chosen) == len(rejected) == 5
        for new, old in zip(chosen, rejected, strict=True):
            code = old["criterion_id"]
            expected = old["score"] + 1 if code in edited and old["score"] < 4 else None
            assert new["score"] == (expected or old["score"])
            # everything except the score is identical (reasoning untouched)
            assert {k: v for k, v in new.items() if k != "score"} == {
                k: v for k, v in old.items() if k != "score"
            }


def test_cli_write_requires_both_confirmations(
    write_cli, capsys, db_session, user, seeded_sme_rubric
):
    evaluation_id = str(_eval_for_writing(db_session, user))
    base = ["--train-evaluations", evaluation_id]
    assert write_cli(*base, "--confirm", "SEED") == 3
    assert write_cli(*base, "--confirm-target", "LOCAL") == 3
    assert write_cli(*base, "--confirm", "WRITE", "--confirm-target", "LOCAL") == 3
    assert write_cli(*base, "--confirm", "SEED", "--confirm-target", "wrong") == 3
    assert "REFUSED" in capsys.readouterr().out
    assert db_session.query(PreferenceLog).count() == 0


def test_cli_write_refuses_an_unsafe_database_target(
    monkeypatch, write_cli, db_session, user, seeded_sme_rubric
):
    def refuse():
        raise PermissionError("unsafe target")

    monkeypatch.setattr(tool, "validate_database_target", refuse)
    evaluation_id = str(_eval_for_writing(db_session, user))
    code = write_cli(
        "--train-evaluations",
        evaluation_id,
        "--confirm",
        "SEED",
        "--confirm-target",
        "LOCAL",
    )
    assert code == 3
    assert db_session.query(PreferenceLog).count() == 0


def test_cli_write_then_verify_export_then_second_run_writes_nothing(
    write_cli, capsys, db_session, user, seeded_sme_rubric
):
    evaluation_id = str(_eval_for_writing(db_session, user))
    argv = [
        "--train-evaluations",
        evaluation_id,
        "--verify-export",
        "--confirm",
        "SEED",
        "--confirm-target",
        "LOCAL",
    ]

    assert write_cli(*argv) == 0
    out = capsys.readouterr().out
    assert "Wrote 5 correction(s)" in out
    assert "expected 2 (OK)" in out
    assert "never publish" in out.lower()
    assert "--cleanup --run-id" in out
    assert db_session.query(PreferenceLog).count() == 5

    assert write_cli(*argv) == 0  # the criteria now have logs, so all are skipped
    assert "Nothing to write" in capsys.readouterr().out
    assert db_session.query(PreferenceLog).count() == 5


def test_reference_evaluations_are_never_written(
    write_cli, db_session, user, seeded_sme_rubric
):
    train = str(_eval_for_writing(db_session, user))
    held_out = make_evaluation(db_session, user, FULL_ANSWER, title="Held out")[0]
    code = write_cli(
        "--train-evaluations",
        train,
        "--reference-evaluations",
        str(held_out),
        "--confirm",
        "SEED",
        "--confirm-target",
        "LOCAL",
    )
    assert code == 0
    written = {r.evaluation_id for r in db_session.query(PreferenceLog).all()}
    assert written == {uuid.UUID(train)}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v -k "write or exporter or reference_evaluations_are"`
Expected: FAIL (`write_corrections` missing; write mode still refused).

- [ ] **Step 3: Implement**

Add these imports: `from server.core.config import get_settings`, `from server.modules.auth.models import User, UserRole`, `from server.modules.auth.service import create_user`, and extend the existing seeder import to `from server.scripts.seed_synthetic_dpo_pairs import (CONFIRM_SEED_KEYWORD, compute_target_fingerprint, is_local_or_test_target, validate_database_target, validate_environment)`. Append:

```python
def get_or_create_house_user(session: Session) -> User:
    """The dedicated user that owns every correction this script writes."""
    existing = session.query(User).filter_by(email=HOUSE_USER_EMAIL).one_or_none()
    if existing is not None:
        return existing
    user = create_user(
        session,
        name="House Rule Seed",
        email=HOUSE_USER_EMAIL,
        password=uuid.uuid4().hex,
        role=UserRole.FACULTY,
    )
    session.flush()
    return user


def write_corrections(session: Session, run: RunPlan, *, run_id: uuid.UUID) -> int:
    """Insert every planned correction in ONE transaction; all or nothing."""
    try:
        user = get_or_create_house_user(session)
        note = format_note(run_id)
        for correction in run.writes:
            session.add(
                PreferenceLog(
                    evaluation_id=correction.evaluation_id,
                    generation_id=correction.generation_id,
                    user_id=user.user_id,
                    agent_name=AGENT_ID,
                    criterion_id=correction.criterion_code,
                    action="EDIT",
                    edited_json={"score": correction.new_score},
                    notes=note,
                )
            )
        session.commit()
        return len(run.writes)
    except Exception:
        session.rollback()
        raise


def _target_ack() -> str:
    """The value --confirm-target must have: LOCAL, or the database fingerprint."""
    configured = (getattr(get_settings(), "database_url", None) or "").strip()
    if configured and is_local_or_test_target(configured):
        return "LOCAL"
    return compute_target_fingerprint(configured) if configured else "(no DATABASE_URL)"


def _check_write_guards(args: argparse.Namespace, *, keyword: str) -> None:
    """Both acknowledgements, and a database target that is allowed."""
    if args.confirm != keyword:
        raise PermissionError(f"Explicit acknowledgement required: pass --confirm {keyword}.")
    validate_database_target()
    expected = _target_ack()
    if (args.confirm_target or "").strip().lower() != expected.lower():
        raise PermissionError(
            "Explicit acknowledgement required for the database target: pass "
            f"--confirm-target {expected}."
        )
```

Replace `_run_plan` entirely with:

```python
def _run_plan(args: argparse.Namespace, session_factory: Any) -> int:
    write = args.confirm is not None or args.confirm_target is not None
    if write:
        _check_write_guards(args, keyword=CONFIRM_SEED_KEYWORD)
    train_ids = _collect_ids(args.train_evaluations, args.train_evaluations_file)
    reference_ids = _collect_ids(
        args.reference_evaluations, args.reference_evaluations_file
    )
    edit_codes = normalize_codes(args.edit_criteria.split(","))
    factory = session_factory if session_factory is not None else get_session_factory()
    session = factory()
    try:
        run = plan_run(
            session,
            train_ids=train_ids,
            reference_ids=reference_ids,
            edit_codes=edit_codes,
        )
        baseline = (
            count_exportable_pairs(session) if (args.verify_export or write) else None
        )
        print(render_report(run, mode="WRITE" if write else "DRY RUN", baseline_pairs=baseline))
        if args.report_csv is not None:
            write_expected_scores_csv(build_expected_scores_rows(run), args.report_csv)
            print(f"Expected-scores CSV written to {args.report_csv}")
        if not write:
            print(
                "\nDry run: nothing was written. To write, add --confirm SEED "
                f"--confirm-target {_target_ack()}."
            )
            return 0
        if not run.writes:
            print("\nNothing to write (every edited criterion was skipped).")
            return 0
        run_id = uuid.UUID(args.run_id) if args.run_id else uuid.uuid4()
        rows = write_corrections(session, run, run_id=run_id)
        print(f"\nWrote {rows} correction(s) for run-id {run_id} (notes='{format_note(run_id)}').")
        if args.verify_export:
            after = count_exportable_pairs(session)
            expected = (baseline or 0) + len(run.pair_generation_ids)
            verdict = "OK" if after == expected else "MISMATCH"
            print(
                f"Export check: {after} exportable SME pair(s) now; expected "
                f"{expected} ({verdict})."
            )
        print("\n".join(REMINDERS))
        print(
            f"To remove these corrections: --cleanup --run-id {run_id} "
            f"--confirm CLEANUP --confirm-target {_target_ack()}"
        )
        return 0
    finally:
        session.close()
```

The dry-run message calls `_target_ack()`, which needs `get_settings`; in the Task 3 tests `get_settings()` returns the real settings (fine: it only reads a URL). Wrap the long lines with ruff format.

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v`
Expected: PASS. The existing Task 3 test for the dry run still passes.

- [ ] **Step 5: Lint and hand off for commit**

Suggested commit: `feat(scripts): write house-rule corrections behind the safety rails`

---

### Task 7: Cleanup

**Files:**
- Modify: `apps/server/scripts/seed_house_rule_edits.py`
- Modify: `apps/server/tests/scripts/test_seed_house_rule_edits.py`

**Interfaces:**
- Consumes: `CONFIRM_CLEANUP_KEYWORD` from the synthetic seeder; `get_effective_criterion_corrections_batch` (`server.modules.feedback.state`, test only).
- Produces: `cleanup(session, *, run_id) -> int` (rows removed); `_run_cleanup(args, session_factory) -> int`; `main` dispatches `--cleanup`.

- [ ] **Step 1: Write the failing tests**

Append:

```python
from server.modules.feedback.state import get_effective_criterion_corrections_batch


def _house_rows(db_session, user, evaluation_id, run_id, *, agent="sme"):
    house = tool.get_or_create_house_user(db_session)
    log = PreferenceLog(
        evaluation_id=evaluation_id,
        user_id=house.user_id,
        agent_name=agent,
        criterion_id="OP-01",
        action="EDIT",
        edited_json={"score": 3},
        notes=tool.format_note(run_id),
    )
    db_session.add(log)
    db_session.commit()
    return log


def test_cleanup_removes_exactly_the_tagged_rows(db_session, user, seeded_sme_rubric):
    evaluation_id = _eval_for_writing(db_session, user)
    run = tool.plan_run(
        db_session,
        train_ids=[evaluation_id],
        reference_ids=[],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    mine, other = uuid.uuid4(), uuid.uuid4()
    tool.write_corrections(db_session, run, run_id=mine)
    survivor = _house_rows(db_session, user, evaluation_id, other)

    removed = tool.cleanup(db_session, run_id=mine)

    assert removed == 5
    remaining = db_session.query(PreferenceLog).all()
    assert [r.log_id for r in remaining] == [survivor.log_id]
    # real evaluation data is untouched
    assert db_session.query(AgentGeneration).count() == 2
    assert db_session.query(EvaluationJob).count() == 1


def test_cleanup_restores_the_earlier_effective_correction(
    db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    earlier = PreferenceLog(
        evaluation_id=evaluation_id,
        user_id=user.user_id,
        agent_name="sme",
        criterion_id="OP-01",
        action="EDIT",
        edited_json={"score": 1},
        notes="real reviewer",
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    db_session.add(earlier)
    db_session.commit()
    run_id = uuid.uuid4()
    _house_rows(db_session, user, evaluation_id, run_id)

    def effective():
        batch = get_effective_criterion_corrections_batch(db_session, [evaluation_id])
        return batch[evaluation_id][("sme", "OP-01")].score

    assert effective() == 3  # the house row is the latest
    assert tool.cleanup(db_session, run_id=run_id) == 1
    assert effective() == 1  # the reviewer's earlier decision is back


def test_cleanup_aborts_if_a_tagged_row_is_not_for_the_sme_agent(
    db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    run_id = uuid.uuid4()
    _house_rows(db_session, user, evaluation_id, run_id)
    _house_rows(db_session, user, evaluation_id, run_id, agent="gad")

    with pytest.raises(tool.IneligibleRunError, match="not for the SME agent"):
        tool.cleanup(db_session, run_id=run_id)
    assert db_session.query(PreferenceLog).count() == 2


def test_cleanup_ignores_rows_with_the_tag_from_another_user(
    db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    run_id = uuid.uuid4()
    db_session.add(
        PreferenceLog(
            evaluation_id=evaluation_id,
            user_id=user.user_id,
            agent_name="sme",
            criterion_id="OP-01",
            action="EDIT",
            edited_json={"score": 3},
            notes=tool.format_note(run_id),
        )
    )
    db_session.commit()
    assert tool.cleanup(db_session, run_id=run_id) == 0
    assert db_session.query(PreferenceLog).count() == 1


def test_cleanup_with_no_house_user_removes_nothing(db_session):
    assert tool.cleanup(db_session, run_id=uuid.uuid4()) == 0


def test_cli_cleanup_needs_both_confirmations_and_a_run_id(
    write_cli, capsys, db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    run_id = uuid.uuid4()
    _house_rows(db_session, user, evaluation_id, run_id)

    assert write_cli("--cleanup", "--run-id", str(run_id)) == 3
    assert (
        write_cli(
            "--cleanup",
            "--run-id",
            str(run_id),
            "--confirm",
            "SEED",
            "--confirm-target",
            "LOCAL",
        )
        == 3
    )
    assert (
        write_cli(
            "--cleanup", "--run-id", str(run_id), "--confirm", "CLEANUP",
            "--confirm-target", "wrong",
        )
        == 3
    )
    assert write_cli("--cleanup", "--confirm", "CLEANUP", "--confirm-target", "LOCAL") == 2
    assert write_cli(
        "--cleanup", "--run-id", "nope", "--confirm", "CLEANUP", "--confirm-target", "LOCAL"
    ) == 2
    assert db_session.query(PreferenceLog).count() == 1

    assert (
        write_cli(
            "--cleanup", "--run-id", str(run_id), "--confirm", "CLEANUP",
            "--confirm-target", "LOCAL",
        )
        == 0
    )
    assert "Removed 1 correction(s)" in capsys.readouterr().out
    assert db_session.query(PreferenceLog).count() == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/scripts/test_seed_house_rule_edits.py -v -k "cleanup"`
Expected: FAIL (`cleanup` missing; the CLI still says "Cleanup is not available yet.").

- [ ] **Step 3: Implement**

Add `CONFIRM_CLEANUP_KEYWORD` to the seeder import list. Append:

```python
def cleanup(session: Session, *, run_id: uuid.UUID | str) -> int:
    """Delete exactly the corrections this script wrote for `run_id`.

    Only rows whose note equals the run tag, that belong to the house user and
    whose action is EDIT are removed. Aborts (deleting nothing) if any of them is
    not for the SME agent. Older decisions become the effective ones again.
    """
    parsed = run_id if isinstance(run_id, uuid.UUID) else uuid.UUID(str(run_id))
    user = session.query(User).filter_by(email=HOUSE_USER_EMAIL).one_or_none()
    if user is None:
        return 0
    try:
        rows = (
            session.query(PreferenceLog)
            .filter(
                PreferenceLog.notes == format_note(parsed),
                PreferenceLog.user_id == user.user_id,
                PreferenceLog.action == "EDIT",
            )
            .all()
        )
        wrong = [r for r in rows if (r.agent_name or "").lower() != AGENT_ID]
        if wrong:
            raise IneligibleRunError(
                f"{len(wrong)} tagged correction(s) are not for the SME agent; "
                "cleanup aborted and nothing was deleted."
            )
        for row in rows:
            session.delete(row)
        session.commit()
        return len(rows)
    except Exception:
        session.rollback()
        raise


def _run_cleanup(args: argparse.Namespace, session_factory: Any) -> int:
    _check_write_guards(args, keyword=CONFIRM_CLEANUP_KEYWORD)
    if not args.run_id:
        raise ValueError("Cleanup requires an exact --run-id <UUID>.")
    run_id = uuid.UUID(args.run_id)
    factory = session_factory if session_factory is not None else get_session_factory()
    session = factory()
    try:
        removed = cleanup(session, run_id=run_id)
    finally:
        session.close()
    print(f"Removed {removed} correction(s) for run-id {run_id}.")
    return 0
```

In `main`, replace the line `raise PermissionError("Cleanup is not available yet.")` with `return _run_cleanup(args, session_factory)`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/scripts -v`
Expected: PASS, including the older synthetic-seeder tests in the same folder.

- [ ] **Step 5: Lint and hand off for commit**

Suggested commit: `feat(scripts): remove a house-rule run's corrections`

---

### Task 8: The runbook

**Files:**
- Create: `training/house-rule-validation.md`

**Interfaces:** none (documentation; the commands quoted must match Tasks 3-7).

- [ ] **Step 1: Write the runbook**

Create `training/house-rule-validation.md` with these sections, in this order (write real prose and the real commands; nothing left blank):

1. **What this proves and what it does not** (two short paragraphs from spec sections "What this proves" and the follow-up).
2. **Rules that must not be broken** (a short list): never publish the adapter trained on these corrections; do not start any other SME training job between the write and the cleanup; only the evaluations you list are touched; run all evaluations under a test account; **set `SME_TOTAL_PROMPT_BUDGET_CHARS=15000` in `.env` (the code default and minimum; the developer `.env` currently has 28000) and restart the backend before running any evaluation of the experiment, keep it at 15000 for the training-data runs AND for the validation benchmarks, and restore the old value afterwards.** Explain why: at 15000 every SLM, long or short, produces the same ~14.4k-character prompt (about 3,600 tokens), which fits the training limits and gave 8/8 clean answers on a long SLM, while 28000 gives ~27k-character prompts and many repaired answers (repaired and fallback generations are not usable training pairs).
3. **Phase 0: remove the old synthetic pairs.** The database holds 25 synthetic SME pairs from run `32f54b7b-1122-4d70-a869-e86eba03cb42`. Command (from `apps/`): `uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs --cleanup --run-id 32f54b7b-1122-4d70-a869-e86eba03cb42 --confirm CLEANUP --confirm-target <LOCAL or fingerprint>`; for the shared Neon database export `SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS="<fingerprint>"` first; the fingerprint is printed by this script's dry run. Verify with the house-rule dry run and `--verify-export`: "Existing exportable SME pairs" must read 0.
4. **Which SLMs to use.** Recommended split of the six faculty-uploaded 6-page SLMs that already have evaluation history: **train** on `BSIT_CMSC313_SLM1`, `SLM11`, `SLM12`, `SLM100` (about 15 stored base-model `ok` SME generations can be reused for free, but any evaluation scored with an adapter applied is refused by the script) and **hold out** `BSIT_CMSC313_SLM5` and `BSIT_CMSC313_SLM10` (they have no stored SME generations, so run each 2-3 times on the base model for the reference scores). About 40 further base-model runs on the four training SLMs bring the total to about 100 pairs. Long SLMs are also fine once the budget is 15000 (rule above): the source is downsampled to the same prompt size. The older note that follows describes the other local files. Say plainly: locally there are 4 distinct real SLMs with readable text in `uploads/sample_slm` (`BSCS_CMSC313_SLM5`, `BSIT_GEC108_SLM1`, `BSIT_CMSC313_SLM1`, `GEC102_SLM1`) plus 2 scanned Capstone SLMs that have no text layer; the spec assumed 10. Recommendation: train on 3, hold out 1; ask faculty for more real SLMs if the result is inconclusive; repeated runs of the same SLM give near-duplicate pairs.
5. **The process** (the numbered phases from the spec, with the commands): pilot (3 SLMs x 2 runs, no edits in the review UI, note the evaluation ids into `train_ids.txt` and `heldout_ids.txt`), dry run + `--verify-export` + `--report-csv`, choose notebook values from the report, full data collection, write, train, load, validate, cleanup. Include the exact edits in the Colab notebook: cell 6 `MAX_SEQ_LENGTH`, cell 7 `max_prompt_length` and `num_train_epochs` (2 or 3 when pairs < 100); do a short T4 smoke run first and lower the values if memory runs out. State that each evaluation gives 2 pairs (`envelope_0` = OP criteria, `envelope_1` = A criteria) and that about 50 evaluations give about 100 pairs.
6. **Validation and acceptance** (copy the four steps and the thresholds from spec section 6; step 4 uses Model = Base and Model = the new version).
7. **Reading failures** (copy from spec section 6).
8. **Cleanup** with the exact command that the write step prints.

- [ ] **Step 2: Check the commands against the script**

Run: `cd apps && uv run --project server python -m server.scripts.seed_house_rule_edits --help`
Expected: the help text lists every flag used in the runbook and contains "must never be published". Fix any mismatch in the runbook.

- [ ] **Step 3: Full check and hand off for commit**

Run: `cd apps && uv run --project server pytest server/tests/scripts -q && uv run --project server ruff check server/scripts/seed_house_rule_edits.py server/tests/scripts/test_seed_house_rule_edits.py && uv run --project server ruff format --check server/scripts/seed_house_rule_edits.py server/tests/scripts/test_seed_house_rule_edits.py`
Expected: all pass.
Suggested commit: `docs(training): house-rule validation runbook`

---

## Self-Review Notes

- **Spec coverage:** rule and default edit set (Task 1); edited/control roles, score-only rows, only score-shaped criteria checked in the snapshot's strategy, fail-closed eligibility, skip counts (Task 2); report with per-evaluation table, totals, prompt lengths and notebook suggestions (Task 3); `--verify-export` (Task 4); expected-scores CSV (Task 5); write behind both confirmations, environment and fingerprint guards, dedicated user, run-id tag, one transaction, exporter integration (Task 6); cleanup with its guards (Task 7); runbook, publish rule, pollution rule (Task 8).
- **Consistency:** `CriterionPlan`, `EvaluationPlan`, `RunPlan`, `_decide`, `plan_evaluation`, `plan_run`, `render_report`, `count_exportable_pairs`, `build_expected_scores_rows`, `write_corrections`, `cleanup`, `_check_write_guards`, `_target_ack`, `main(argv, *, session_factory)` keep the same names and signatures across tasks. `_run_plan` is replaced in Tasks 4, 5 and 6 (each shows the changed lines; Task 6 shows the whole function).
- **Known executor checks:** verify `create_user`'s commit behavior (Task 6), and adapt the test helper if a model has another NOT NULL column (Task 2).
