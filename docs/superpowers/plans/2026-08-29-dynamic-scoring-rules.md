# Dynamic Scoring Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each rubric criterion's scoring rule ("basis") a stored,
admin-editable field surfaced in the Rubric Editor, wired into SME's scoring
prompt so edits change how SME scores.

**Architecture:** One nullable `scoring_rule` column on `rubric_criteria`,
read at evaluation time by a helper that mirrors
`get_active_rubric_descriptions`. SME's grouped-LLM prompt uses the stored
rule with the current hardcoded rules as fallback. The editor (already
DB-connected, uncommitted) swaps its "Field"/title column for a "Scoring
rule" column.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (Python 3.12, ruff E/F/I/UP,
line length 88), React 18 + TanStack Query + Vite + Tailwind, vitest +
@testing-library/react, pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-dynamic-scoring-rules-design.md`

## Global Constraints

- Backend runs from the **repo root**; all commands pass `--project server`.
- Backend lint: `uv run --project server ruff check server` — rules E, F, I,
  UP; line length 88.
- Alembic head is `20260820_0002`. New migration `revision = "20260829_0001"`,
  `down_revision = "20260820_0002"`.
- Migrations MUST NOT import application code that can change — embed literal
  data in the migration file.
- `scoring_rule` edits are **current-value only** (overwrite in place). No
  versioning, no audit log.
- Frontend: no shadcn/external component kits; custom components only.
- This plan edits files from the uncommitted Rubric Editor work. Commit that
  first (`feat/dynamic-rubric-editor`) or fold both together — the plan does
  not assume either.

---

## The 10 scoring-rule texts (verbatim, current `_SCORING_RULES`)

Used in Task 1 (migration backfill) and Task 3 (fallback constant rename).
Copy exactly.

```python
SCORING_RULES = {
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
    "A-03": (
        "Count genuine progress-monitoring mechanisms, spanning up to 4 "
        "types (checkpoint, self-assessment, reflection, cumulative). "
        "Score: 4+ mechanisms -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
    "A-04": (
        "Count distinct feedback/intervention mechanism TYPES (answer key, "
        "rubric, remediation referral, positive reinforcement). Score: "
        "3-4 types -> 4, 2 types -> 3, 1 type -> 2, 0 types -> 1."
    ),
    "A-05": (
        "Score the percentage of stated objectives that are measured by a "
        "real assessment on the moderate scale: 4 if >=80%, 3 if >=50%, "
        "2 if >=20%, else 1. No objectives found -> 1."
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
    "OP-02": (
        "Count genuine interactive elements with real task content (not "
        "just a label like 'Activity 1' with no actual task). Score: "
        "4+ elements -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
    "OP-03": (
        "Score the percentage of tasks with clear, complete directions on "
        "the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "OP-04": (
        "Score the percentage of sections that are clear and internally "
        "consistent (no contradictions or garbled content) on the moderate "
        "scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "OP-05": (
        "Count genuine enhancement activities beyond the core lesson "
        "content. Score: 3+ activities -> 4, 2 -> 3, 1 -> 2, 0 -> 1."
    ),
}
```

---

## Task 1: Schema — `scoring_rule` column, model, seed data

**Files:**
- Create: `server/alembic/versions/20260829_0001_add_rubric_criterion_scoring_rule.py`
- Modify: `server/modules/rubrics/models.py`
- Modify: `server/data/rubrics/rubrics.json`
- Modify: `server/scripts/seed_rubrics.py`
- Test: `server/tests/migrations/test_rubric_scoring_rule_migration.py`

**Interfaces:**
- Produces: `RubricCriterion.scoring_rule` (`Mapped[str | None]`, DB column
  `scoring_rule TEXT NULL`). After the migration, every SME and Coordinator
  criterion row has its `scoring_rule` set to the matching text from the
  `SCORING_RULES` dict above; GAD/ITSO rows are `NULL`.

- [ ] **Step 1: Write the failing migration test**

Create `server/tests/migrations/test_rubric_scoring_rule_migration.py`
(model it on `test_agent_result_group_responses_migration.py`):

```python
"""Tests for 20260829_0001_add_rubric_criterion_scoring_rule migration."""

from __future__ import annotations

import os
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _run(command, config, revision):
    from server.core.config import get_settings

    get_settings.cache_clear()
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = ""
    try:
        command(config, revision)
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old
        get_settings.cache_clear()


def _seed_minimal_rubrics(conn) -> None:
    conn.execute(
        text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
    )
    conn.execute(text("INSERT INTO alembic_version VALUES ('20260820_0002')"))
    conn.execute(
        text(
            "CREATE TABLE rubric_sets ("
            "rubric_set_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
            "name TEXT NOT NULL, version_number INTEGER NOT NULL, "
            "status TEXT NOT NULL, created_at DATETIME NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE rubric_domains ("
            "rubric_domain_id TEXT PRIMARY KEY, rubric_set_id TEXT NOT NULL, "
            "code TEXT NOT NULL, title TEXT NOT NULL, display_order INTEGER NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE rubric_criteria ("
            "rubric_criterion_id TEXT PRIMARY KEY, rubric_domain_id TEXT NOT NULL, "
            "criterion_code TEXT NOT NULL, title TEXT NOT NULL, "
            "description TEXT NOT NULL, display_order INTEGER NOT NULL)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_sets VALUES "
            "('s-sme','sme','SME',1,'active','2026-01-01'),"
            "('s-gad','gad','GAD',1,'active','2026-01-01')"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_domains VALUES "
            "('d-sme','s-sme','A','Assessment',1),"
            "('d-gad','s-gad','GAD','Gender',1)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_criteria VALUES "
            "('c-sme','d-sme','A-02','Varied','desc',2),"
            "('c-gad','d-gad','GAD-01','Stereo','desc',1)"
        )
    )


def test_migration_upgrade_backfills_sme_and_downgrade_drops(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'test_scoring_rule.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        _seed_minimal_rubrics(conn)

    _run(upgrade, _config(url), "20260829_0001")

    with engine.connect() as conn:
        assert (
            MigrationContext.configure(conn).get_current_revision()
            == "20260829_0001"
        )
        cols = {c["name"] for c in inspect(engine).get_columns("rubric_criteria")}
        assert "scoring_rule" in cols
        sme_rule = conn.execute(
            text("SELECT scoring_rule FROM rubric_criteria WHERE rubric_criterion_id='c-sme'")
        ).scalar()
        assert sme_rule is not None and "assessment TYPES" in sme_rule
        gad_rule = conn.execute(
            text("SELECT scoring_rule FROM rubric_criteria WHERE rubric_criterion_id='c-gad'")
        ).scalar()
        assert gad_rule is None

    _run(downgrade, _config(url), "20260820_0002")
    with engine.connect() as conn:
        cols = {c["name"] for c in inspect(engine).get_columns("rubric_criteria")}
        assert "scoring_rule" not in cols

    engine.dispose()
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `uv run --project server pytest server/tests/migrations/test_rubric_scoring_rule_migration.py -q`
Expected: FAIL — migration `20260829_0001` does not exist (`KeyError` / `CommandError`).

- [ ] **Step 3: Write the migration**

Create `server/alembic/versions/20260829_0001_add_rubric_criterion_scoring_rule.py`:

```python
"""add scoring_rule to rubric_criteria

Revision ID: 20260829_0001
Revises: 20260820_0002
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "20260829_0001"
down_revision = "20260820_0002"
branch_labels = None
depends_on = None

# Verbatim copy of server/modules/agents/sme/group_prompt.py::_SCORING_RULES
# at the time of writing. Embedded here because migrations must not import
# app code that can change.
_SCORING_RULES = {
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
    "A-03": (
        "Count genuine progress-monitoring mechanisms, spanning up to 4 "
        "types (checkpoint, self-assessment, reflection, cumulative). "
        "Score: 4+ mechanisms -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
    "A-04": (
        "Count distinct feedback/intervention mechanism TYPES (answer key, "
        "rubric, remediation referral, positive reinforcement). Score: "
        "3-4 types -> 4, 2 types -> 3, 1 type -> 2, 0 types -> 1."
    ),
    "A-05": (
        "Score the percentage of stated objectives that are measured by a "
        "real assessment on the moderate scale: 4 if >=80%, 3 if >=50%, "
        "2 if >=20%, else 1. No objectives found -> 1."
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
    "OP-02": (
        "Count genuine interactive elements with real task content (not "
        "just a label like 'Activity 1' with no actual task). Score: "
        "4+ elements -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
    "OP-03": (
        "Score the percentage of tasks with clear, complete directions on "
        "the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "OP-04": (
        "Score the percentage of sections that are clear and internally "
        "consistent (no contradictions or garbled content) on the moderate "
        "scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "OP-05": (
        "Count genuine enhancement activities beyond the core lesson "
        "content. Score: 3+ activities -> 4, 2 -> 3, 1 -> 2, 0 -> 1."
    ),
}


def upgrade():
    op.add_column(
        "rubric_criteria",
        sa.Column("scoring_rule", sa.Text(), nullable=True),
    )

    bind = op.get_bind()
    for code, rule in _SCORING_RULES.items():
        bind.execute(
            sa.text(
                "UPDATE rubric_criteria SET scoring_rule = :rule "
                "WHERE criterion_code = :code AND rubric_domain_id IN ("
                "  SELECT rd.rubric_domain_id FROM rubric_domains rd "
                "  JOIN rubric_sets rs ON rs.rubric_set_id = rd.rubric_set_id "
                "  WHERE rs.agent_id IN ('sme', 'coordinator')"
                ")"
            ),
            {"rule": rule, "code": code},
        )


def downgrade():
    op.drop_column("rubric_criteria", "scoring_rule")
```

- [ ] **Step 4: Add the model column**

In `server/modules/rubrics/models.py`, inside `class RubricCriterion`, after
the `description` column:

```python
    scoring_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
```

(`Text` and `Mapped`/`mapped_column` are already imported.)

- [ ] **Step 5: Run the migration test — verify it passes**

Run: `uv run --project server pytest server/tests/migrations/test_rubric_scoring_rule_migration.py -q`
Expected: PASS.

- [ ] **Step 6: Update seed data + seed script**

In `server/data/rubrics/rubrics.json`, add a `"scoring_rule"` key to each
criterion object in the `sme` and `coordinator` rubric sets, using the
matching text from the `SCORING_RULES` dict at the top of this plan. Do
**not** add `scoring_rule` to `gad` or `itso` criteria.

In `server/scripts/seed_rubrics.py`, in `seed_domain`, add to the
`RubricCriterion(...)` constructor call:

```python
            scoring_rule=criterion_data.get("scoring_rule"),
```

- [ ] **Step 7: Run the existing rubric test suite — verify still green**

Run: `uv run --project server pytest server/tests/rubrics/ -q`
Expected: PASS (existing tests unaffected — new column is nullable and not
yet read).

- [ ] **Step 8: Lint**

Run: `uv run --project server ruff check server/alembic/versions/20260829_0001_add_rubric_criterion_scoring_rule.py server/modules/rubrics/models.py server/scripts/seed_rubrics.py`
Expected: no errors on these files.

- [ ] **Step 9: Commit**

```bash
git add server/alembic/versions/20260829_0001_add_rubric_criterion_scoring_rule.py \
        server/modules/rubrics/models.py server/data/rubrics/rubrics.json \
        server/scripts/seed_rubrics.py \
        server/tests/migrations/test_rubric_scoring_rule_migration.py
git commit -m "feat(rubrics): add scoring_rule column to rubric_criteria

Nullable TEXT column, backfilled for SME + Coordinator criteria from the
current hardcoded _SCORING_RULES. GAD/ITSO left NULL.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01B3xJSgEmsJPivZEGB4jayH"
```

---

## Task 2: Read helper — `get_active_rubric_scoring_rules`

**Files:**
- Modify: `server/modules/rubrics/service.py`
- Test: `server/tests/rubrics/test_rubrics.py`

**Interfaces:**
- Consumes: `RubricCriterion.scoring_rule` (Task 1).
- Produces: `get_active_rubric_scoring_rules(agent_id: str, db: Any | None = None) -> dict[str, str]`
  — `{criterion_code: scoring_rule}` for the active rubric set, skipping
  rows whose `scoring_rule` is `None` or blank. Returns `{}` when there is
  no active rubric set.

- [ ] **Step 1: Write the failing test**

In `server/tests/rubrics/test_rubrics.py`, add (the file already has
`_seed_from_json(db_session)` and imports from `server.modules.rubrics.service`):

```python
def test_active_rubric_scoring_rules_returns_backfilled_sme_rules(db_session) -> None:
    from server.modules.rubrics.models import RubricCriterion
    from server.modules.rubrics.service import get_active_rubric_scoring_rules

    _seed_from_json(db_session)
    # rubrics.json now carries scoring_rule for SME; simulate a NULL row.
    a01 = (
        db_session.query(RubricCriterion)
        .filter_by(criterion_code="A-01")
        .join(RubricCriterion.__mapper__.relationships and None)  # placeholder removed below
    )
```

Replace the above with this concrete version (no relationship on the model,
so scope by a subquery through the seed helper's known SME set name):

```python
def test_active_rubric_scoring_rules_returns_sme_rules_and_skips_blank(db_session) -> None:
    from server.modules.rubrics.models import (
        RubricCriterion,
        RubricDomain,
        RubricSet,
    )
    from server.modules.rubrics.service import get_active_rubric_scoring_rules

    _seed_from_json(db_session)

    rules = get_active_rubric_scoring_rules("sme", db=db_session)
    assert set(rules) == {
        "A-01", "A-02", "A-03", "A-04", "A-05",
        "OP-01", "OP-02", "OP-03", "OP-04", "OP-05",
    }
    assert "assessment TYPES" in rules["A-02"]

    # A criterion with NULL scoring_rule is skipped.
    sme_a01 = (
        db_session.query(RubricCriterion)
        .join(RubricDomain, RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id)
        .join(RubricSet, RubricDomain.rubric_set_id == RubricSet.rubric_set_id)
        .filter(RubricSet.agent_id == "sme", RubricCriterion.criterion_code == "A-01")
        .one()
    )
    sme_a01.scoring_rule = None
    db_session.flush()
    rules_after = get_active_rubric_scoring_rules("sme", db=db_session)
    assert "A-01" not in rules_after
    assert "A-02" in rules_after


def test_active_rubric_scoring_rules_empty_when_no_active_set(db_session) -> None:
    from server.modules.rubrics.service import get_active_rubric_scoring_rules

    assert get_active_rubric_scoring_rules("sme", db=db_session) == {}
```

Also update `_seed_from_json` in that file to carry the new key:

```python
                db_session.add(
                    RubricCriterion(
                        rubric_domain_id=domain.rubric_domain_id,
                        criterion_code=criterion_data["criterion_code"],
                        title=criterion_data["title"],
                        description=criterion_data["description"],
                        display_order=criterion_data["display_order"],
                        scoring_rule=criterion_data.get("scoring_rule"),
                    )
                )
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `uv run --project server pytest server/tests/rubrics/test_rubrics.py -q -k scoring_rules`
Expected: FAIL — `ImportError: cannot import name 'get_active_rubric_scoring_rules'`.

- [ ] **Step 3: Implement the helper**

In `server/modules/rubrics/service.py`, add after
`get_active_rubric_descriptions` (copy its body, swap the returned field):

```python
def get_active_rubric_scoring_rules(
    agent_id: str, db: Any | None = None
) -> dict[str, str]:
    """Return ``{criterion_code: scoring_rule}`` for the active rubric set.

    Mirrors ``get_active_rubric_descriptions`` but returns the per-criterion
    scoring rule. Criteria whose ``scoring_rule`` is NULL or blank are
    omitted. Returns ``{}`` if no active rubric set exists.
    """

    session = db or get_session_factory()()
    close_session = db is None
    try:
        rubric_set = (
            session.query(RubricSet)
            .filter_by(agent_id=agent_id, status="active")
            .order_by(RubricSet.version_number.desc())
            .first()
        )
        if rubric_set is None:
            return {}

        criteria = (
            session.query(RubricCriterion)
            .join(
                RubricDomain,
                RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
            )
            .filter(RubricDomain.rubric_set_id == rubric_set.rubric_set_id)
            .order_by(
                RubricDomain.display_order.asc(),
                RubricDomain.code.asc(),
                RubricCriterion.display_order.asc(),
                RubricCriterion.criterion_code.asc(),
            )
            .all()
        )
        return {
            c.criterion_code: c.scoring_rule
            for c in criteria
            if c.scoring_rule and c.scoring_rule.strip()
        }
    finally:
        if close_session:
            session.close()
```

Add `"get_active_rubric_scoring_rules"` to `__all__` (keep it sorted).

- [ ] **Step 4: Run the test — verify it passes**

Run: `uv run --project server pytest server/tests/rubrics/test_rubrics.py -q`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/modules/rubrics/service.py server/tests/rubrics/test_rubrics.py`
Expected: no NEW errors (pre-existing E501 in `get_active_rubric_context` is
not ours; do not touch it).

- [ ] **Step 6: Commit**

```bash
git add server/modules/rubrics/service.py server/tests/rubrics/test_rubrics.py
git commit -m "feat(rubrics): add get_active_rubric_scoring_rules reader

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01B3xJSgEmsJPivZEGB4jayH"
```

---

## Task 3: SME prompt wiring

**Files:**
- Modify: `server/modules/agents/sme/group_prompt.py`
- Modify: `server/modules/agents/sme/group_execution.py`
- Modify: `server/modules/agents/sme/pipeline.py`
- Test: `server/tests/agents/sme/test_group_prompt_scoring_rules.py` (create)
- Test: `server/tests/agents/sme/test_sme_run.py` (existing — check impact)

**Interfaces:**
- Consumes: `get_active_rubric_scoring_rules` (Task 2);
  `FALLBACK_SCORING_RULES` (renamed this task).
- Produces:
  - `group_prompt.FALLBACK_SCORING_RULES: dict[str, str]` (was `_SCORING_RULES`).
  - `build_group_prompt(group, codes, titles, descriptions, scoring_rules, full_text, *, prompt_preamble=None) -> str`
    — new 5th positional param `scoring_rules: dict[str, str]`.
  - `execute_group(group, codes, titles, descriptions, scoring_rules, client, full_text, *, prompt_preamble=None)`
    — new 5th positional param `scoring_rules: dict[str, str]`.

- [ ] **Step 1: Write the failing test**

Create `server/tests/agents/sme/test_group_prompt_scoring_rules.py`:

```python
"""build_group_prompt uses the passed scoring rule, falling back to the constant."""

from __future__ import annotations

import json

from server.modules.agents.sme.group_prompt import (
    FALLBACK_SCORING_RULES,
    build_group_prompt,
)


def test_build_group_prompt_prefers_passed_scoring_rule() -> None:
    prompt = build_group_prompt(
        "assessment_alignment",
        ("A-02", "A-05"),
        {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"},
        {"A-02": "desc a02", "A-05": "desc a05"},
        {"A-02": "EDITED RULE: count things differently"},
        "some document text",
    )
    payload = json.loads(prompt)
    assert payload["criteria"]["A-02"]["scoring_rule"] == (
        "EDITED RULE: count things differently"
    )
    # A-05 not in the passed dict -> falls back to the constant.
    assert payload["criteria"]["A-05"]["scoring_rule"] == FALLBACK_SCORING_RULES["A-05"]


def test_fallback_scoring_rules_has_all_ten_codes() -> None:
    assert set(FALLBACK_SCORING_RULES) == {
        "A-01", "A-02", "A-03", "A-04", "A-05",
        "OP-01", "OP-02", "OP-03", "OP-04", "OP-05",
    }
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `uv run --project server pytest server/tests/agents/sme/test_group_prompt_scoring_rules.py -q`
Expected: FAIL — `ImportError: cannot import name 'FALLBACK_SCORING_RULES'`.

- [ ] **Step 3: Rename the constant and add the param in `group_prompt.py`**

In `server/modules/agents/sme/group_prompt.py`:

1. Rename `_SCORING_RULES` → `FALLBACK_SCORING_RULES` (definition + the one
   use inside `build_group_prompt`).
2. Update the module docstring's first paragraph to note the rule now comes
   from the DB with this constant as fallback (mirror the existing
   description wording).
3. Change `build_group_prompt`'s signature to add `scoring_rules` as the
   5th positional parameter (after `descriptions`, before `full_text`):

```python
def build_group_prompt(
    group: str,
    codes: tuple[str, ...],
    titles: dict[str, str],
    descriptions: dict[str, str],
    scoring_rules: dict[str, str],
    full_text: str,
    *,
    prompt_preamble: str | None = None,
) -> str:
```

4. In the `criteria` dict comprehension, change the `scoring_rule` line to:

```python
            "scoring_rule": scoring_rules.get(code) or FALLBACK_SCORING_RULES[code],
```

5. Update `__all__` to `["FALLBACK_DESCRIPTIONS", "FALLBACK_SCORING_RULES", "build_group_prompt"]`.

- [ ] **Step 4: Thread `scoring_rules` through `group_execution.py`**

In `server/modules/agents/sme/group_execution.py`, change `execute_group`'s
signature to add `scoring_rules: dict[str, str]` as the 5th positional
param (after `descriptions`, before `client`):

```python
def execute_group(
    group: str,
    codes: tuple[str, ...],
    titles: dict[str, str],
    descriptions: dict[str, str],
    scoring_rules: dict[str, str],
    client: RunLLMClient,
    full_text: str,
    *,
    prompt_preamble: str | None = None,
) -> tuple[tuple[CriterionScore, ...], str, dict[str, Any]]:
```

And update the `build_group_prompt(...)` call:

```python
    prompt = build_group_prompt(
        group,
        codes,
        titles,
        descriptions,
        scoring_rules,
        full_text,
        prompt_preamble=prompt_preamble,
    )
```

- [ ] **Step 5: Wire `pipeline.py` to fetch and pass the rules**

In `server/modules/agents/sme/pipeline.py`:

1. Add to the rubrics import:

```python
from server.modules.rubrics.service import (
    get_active_rubric_criteria,
    get_active_rubric_descriptions,
    get_active_rubric_scoring_rules,
    resolve_rubric_agent_id,
)
```

2. Add to the `group_prompt` import:

```python
from .group_prompt import FALLBACK_DESCRIPTIONS as _FALLBACK_DESCRIPTIONS
from .group_prompt import FALLBACK_SCORING_RULES as _FALLBACK_SCORING_RULES
```

3. In `_run_full_llm_scoring`, after `descriptions = self._rubric_descriptions(db)`:

```python
        scoring_rules = get_active_rubric_scoring_rules(
            resolve_rubric_agent_id(self.rubric_source_type), db=db
        )
```

4. Inside the `for group_name in groups.GROUP_NAMES:` loop, after
   `group_descriptions = {...}`:

```python
            group_scoring_rules = {
                code: scoring_rules.get(code) or _FALLBACK_SCORING_RULES[code]
                for code in codes
            }
```

5. Update the `execute_group(...)` call to pass it 5th:

```python
                scores, prompt_text, response_snapshot = execute_group(
                    group_name,
                    codes,
                    group_titles,
                    group_descriptions,
                    group_scoring_rules,
                    client,
                    full_text,
                    prompt_preamble=prompt_preamble,
                )
```

- [ ] **Step 6: Run the new prompt test — verify it passes**

Run: `uv run --project server pytest server/tests/agents/sme/test_group_prompt_scoring_rules.py -q`
Expected: PASS.

- [ ] **Step 7: Run the SME agent test suite — fix any call-site fallout**

Run: `uv run --project server pytest server/tests/agents/sme/ -q`
Expected: PASS. If a test calls `build_group_prompt` or `execute_group`
positionally without `scoring_rules`, add `{}` (or a small dict) in the new
5th position — that is the correct fix, not reverting the signature.

- [ ] **Step 8: Run the broader agent + supervision suites**

Run: `uv run --project server pytest server/tests/agents/ -q`
Expected: PASS. Same fix rule as Step 7 for any positional call sites.

- [ ] **Step 9: Lint**

Run: `uv run --project server ruff check server/modules/agents/sme/`
Expected: no new errors.

- [ ] **Step 10: Commit**

```bash
git add server/modules/agents/sme/group_prompt.py \
        server/modules/agents/sme/group_execution.py \
        server/modules/agents/sme/pipeline.py \
        server/tests/agents/sme/
git commit -m "feat(sme): score from DB scoring_rule, hardcoded rules as fallback

_SCORING_RULES -> FALLBACK_SCORING_RULES; build_group_prompt/execute_group
take a scoring_rules dict; pipeline fetches it via
get_active_rubric_scoring_rules so admin edits change SME scoring.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01B3xJSgEmsJPivZEGB4jayH"
```

---

## Task 4: Editor API — `scoring_rule` in read + update, drop `title` from update

**Files:**
- Modify: `server/modules/rubrics/schemas.py`
- Modify: `server/modules/rubrics/service.py`
- Modify: `server/modules/rubrics/router.py`
- Test: `server/tests/rubrics/test_rubric_editor.py` (existing)

**Interfaces:**
- Consumes: `RubricCriterion.scoring_rule` (Task 1).
- Produces:
  - `RubricCriterionOut` gains `scoring_rule: str | None`.
  - `RubricCriterionUpdate` = `{description: str, scoring_rule: str | None}`
    (no `title`). `description` required + non-blank + trimmed;
    `scoring_rule` required key, nullable value — non-blank trimmed, blank
    or `null` → `None`.
  - `update_criterion(db, criterion_id, *, description: str, scoring_rule: str | None) -> RubricCriterion`
    (renamed from `update_criterion_text`, `title` param removed).
  - `get_rubric_sets_for_editor` criterion dicts gain `"scoring_rule"`.

- [ ] **Step 1: Update the existing editor tests to the new contract (they will fail)**

In `server/tests/rubrics/test_rubric_editor.py`:

- In `test_get_rubric_sets_for_editor_returns_nested_active_sets`, add after
  the existing `first` assertions:

```python
    assert "scoring_rule" in first  # present (may be None for some agents)
```

- Replace `test_update_criterion_text_persists_new_title_and_description`
  with:

```python
def test_update_criterion_persists_description_and_scoring_rule(db_session) -> None:
    _seed_from_json(db_session)
    criterion = _criterion(db_session, "sme", "OP-01")

    update_criterion(
        db_session,
        criterion.rubric_criterion_id,
        description="Topics flow coherently across chapters.",
        scoring_rule="EDITED: 0 issues -> 4, else lower.",
    )
    db_session.commit()

    refreshed = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=criterion.rubric_criterion_id)
        .one()
    )
    assert refreshed.description == "Topics flow coherently across chapters."
    assert refreshed.scoring_rule == "EDITED: 0 issues -> 4, else lower."
    assert refreshed.criterion_code == "OP-01"
    # title is unchanged (not editable anymore)
    assert refreshed.title == "Topic Coherence"


def test_update_criterion_blank_scoring_rule_clears_to_null(db_session) -> None:
    _seed_from_json(db_session)
    criterion = _criterion(db_session, "sme", "OP-01")

    update_criterion(
        db_session,
        criterion.rubric_criterion_id,
        description="still here",
        scoring_rule="   ",
    )
    db_session.commit()

    refreshed = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=criterion.rubric_criterion_id)
        .one()
    )
    assert refreshed.scoring_rule is None
```

- In `test_update_criterion_text_missing_id_raises_lookup_error`, rename the
  call to `update_criterion` and drop `title=`:

```python
def test_update_criterion_missing_id_raises_lookup_error(db_session) -> None:
    import uuid

    _seed_from_json(db_session)
    with pytest.raises(LookupError):
        update_criterion(
            db_session, uuid.uuid4(), description="y", scoring_rule=None
        )
```

- In `test_rubrics_patch_criterion_access_control`, change the payload to
  `{"description": "Lessons are interactive.", "scoring_rule": "count elements"}`
  and the success assertion to
  `assert response.json()["description"] == "Lessons are interactive."`.

- In `test_patch_criterion_reflects_in_active_rubric_context`, change the
  PATCH body to include `scoring_rule` and drop `title`:

```python
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{criterion_id}",
        json={
            "description": "Topics flow coherently across chapters.",
            "scoring_rule": None,
        },
    )
    assert response.status_code == 200

    context = get_active_rubric_context("sme", db=db_session)
    assert (
        "OP-01 | Title: Topic Coherence | Description: "
        "Topics flow coherently across chapters." in context
    )
```

- Replace `test_patch_criterion_blank_title_rejected` with:

```python
def test_patch_criterion_blank_description_rejected(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    criterion_id = str(_criterion(db_session, "sme", "OP-01").rubric_criterion_id)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{criterion_id}",
        json={"description": "   ", "scoring_rule": None},
    )
    assert response.status_code == 422
```

- Add a new test:

```python
def test_patch_criterion_sets_scoring_rule(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    criterion = _criterion(db_session, "sme", "A-02")
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{criterion.rubric_criterion_id}",
        json={"description": "keep", "scoring_rule": "NEW RULE: 6+ types -> 4"},
    )
    assert response.status_code == 200
    assert response.json()["scoring_rule"] == "NEW RULE: 6+ types -> 4"
```

Update the import line at the top of the file:

```python
from server.modules.rubrics.service import (
    get_active_rubric_context,
    get_rubric_sets_for_editor,
    update_criterion,
    update_domain_title,
)
```

- [ ] **Step 2: Run the editor tests — verify they fail**

Run: `uv run --project server pytest server/tests/rubrics/test_rubric_editor.py -q`
Expected: FAIL — `ImportError` on `update_criterion`, plus schema/field
mismatches.

- [ ] **Step 3: Update `schemas.py`**

```python
class RubricCriterionOut(BaseModel):
    rubric_criterion_id: uuid.UUID
    criterion_code: str
    title: str
    description: str
    scoring_rule: str | None
    display_order: int


class RubricCriterionUpdate(BaseModel):
    description: str
    scoring_rule: str | None

    @field_validator("description")
    @classmethod
    def _check_description(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("scoring_rule")
    @classmethod
    def _clean_scoring_rule(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
```

`_clean_title` is still used by `RubricDomainUpdate` — keep it. The
`RubricCriterionUpdate._check_title` validator and the `title` field are
removed.

- [ ] **Step 4: Update `service.py`**

Rename `update_criterion_text` → `update_criterion`, drop `title`, add
`scoring_rule`:

```python
def update_criterion(
    db: Any,
    criterion_id: uuid.UUID,
    *,
    description: str,
    scoring_rule: str | None,
) -> RubricCriterion:
    """Update a criterion's description and scoring rule in place.

    ``criterion_code`` and ``title`` are never changed here. A blank or
    ``None`` ``scoring_rule`` is stored as SQL NULL. Raises ``LookupError``
    when the id does not exist so the router can map it to a 404.
    """

    criterion = (
        db.query(RubricCriterion)
        .filter_by(rubric_criterion_id=criterion_id)
        .one_or_none()
    )
    if criterion is None:
        raise LookupError(f"rubric criterion {criterion_id} not found")
    criterion.description = description
    criterion.scoring_rule = (scoring_rule or None) and scoring_rule.strip() or None
    db.flush()
    return criterion
```

(Simpler: `criterion.scoring_rule = scoring_rule.strip() if scoring_rule and scoring_rule.strip() else None` — use whichever reads cleaner; the
schema already trimmed it, so `criterion.scoring_rule = scoring_rule` is
also acceptable. Pick one and keep it.)

In `get_rubric_sets_for_editor`, add to the criterion dict:

```python
                                "scoring_rule": c.scoring_rule,
```

In `__all__`, rename `"update_criterion_text"` → `"update_criterion"`.

- [ ] **Step 5: Update `router.py`**

- Import: `from .service import (get_rubric_sets_for_editor, update_criterion, update_domain_title)`.
- In `patch_criterion`:

```python
    try:
        criterion = update_criterion(
            db,
            criterion_id,
            description=body.description,
            scoring_rule=body.scoring_rule,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    db.commit()
    return RubricCriterionOut(
        rubric_criterion_id=criterion.rubric_criterion_id,
        criterion_code=criterion.criterion_code,
        title=criterion.title,
        description=criterion.description,
        scoring_rule=criterion.scoring_rule,
        display_order=criterion.display_order,
    )
```

- [ ] **Step 6: Run the editor tests — verify they pass**

Run: `uv run --project server pytest server/tests/rubrics/ -q`
Expected: PASS.

- [ ] **Step 7: Lint**

Run: `uv run --project server ruff check server/modules/rubrics/`
Expected: no new errors.

- [ ] **Step 8: Commit**

```bash
git add server/modules/rubrics/schemas.py server/modules/rubrics/service.py \
        server/modules/rubrics/router.py server/tests/rubrics/test_rubric_editor.py
git commit -m "feat(rubrics): editor API reads/writes scoring_rule, drops title edit

GET returns scoring_rule per criterion; PATCH body is {description,
scoring_rule}; update_criterion_text -> update_criterion.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01B3xJSgEmsJPivZEGB4jayH"
```

---

## Task 5: Editor UI — Scoring rule column

**Files:**
- Modify: `client/src/features/admin/rubric-editor/types.ts`
- Modify: `client/src/features/admin/rubric-editor/components/RubricTableEditor.tsx`
- Test: `client/src/features/admin/rubric-editor/api/__tests__/rubricEditor.api.test.ts`
- Test: `client/src/features/admin/rubric-editor/components/__tests__/RubricTableEditor.test.tsx`

**Interfaces:**
- Consumes: `GET /admin/rubrics` (each criterion has `scoring_rule: string | null`),
  `PATCH /admin/rubrics/criteria/{id}` body `{ description, scoring_rule }`.
- Produces: editor table columns **Criterion ID · Entry · Scoring rule ·
  Action**; no "Field" column.

- [ ] **Step 1: Update the api test (will fail)**

In `rubricEditor.api.test.ts`, change the criterion PATCH test:

```python
  it('PATCHes a criterion with a description + scoring_rule body', async () => {
```

(keep TS) — body assertion:

```ts
    await rubricEditorApi.updateCriterion('crit-1', {
      description: 'New description.',
      scoring_rule: 'New rule: count differently.',
    });

    expect(capturedUrl).toBe('/admin/rubrics/criteria/crit-1');
    expect(capturedInit?.method).toBe('PATCH');
    expect(JSON.parse(capturedInit?.body as string)).toEqual({
      description: 'New description.',
      scoring_rule: 'New rule: count differently.',
    });
```

- [ ] **Step 2: Update the component test (will fail)**

Rewrite `RubricTableEditor.test.tsx`'s mock data and assertions:

```tsx
const mockData: RubricSetListResponse = {
  rubric_sets: [
    {
      rubric_set_id: 'set-sme',
      agent_id: 'sme',
      name: 'SME Rubric v1',
      version_number: 1,
      status: 'active',
      domains: [
        {
          rubric_domain_id: 'dom-op',
          code: 'OP',
          title: 'Organization & Presentation',
          display_order: 1,
          criteria: [
            {
              rubric_criterion_id: 'crit-op1',
              criterion_code: 'OP-01',
              title: 'Topic Coherence',
              description: 'Topics are coherent from Unit to Chapter.',
              scoring_rule: '0 issues -> 4, 1 -> 3, 2 -> 2, 3+ -> 1.',
              display_order: 1,
            },
          ],
        },
      ],
    },
    {
      rubric_set_id: 'set-gad',
      agent_id: 'gad',
      name: 'GAD Rubric v1',
      version_number: 1,
      status: 'active',
      domains: [
        {
          rubric_domain_id: 'dom-gad',
          code: 'GAD',
          title: 'Inclusivity',
          display_order: 1,
          criteria: [
            {
              rubric_criterion_id: 'crit-gad1',
              criterion_code: 'GAD-01',
              title: 'Free from Stereotypes',
              description: 'The material is free from gender stereotypes.',
              scoring_rule: null,
              display_order: 1,
            },
          ],
        },
      ],
    },
  ],
};
```

Tests:

```tsx
  it('renders Criterion ID, Entry and Scoring rule columns, no Field column', () => {
    render(<RubricTableEditor />);
    expect(screen.queryByRole('columnheader', { name: /field/i })).toBeNull();
    expect(screen.getAllByRole('columnheader', { name: /scoring rule/i }).length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue('OP-01')).toBeDefined();
    expect(
      screen.getByDisplayValue('Topics are coherent from Unit to Chapter.'),
    ).toBeDefined();
    expect(
      screen.getByDisplayValue('0 issues -> 4, 1 -> 3, 2 -> 2, 3+ -> 1.'),
    ).toBeDefined();
  });

  it('saves description + scoring rule via the update-criterion mutation', () => {
    render(<RubricTableEditor />);
    fireEvent.click(screen.getByRole('button', { name: /edit .*OP-01/i }));
    fireEvent.change(
      screen.getByDisplayValue('0 issues -> 4, 1 -> 3, 2 -> 2, 3+ -> 1.'),
      { target: { value: 'EDITED RULE' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /finish editing .*OP-01/i }));
    expect(updateCriterionMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        criterionId: 'crit-op1',
        body: {
          description: 'Topics are coherent from Unit to Chapter.',
          scoring_rule: 'EDITED RULE',
        },
      }),
    );
  });

  it('shows a "not used yet" note for non-SME agents', () => {
    render(<RubricTableEditor />);
    expect(screen.getByText(/not used by this agent's scoring yet/i)).toBeDefined();
  });

  it('keeps criterion code read-only and structural buttons disabled', () => {
    render(<RubricTableEditor />);
    expect((screen.getByDisplayValue('OP-01') as HTMLInputElement).readOnly).toBe(true);
    expect(
      (screen.getAllByRole('button', { name: /add row/i })[0] as HTMLButtonElement).disabled,
    ).toBe(true);
  });
```

Keep the existing `vi.mock('../../hooks/useRubrics', ...)` block and the
`updateCriterionMutate` / `updateDomainMutate` spies.

- [ ] **Step 3: Run both test files — verify they fail**

Run: `cd client && pnpm vitest run src/features/admin/rubric-editor`
Expected: FAIL — type errors / missing "Scoring rule" column / missing note.

- [ ] **Step 4: Update `types.ts`**

```ts
export type RubricCriterion = {
  rubric_criterion_id: string;
  criterion_code: string;
  title: string;
  description: string;
  scoring_rule: string | null;
  display_order: number;
};
```

Change the criterion update payload type used by `rubricEditor.api.ts` /
`useRubrics.ts` from `{ title; description }` to:

```ts
export type CriterionUpdate = {
  description: string;
  scoring_rule: string | null;
};
```

(Rename the type if the current name says "Text"; update the import in
`rubricEditor.api.ts` and `useRubrics.ts` accordingly.)

- [ ] **Step 5: Update `RubricTableEditor.tsx`**

1. `Draft` type → `{ description: string; scoring_rule: string }`.
2. `startEditing`: seed `{ description: criterion.description, scoring_rule: criterion.scoring_rule ?? '' }`.
3. `finishEditing`: build the body from the draft and fire when either field
   changed:

```tsx
  const finishEditing = (criterion: RubricCriterion) => {
    const draft = drafts[criterion.rubric_criterion_id];
    const description = (draft?.description ?? criterion.description).trim();
    const rawRule = draft?.scoring_rule ?? criterion.scoring_rule ?? '';
    const scoring_rule = rawRule.trim() ? rawRule.trim() : null;

    const descChanged = description !== criterion.description;
    const ruleChanged = scoring_rule !== (criterion.scoring_rule ?? null);
    if (description && (descChanged || ruleChanged)) {
      updateCriterion.mutate({
        criterionId: criterion.rubric_criterion_id,
        body: { description, scoring_rule },
      });
    }
    setEditingRowIds((current) => {
      const next = new Set(current);
      next.delete(criterion.rubric_criterion_id);
      return next;
    });
  };
```

4. `updateDraft` key type follows the new `Draft`.
5. Table `<thead>`: replace the "Field" `<th>` with nothing (remove it), and
   add a "Scoring rule" `<th>` after "Entry":

```tsx
                          <th className="py-3 px-4 font-semibold text-slate-500 min-w-[16rem]">
                            Scoring rule
                          </th>
```

Columns are now: Criterion ID, Entry, Scoring rule, Action. Update the empty
-state `<td colSpan={4}>` — still 4 columns, no change needed.

6. In the row body: **delete the entire "Field"/title `<td>`** (the input
   with `aria-label={`${criterion.criterion_code} title`}`). Keep the
   description `<td>` (rename its column meaning to "Entry" — already is).
   After the description `<td>`, add a scoring-rule `<td>`:

```tsx
                            <td className="py-2.5 px-4 text-sm font-medium align-top">
                              <textarea
                                rows={3}
                                value={
                                  isEditing && draft
                                    ? draft.scoring_rule
                                    : (criterion.scoring_rule ?? '')
                                }
                                readOnly={!isEditing}
                                onChange={(event) =>
                                  updateDraft(
                                    criterion.rubric_criterion_id,
                                    'scoring_rule',
                                    event.target.value,
                                  )
                                }
                                className="w-full border border-slate-200 bg-white rounded-sm text-xs px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] read-only:border-transparent read-only:bg-transparent read-only:ring-0 font-medium text-slate-700 resize-y"
                                aria-label={`${criterion.criterion_code} scoring rule`}
                                placeholder="No scoring rule set"
                              />
                              {rubricSet.agent_id !== 'sme' && (
                                <p className="mt-1 text-[11px] italic text-slate-400">
                                  Stored for reference — not used by this agent&apos;s
                                  scoring yet.
                                </p>
                              )}
                            </td>
```

7. Remove `title` from the draft-value logic (`titleValue` const) and the
   `RubricCriterion` import stays.

- [ ] **Step 6: Run both test files — verify they pass**

Run: `cd client && pnpm vitest run src/features/admin/rubric-editor`
Expected: PASS.

- [ ] **Step 7: Typecheck, lint, format**

Run:
```bash
cd client && pnpm exec tsc --noEmit && pnpm exec eslint src/features/admin/rubric-editor && pnpm exec prettier --write "src/features/admin/rubric-editor/**/*.{ts,tsx}"
```
Expected: tsc exit 0, eslint exit 0, prettier writes formatting.

- [ ] **Step 8: Re-run tests after formatting**

Run: `cd client && pnpm vitest run src/features/admin/rubric-editor`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add client/src/features/admin/rubric-editor/
git commit -m "feat(rubric-editor): replace Field column with editable Scoring rule

Editor table is now Criterion ID / Entry / Scoring rule / Action. Title is
no longer editable. Non-SME rows show a 'not used for scoring yet' note.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01B3xJSgEmsJPivZEGB4jayH"
```

---

## Task 6: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Backend — rubrics + agents + migrations**

Run: `uv run --project server pytest server/tests/rubrics/ server/tests/agents/ server/tests/migrations/ -q`
Expected: PASS.

- [ ] **Step 2: Backend — full suite**

Run: `uv run --project server pytest -q`
Expected: PASS (or no new failures vs. a pre-change baseline — capture the
baseline first if unsure).

- [ ] **Step 3: Backend lint (whole tree, as CI runs it)**

Run: `uv run --project server ruff check server`
Expected: no NEW errors introduced by this work. Pre-existing violations in
files this plan did not create (e.g. `service.py`'s
`get_active_rubric_context`, `models.py` import block) are out of scope.

- [ ] **Step 4: Frontend — full test + build**

Run: `cd client && pnpm vitest run && pnpm build`
Expected: tests PASS, build succeeds.

- [ ] **Step 5: Update the design memory**

Update `sme-dynamic-rubric-dpo-tension` memory: the scoring-rule slice is
now implemented (SME wired, Coordinator/GAD/ITSO stored-only), grouping
untouched, DPO export still reads the per-eval snapshot. No new memory file
needed — edit the existing one.

- [ ] **Step 6: Final commit (if memory or docs changed)**

```bash
git add docs/superpowers/ .claude/
git commit -m "docs: record dynamic-scoring-rules implementation status

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01B3xJSgEmsJPivZEGB4jayH"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
| --- | --- |
| §5.1 schema/model/seed | Task 1 |
| §5.2 read helper | Task 2 |
| §5.3 SME prompt wiring | Task 3 |
| §5.4 editor API | Task 4 |
| §5.5 editor UI | Task 5 |
| §6 engine-fallback limitation | No code — documented in spec; Task 3 keeps `registry` untouched |
| §7 DPO impact | No code — Task 6 Step 5 updates the memory |
| §8 testing | Tasks 1–5 (TDD steps) + Task 6 (full suite) |
| §9 sequencing | Global Constraints note |

**Placeholder scan:** the Task 2 Step 1 test has a deliberately-marked
placeholder snippet immediately replaced by the concrete version below it —
the executor uses the second block. No other placeholders.

**Type consistency:** `update_criterion` (not `update_criterion_text`) used
in Tasks 4 and referenced nowhere else; `scoring_rules` param is 5th
positional in both `build_group_prompt` and `execute_group` (Task 3);
`RubricCriterion.scoring_rule: string | null` on the frontend matches
`scoring_rule: str | None` on `RubricCriterionOut`; PATCH body
`{ description, scoring_rule }` consistent between Task 4 (API) and Task 5
(UI + api test).
