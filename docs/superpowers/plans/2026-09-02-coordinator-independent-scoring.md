# Coordinator Independent 10-Criterion Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Coordinator agent score all 10 rubric criteria independently, through a curriculum-aware lens, using SME's current measurement-extraction + deterministic-calculator scoring mechanism copied into `coordinator/`.

**Architecture:** Coordinator gets its own frozen 10-criterion rubric snapshot (new Rubric v3, adapter_version 2). At evaluation time it packs the snapshot into 2 domain-based envelopes, makes one LLM call per envelope (with one repair retry), validates the returned grounded measurements, and maps each to a 1-4 band with pure calculators. Criterion A-05 keeps the `curriculum_alignment` strategy: the LLM extracts SLM objectives + curriculum-grounded alignment claims, ungrounded claims are demoted, and the score is a ratio band. The scoring machinery is copied from `sme/`, not imported.

**Tech Stack:** Python 3.12, FastAPI modular monolith, SQLAlchemy + Alembic, pydantic v2 contracts, pytest, uv, ruff. LLM access via `server.modules.agents.runtime.llm.RunLLMClient`.

**Spec:** `docs/superpowers/specs/2026-09-02-coordinator-independent-scoring-design.md`

## Global Constraints

- Run backend commands from the **repo root**, never inside `server/`. Always pass `--project server`.
- Lint: `uv run --project server ruff check server` — rules E, F, I, UP; **line length 88**.
- Tests: `uv run --project server pytest <path>`.
- Per-module layout under `server/modules/agents/coordinator/`: one file = one responsibility. No file imports from `server/modules/agents/sme/` — copy instead. Shared `server/modules/rubrics/**` (contracts, calculators, manifests) IS imported directly.
- Migrations must not import application code — embed any needed constants verbatim (see `server/alembic/versions/20260829_0002_backfill_gad_scoring_rule.py`).
- The user commits manually. Each task's final step stages the exact files and writes the commit message, but **do not run `git commit`** unless the user says so in that session — leave the tree staged/dirty and report.
- Commit message trailer (when the user does ask you to commit):
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01RzwtR4a3S2sTr5RFGtsrVx
  ```
- TDD: write the failing test, watch it fail, implement minimally, watch it pass.
- Coordinator's 10 criterion codes, in **snapshot order** (domain OP then domain A, matching `server/data/rubrics/rubrics.json`):
  `OP-01, OP-02, OP-03, OP-04, OP-05, A-01, A-02, A-03, A-04, A-05`
- Coordinator prompt budget setting: `settings.agent_total_prompt_budget_chars` (default 32000). No new setting.
- Coordinator temperature: `settings.get_agent_temperature("coordinator")` (falls back to global `llm_temperature`).

---

## File Structure

**New files (`server/modules/agents/coordinator/`):**

| File | Responsibility |
|---|---|
| `bands.py` | Pure band math. Verbatim copy of `sme/bands.py`. |
| `slicing.py` | `GAP_MARKER` + `downsample()` only. Trimmed copy of `sme/slicing.py`. |
| `packing.py` | `pack_domains()` — snapshot domains -> ≤3 criterion envelopes. Copy of `sme/packing.py`. |
| `prompt.py` | Envelope prompt construction + source downsampling + curriculum-context injection. Copy-adapted from `sme/prompt.py`. |
| `response.py` | Strict schema + parse + grounding of one envelope response, incl. `curriculum_alignment`. Copy-adapted from `sme/response.py`. |
| `scoring.py` | Measurement dict -> `CriterionScore` via pure calculators, incl. `score_curriculum_alignment`. Copy-adapted from `sme/scoring.py`. |
| `execution.py` | One envelope LLM call + one repair retry; second failure raises. Copy-adapted from `sme/execution.py`. |
| `summary.py` | `build_alignment_summary()` — deterministic result summary. Rewritten (small). |

**Rewritten:**
- `server/modules/agents/coordinator/agent.py` — the `Coordinator` class.

**Deleted:**
- `server/modules/agents/coordinator/extraction.py`
- `server/modules/agents/coordinator/curriculum.py`
- `server/tests/agents/coordinator/test_coordinator_contract.py`

**Modified (non-agent):**
- `server/modules/rubrics/manifests.py` — `COORDINATOR_MANIFEST_V1` widened to 10 criteria + 4 strategies + adapter_version 2.
- `server/scripts/seed_rubrics.py` — resolve all 10 coordinator strategies; `seed_coordinator_v3_if_needed`.
- `server/alembic/versions/20260902_0001_coordinator_rubric_v3.py` — new data migration.

**New tests (`server/tests/agents/coordinator/`):** `test_coordinator_bands.py`, `test_coordinator_slicing.py`, `test_coordinator_packing.py`, `test_coordinator_prompt.py`, `test_coordinator_response.py`, `test_coordinator_scoring.py`, `test_coordinator_execution.py`, `test_coordinator_agent.py`. Plus `server/tests/migrations/test_coordinator_rubric_v3_migration.py`.

---

## Task 1: Coordinator capability manifest -> 10 criteria, 4 strategies, adapter_version 2

**Files:**
- Modify: `server/modules/rubrics/manifests.py:283-303` (`COORDINATOR_MANIFEST_V1`)
- Test: `server/tests/rubrics/test_manifests.py` (add cases; file may not exist — if absent create `server/tests/rubrics/test_coordinator_manifest.py`)

**Interfaces:**
- Consumes: `AgentCapabilityManifest`, `StrategyCapability` (already in `manifests.py`).
- Produces: `get_agent_manifest("coordinator")` returns a manifest with `adapter_version == 2`, `min_criteria == 1`, `max_criteria == 10`, `allowed_criterion_codes` = the 10 codes, `supported_strategies == ("curriculum_alignment", "llm_rubric_guidance", "count_band", "ratio_band")`.

- [ ] **Step 1: Write the failing test**

Create/append `server/tests/rubrics/test_coordinator_manifest.py`:

```python
from server.modules.rubrics.manifests import get_agent_manifest

CODES = (
    "OP-01", "OP-02", "OP-03", "OP-04", "OP-05",
    "A-01", "A-02", "A-03", "A-04", "A-05",
)


def test_coordinator_manifest_supports_ten_criteria_and_four_strategies():
    m = get_agent_manifest("coordinator")
    assert m.adapter_version == 2
    assert m.min_criteria == 1
    assert m.max_criteria == 10
    assert set(m.allowed_criterion_codes) == set(CODES)
    assert set(m.supported_strategies) == {
        "curriculum_alignment",
        "llm_rubric_guidance",
        "count_band",
        "ratio_band",
    }
    shapes = {c.measurement_shape for c in m.capabilities}
    assert "curriculum_alignment" in shapes
    assert "grounded_instances" in shapes
    assert "qualifying_units" in shapes
    assert "grounded_score" in shapes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/rubrics/test_coordinator_manifest.py -v`
Expected: FAIL — `adapter_version == 1`, `max_criteria == 1`.

- [ ] **Step 3: Implement**

Replace the `COORDINATOR_MANIFEST_V1 = AgentCapabilityManifest(...)` block in `server/modules/rubrics/manifests.py` with:

```python
COORDINATOR_MANIFEST_V1 = AgentCapabilityManifest(
    agent_id="coordinator",
    adapter_key="coordinator",
    adapter_version=2,
    prompt_budget_setting="agent_total_prompt_budget_chars",
    supported_strategies=(
        "curriculum_alignment",
        "llm_rubric_guidance",
        "count_band",
        "ratio_band",
    ),
    supported_count_modes=("minimum_count",),
    supported_ratio_modes=("coverage_percentage",),
    capabilities=(
        StrategyCapability(
            strategy="curriculum_alignment",
            mode=None,
            measurement_shape="curriculum_alignment",
        ),
        StrategyCapability(
            strategy="llm_rubric_guidance",
            mode=None,
            measurement_shape="grounded_score",
        ),
        StrategyCapability(
            strategy="count_band",
            mode="minimum_count",
            measurement_shape="grounded_instances",
        ),
        StrategyCapability(
            strategy="ratio_band",
            mode="coverage_percentage",
            measurement_shape="qualifying_units",
        ),
    ),
    supported_measurement_shapes=(
        "curriculum_alignment",
        "grounded_score",
        "grounded_instances",
        "qualifying_units",
    ),
    min_criteria=1,
    max_criteria=10,
    default_prompt_budget_chars=32000,
    allowed_criterion_codes=(
        "OP-01", "OP-02", "OP-03", "OP-04", "OP-05",
        "A-01", "A-02", "A-03", "A-04", "A-05",
    ),
)
```

Leave the constant name `COORDINATOR_MANIFEST_V1` and its registry entry unchanged.

- [ ] **Step 4: Run tests**

Run: `uv run --project server pytest server/tests/rubrics/test_coordinator_manifest.py -v`
Expected: PASS.

Run: `uv run --project server pytest server/tests/rubrics/ -q`
Expected: existing manifest tests may assert the old coordinator shape — fix those assertions to the new values (10 criteria, adapter_version 2). Do not weaken unrelated assertions.

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/modules/rubrics/manifests.py`
Expected: clean.

- [ ] **Step 6: Stage**

```bash
git add server/modules/rubrics/manifests.py server/tests/rubrics/
```
Commit message: `feat(rubrics): widen coordinator manifest to 10 criteria, adapter_version 2`

---

## Task 2: Seed logic for Coordinator Rubric v3

**Files:**
- Modify: `server/scripts/seed_rubrics.py` — `_resolve_criterion_strategy` (around line 217), `seed_coordinator_v2_if_needed` (around line 592, rename + rewrite), `main()` (around line 470)
- Test: `server/tests/rubrics/test_rubrics.py` (has coordinator seed assertions today) + new `server/tests/rubrics/test_coordinator_v3_seed.py`

**Interfaces:**
- Consumes: existing `seed_rubrics.py` helpers — `activate_revision`, `get_form_definition_by_id`, `validate_form_definition`, models `RubricSet`, `RubricDomain`, `RubricCriterion`, `RubricAgentActivation`.
- Produces: `seed_coordinator_v3_if_needed(session) -> RubricSet | None` — idempotent; creates coordinator rubric version 3 (status `published`, adapter_key `coordinator`, adapter_version 2) with 10 criteria and activates it. `_resolve_criterion_strategy("coordinator", code, desc, {})` returns a valid `(strategy, config)` for every one of the 10 codes.

**Coordinator v3 criterion strategy configs** (copy of `SME_STRATEGY_CONFIGS` in this file, plus A-05 override):

```python
_COORDINATOR_STRATEGY_CONFIGS: dict[str, dict[str, Any]] = {
    "OP-01": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
        "short_sample": {
            "min_units": 4,
            "max_issues_4": 0,
            "max_issues_3": 1,
            "max_issues_2": 2,
        },
    },
    "OP-02": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 4,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "OP-03": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "OP-04": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "OP-05": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 3,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-01": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "A-02": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 5,
        "threshold_3": 3,
        "threshold_2": 2,
    },
    "A-03": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 4,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-04": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 3,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-05": {"strategy": "curriculum_alignment"},
}
```

> **Before writing:** open `server/scripts/seed_rubrics.py` and confirm the exact
> current shape of `SME_STRATEGY_CONFIGS` for OP-01..OP-05 and A-01..A-04. If any
> differ from the block above (e.g. OP-01 has no `short_sample`, or different
> thresholds), use the values actually in `SME_STRATEGY_CONFIGS` — the point is
> "same as SME today", not the literals transcribed here.

**Coordinator v3 criterion titles / descriptions:** copy from the `coordinator` v1 entry in `server/data/rubrics/rubrics.json` (it already lists all 10 with titles + descriptions), **except** A-05 title `"Curriculum Alignment"` and description:
`"Evaluate alignment between the student learning material's stated objectives and the confirmed course curriculum/syllabus topics."`

- [ ] **Step 1: Write the failing test**

Create `server/tests/rubrics/test_coordinator_v3_seed.py`:

```python
from server.modules.rubrics.models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.scripts.seed_rubrics import seed_coordinator_v3_if_needed

CODES = {
    "OP-01", "OP-02", "OP-03", "OP-04", "OP-05",
    "A-01", "A-02", "A-03", "A-04", "A-05",
}


def test_seed_coordinator_v3_creates_and_activates_ten_criteria(db_session):
    result = seed_coordinator_v3_if_needed(db_session)
    db_session.flush()
    assert result is not None
    assert result.version_number == 3
    assert result.adapter_version == 2
    assert result.status == "published"

    crits = (
        db_session.query(RubricCriterion)
        .join(RubricDomain)
        .filter(RubricDomain.rubric_set_id == result.rubric_set_id)
        .all()
    )
    assert {c.criterion_code for c in crits} == CODES
    a05 = next(c for c in crits if c.criterion_code == "A-05")
    assert a05.scoring_strategy == "curriculum_alignment"

    activation = (
        db_session.query(RubricAgentActivation)
        .filter_by(agent_id="coordinator")
        .one()
    )
    assert activation.rubric_set_id == result.rubric_set_id


def test_seed_coordinator_v3_is_idempotent(db_session):
    first = seed_coordinator_v3_if_needed(db_session)
    db_session.flush()
    second = seed_coordinator_v3_if_needed(db_session)
    db_session.flush()
    assert second is not None
    assert second.rubric_set_id == first.rubric_set_id
    count = (
        db_session.query(RubricSet)
        .filter_by(agent_id="coordinator", version_number=3)
        .count()
    )
    assert count == 1
```

> Check `server/tests/rubrics/conftest.py` for the DB session fixture name
> (`db_session`, `session`, or similar) and match it.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/rubrics/test_coordinator_v3_seed.py -v`
Expected: FAIL — `ImportError: cannot import name 'seed_coordinator_v3_if_needed'`.

- [ ] **Step 3: Implement**

In `server/scripts/seed_rubrics.py`:

1. Add the `_COORDINATOR_STRATEGY_CONFIGS` dict (above) near `SME_STRATEGY_CONFIGS`.

2. In `_resolve_criterion_strategy`, replace the branch
   `elif agent_id == "coordinator" and criterion_code == "A-05":` with:

```python
    elif agent_id == "coordinator":
        cfg = _COORDINATOR_STRATEGY_CONFIGS.get(criterion_code)
        if cfg:
            return cfg["strategy"], cfg
```

3. Rename `seed_coordinator_v2_if_needed` -> `seed_coordinator_v3_if_needed` and
   rewrite its body. Use the existing v2 helper as the structural template
   (existing-v3 check + validate + activation reconciliation, then the
   create-new path). The create path builds:
   - `RubricSet(agent_id="coordinator", version_number=3, status="published",
     adapter_key="coordinator", adapter_version=2, published_at=now, ...)`
   - two `RubricDomain` rows: `code="OP", title="Organization and Presentation",
     display_order=1` then `code="A", title="Assessment", display_order=2`
     (match the domain titles in `rubrics.json`)
   - 10 `RubricCriterion` rows (5 per domain, `display_order` 1..5 within each),
     `criterion_code`/`title`/`description` per the mapping above,
     `scoring_strategy`/`strategy_config` from
     `_resolve_criterion_strategy("coordinator", code, desc, {})`
   - `validate_form_definition(get_form_definition_by_id(session, set_id))` must
     be valid — raise `ValueError` with the issue messages if not
   - `activate_revision(session, "coordinator", set_id, actor_id=None,
     is_system=True)`

4. In `main()`, change `seed_coordinator_v2_if_needed(session)` ->
   `seed_coordinator_v3_if_needed(session)`.

5. Delete the now-unreferenced `seed_coordinator_v2_if_needed` body (it is
   replaced, not kept — its manifest re-validation would fail against
   adapter_version 2).

- [ ] **Step 4: Run tests**

Run: `uv run --project server pytest server/tests/rubrics/test_coordinator_v3_seed.py -v`
Expected: PASS.

Run: `uv run --project server pytest server/tests/rubrics/ -q`
Expected: update any test asserting coordinator v2 is the active revision or that coordinator has 1 criterion. Fix to v3 / 10 criteria.

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/scripts/seed_rubrics.py`

- [ ] **Step 6: Stage**

```bash
git add server/scripts/seed_rubrics.py server/tests/rubrics/
```
Commit message: `feat(rubrics): seed Coordinator Rubric v3 with 10 criteria`

---

## Task 3: Alembic migration — Coordinator Rubric v3

**Files:**
- Create: `server/alembic/versions/20260902_0001_coordinator_rubric_v3.py`
- Test: `server/tests/migrations/test_coordinator_rubric_v3_migration.py`

**Interfaces:**
- Consumes: current alembic head. Find it: `uv run --project server alembic heads` (expected `20260830_0002` or the merge revision `479684525d98` — set `down_revision` to whatever `alembic heads` prints).
- Produces: after `upgrade`, `rubric_agent_activations` for `coordinator` points at a `rubric_sets` row with `version_number = 3`, `adapter_version = 2`, and 10 `rubric_criteria` rows (A-05 `scoring_strategy = 'curriculum_alignment'`). After `downgrade`, it points back at `version_number = 2` and the v3 rows are gone.

- [ ] **Step 1: Write the failing test**

Create `server/tests/migrations/test_coordinator_rubric_v3_migration.py`:

```python
"""Coordinator Rubric v3 migration: upgrade activates 10-criterion v3, downgrade restores v2."""

import sqlalchemy as sa

# Follow the exact harness pattern used by the other files in
# server/tests/migrations/ (e.g. test_rubric_scoring_rule_migration.py) for
# obtaining an alembic config + engine and running upgrade/downgrade to a rev.

REV = "20260902_0001"
DOWN = "20260830_0002"  # replace with actual current head from `alembic heads`


def test_upgrade_activates_coordinator_v3(alembic_runner, alembic_engine):
    alembic_runner.migrate_up_to(REV)
    with alembic_engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT rs.version_number, rs.adapter_version "
                "FROM rubric_agent_activations a "
                "JOIN rubric_sets rs ON rs.rubric_set_id = a.rubric_set_id "
                "WHERE a.agent_id = 'coordinator'"
            )
        ).one()
        assert row.version_number == 3
        assert row.adapter_version == 2

        codes = {
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT c.criterion_code FROM rubric_criteria c "
                    "JOIN rubric_domains d ON d.rubric_domain_id = c.rubric_domain_id "
                    "JOIN rubric_sets rs ON rs.rubric_set_id = d.rubric_set_id "
                    "WHERE rs.agent_id = 'coordinator' AND rs.version_number = 3"
                )
            )
        }
        assert codes == {
            "OP-01", "OP-02", "OP-03", "OP-04", "OP-05",
            "A-01", "A-02", "A-03", "A-04", "A-05",
        }
        strat = conn.execute(
            sa.text(
                "SELECT c.scoring_strategy FROM rubric_criteria c "
                "JOIN rubric_domains d ON d.rubric_domain_id = c.rubric_domain_id "
                "JOIN rubric_sets rs ON rs.rubric_set_id = d.rubric_set_id "
                "WHERE rs.agent_id = 'coordinator' AND rs.version_number = 3 "
                "AND c.criterion_code = 'A-05'"
            )
        ).scalar_one()
        assert strat == "curriculum_alignment"


def test_downgrade_restores_coordinator_v2(alembic_runner, alembic_engine):
    alembic_runner.migrate_up_to(REV)
    alembic_runner.migrate_down_to(DOWN)
    with alembic_engine.connect() as conn:
        version = conn.execute(
            sa.text(
                "SELECT rs.version_number FROM rubric_agent_activations a "
                "JOIN rubric_sets rs ON rs.rubric_set_id = a.rubric_set_id "
                "WHERE a.agent_id = 'coordinator'"
            )
        ).scalar_one()
        assert version == 2
        remaining = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM rubric_sets "
                "WHERE agent_id = 'coordinator' AND version_number = 3"
            )
        ).scalar_one()
        assert remaining == 0
```

> Match the fixture names / helper style of the existing migration tests in
> `server/tests/migrations/` exactly — do not invent `alembic_runner` if that
> repo uses a different harness.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/migrations/test_coordinator_rubric_v3_migration.py -v`
Expected: FAIL — revision `20260902_0001` does not exist.

- [ ] **Step 3: Implement the migration**

Create `server/alembic/versions/20260902_0001_coordinator_rubric_v3.py`:

```python
"""Coordinator Rubric v3: 10-criterion independent scoring, adapter_version 2

Revision ID: 20260902_0001
Revises: 20260830_0002
Create Date: 2026-09-02
"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op

revision = "20260902_0001"
down_revision = "20260830_0002"  # replace with actual `alembic heads` output
branch_labels = None
depends_on = None

# Verbatim data — migrations must not import app code.
_DOMAINS = (
    ("OP", "Organization and Presentation", 1),
    ("A", "Assessment", 2),
)

# (code, domain_code, display_order, title, description, scoring_strategy, strategy_config)
_CRITERIA = (
    ("OP-01", "OP", 1, "Content Coherence",
     "Topics progress logically and coherently from unit to chapter.",
     "ratio_band",
     {"strategy": "ratio_band", "mode": "coverage_percentage",
      "threshold_4": 80.0, "threshold_3": 50.0, "threshold_2": 20.0,
      "short_sample": {"min_units": 4, "max_issues_4": 0,
                       "max_issues_3": 1, "max_issues_2": 2}}),
    ("OP-02", "OP", 2, "Interactivity",
     "Each lesson includes interactive elements with real task content.",
     "count_band",
     {"strategy": "count_band", "mode": "minimum_count",
      "threshold_4": 4, "threshold_3": 2, "threshold_2": 1}),
    ("OP-03", "OP", 3, "Clear Directions",
     "Task directions are clear and complete enough to be performed.",
     "ratio_band",
     {"strategy": "ratio_band", "mode": "coverage_percentage",
      "threshold_4": 80.0, "threshold_3": 50.0, "threshold_2": 20.0}),
    ("OP-04", "OP", 4, "Accurate Sections",
     "Paragraphs and sections are clear and internally consistent.",
     "ratio_band",
     {"strategy": "ratio_band", "mode": "coverage_percentage",
      "threshold_4": 80.0, "threshold_3": 50.0, "threshold_2": 20.0}),
    ("OP-05", "OP", 5, "Enhancement Activities",
     "Enhancement activities beyond the core lesson are provided.",
     "count_band",
     {"strategy": "count_band", "mode": "minimum_count",
      "threshold_4": 3, "threshold_3": 2, "threshold_2": 1}),
    ("A-01", "A", 1, "Learner Transformation",
     "Tasks engage students in transforming what they learn.",
     "ratio_band",
     {"strategy": "ratio_band", "mode": "coverage_percentage",
      "threshold_4": 80.0, "threshold_3": 50.0, "threshold_2": 20.0}),
    ("A-02", "A", 2, "Varied Assessment Tools",
     "Progress is assessed using varied assessment tools.",
     "count_band",
     {"strategy": "count_band", "mode": "minimum_count",
      "threshold_4": 5, "threshold_3": 3, "threshold_2": 2}),
    ("A-03", "A", 3, "Progress Monitoring",
     "The material keeps an on-going record of student progress.",
     "count_band",
     {"strategy": "count_band", "mode": "minimum_count",
      "threshold_4": 4, "threshold_3": 2, "threshold_2": 1}),
    ("A-04", "A", 4, "Prescriptive Feedback",
     "Positive, meaningful feedback and prescriptive intervention guides "
     "are provided.",
     "count_band",
     {"strategy": "count_band", "mode": "minimum_count",
      "threshold_4": 3, "threshold_3": 2, "threshold_2": 1}),
    ("A-05", "A", 5, "Curriculum Alignment",
     "Evaluate alignment between the student learning material's stated "
     "objectives and the confirmed course curriculum/syllabus topics.",
     "curriculum_alignment",
     {"strategy": "curriculum_alignment"}),
)


def upgrade():
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    set_id = uuid.uuid4()

    bind.execute(
        sa.text(
            "INSERT INTO rubric_sets (rubric_set_id, agent_id, name, "
            "version_number, status, adapter_key, adapter_version, "
            "published_at, created_at) VALUES (:sid, 'coordinator', "
            "'Coordinator Rubric v3', 3, 'published', 'coordinator', 2, "
            ":now, :now)"
        ),
        {"sid": str(set_id), "now": now},
    )

    domain_ids: dict[str, str] = {}
    for code, title, order in _DOMAINS:
        did = str(uuid.uuid4())
        domain_ids[code] = did
        bind.execute(
            sa.text(
                "INSERT INTO rubric_domains (rubric_domain_id, rubric_set_id, "
                "code, title, display_order) VALUES (:did, :sid, :code, "
                ":title, :order)"
            ),
            {"did": did, "sid": str(set_id), "code": code, "title": title,
             "order": order},
        )

    for (code, dom, order, title, desc, strat, cfg) in _CRITERIA:
        bind.execute(
            sa.text(
                "INSERT INTO rubric_criteria (rubric_criterion_id, "
                "rubric_domain_id, criterion_code, title, description, "
                "scoring_strategy, strategy_config, display_order) VALUES "
                "(:cid, :did, :code, :title, :desc, :strat, :cfg, :order)"
            ),
            {"cid": str(uuid.uuid4()), "did": domain_ids[dom], "code": code,
             "title": title, "desc": desc, "strat": strat,
             "cfg": sa.text("CAST(:cfgjson AS JSON)").bindparams(
                 cfgjson=__import__("json").dumps(cfg))
             if bind.dialect.name == "postgresql"
             else __import__("json").dumps(cfg),
             "order": order},
        )

    bind.execute(
        sa.text(
            "UPDATE rubric_agent_activations SET rubric_set_id = :sid, "
            "updated_at = :now WHERE agent_id = 'coordinator'"
        ),
        {"sid": str(set_id), "now": now},
    )


def downgrade():
    bind = op.get_bind()
    v2 = bind.execute(
        sa.text(
            "SELECT rubric_set_id FROM rubric_sets WHERE agent_id = "
            "'coordinator' AND version_number = 2"
        )
    ).scalar_one()
    bind.execute(
        sa.text(
            "UPDATE rubric_agent_activations SET rubric_set_id = :sid "
            "WHERE agent_id = 'coordinator'"
        ),
        {"sid": str(v2)},
    )
    bind.execute(
        sa.text(
            "DELETE FROM rubric_criteria WHERE rubric_domain_id IN ("
            "SELECT d.rubric_domain_id FROM rubric_domains d "
            "JOIN rubric_sets rs ON rs.rubric_set_id = d.rubric_set_id "
            "WHERE rs.agent_id = 'coordinator' AND rs.version_number = 3)"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM rubric_domains WHERE rubric_set_id IN ("
            "SELECT rubric_set_id FROM rubric_sets WHERE agent_id = "
            "'coordinator' AND version_number = 3)"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM rubric_sets WHERE agent_id = 'coordinator' "
            "AND version_number = 3"
        )
    )
```

> **JSON column binding:** the `strategy_config` column is `sa.JSON`. The
> conditional `CAST(... AS JSON)` above is ugly — before writing, check how
> `20260829_0004_dynamic_cid_forms.py` (or any migration that writes
> `rubric_criteria.strategy_config`) binds JSON, and copy that exact idiom
> instead. If none exists, pass a Python `dict` directly and let SQLAlchemy's
> JSON type adapt it (works for both sqlite and postgres): `"cfg": cfg` with
> the column typed via `sa.bindparam("cfg", type_=sa.JSON())`.

- [ ] **Step 4: Run tests**

Run: `uv run --project server pytest server/tests/migrations/test_coordinator_rubric_v3_migration.py -v`
Expected: PASS.

Run: `uv run --project server alembic upgrade head` then `uv run --project server alembic downgrade -1` then `uv run --project server alembic upgrade head` against a scratch DB — expected: no errors, head reached.

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/alembic/versions/20260902_0001_coordinator_rubric_v3.py`
(If ruff flags the `__import__("json")` hack, add `import json` at module top and use `json.dumps`.)

- [ ] **Step 6: Stage**

```bash
git add server/alembic/versions/20260902_0001_coordinator_rubric_v3.py server/tests/migrations/test_coordinator_rubric_v3_migration.py
```
Commit message: `feat(rubrics): migrate Coordinator to Rubric v3 (10 criteria)`

---

## Task 4: `coordinator/bands.py` and `coordinator/slicing.py`

**Files:**
- Create: `server/modules/agents/coordinator/bands.py`
- Create: `server/modules/agents/coordinator/slicing.py`
- Test: `server/tests/agents/coordinator/test_coordinator_bands.py`, `server/tests/agents/coordinator/test_coordinator_slicing.py`

**Interfaces:**
- Produces:
  - `coordinator.bands.ratio_band(numerator: int, denominator: int, *, scale: str = "moderate", empty_score: int = 1) -> RatioBand` where `RatioBand` has `.band: int`, `.pct: float | None`.
  - `coordinator.bands.count_band(count: int, thresholds: tuple[tuple[int, int], ...]) -> int`
  - `coordinator.slicing.GAP_MARKER: str` (`"\n\n[...]\n\n"`)
  - `coordinator.slicing.downsample(text: str, *, budget: int = 9000, windows: int = 6) -> str`

- [ ] **Step 1: Write the failing tests**

`server/tests/agents/coordinator/test_coordinator_bands.py`:

```python
from server.modules.agents.coordinator.bands import count_band, ratio_band


def test_ratio_band_moderate_thresholds():
    assert ratio_band(8, 10).band == 4
    assert ratio_band(5, 10).band == 3
    assert ratio_band(2, 10).band == 2
    assert ratio_band(1, 10).band == 1


def test_ratio_band_empty_denominator_scores_one():
    r = ratio_band(0, 0)
    assert r.band == 1
    assert r.pct is None


def test_count_band():
    thresholds = ((5, 4), (3, 3), (2, 2))
    assert count_band(6, thresholds) == 4
    assert count_band(3, thresholds) == 3
    assert count_band(1, thresholds) == 1
```

`server/tests/agents/coordinator/test_coordinator_slicing.py`:

```python
from server.modules.agents.coordinator.slicing import GAP_MARKER, downsample


def test_downsample_returns_text_unchanged_when_within_budget():
    text = "short document"
    assert downsample(text, budget=9000) == text


def test_downsample_samples_windows_and_marks_gaps_and_anchors_tail():
    text = "".join(f"para{i} " for i in range(4000))  # well over budget
    out = downsample(text, budget=600, windows=6)
    assert len(out) <= 600 + 5 * len(GAP_MARKER)
    assert GAP_MARKER in out
    assert out.endswith(text[-100:][-(600 // 6):])
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_bands.py server/tests/agents/coordinator/test_coordinator_slicing.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`coordinator/bands.py`: copy `server/modules/agents/sme/bands.py` **verbatim** (only the module docstring's spec path reference may be dropped). Keep `RatioBand`, `ratio_band`, `count_band`, `mean_band`, `__all__`.

`coordinator/slicing.py`: copy only the needed parts of `server/modules/agents/sme/slicing.py`:

```python
"""Whole-document downsampling for Coordinator envelope source text.

Independent copy of the shared helper (see
server/modules/agents/sme/slicing.py) so the coordinator package has no
import-time dependency on the sme package.
"""

from __future__ import annotations

GAP_MARKER = "\n\n[...]\n\n"


def downsample(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample ``windows`` evenly-spaced chunks spanning the whole document.

    Returns ``text`` unchanged when it already fits ``budget``. Otherwise
    samples ``windows`` chunks of ``budget // windows`` chars from evenly
    spaced start points, joined by ``GAP_MARKER``; the last window is
    anchored to the true end of the document.
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
    return GAP_MARKER.join(chunks)


__all__ = ["GAP_MARKER", "downsample"]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_bands.py server/tests/agents/coordinator/test_coordinator_slicing.py -v`
Expected: PASS. (If the tail-anchor assertion is brittle, relax it to `assert text[-chunk_size:] in out`.)

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/modules/agents/coordinator/bands.py server/modules/agents/coordinator/slicing.py`

- [ ] **Step 6: Stage**

```bash
git add server/modules/agents/coordinator/bands.py server/modules/agents/coordinator/slicing.py server/tests/agents/coordinator/test_coordinator_bands.py server/tests/agents/coordinator/test_coordinator_slicing.py
```
Commit message: `feat(coordinator): add copied band math and downsample helpers`

---

## Task 5: `coordinator/packing.py`

**Files:**
- Create: `server/modules/agents/coordinator/packing.py`
- Test: `server/tests/agents/coordinator/test_coordinator_packing.py`

**Interfaces:**
- Consumes: `server.modules.rubrics.contracts.DomainDefinition`, `CriterionDefinition`.
- Produces: `coordinator.packing.pack_domains(domains) -> tuple[tuple[CriterionDefinition, ...], ...]` — ≤3 envelopes, snapshot order preserved. For Coordinator's OP + A domains -> exactly 2 envelopes: `(OP-01..OP-05), (A-01..A-05)`.

- [ ] **Step 1: Write the failing test**

`server/tests/agents/coordinator/test_coordinator_packing.py`:

```python
import pytest

from server.modules.agents.coordinator.packing import pack_domains
from server.modules.agents.exceptions import AgentExecutionError

# Reuse the domain/criterion builders from the shared agent test helpers.
from server.tests.agents.helpers import make_domain  # confirm this exists


def test_op_and_a_domains_pack_into_two_ordered_envelopes():
    domains = (
        make_domain("OP", ["OP-01", "OP-02", "OP-03", "OP-04", "OP-05"]),
        make_domain("A", ["A-01", "A-02", "A-03", "A-04", "A-05"]),
    )
    envelopes = pack_domains(domains)
    assert len(envelopes) == 2
    assert [c.criterion_code for c in envelopes[0]] == [
        "OP-01", "OP-02", "OP-03", "OP-04", "OP-05"
    ]
    assert [c.criterion_code for c in envelopes[1]] == [
        "A-01", "A-02", "A-03", "A-04", "A-05"
    ]


def test_no_criteria_raises():
    with pytest.raises(AgentExecutionError):
        pack_domains(())
```

> If `server/tests/agents/helpers.py` has no `make_domain`, check what SME's
> packing tests use (`server/tests/agents/sme/`) and reuse that builder, or
> construct `DomainDefinition`/`CriterionDefinition` inline with
> `LlmRubricGuidanceConfig` configs.

- [ ] **Step 2: Run to verify fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_packing.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Copy `server/modules/agents/sme/packing.py` to `server/modules/agents/coordinator/packing.py` **verbatim**, then change the one user-facing string: `"SME snapshot contains no criteria"` -> `"Coordinator snapshot contains no criteria"`. Keep `domain_weight`, `pack_domains`, `__all__`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_packing.py -v`
Expected: PASS.

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/modules/agents/coordinator/packing.py`

- [ ] **Step 6: Stage**

```bash
git add server/modules/agents/coordinator/packing.py server/tests/agents/coordinator/test_coordinator_packing.py
```
Commit message: `feat(coordinator): add copied domain packing`

---

## Task 6: `coordinator/prompt.py`

**Files:**
- Create: `server/modules/agents/coordinator/prompt.py`
- Test: `server/tests/agents/coordinator/test_coordinator_prompt.py`

**Interfaces:**
- Consumes: `coordinator.slicing.downsample`, `coordinator.slicing.GAP_MARKER`; `server.modules.rubrics.contracts` configs incl. `CurriculumAlignmentConfig`; `server.modules.agents.exceptions.AgentExecutionError`.
- Produces:
  - `coordinator.prompt.REPAIR_SUFFIX: str`
  - `coordinator.prompt.build_envelope_prompt_and_source(criteria: tuple[CriterionDefinition, ...], canonical_source_text: str, curriculum_context: str, prompt_budget: int, prompt_preamble: str | None = None) -> tuple[str, str]` — returns `(prompt, source_packet)`. Injects a `=== CURRICULUM CONTEXT ===` block **only** when the envelope contains a criterion whose `strategy_config` is `CurriculumAlignmentConfig`.

**Coordinator preamble** (prepended to every envelope prompt, before any roadmap preamble):

```
You are the Program Coordinator evaluation agent for Student Learning
Materials (SLM). You judge each criterion the same way the Subject Matter
Expert does, but from a curriculum-alignment perspective: your role is to
confirm the material serves the confirmed course curriculum. For the
curriculum-alignment criterion you are given a CURRICULUM CONTEXT block —
every alignment claim you make about it must quote it verbatim.
```

**A-05 (`CurriculumAlignmentConfig`) criterion block** — the model emits objectives + alignment rows, never a score:

```
CRITERION: A-05
Title: <title>
Description: <description>
Strategy: Curriculum Objective Alignment
Instructions: Extract every learning objective STATED IN THE SLM as an
exact verbatim substring of the source text. For each objective, decide
whether the CURRICULUM CONTEXT addresses it. If addressed, copy the exact
verbatim span from CURRICULUM CONTEXT that supports it into
assessment_excerpt; if not, set is_aligned false and leave
assessment_excerpt null. Do NOT assign a score.
```

**A-05 example measurement**:

```json
{
  "criterion_id": "A-05",
  "criterion_title": "<title>",
  "alignments": [
    {
      "objective_text": "Exact verbatim objective excerpt from the SLM.",
      "is_aligned": true,
      "assessment_excerpt": "Exact verbatim span from the curriculum context.",
      "reasoning": "Why the curriculum span addresses this objective."
    }
  ],
  "summary": "Overview of objective-curriculum alignment."
}
```

- [ ] **Step 1: Write the failing test**

`server/tests/agents/coordinator/test_coordinator_prompt.py`:

```python
import json

import pytest

from server.modules.agents.coordinator.prompt import (
    REPAIR_SUFFIX,
    build_envelope_prompt_and_source,
)
from server.modules.agents.exceptions import AgentExecutionError
from server.tests.agents.helpers import make_criterion  # confirm / adapt

CURRICULUM = "Curriculum topic: photosynthesis converts light to chemical energy."


def test_curriculum_block_only_present_for_a05_envelope():
    op_env = (make_criterion("OP-02", strategy="count_band"),)
    a_env = (make_criterion("A-05", strategy="curriculum_alignment"),)

    op_prompt, _ = build_envelope_prompt_and_source(
        op_env, "doc text", CURRICULUM, prompt_budget=32000
    )
    a_prompt, _ = build_envelope_prompt_and_source(
        a_env, "doc text", CURRICULUM, prompt_budget=32000
    )
    assert "CURRICULUM CONTEXT" not in op_prompt
    assert "CURRICULUM CONTEXT" in a_prompt
    assert CURRICULUM in a_prompt


def test_preamble_and_repair_reservation():
    env = (make_criterion("A-01", strategy="ratio_band"),)
    prompt, _ = build_envelope_prompt_and_source(
        env, "doc text", CURRICULUM, prompt_budget=32000,
        prompt_preamble="Program roadmap context (advisory): Course code: CHEM1",
    )
    assert "Program Coordinator evaluation agent" in prompt
    assert "Program roadmap context (advisory)" in prompt
    assert len(prompt) + len(REPAIR_SUFFIX) <= 32000


def test_oversized_source_is_downsampled():
    env = (make_criterion("OP-01", strategy="ratio_band"),)
    big = "sentence. " * 20000
    _, packet = build_envelope_prompt_and_source(
        env, big, CURRICULUM, prompt_budget=6000
    )
    assert len(packet) < len(big)


def test_instructions_exceeding_budget_raise():
    env = (make_criterion("A-01", strategy="ratio_band"),)
    with pytest.raises(AgentExecutionError):
        build_envelope_prompt_and_source(env, "doc", CURRICULUM, prompt_budget=200)
```

> `make_criterion(code, strategy=...)` — if the shared helpers don't provide
> this, add a small local builder in the test that returns a
> `CriterionDefinition` with the right `strategy_config` type per `strategy`
> (`ratio_band` -> `RatioBandConfig(threshold_4=80, threshold_3=50, threshold_2=20)`,
> `count_band` -> `CountBandConfig(mode="minimum_count", threshold_4=4, threshold_3=2, threshold_2=1)`,
> `curriculum_alignment` -> `CurriculumAlignmentConfig()`,
> `llm_rubric_guidance` -> `LlmRubricGuidanceConfig(guidance="...")`).

- [ ] **Step 2: Run to verify fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Start from a **verbatim copy** of `server/modules/agents/sme/prompt.py`, then:

1. Change the import `from .slicing import GAP_MARKER` ->
   `from .slicing import GAP_MARKER, downsample`. Delete the local
   `downsample_source_text` function; use `downsample` from slicing (same
   algorithm). Where `sme/prompt.py` called `downsample_source_text(text,
   budget=available_for_source, windows=6)`, call
   `downsample(text, budget=available_for_source, windows=6)`.
2. `REPAIR_SUFFIX` — change `category=SME_INVALID` -> `category=COORDINATOR_INVALID`.
3. Add `CurriculumAlignmentConfig` to the contracts import.
4. In `_criterion_prompt_block`, add an `isinstance(config, CurriculumAlignmentConfig)`
   branch emitting the A-05 block text above.
5. In `_example_measurement`, add a `CurriculumAlignmentConfig` branch returning
   the A-05 example dict above.
6. In `build_envelope_prompt`, replace the SME evaluator-instructions string
   with the **Coordinator preamble** above, and add a `curriculum_context`
   parameter (`str`). After the source-text block, when
   `any(isinstance(c.strategy_config, CurriculumAlignmentConfig) for c in
   criteria)`, append:
   ```
   === CURRICULUM CONTEXT ===
   {curriculum_context}
   === END CURRICULUM CONTEXT ===
   ```
   Otherwise omit it entirely.
7. `build_envelope_prompt_and_source` gains a `curriculum_context: str`
   positional parameter (after `canonical_source_text`), threaded into both
   `build_envelope_prompt` calls. The `template_without_source` measurement of
   available budget must pass the real `curriculum_context` (so the reserved
   space accounts for it), with `source_text=""`.
8. Keep the two `AgentExecutionError` budget guards. Their messages: replace
   `"SME "` -> `"Coordinator "`.
9. `__all__` = `["REPAIR_SUFFIX", "build_envelope_prompt", "build_envelope_prompt_and_source"]`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_prompt.py -v`
Expected: PASS.

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/modules/agents/coordinator/prompt.py`

- [ ] **Step 6: Stage**

```bash
git add server/modules/agents/coordinator/prompt.py server/tests/agents/coordinator/test_coordinator_prompt.py
```
Commit message: `feat(coordinator): add grouped-scoring prompt builder with curriculum context`

---

## Task 7: `coordinator/response.py`

**Files:**
- Create: `server/modules/agents/coordinator/response.py`
- Test: `server/tests/agents/coordinator/test_coordinator_response.py`

**Interfaces:**
- Consumes: `server.modules.rubrics.contracts` (all configs + `CurriculumAlignmentMeasurement`, `ObjectiveAlignmentRow`); `coordinator.slicing.GAP_MARKER`; `AgentExecutionError`.
- Produces:
  - `coordinator.response.build_envelope_schema(criteria) -> dict` — JSON schema incl. a `curriculum_alignment` item shape for A-05.
  - `coordinator.response.parse_and_validate_envelope_response(raw_response: str, criteria: tuple[CriterionDefinition, ...], source_packet: str, curriculum_context: str) -> dict[str, Any]` — returns `{"summary": str, "criterion_measurements": [dict, ...]}`. For a `curriculum_alignment` criterion: every returned `alignments[i].objective_text` must be a verbatim substring of `source_packet`; every row with `is_aligned == true` whose `assessment_excerpt` is **not** a verbatim substring of `curriculum_context` is **demoted** in-place to `is_aligned = false, assessment_excerpt = None`, and a running `grounding_rejected_count` is attached to the returned measurement dict as `_grounding_rejected_count: int` (private key, consumed by scoring).

- [ ] **Step 1: Write the failing test**

`server/tests/agents/coordinator/test_coordinator_response.py`:

```python
import json

import pytest

from server.modules.agents.coordinator.response import (
    parse_and_validate_envelope_response,
)
from server.modules.agents.exceptions import AgentExecutionError
from server.tests.agents.helpers import make_criterion  # adapt as in Task 6

SOURCE = "Objective: explain photosynthesis. Objective: describe cell walls."
CURRICULUM = "Unit 2 covers photosynthesis and light reactions in detail."


def _wrap(measurements):
    return json.dumps({"summary": "ok", "criterion_measurements": measurements})


def test_curriculum_alignment_grounded_row_kept():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    raw = _wrap([{
        "criterion_id": "A-05",
        "criterion_title": crit.title,
        "alignments": [{
            "objective_text": "Objective: explain photosynthesis.",
            "is_aligned": True,
            "assessment_excerpt": "Unit 2 covers photosynthesis and light reactions",
            "reasoning": "direct topic match",
        }],
    }])
    out = parse_and_validate_envelope_response((crit,), raw, SOURCE, CURRICULUM) \
        if False else parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    m = out["criterion_measurements"][0]
    assert m["alignments"][0]["is_aligned"] is True
    assert m["_grounding_rejected_count"] == 0


def test_curriculum_alignment_ungrounded_row_demoted():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    raw = _wrap([{
        "criterion_id": "A-05",
        "criterion_title": crit.title,
        "alignments": [{
            "objective_text": "Objective: describe cell walls.",
            "is_aligned": True,
            "assessment_excerpt": "Curriculum discusses mitochondria at length",
            "reasoning": "made up",
        }],
    }])
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    m = out["criterion_measurements"][0]
    assert m["alignments"][0]["is_aligned"] is False
    assert m["alignments"][0]["assessment_excerpt"] is None
    assert m["_grounding_rejected_count"] == 1


def test_objective_text_not_in_source_rejected():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    raw = _wrap([{
        "criterion_id": "A-05",
        "criterion_title": crit.title,
        "alignments": [{
            "objective_text": "Objective: fabricate quantum tunneling.",
            "is_aligned": False,
            "assessment_excerpt": None,
        }],
    }])
    with pytest.raises(AgentExecutionError):
        parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)


def test_non_curriculum_criteria_still_validated_like_sme():
    crit = make_criterion("OP-02", strategy="count_band")
    raw = _wrap([{
        "criterion_id": "OP-02",
        "criterion_title": crit.title,
        "instances": [{"excerpt": "Objective: explain photosynthesis."}],
    }])
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    assert out["criterion_measurements"][0]["instances"][0]["excerpt"] in SOURCE
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_response.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Start from a **verbatim copy** of `server/modules/agents/sme/response.py`, then:

1. Rename `SME_TEXT_MAX` -> `COORD_TEXT_MAX` (value 2000). Update all references.
2. Change all `AgentExecutionError` message prefixes `"SME "` -> `"Coordinator "`.
3. Import `CurriculumAlignmentConfig`, `CurriculumAlignmentMeasurement`,
   `ObjectiveAlignmentRow` from `server.modules.rubrics.contracts`.
4. `_criterion_schema`: add a `CurriculumAlignmentConfig` branch:
   ```python
   if isinstance(config, CurriculumAlignmentConfig):
       return {
           "type": "object",
           "additionalProperties": False,
           "required": ["criterion_id", "criterion_title", "alignments"],
           "properties": {
               "criterion_id": {"const": criterion.criterion_code},
               "criterion_title": {"const": criterion.title},
               "alignments": {
                   "type": "array",
                   "maxItems": 100,
                   "items": {
                       "type": "object",
                       "additionalProperties": False,
                       "required": ["objective_text", "is_aligned"],
                       "properties": {
                           "objective_text": {
                               "type": "string", "minLength": 1,
                               "maxLength": COORD_TEXT_MAX,
                           },
                           "is_aligned": {"type": "boolean"},
                           "assessment_excerpt": {
                               "anyOf": [
                                   {"type": "string", "minLength": 1,
                                    "maxLength": COORD_TEXT_MAX},
                                   {"type": "null"},
                               ]
                           },
                           "reasoning": _optional_string_schema(COORD_TEXT_MAX),
                       },
                   },
               },
               "summary": _optional_string_schema(COORD_TEXT_MAX),
           },
       }
   ```
5. `parse_and_validate_envelope_response`: add a `curriculum_context: str`
   parameter (after `source_packet`). Add a `CurriculumAlignmentConfig` branch
   in the per-measurement `if/elif` chain, before the final `else`:
   - allowed keys: `{"criterion_id", "criterion_title", "alignments", "summary"}`
   - `alignments` must be a list, ≤ 100 items
   - for each row: exact keys subset of
     `{"objective_text", "is_aligned", "assessment_excerpt", "reasoning"}` with
     `objective_text` + `is_aligned` required
   - `objective_text`: non-empty, trimmed, ≤ `COORD_TEXT_MAX`, and
     `GAP_MARKER.strip() not in it` and `it in source_packet` — else raise
     `AgentExecutionError("Coordinator '<cid>' objective_text is not an exact
     substring of source text")`
   - `is_aligned` must be `bool`
   - `assessment_excerpt`: `None` or non-empty trimmed str ≤ `COORD_TEXT_MAX`
   - `reasoning`: `None` or `_is_strict_optional_text`
   - **demotion pass:** initialise `rejected = 0`. For each row, if
     `is_aligned is True`: if `assessment_excerpt` is a non-empty string and
     `assessment_excerpt.strip() in curriculum_context`, keep it; else set
     `row["is_aligned"] = False`, `row["assessment_excerpt"] = None`,
     `rejected += 1`. If `is_aligned is False`, force
     `row["assessment_excerpt"] = None`.
   - after the loop, set `m["_grounding_rejected_count"] = rejected` on the
     validated measurement dict.
6. The final `validated_measurements.append(dict(m))` must preserve the
   `_grounding_rejected_count` key for curriculum measurements (it will, since
   it's a plain key on `m`).
7. `__all__` unchanged names (`build_envelope_schema`,
   `parse_and_validate_envelope_response`).

- [ ] **Step 4: Run to verify pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_response.py -v`
Expected: PASS. Fix the `if False else` line in the first test to a plain call — it is a placeholder guarding argument order; the real signature is `parse_and_validate_envelope_response(raw, criteria, source_packet, curriculum_context)`.

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/modules/agents/coordinator/response.py`

- [ ] **Step 6: Stage**

```bash
git add server/modules/agents/coordinator/response.py server/tests/agents/coordinator/test_coordinator_response.py
```
Commit message: `feat(coordinator): add envelope response schema, parsing, and curriculum grounding`

---

## Task 8: `coordinator/scoring.py`

**Files:**
- Create: `server/modules/agents/coordinator/scoring.py`
- Test: `server/tests/agents/coordinator/test_coordinator_scoring.py`

**Interfaces:**
- Consumes: `server.modules.rubrics.strategies.calculators` (`score_count`, `score_ratio`, `normalize_llm_guidance_score`); `server.modules.rubrics.contracts` configs + measurement DTOs; `coordinator.bands.ratio_band`; `server.modules.agents.contracts.CriterionScore`.
- Produces:
  - `coordinator.scoring.score_curriculum_alignment(criterion: CriterionDefinition, measurement_dict: dict[str, Any]) -> CriterionScore` — `aligned = number of rows with is_aligned == true`, `total = len(alignments)`, `band = ratio_band(aligned, total, scale="moderate").band`; justification states `aligned/total` and the `_grounding_rejected_count`; evidence = the kept `assessment_excerpt` values (≤ 8).
  - `coordinator.scoring.score_criterion_measurement(criterion, measurement_dict) -> CriterionScore` — dispatches: `CurriculumAlignmentConfig` -> `score_curriculum_alignment`; otherwise identical to SME's.
  - `coordinator.scoring.score_envelope(criteria, parsed_response) -> tuple[CriterionScore, ...]`

- [ ] **Step 1: Write the failing test**

`server/tests/agents/coordinator/test_coordinator_scoring.py`:

```python
from server.modules.agents.coordinator.scoring import (
    score_criterion_measurement,
    score_curriculum_alignment,
)
from server.tests.agents.helpers import make_criterion  # adapt as before


def _alignment_measurement(rows, rejected=0):
    return {
        "criterion_id": "A-05",
        "criterion_title": "Curriculum Alignment",
        "alignments": rows,
        "_grounding_rejected_count": rejected,
    }


def test_curriculum_alignment_band_boundaries():
    crit = make_criterion("A-05", strategy="curriculum_alignment")

    all_aligned = [
        {"objective_text": f"o{i}", "is_aligned": True,
         "assessment_excerpt": f"c{i}", "reasoning": None}
        for i in range(10)
    ]
    assert score_curriculum_alignment(crit, _alignment_measurement(all_aligned)).score == 4

    half = [
        {"objective_text": f"o{i}", "is_aligned": i < 5,
         "assessment_excerpt": f"c{i}" if i < 5 else None, "reasoning": None}
        for i in range(10)
    ]
    assert score_curriculum_alignment(crit, _alignment_measurement(half)).score == 3

    one = [
        {"objective_text": f"o{i}", "is_aligned": i == 0,
         "assessment_excerpt": "c0" if i == 0 else None, "reasoning": None}
        for i in range(10)
    ]
    assert score_curriculum_alignment(crit, _alignment_measurement(one)).score == 1


def test_curriculum_alignment_no_objectives_scores_one():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    s = score_curriculum_alignment(crit, _alignment_measurement([]))
    assert s.score == 1


def test_curriculum_alignment_justification_reports_rejections():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    rows = [{"objective_text": "o0", "is_aligned": True,
             "assessment_excerpt": "c0", "reasoning": None}]
    s = score_curriculum_alignment(crit, _alignment_measurement(rows, rejected=2))
    assert "2" in s.justification


def test_count_band_criterion_delegates_to_shared_calculator():
    crit = make_criterion("OP-02", strategy="count_band")  # thresholds 4/2/1
    m = {
        "criterion_id": "OP-02",
        "criterion_title": crit.title,
        "instances": [{"excerpt": f"x{i}"} for i in range(4)],
    }
    assert score_criterion_measurement(crit, m).score == 4
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Start from a **verbatim copy** of `server/modules/agents/sme/scoring.py`, then:

1. Add imports: `from server.modules.rubrics.contracts import CurriculumAlignmentConfig`
   and `from .bands import ratio_band`.
2. Add `score_curriculum_alignment`:

```python
def score_curriculum_alignment(
    criterion: CriterionDefinition,
    measurement_dict: dict[str, Any],
) -> CriterionScore:
    """Score A-05 from grounded curriculum alignment rows (post-demotion)."""
    rows = measurement_dict.get("alignments", [])
    total = len(rows)
    aligned_rows = [r for r in rows if r.get("is_aligned") is True]
    aligned = len(aligned_rows)
    rejected = int(measurement_dict.get("_grounding_rejected_count", 0))

    band = ratio_band(aligned, total, scale="moderate")
    if total == 0:
        justification = (
            "Curriculum alignment: no objectives found in the SLM. Score 1."
        )
    else:
        pct = band.pct if band.pct is not None else 0.0
        rej = (
            f" ({rejected} unsupported claim(s) rejected)" if rejected else ""
        )
        justification = (
            f"Curriculum alignment: {aligned}/{total} objective(s) addressed "
            f"by the course curriculum ({pct:.1f}% coverage){rej}. "
            f"Score {band.band}."
        )
    evidence = tuple(
        str(r["assessment_excerpt"])
        for r in aligned_rows
        if r.get("assessment_excerpt")
    )[:8]
    return CriterionScore(
        criterion_id=criterion.criterion_code,
        criterion_title=criterion.title,
        score=band.band,
        justification=justification,
        chunk_ids=(),
        evidence=evidence,
    )
```

3. In `score_criterion_measurement`, add as the **first** branch:

```python
    if isinstance(config, CurriculumAlignmentConfig):
        return score_curriculum_alignment(criterion, measurement_dict)
```

4. `score_envelope` is unchanged (it already `zip`s criteria with
   `parsed_response["criterion_measurements"]`).
5. `__all__` — add `"score_curriculum_alignment"`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_scoring.py -v`
Expected: PASS.

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/modules/agents/coordinator/scoring.py`

- [ ] **Step 6: Stage**

```bash
git add server/modules/agents/coordinator/scoring.py server/tests/agents/coordinator/test_coordinator_scoring.py
```
Commit message: `feat(coordinator): add measurement scoring with curriculum-alignment band`

---

## Task 9: `coordinator/execution.py`

**Files:**
- Create: `server/modules/agents/coordinator/execution.py`
- Test: `server/tests/agents/coordinator/test_coordinator_execution.py`

**Interfaces:**
- Consumes: `coordinator.prompt.build_envelope_prompt_and_source`, `coordinator.prompt.REPAIR_SUFFIX`, `coordinator.response.build_envelope_schema`, `coordinator.response.parse_and_validate_envelope_response`, `coordinator.scoring.score_envelope`; `server.core.config.get_settings`; `server.core.llm.ResponseContract`; `server.modules.agents.runtime.llm.RunLLMClient` + `error_reference`; `AgentExecutionError`, `AgentLLMError`.
- Produces: `coordinator.execution.execute_envelope(envelope_idx: int, criteria: tuple[CriterionDefinition, ...], client: RunLLMClient, canonical_source_text: str, curriculum_context: str, *, prompt_preamble: str | None = None, temperature: float | None = None, deadline: float | None = None) -> tuple[tuple[CriterionScore, ...], str, dict[str, Any], bool]` — `(scores, prompt_text, parsed_response_dict, repair_occurred)`. Raises `AgentExecutionError` if validation fails twice.

- [ ] **Step 1: Write the failing test**

`server/tests/agents/coordinator/test_coordinator_execution.py`:

```python
import json

import pytest

from server.modules.agents.coordinator.execution import execute_envelope
from server.modules.agents.exceptions import AgentExecutionError
from server.tests.agents.helpers import make_criterion, FakeRunLLMClient  # adapt

SOURCE = "Objective: explain photosynthesis."
CURRICULUM = "Unit 2 covers photosynthesis."


def _good_response(crit):
    return json.dumps({
        "summary": "ok",
        "criterion_measurements": [{
            "criterion_id": "A-05",
            "criterion_title": crit.title,
            "alignments": [{
                "objective_text": "Objective: explain photosynthesis.",
                "is_aligned": True,
                "assessment_excerpt": "Unit 2 covers photosynthesis",
                "reasoning": None,
            }],
        }],
    })


def test_success_first_try(monkeypatch):
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    client = FakeRunLLMClient(responses=[_good_response(crit)])
    scores, prompt, parsed, repaired = execute_envelope(
        1, (crit,), client, SOURCE, CURRICULUM
    )
    assert repaired is False
    assert scores[0].criterion_id == "A-05"
    assert "criterion_measurements" in parsed


def test_repair_once_then_succeed():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    client = FakeRunLLMClient(responses=["not json", _good_response(crit)])
    scores, _, _, repaired = execute_envelope(1, (crit,), client, SOURCE, CURRICULUM)
    assert repaired is True
    assert scores[0].score >= 1


def test_second_failure_raises():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    client = FakeRunLLMClient(responses=["not json", "still not json"])
    with pytest.raises(AgentExecutionError):
        execute_envelope(1, (crit,), client, SOURCE, CURRICULUM)
```

> Check `server/tests/agents/` for an existing fake/stub `RunLLMClient`
> (SME's execution tests must use one). Reuse it; only add a `responses`
> queue if it lacks one.

- [ ] **Step 2: Run to verify fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_execution.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Start from a **verbatim copy** of `server/modules/agents/sme/execution.py`, then:

1. Imports: from `.prompt` import `REPAIR_SUFFIX`, `build_envelope_prompt_and_source`;
   from `.response` import `build_envelope_schema`, `parse_and_validate_envelope_response`;
   from `.scoring` import `score_envelope`.
2. `execute_envelope` signature gains `curriculum_context: str` (positional,
   after `canonical_source_text`).
3. `prompt_budget = settings.agent_total_prompt_budget_chars` (not
   `sme_total_prompt_budget_chars`).
4. `build_envelope_prompt_and_source(criteria, canonical_source_text,
   curriculum_context, prompt_budget=prompt_budget,
   prompt_preamble=prompt_preamble)`.
5. Schema name: `name=f"coordinator_envelope_{envelope_idx}"`.
6. `temp = ... settings.get_agent_temperature("coordinator")`.
7. `parse_and_validate_envelope_response(completion.content, criteria,
   source_packet, curriculum_context)` — both the first call and the repair
   call.
8. Log label `[SME_REPAIR]` -> `[COORDINATOR_REPAIR]`. Error strings
   `"SME "` -> `"Coordinator "`.
9. `__all__ = ["execute_envelope"]`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_execution.py -v`
Expected: PASS.

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/modules/agents/coordinator/execution.py`

- [ ] **Step 6: Stage**

```bash
git add server/modules/agents/coordinator/execution.py server/tests/agents/coordinator/test_coordinator_execution.py
```
Commit message: `feat(coordinator): add envelope LLM transport with repair-once`

---

## Task 10: `coordinator/summary.py` and the `Coordinator` agent rewrite

**Files:**
- Create: `server/modules/agents/coordinator/summary.py`
- Rewrite: `server/modules/agents/coordinator/agent.py`
- Delete: `server/modules/agents/coordinator/extraction.py`, `server/modules/agents/coordinator/curriculum.py`, `server/tests/agents/coordinator/test_coordinator_contract.py`
- Test: `server/tests/agents/coordinator/test_coordinator_agent.py`

**Interfaces:**
- Consumes: `coordinator.packing.pack_domains`, `coordinator.execution.execute_envelope`, `coordinator.summary.build_alignment_summary`; `server.modules.rubrics.snapshot_contracts.EvaluationFormSnapshotDTO`; `server.modules.rubrics.contracts.CurriculumAlignmentConfig`, `DomainDefinition`; `server.modules.agents.contracts.AgentEvaluationResult`, `CriterionScore`; `RunLLMClient`; `sanitize_provenance`; `get_llm_model_name`.
- Produces: `Coordinator` class with class attrs `agent_name = "coordinator"`, `rubric_source_type = "rubric_coord"`, `reference_source_types = ("syllabus",)`, `domain_keywords = (...)` (keep the existing tuple from the current `agent.py`), `__init__(self, *, llm_client=None)`, and:

```python
def run(
    self,
    *,
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
    form_snapshot: EvaluationFormSnapshotDTO,
    chunk_infos: list[dict[str, Any]],
    context_text: str | None = None,
    prompt_version_id: uuid.UUID | None = None,
    llm_client: Any | None = None,
    reference_document_ids: dict[str, Any] | None = None,
    roadmap_context: dict[str, Any] | None = None,
    canonical_source_text: str | None = None,
    curriculum_id: uuid.UUID | None = None,
    curriculum_context: str | None = None,
    **kwargs: Any,
) -> AgentEvaluationResult: ...
```

**`build_alignment_summary`** (`coordinator/summary.py`) — deterministic, no LLM:

```python
from __future__ import annotations

from ..contracts import CriterionScore

_WEAK_THRESHOLD = 2


def build_alignment_summary(criterion_scores: tuple[CriterionScore, ...]) -> str:
    """One-line deterministic summary of Coordinator's 10-criterion result."""
    if not criterion_scores:
        return ""
    a05 = next((c for c in criterion_scores if c.criterion_id == "A-05"), None)
    weak = sorted(
        (c for c in criterion_scores if c.score <= _WEAK_THRESHOLD),
        key=lambda c: c.score,
    )
    parts: list[str] = []
    if a05 is not None:
        parts.append(f"Curriculum alignment (A-05) scored {a05.score}/4.")
    if weak:
        titles = ", ".join(c.criterion_title for c in weak)
        parts.append(f"Weakest areas: {titles}.")
    else:
        parts.append("No criteria scored below 3.")
    return " ".join(parts)


__all__ = ["build_alignment_summary"]
```

**`agent.py` snapshot validation** — a Coordinator-local function:

```python
def _validate_coordinator_snapshot(
    form_snapshot: EvaluationFormSnapshotDTO,
    evaluation_id: uuid.UUID,
    agent_name: str,
) -> tuple[DomainDefinition, ...]:
    if not isinstance(form_snapshot, EvaluationFormSnapshotDTO):
        raise AgentExecutionError(
            "Coordinator requires a valid EvaluationFormSnapshotDTO"
        )
    if form_snapshot.agent_id != agent_name:
        raise AgentExecutionError(
            f"Snapshot agent_id '{form_snapshot.agent_id}' does not match "
            f"'{agent_name}'"
        )
    if form_snapshot.evaluation_id != evaluation_id:
        raise AgentExecutionError(
            f"Snapshot evaluation_id '{form_snapshot.evaluation_id}' does not "
            f"match '{evaluation_id}'"
        )
    if (
        form_snapshot.adapter_key != agent_name
        or form_snapshot.adapter_version != 2
    ):
        raise AgentExecutionError(
            f"Invalid snapshot adapter key '{form_snapshot.adapter_key}' or "
            f"version {form_snapshot.adapter_version}"
        )
    domains = form_snapshot.form.domains
    codes = [c.criterion_code for d in domains for c in d.criteria]
    if len(codes) != 10 or len(set(codes)) != 10:
        raise AgentExecutionError(
            f"Coordinator snapshot must contain exactly 10 unique criteria, "
            f"found {len(codes)}"
        )
    a05 = next(
        (c for d in domains for c in d.criteria if c.criterion_code == "A-05"),
        None,
    )
    if a05 is None or not isinstance(a05.strategy_config, CurriculumAlignmentConfig):
        raise AgentExecutionError(
            "Coordinator snapshot criterion A-05 must use CurriculumAlignmentConfig"
        )
    return domains
```

**`agent.py` `run()` body** (after copying `_format_roadmap_note` from the current
`curriculum.py::format_roadmap_note` — rename to a module-level function):

```python
    del kwargs, prompt_version_id, context_text
    domains = _validate_coordinator_snapshot(
        form_snapshot, evaluation_id, self.agent_name
    )
    if not chunk_infos:
        raise AgentExecutionError("document chunks are required for evaluation")

    full_text = canonical_source_text
    if not full_text or not full_text.strip():
        raise AgentExecutionError("canonical source text is required")

    curriculum_id = curriculum_id or (reference_document_ids or {}).get("curriculum")
    if (
        curriculum_id is None
        or not isinstance(curriculum_context, str)
        or not curriculum_context.strip()
    ):
        raise AgentExecutionError(
            "Coordinator requires curriculum_id and authoritative curriculum context"
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
            requested_model=getattr(client, "model", None) or get_llm_model_name(),
        )
    )

    start = time.perf_counter()
    roadmap_note = _format_roadmap_note(roadmap_context) or None
    envelopes = pack_domains(domains)
    all_scores: list[CriterionScore] = []
    envelope_prompts: dict[str, str] = {}
    envelope_responses: dict[str, dict[str, Any]] = {}
    any_repair = False
    grounding_rejected = 0

    for idx, env_criteria in enumerate(envelopes):
        env_key = f"envelope_{idx}"
        scores, prompt_text, parsed, repaired = execute_envelope(
            idx,
            env_criteria,
            adapter,
            full_text,
            curriculum_text,
            prompt_preamble=roadmap_note,
        )
        all_scores.extend(scores)
        envelope_prompts[env_key] = prompt_text
        envelope_responses[env_key] = parsed
        any_repair = any_repair or repaired
        for m in parsed.get("criterion_measurements", []):
            grounding_rejected += int(m.get("_grounding_rejected_count", 0))

    criterion_scores = tuple(all_scores)
    expected = tuple(c.criterion_code for d in domains for c in d.criteria)
    if tuple(s.criterion_id for s in criterion_scores) != expected:
        raise AgentExecutionError(
            "Coordinator scored criterion order does not match the frozen snapshot"
        )
    subtotal = sum(s.score for s in criterion_scores) / len(criterion_scores)
    total_seconds = time.perf_counter() - start
    actual_model = (
        adapter.actual_model
        if adapter.actual_model != "unknown"
        else adapter.requested_model
    )

    provenance = {
        "requested_model": adapter.requested_model,
        "actual_model": actual_model,
        "fallback_occurred": adapter.fallback_occurred,
        "repair_occurred": any_repair,
        "grouped_calls": len(envelopes),
        "logical_calls": adapter.telemetry.get("call_count", 0),
        "physical_attempts": adapter.telemetry.get("attempt_count", 0),
        "input_tokens": adapter.telemetry.get("prompt_tokens", 0),
        "output_tokens": adapter.telemetry.get("completion_tokens", 0),
        "truncation_count": adapter.telemetry.get("cap_hit_count", 0),
        "cap_hit_count": adapter.telemetry.get("cap_hit_count", 0),
        "provider_seconds_ms": round(
            adapter.telemetry.get("provider_seconds", 0) * 1000
        ),
        "grounding_rejected_count": grounding_rejected,
    }

    return AgentEvaluationResult(
        agent_name=self.agent_name,
        evaluation_id=evaluation_id,
        document_id=document_id,
        subtotal=subtotal,
        criterion_scores=criterion_scores,
        summary=build_alignment_summary(criterion_scores),
        model_name=actual_model,
        processing_seconds=total_seconds,
        token_count=len(full_text.split()),
        prompt_version_id=None,
        success=True,
        metadata={
            "group_prompts": envelope_prompts,
            "group_responses": envelope_responses,
        },
        provenance=sanitize_provenance(provenance),
    )
```

> The `_grounding_rejected_count` private key must be **stripped** from the
> measurements before they land in `metadata["group_responses"]` — synthesis
> serialises that payload and may reject unknown keys / it pollutes the DPO
> snapshot. In the loop, after reading it for the provenance tally, do:
> `m.pop("_grounding_rejected_count", None)`. Do this on a copy if `parsed`
> is reused; here `parsed` is only used for the snapshot, so mutating in place
> is fine — pop it right after the tally line.

- [ ] **Step 1: Write the failing test**

`server/tests/agents/coordinator/test_coordinator_agent.py`:

```python
import json
import uuid

import pytest

from server.modules.agents.coordinator.agent import Coordinator
from server.modules.agents.exceptions import AgentExecutionError
from server.tests.agents.helpers import (  # adapt names to what exists
    FakeRunLLMClient,
    make_coordinator_snapshot,  # builds a 10-criterion adapter_version-2 DTO
)

TEN = ("OP-01", "OP-02", "OP-03", "OP-04", "OP-05",
       "A-01", "A-02", "A-03", "A-04", "A-05")
CURRICULUM = "Unit 2 covers photosynthesis and cellular respiration."
SOURCE = "Objective: explain photosynthesis. " * 3 + "Answer key provided. " * 3


def _envelope_response(codes, titles):
    measurements = []
    for code in codes:
        if code == "A-05":
            measurements.append({
                "criterion_id": code,
                "criterion_title": titles[code],
                "alignments": [{
                    "objective_text": "Objective: explain photosynthesis.",
                    "is_aligned": True,
                    "assessment_excerpt": "Unit 2 covers photosynthesis",
                    "reasoning": None,
                }],
            })
        elif code in ("OP-02", "OP-05", "A-02", "A-03", "A-04"):
            measurements.append({
                "criterion_id": code,
                "criterion_title": titles[code],
                "instances": [{"excerpt": "Answer key provided."}],
            })
        else:
            measurements.append({
                "criterion_id": code,
                "criterion_title": titles[code],
                "total_units": [{"unit_id": "u1", "evidence": "Answer key provided."}],
                "qualifying_unit_ids": ["u1"],
                "has_measurable_content": True,
            })
    return json.dumps({"summary": "ok", "criterion_measurements": measurements})


def test_run_scores_all_ten_criteria_in_snapshot_order():
    snap, titles = make_coordinator_snapshot()
    client = FakeRunLLMClient(responses=[
        _envelope_response(TEN[:5], titles),
        _envelope_response(TEN[5:], titles),
    ])
    result = Coordinator().run(
        evaluation_id=snap.evaluation_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=[{"chunk_id": str(uuid.uuid4())}],
        canonical_source_text=SOURCE,
        curriculum_id=uuid.uuid4(),
        curriculum_context=CURRICULUM,
        llm_client=client,
    )
    assert result.success is True
    assert tuple(s.criterion_id for s in result.criterion_scores) == TEN
    assert result.subtotal == sum(s.score for s in result.criterion_scores) / 10
    assert result.metadata["group_prompts"].keys() == {"envelope_0", "envelope_1"}
    assert result.metadata["group_responses"]["envelope_1"]
    assert "_grounding_rejected_count" not in json.dumps(
        result.metadata["group_responses"]
    )
    assert result.provenance["grouped_calls"] == 2


def test_run_without_curriculum_context_fails():
    snap, _ = make_coordinator_snapshot()
    with pytest.raises(AgentExecutionError):
        Coordinator().run(
            evaluation_id=snap.evaluation_id,
            document_id=uuid.uuid4(),
            form_snapshot=snap,
            chunk_infos=[{"chunk_id": str(uuid.uuid4())}],
            canonical_source_text=SOURCE,
            curriculum_id=None,
            curriculum_context=None,
            llm_client=FakeRunLLMClient(responses=[]),
        )


def test_run_envelope_double_failure_propagates():
    snap, titles = make_coordinator_snapshot()
    client = FakeRunLLMClient(responses=["bad", "still bad"])
    with pytest.raises(AgentExecutionError):
        Coordinator().run(
            evaluation_id=snap.evaluation_id,
            document_id=uuid.uuid4(),
            form_snapshot=snap,
            chunk_infos=[{"chunk_id": str(uuid.uuid4())}],
            canonical_source_text=SOURCE,
            curriculum_id=uuid.uuid4(),
            curriculum_context=CURRICULUM,
            llm_client=client,
        )
```

> `make_coordinator_snapshot` almost certainly does not exist yet. Build it in
> `server/tests/agents/helpers.py` (or a coordinator `conftest.py`) by mirroring
> however SME's tests build their `EvaluationFormSnapshotDTO` — same
> `rubrics/snapshot_contracts` builders — with: `agent_id="coordinator"`,
> `adapter_key="coordinator"`, `adapter_version=2`, two domains (OP, A), the 10
> criteria with the strategy configs from Task 2's `_COORDINATOR_STRATEGY_CONFIGS`.
> Return `(snapshot_dto, {code: title})`.

- [ ] **Step 2: Run to verify fail**

Run: `uv run --project server pytest server/tests/agents/coordinator/test_coordinator_agent.py -v`
Expected: FAIL — import error / `AttributeError` on old `Coordinator`.

- [ ] **Step 3: Implement**

1. Create `coordinator/summary.py` (code above).
2. `git rm server/modules/agents/coordinator/extraction.py server/modules/agents/coordinator/curriculum.py server/tests/agents/coordinator/test_coordinator_contract.py`.
3. Rewrite `coordinator/agent.py`:
   - module docstring: describe the 10-criterion grouped scoring
   - imports per the Interfaces block
   - `_format_roadmap_note` — paste the body of the current
     `curriculum.py::format_roadmap_note` verbatim (it has no external deps
     beyond stdlib)
   - `_validate_coordinator_snapshot` (code above)
   - `class Coordinator` with class attrs (keep the current file's
     `domain_keywords` tuple) + `__init__` + `run` (body above)
   - `__all__ = ["Coordinator"]`
4. Confirm `coordinator/__init__.py` still does `from .agent import Coordinator`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --project server pytest server/tests/agents/coordinator/ -v`
Expected: PASS (all coordinator unit tests).

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/modules/agents/coordinator/`
Expected: clean. Confirm no remaining references to the deleted modules:
`uv run --project server python -c "import server.modules.agents.coordinator.agent"`

- [ ] **Step 6: Stage**

```bash
git add server/modules/agents/coordinator/ server/tests/agents/coordinator/
git add -u server/modules/agents/coordinator/ server/tests/agents/coordinator/
```
Commit message: `feat(coordinator): score all 10 criteria via grouped measurement extraction`

---

## Task 11: Downstream integration — orchestrator, synthesis, fixtures

**Files:**
- Modify: `server/tests/evaluations/test_orchestrator.py` — any case asserting a 1-criterion Coordinator snapshot/result
- Modify: `server/tests/agents/integration/test_provenance_persist.py`, `server/tests/agents/integration/test_synthesis_persist.py`, `server/tests/agents/integration/test_sme_dispatch_contract.py` — Coordinator criterion-count assumptions
- Modify: `server/tests/agents/helpers.py` / relevant `conftest.py` — shared Coordinator snapshot/result builders
- Modify: any `server/tests/rubrics/` or `server/tests/evaluations/` test asserting `coordinator` active revision is v2 or has 1 criterion
- Inspect (likely no change): `server/modules/evaluations/orchestrator.py`, `server/modules/agents/supervision/dispatch.py`, `server/modules/synthesis/service.py`

**Interfaces:**
- Consumes: everything from Tasks 1-10.
- Produces: green full agent + evaluations + synthesis + rubrics test suites with Coordinator as a 10-criterion agent.

- [ ] **Step 1: Establish the baseline**

Run: `uv run --project server pytest server/tests/agents/ server/tests/evaluations/ server/tests/synthesis/ server/tests/rubrics/ -q`
Record every failure. Expected failure shapes:
- fixtures that build a coordinator snapshot with 1 criterion -> DTO/manifest validation error
- assertions like `assert len(coordinator_result.criterion_scores) == 1` or `== "A-05"`
- `dispatch.py` contract tests that pin coordinator's returned code set
- rubric tests asserting coordinator v2 active

- [ ] **Step 2: Fix fixtures first**

Update the shared Coordinator snapshot/result builders in
`server/tests/agents/helpers.py` (and any `conftest.py` that has its own) so
they produce the 10-criterion, adapter_version-2 shape by default. Grep:
`grep -rn "coordinator" server/tests/ | grep -iE "snapshot|criterion|A-05|adapter_version"`

- [ ] **Step 3: Fix assertions**

For each recorded failure, update the assertion to the new reality:
- Coordinator returns 10 `criterion_scores` in order
  `OP-01..OP-05, A-01..A-05`
- `subtotal` is the mean of 10 scores
- `summary` is non-empty (from `build_alignment_summary`)
- provenance has `grouped_calls == 2`, `grounding_rejected_count` present
Do **not** delete a test that checks real behaviour — adapt it. If a test was
specifically about the retired extraction/compute path and has no analogue,
remove it and note why in the commit message.

- [ ] **Step 4: Confirm orchestrator/dispatch need no code change**

Read `server/modules/agents/supervision/dispatch.py` around the `coordinator`
kwargs block (it passes `curriculum_id`, `curriculum_context`,
`roadmap_context`, `canonical_source_text` — all consumed by the new `run`).
Read `server/modules/evaluations/orchestrator.py` for any `coordinator`
special-casing beyond the factory entry (there should be none). If either
does pin a 1-criterion assumption, fix it minimally and add a regression test.

- [ ] **Step 5: Full run**

Run: `uv run --project server pytest server/tests/agents/ server/tests/evaluations/ server/tests/synthesis/ server/tests/rubrics/ server/tests/migrations/ -q`
Expected: PASS.

Run: `uv run --project server ruff check server`
Expected: clean.

- [ ] **Step 6: End-to-end smoke (manual, no commit)**

If a local evaluation smoke path exists (see `README.md`), run one evaluation
against a real SLM + curriculum and confirm the Coordinator `AgentResult` row
has 10 `criterion_scores`, non-null `group_prompts` / `group_responses`, and a
sane `subtotal`. Record the result in the task notes.

- [ ] **Step 7: Stage**

```bash
git add server/tests/
```
Commit message: `test(coordinator): update fixtures and downstream tests for 10-criterion Coordinator`

---

## Self-Review

**1. Spec coverage:**

| Spec item | Task |
|---|---|
| Manifest widened to 10 criteria / 4 strategies / adapter_version 2 | Task 1 |
| Coordinator Rubric v3 seed logic + strategy resolution | Task 2 |
| Alembic migration + activation + downgrade | Task 3 |
| `pack_domains` copy | Task 5 |
| `downsample` / uniform slicing, no semantic slicers | Task 4, Task 6 |
| Copied measurement-extraction scoring | Tasks 6-8 |
| A-05 `curriculum_alignment` prompt block | Task 6 |
| A-05 groundedness demotion + `grounding_rejected_count` | Task 7 (response), Task 8 (scoring), Task 10 (provenance tally) |
| `curriculum_context` injected only into A-05 envelope | Task 6 |
| Repair-once, second failure raises, no partial results | Task 9, Task 10 |
| `curriculum_context` hard-required | Task 10 |
| Result: mean subtotal, 10 scores, deterministic summary, group_prompts/responses metadata, provenance | Task 10 |
| Delete `extraction.py` / `curriculum.py` / `summary.py` / `test_coordinator_contract.py` | Task 10 |
| No `dispatch.py` / `supervisor.py` / frontend changes | Task 11 (verified) |
| Downstream generic-over-agent consumers unaffected | Task 11 |
| Rubric v2 kept `published` | Task 2 (v2 helper removed, rows untouched), Task 3 (downgrade restores v2 activation) |
| Non-goal: Phase B DPO export / edit UI | not in plan (correct) |

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". Copy tasks give the source file + explicit edit list. New logic (curriculum scoring, groundedness, summary, migration, manifest) is written out in full. Test bodies are concrete. The recurring "confirm the shared helper exists / match the fixture name" notes are deliberate verification steps, not placeholders — the fallback (build the helper inline) is stated each time.

**3. Type consistency:**
- `parse_and_validate_envelope_response(raw, criteria, source_packet, curriculum_context)` — 4 positional args, consistent across Task 7 (def), Task 8 (n/a), Task 9 (`execute_envelope` calls it). The Task 7 test's `if False else` line is flagged in that task's Step 4 to be simplified to the plain call.
- `execute_envelope(envelope_idx, criteria, client, canonical_source_text, curriculum_context, *, prompt_preamble=None, temperature=None, deadline=None)` — consistent Task 8 (def) and Task 10 (`agent.py` call passes `idx, env_criteria, adapter, full_text, curriculum_text, prompt_preamble=roadmap_note`).
- `score_curriculum_alignment(criterion, measurement_dict)` — consistent Task 7/8 naming.
- `build_alignment_summary(criterion_scores)` — Task 10 def + call.
- `_COORDINATOR_STRATEGY_CONFIGS` keys (Task 2) == the 10 codes used in the migration `_CRITERIA` (Task 3) == `TEN` in Task 10 test. A-05 -> `{"strategy": "curriculum_alignment"}` in all three.
- `ratio_band(...).band` / `.pct` — Task 4 def, Task 8 use. Consistent.
- Manifest `adapter_version == 2` (Task 1) == snapshot validation `adapter_version != 2` check (Task 10) == migration `adapter_version 2` (Task 3) == seed `adapter_version=2` (Task 2).

Fixed inline: none required beyond the noted `if False else` cleanup instruction already embedded in Task 7 Step 4.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-02-coordinator-independent-scoring.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

Which approach?
