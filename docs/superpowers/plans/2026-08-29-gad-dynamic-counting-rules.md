# GAD Dynamic Counting Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each GAD criterion's semantic counting guidance a stored, admin-editable `scoring_rule` that is injected into the GAD extraction prompt at evaluation time, with the current wording kept as a code fallback.

**Architecture:** GAD's pipeline is unchanged — the LLM still extracts facts (counts + grounded excerpts), Python still assigns the 1–4 bands, grounding and determinism stay. Only the *counting-guidance text* per criterion moves from a hardcoded block in `gad/prompt.py` into `rubric_criteria.scoring_rule` (column already exists), read via the existing `get_active_rubric_scoring_rules` and injected into `build_combined_prompt` between the criterion header and a fixed structural scaffold that stays in code.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pytest (backend, run from repo root with `uv run --project server`); React 18 + TypeScript + vitest + @testing-library/react, pnpm (frontend in `client/`).

**Spec:** `docs/superpowers/specs/2026-08-29-gad-dynamic-counting-rules-design.md`

## Global Constraints

- Backend: ruff-enforced (E, F, I, UP), line length 88, Python 3.12. Run backend commands from the **repo root** with `PYTHONPATH=.` and `--project server`.
- Alembic: no root `pyproject.toml`; always `-c server/alembic.ini`. Current head is `20260829_0001`. `alembic ... current` needs `PYTHONPATH=.` or it fails `ModuleNotFoundError: No module named 'server'`.
- Migrations must not import app code — embed literal data in the migration file.
- Frontend: no shadcn / external component kits; custom components only. `client/` uses pnpm.
- The GAD counting-rule text exists in **exactly one canonical form**, copied verbatim to three places: `FALLBACK_GAD_INSTRUCTIONS` in `gad/prompt.py`, the migration's embedded dict, and `server/data/rubrics/rubrics.json`. A test asserts all three match.
- Do NOT change the GAD band ladders (`stereotypes.py` etc.), `envelope.py`, or `grounding.py`.
- The five canonical GAD counting-rule strings (day-one seed = fallback = backfill):

```python
FALLBACK_GAD_INSTRUCTIONS = {
    "GAD-01": (
        "Count each unique instance of gender stereotypes or gender-biased "
        "representations \u2014 content that reinforces stereotypes about gender "
        "roles, abilities, behaviors, occupations, or characteristics, or that "
        "explicitly or implicitly portrays one gender using stereotypical "
        "assumptions. Do NOT count discussions of gender stereotypes presented "
        "for educational, analytical, historical, or critical purposes, or "
        "gender-neutral content. Count each unique instance once."
    ),
    "GAD-02": (
        "Count meaningful female and male representations: named individuals, "
        "names listed under a gender-labeled group or heading, characters, "
        "illustrations depicting people, examples or case studies involving "
        "people, explicit gender references (woman, man, girl, boy, female, "
        "male), and gender-specific pronouns (she, her, he, him). Count each "
        "meaningful representation once within the same discussion, example, or "
        "scenario; if the same individual appears in different examples, count "
        "each appearance separately. Do NOT infer gender when it is ambiguous, "
        "and ignore gender-neutral references."
    ),
    "GAD-03": (
        "Count each unique instance that portrays one gender as less capable, "
        "less respected, less deserving, or as having fewer opportunities than "
        "another. Do NOT count discussions of discrimination presented for "
        "educational, analytical, historical, or critical purposes. Count each "
        "unique instance once."
    ),
    "GAD-04": (
        "Count each unique instance where the material excludes one gender's "
        "experiences, disproportionately favors one gender's experiences, or "
        "assumes that activities, roles, responsibilities, interests, or "
        "aspirations belong primarily to one gender. Do NOT count "
        "gender-neutral examples or discussions presented for educational, "
        "analytical, historical, or critical purposes. Count each unique "
        "instance once."
    ),
    "GAD-05": (
        "Count each unique instance of discriminatory, prejudicial, "
        "exclusionary, or inequality-promoting content related to gender, race, "
        "social class, disability, religion, sexual orientation, or ethnic "
        "background. Do NOT count historical, educational, analytical, or "
        "critical discussions of discrimination. Count each unique instance "
        "once."
    ),
}
```

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `server/modules/agents/gad/prompt.py` | builds the combined GAD extraction prompt | add `FALLBACK_GAD_INSTRUCTIONS`; `build_combined_prompt` gains `scoring_rules`; inject per-criterion rule ahead of the fixed scaffold |
| `server/modules/agents/gad/pipeline.py` | GAD execution engine | add `_rubric_scoring_rules` method; resolve `{code: db_rule or fallback}`; thread `scoring_rules` through `_fit_gad_chunks` + both `build_combined_prompt` calls |
| `server/alembic/versions/20260829_0002_backfill_gad_scoring_rule.py` | data-only migration | **new** — `UPDATE` the 5 GAD rows on upgrade, null them on downgrade |
| `server/data/rubrics/rubrics.json` | seed rubric data | add `scoring_rule` to the 5 GAD criteria |
| `client/src/features/admin/rubric-editor/components/RubricTableEditor.tsx` | rubric editor table | treat `gad` as a wired agent (drop the "not used yet" note for GAD rows) |
| `server/tests/agents/gad/test_gad_dynamic_rules.py` | **new** — prompt injection + pipeline wiring tests | |
| `server/tests/migrations/test_gad_scoring_rule_backfill_migration.py` | **new** — migration up/down test | |
| `server/tests/migrations/test_curriculum_map_migration.py` | lineage guard | bump `CHAIN_HEAD_REV` to `20260829_0002` |
| `server/tests/migrations/test_migration_lineage_bridge.py` | lineage guard | bump head assertion; add `20260829_0002` down_revision assertion |
| `server/tests/rubrics/test_rubrics.py` | rubric reader tests | add `get_active_rubric_scoring_rules("gad")` case |
| `client/src/features/admin/rubric-editor/components/__tests__/RubricTableEditor.test.tsx` | editor component test | GAD row has no note; add an ITSO row as the "not used yet" example |

---

### Task 1: Inject per-criterion counting rules into the GAD prompt

**Files:**
- Modify: `server/modules/agents/gad/prompt.py`
- Test: `server/tests/agents/gad/test_gad_dynamic_rules.py` (create)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `FALLBACK_GAD_INSTRUCTIONS: dict[str, str]` in `server/modules/agents/gad/prompt.py` — keys `"GAD-01"`..`"GAD-05"`, values exactly the strings in Global Constraints.
  - `build_combined_prompt(*, packed_chunks, prompt_version, gad_managed_prompt=None, scoring_rules=None)` — `scoring_rules` is `dict[str, str] | None`; `None` is treated as `{}`. Per criterion the emitted block is `"{criterion_id} ({title}):\n    {scoring_rules.get(code) or FALLBACK_GAD_INSTRUCTIONS[code]}\n\n"` followed by the existing fixed scaffold lines for that criterion type.

- [ ] **Step 1: Write the failing test**

Create `server/tests/agents/gad/test_gad_dynamic_rules.py`:

```python
"""Dynamic per-criterion counting rules for the GAD extraction prompt."""

from __future__ import annotations

import json

from server.modules.agents.gad.prompt import (
    FALLBACK_GAD_INSTRUCTIONS,
    build_combined_prompt,
)

_CHUNKS = [{"chunk_id": "c1", "text": "Sample learning material text."}]


def _instructions(prompt: str) -> str:
    return "\n".join(json.loads(prompt)["instructions"])


def test_all_five_codes_have_fallback_text() -> None:
    assert set(FALLBACK_GAD_INSTRUCTIONS) == {
        "GAD-01",
        "GAD-02",
        "GAD-03",
        "GAD-04",
        "GAD-05",
    }
    assert all(v.strip() for v in FALLBACK_GAD_INSTRUCTIONS.values())


def test_prompt_uses_fallback_when_no_rules_supplied() -> None:
    text = _instructions(
        build_combined_prompt(packed_chunks=_CHUNKS, prompt_version="v1")
    )
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-01"] in text
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-05"] in text


def test_supplied_rule_overrides_fallback_per_criterion() -> None:
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            prompt_version="v1",
            scoring_rules={"GAD-01": "EDITED GAD-01 COUNTING RULE"},
        )
    )
    assert "EDITED GAD-01 COUNTING RULE" in text
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-01"] not in text
    # untouched criteria still use the fallback
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-02"] in text


def test_structural_scaffold_survives_rule_injection() -> None:
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            prompt_version="v1",
            scoring_rules={c: f"rule {c}" for c in FALLBACK_GAD_INSTRUCTIONS},
        )
    )
    assert "exact 'excerpt'" in text
    assert "'chunk_id'" in text
    assert "Do NOT include" in text and "score" in text
    assert "10" in text  # MAX_INSTANCES_PER_CRITERION still stated
    # GAD-02 balance scaffold still present
    assert "female_count" in text and "male_count" in text


def test_blank_rule_falls_back() -> None:
    text = _instructions(
        build_combined_prompt(
            packed_chunks=_CHUNKS,
            prompt_version="v1",
            scoring_rules={"GAD-03": "   "},
        )
    )
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-03"] in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/agents/gad/test_gad_dynamic_rules.py -q`
Expected: FAIL — `ImportError: cannot import name 'FALLBACK_GAD_INSTRUCTIONS'`.

- [ ] **Step 3: Add `FALLBACK_GAD_INSTRUCTIONS`**

In `server/modules/agents/gad/prompt.py`, after the imports and before `build_combined_prompt`, add the `FALLBACK_GAD_INSTRUCTIONS` dict exactly as written in Global Constraints.

- [ ] **Step 4: Add the `scoring_rules` parameter and inject**

Change the signature:

```python
def build_combined_prompt(
    *,
    packed_chunks: list[dict[str, Any]],
    prompt_version: str | None,
    gad_managed_prompt: str | None = None,
    scoring_rules: dict[str, str] | None = None,
) -> str:
```

Near the top of the body:

```python
    rules = scoring_rules or {}

    def _rule(code: str) -> str:
        supplied = rules.get(code)
        if supplied and supplied.strip():
            return supplied.strip()
        return FALLBACK_GAD_INSTRUCTIONS[code]
```

In the `for definition in registry.CRITERIA:` loop that builds `criterion_details`, replace the descriptive portions of both branches with the rule, keeping only the **structural** lines:

```python
    for definition in registry.CRITERIA:
        code = definition.criterion_id
        header = f"  {code} ({definition.title}):\n    {_rule(code)}\n"
        if definition.balance:
            criterion_details.append(
                header
                + "    - Return non-negative integer 'female_count' and "
                "'male_count'.\n"
                "    - Include a non-empty 'summary' (1-2 sentences).\n"
                "    - Do NOT include 'instances', 'instance_count', or any "
                "numeric score fields."
            )
        else:
            criterion_details.append(
                header
                + "    - Count instances with non-negative integer "
                "'instance_count'.\n"
                "    - List each unique instance with exact 'excerpt' "
                "and 'chunk_id' from document_chunks.\n"
                f"    - Max {MAX_INSTANCES_PER_CRITERION} instances.\n"
                "    - Include a non-empty 'summary' (1-2 sentences).\n"
                "    - Do NOT include numeric score fields."
            )
```

Add `FALLBACK_GAD_INSTRUCTIONS` to `__all__` (create `__all__` if the module has none — check the file end; currently it has no `__all__`, so add `__all__ = ["FALLBACK_GAD_INSTRUCTIONS", "build_combined_prompt", "build_combined_repair_prompt"]`).

- [ ] **Step 5: Run the new test to verify it passes**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/agents/gad/test_gad_dynamic_rules.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Run the existing GAD prompt tests and fix fallout**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/agents/gad/ -q`
Expected: PASS. If `test_gad_single_pass.py` / `test_gad_scoring.py` assertions about specific old wording fail (e.g. a check for a phrase that moved into `FALLBACK_GAD_INSTRUCTIONS`), update those assertions to look for the new canonical text or the structural scaffold — do not weaken a score-word absence check (`test_no_score_terms...` must still pass; the fallback strings contain no "score"/"band"/"rating").

- [ ] **Step 7: Lint**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && uv run --project server ruff check server/modules/agents/gad/prompt.py server/tests/agents/gad/test_gad_dynamic_rules.py`
Expected: clean (or only pre-existing warnings unrelated to these files).

- [ ] **Step 8: Commit**

```bash
git add server/modules/agents/gad/prompt.py server/tests/agents/gad/test_gad_dynamic_rules.py
git commit -m "feat(gad): inject per-criterion counting rules into the extraction prompt"
```

---

### Task 2: Wire the DB rules into the GAD pipeline

**Files:**
- Modify: `server/modules/agents/gad/pipeline.py`
- Test: `server/tests/agents/gad/test_gad_dynamic_rules.py` (append)

**Interfaces:**
- Consumes: `build_combined_prompt(..., scoring_rules=...)` and `FALLBACK_GAD_INSTRUCTIONS` from Task 1; `get_active_rubric_scoring_rules(agent_id, db=None) -> dict[str, str]` and `resolve_rubric_agent_id(source_type) -> str` from `server.modules.rubrics.service` (already exist).
- Produces:
  - `GADScoredAgent._rubric_scoring_rules(self, db: Any | None = None) -> dict[str, str]` — returns `get_active_rubric_scoring_rules(resolve_rubric_agent_id(self.rubric_source_type), db=db)`.
  - `_fit_gad_chunks(chunks, *, budget, prompt_version, managed_prompt, scoring_rules)` — new required keyword `scoring_rules: dict[str, str]`, forwarded to its internal `build_combined_prompt` call.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/agents/gad/test_gad_dynamic_rules.py`. Use the same `_SequenceLLM` test-double shape the existing GAD suite uses (`server/tests/agents/gad/test_gad_scoring.py` lines ~47-82) — copy it locally so the new file is self-contained:

```python
import uuid

from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.gad.agent import GAD

_FIVE_SECTION_RESPONSE = {
    "gad-01": {"criterion": "x", "instance_count": 0, "instances": [],
               "summary": "none."},
    "gad-02": {"criterion": "x", "female_count": 0, "male_count": 0,
               "summary": "balanced."},
    "gad-03": {"criterion": "x", "instance_count": 0, "instances": [],
               "summary": "none."},
    "gad-04": {"criterion": "x", "instance_count": 0, "instances": [],
               "summary": "none."},
    "gad-05": {"criterion": "x", "instance_count": 0, "instances": [],
               "summary": "none."},
}


class _SequenceLLM:
    model = "gad-test-model"

    def __init__(self) -> None:
        self.prompts: list[dict] = []

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        del temperature, max_new_tokens
        self.prompts.append(json.loads(prompt))
        return json.dumps(_FIVE_SECTION_RESPONSE)

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None,
        response_contract: ResponseContract,
    ) -> CompletionResult:
        del deadline
        assert response_contract.mode == "json_object"
        return CompletionResult(
            content=self.generate(
                prompt, temperature=temperature, max_new_tokens=max_new_tokens
            ),
            served_model=self.model,
            finish_reason="stop",
        )


_DOC_CHUNKS = [
    {"chunk_id": "c1", "page_number": 1,
     "text": "The learning material discusses community roles and helpers."}
]


def _run_gad(monkeypatch, rules: dict[str, str]) -> str:
    monkeypatch.setattr(
        "server.modules.agents.gad.pipeline.GADScoredAgent._rubric_scoring_rules",
        lambda self, db=None: rules,
    )
    fake = _SequenceLLM()
    GAD(llm_client=fake).run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_DOC_CHUNKS,
    )
    return "\n".join(fake.prompts[0]["instructions"])


def test_db_rule_reaches_the_extraction_prompt(monkeypatch) -> None:
    text = _run_gad(monkeypatch, {"GAD-01": "EDITED GAD-01 COUNTING RULE"})
    assert "EDITED GAD-01 COUNTING RULE" in text
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-02"] in text


def test_empty_db_rules_fall_back(monkeypatch) -> None:
    text = _run_gad(monkeypatch, {})
    assert FALLBACK_GAD_INSTRUCTIONS["GAD-01"] in text
```

Note: `test_gad_dynamic_rules.py` must `import json` at the top (Task 1 already added it via the `_instructions` helper — confirm it is there).

- [ ] **Step 2: Run to verify it fails**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/agents/gad/test_gad_dynamic_rules.py::test_db_rule_reaches_the_extraction_prompt -q`
Expected: FAIL — `AttributeError: ... has no attribute '_rubric_scoring_rules'` (the monkeypatch target does not exist yet).

- [ ] **Step 3: Add the reader method**

In `server/modules/agents/gad/pipeline.py`:

Add imports near the other `server.` imports:

```python
from server.modules.rubrics.service import (
    get_active_rubric_scoring_rules,
    resolve_rubric_agent_id,
)
```

and add to the `from . import ...` line or a new import: `from .prompt import FALLBACK_GAD_INSTRUCTIONS`.

On `class GADScoredAgent`, add:

```python
    def _rubric_scoring_rules(self, db: Any | None = None) -> dict[str, str]:
        """Active per-criterion counting rules for this agent's rubric.

        A method (not a bare call) so tests can patch it without a DB — a
        bare ``get_active_rubric_scoring_rules`` reaches ``get_session_factory``
        and raises ``InfrastructureUnavailableError`` under ``DATABASE_URL=''``.
        """
        return get_active_rubric_scoring_rules(
            resolve_rubric_agent_id(self.rubric_source_type), db=db
        )
```

- [ ] **Step 4: Resolve and thread `scoring_rules` through `_run_gad_scoring`**

In `_run_gad_scoring`, before the `_fit_gad_chunks` call, build the resolved map:

```python
        db_rules = self._rubric_scoring_rules()
        scoring_rules = {
            d.criterion_id: (db_rules.get(d.criterion_id) or "").strip()
            or FALLBACK_GAD_INSTRUCTIONS[d.criterion_id]
            for d in registry.CRITERIA
        }
```

Add `scoring_rules` as a required keyword to `_fit_gad_chunks`:

```python
def _fit_gad_chunks(
    chunks: list[dict[str, Any]],
    *,
    budget: int,
    prompt_version: str | None,
    managed_prompt: str | None,
    scoring_rules: dict[str, str],
) -> tuple[list[dict[str, Any]], bool]:
```

and forward it in that function's internal `rendered()`:

```python
    def rendered(items: list[dict[str, Any]]) -> str:
        return prompt.build_combined_prompt(
            packed_chunks=items,
            prompt_version=prompt_version,
            gad_managed_prompt=managed_prompt,
            scoring_rules=scoring_rules,
        )
```

Update the `_fit_gad_chunks(...)` call in `_run_gad_scoring` to pass `scoring_rules=scoring_rules`.

Update the real `prompt.build_combined_prompt(...)` call in `_run_gad_scoring` (the one assigned to `combined_prompt`) to pass `scoring_rules=scoring_rules`.

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/agents/gad/test_gad_dynamic_rules.py -q`
Expected: PASS (7 tests).

- [ ] **Step 6: Run the full GAD + supervision agent suites**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/agents/gad/ server/tests/agents/integration/ -q`
Expected: PASS, except the two pre-existing failures noted in the branch's test baseline (`test_sme_dispatch_contract`, `test_itso_supervision_boundaries` if already failing on this branch — verify with `git stash` if unsure). Any GAD or `_fit_gad_chunks` call-site failure is real and must be fixed (a test that calls `_fit_gad_chunks` directly now needs `scoring_rules={...}`).

- [ ] **Step 7: Lint**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && uv run --project server ruff check server/modules/agents/gad/pipeline.py`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add server/modules/agents/gad/pipeline.py server/tests/agents/gad/test_gad_dynamic_rules.py
git commit -m "feat(gad): read per-criterion counting rules from the active rubric"
```

---

### Task 3: Backfill migration + seed data + reader coverage

**Files:**
- Create: `server/alembic/versions/20260829_0002_backfill_gad_scoring_rule.py`
- Create: `server/tests/migrations/test_gad_scoring_rule_backfill_migration.py`
- Modify: `server/data/rubrics/rubrics.json`
- Modify: `server/tests/migrations/test_curriculum_map_migration.py:77`
- Modify: `server/tests/migrations/test_migration_lineage_bridge.py:92`
- Modify: `server/tests/rubrics/test_rubrics.py`

**Interfaces:**
- Consumes: `FALLBACK_GAD_INSTRUCTIONS` values from Task 1 (copied verbatim, not imported).
- Produces: Alembic revision `20260829_0002` with `down_revision = "20260829_0001"`; the migration tree's single head becomes `20260829_0002`.

- [ ] **Step 1: Write the failing migration test**

Create `server/tests/migrations/test_gad_scoring_rule_backfill_migration.py`. Model it **exactly** on the existing `server/tests/migrations/test_rubric_scoring_rule_migration.py` — copy its `ROOT`, `_config`, `_run`, and `_seed_minimal_rubrics` helpers verbatim (note: `ROOT = Path(__file__).resolve().parents[2]` and `Config(str(ROOT / "alembic.ini"))`, NOT `parents[3]` / `"server" / "alembic.ini"`). That helper hand-creates the three rubric tables **without** a `scoring_rule` column and stamps `alembic_version` to `20260820_0002`, seeding one SME criterion (`c-sme`, `A-02`) and one GAD criterion (`c-gad`, `GAD-01`).

```python
"""Tests for 20260829_0002_backfill_gad_scoring_rule migration."""

from __future__ import annotations

import os
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

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


def test_backfill_sets_gad_rules_and_downgrade_clears_them(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'gad_backfill.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        _seed_minimal_rubrics(conn)

    # Runs 20260829_0001 (add column + backfill sme/coord) then 20260829_0002.
    _run(upgrade, _config(url), "20260829_0002")
    with engine.connect() as conn:
        assert (
            MigrationContext.configure(conn).get_current_revision()
            == "20260829_0002"
        )
        gad_rule = conn.execute(
            text("SELECT scoring_rule FROM rubric_criteria "
                 "WHERE rubric_criterion_id='c-gad'")
        ).scalar()
        sme_rule = conn.execute(
            text("SELECT scoring_rule FROM rubric_criteria "
                 "WHERE rubric_criterion_id='c-sme'")
        ).scalar()
    assert gad_rule is not None and "unique instance" in gad_rule
    assert sme_rule is not None  # set by 20260829_0001, untouched here

    # Downgrade one step: GAD rows null again, column still present.
    _run(downgrade, _config(url), "20260829_0001")
    with engine.connect() as conn:
        gad_after = conn.execute(
            text("SELECT scoring_rule FROM rubric_criteria "
                 "WHERE rubric_criterion_id='c-gad'")
        ).scalar()
        sme_after = conn.execute(
            text("SELECT scoring_rule FROM rubric_criteria "
                 "WHERE rubric_criterion_id='c-sme'")
        ).scalar()
    assert gad_after is None
    assert sme_after is not None  # 0001's backfill still stands

    engine.dispose()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/migrations/test_gad_scoring_rule_backfill_migration.py -q`
Expected: FAIL — `alembic.util.exc.CommandError: Can't locate revision identified by '20260829_0002'`.

- [ ] **Step 3: Write the migration**

Create `server/alembic/versions/20260829_0002_backfill_gad_scoring_rule.py`:

```python
"""backfill scoring_rule for GAD rubric criteria

Revision ID: 20260829_0002
Revises: 20260829_0001
Create Date: 2026-08-29
"""

import sqlalchemy as sa

from alembic import op

revision = "20260829_0002"
down_revision = "20260829_0001"
branch_labels = None
depends_on = None

# Verbatim copy of server/modules/agents/gad/prompt.py's
# FALLBACK_GAD_INSTRUCTIONS at the time of writing. Embedded here because
# migrations must not import app code that can change.
_GAD_RULES = {
    "GAD-01": (
        "Count each unique instance of gender stereotypes or gender-biased "
        "representations \u2014 content that reinforces stereotypes about gender "
        "roles, abilities, behaviors, occupations, or characteristics, or that "
        "explicitly or implicitly portrays one gender using stereotypical "
        "assumptions. Do NOT count discussions of gender stereotypes presented "
        "for educational, analytical, historical, or critical purposes, or "
        "gender-neutral content. Count each unique instance once."
    ),
    "GAD-02": (
        "Count meaningful female and male representations: named individuals, "
        "names listed under a gender-labeled group or heading, characters, "
        "illustrations depicting people, examples or case studies involving "
        "people, explicit gender references (woman, man, girl, boy, female, "
        "male), and gender-specific pronouns (she, her, he, him). Count each "
        "meaningful representation once within the same discussion, example, or "
        "scenario; if the same individual appears in different examples, count "
        "each appearance separately. Do NOT infer gender when it is ambiguous, "
        "and ignore gender-neutral references."
    ),
    "GAD-03": (
        "Count each unique instance that portrays one gender as less capable, "
        "less respected, less deserving, or as having fewer opportunities than "
        "another. Do NOT count discussions of discrimination presented for "
        "educational, analytical, historical, or critical purposes. Count each "
        "unique instance once."
    ),
    "GAD-04": (
        "Count each unique instance where the material excludes one gender's "
        "experiences, disproportionately favors one gender's experiences, or "
        "assumes that activities, roles, responsibilities, interests, or "
        "aspirations belong primarily to one gender. Do NOT count "
        "gender-neutral examples or discussions presented for educational, "
        "analytical, historical, or critical purposes. Count each unique "
        "instance once."
    ),
    "GAD-05": (
        "Count each unique instance of discriminatory, prejudicial, "
        "exclusionary, or inequality-promoting content related to gender, race, "
        "social class, disability, religion, sexual orientation, or ethnic "
        "background. Do NOT count historical, educational, analytical, or "
        "critical discussions of discrimination. Count each unique instance "
        "once."
    ),
}

_SCOPE = (
    " AND rubric_domain_id IN ("
    "  SELECT rd.rubric_domain_id FROM rubric_domains rd "
    "  JOIN rubric_sets rs ON rs.rubric_set_id = rd.rubric_set_id "
    "  WHERE rs.agent_id = 'gad')"
)


def upgrade():
    bind = op.get_bind()
    for code, rule in _GAD_RULES.items():
        bind.execute(
            sa.text(
                "UPDATE rubric_criteria SET scoring_rule = :rule "
                "WHERE criterion_code = :code" + _SCOPE
            ),
            {"rule": rule, "code": code},
        )


def downgrade():
    bind = op.get_bind()
    for code in _GAD_RULES:
        bind.execute(
            sa.text(
                "UPDATE rubric_criteria SET scoring_rule = NULL "
                "WHERE criterion_code = :code" + _SCOPE
            ),
            {"code": code},
        )
```

- [ ] **Step 4: Run the migration test**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/migrations/test_gad_scoring_rule_backfill_migration.py -q`
Expected: PASS.

- [ ] **Step 5: Update the two lineage guards**

`server/tests/migrations/test_curriculum_map_migration.py` line ~76-77: change the comment and constant to:

```python
#: rubric-criterion GAD scoring_rule backfill (20260829_0002).
CHAIN_HEAD_REV = "20260829_0002"
```

`server/tests/migrations/test_migration_lineage_bridge.py` line 92:

```python
    assert script.get_heads() == ["20260829_0002"]
```

and after line 99 add:

```python
    assert script.get_revision("20260829_0002").down_revision == "20260829_0001"
```

- [ ] **Step 6: Run the migration lineage suite**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/migrations/ -q`
Expected: PASS (all lineage/single-head tests green).

- [ ] **Step 7: Add the GAD rules to `rubrics.json`**

In `server/data/rubrics/rubrics.json`, for the `agent_id: "gad"` rubric set, add a `"scoring_rule"` key to each of the 5 criteria objects, value = the matching `_GAD_RULES` / `FALLBACK_GAD_INSTRUCTIONS` string (use the real `—` em-dash character in the JSON, not `\u2014`).

- [ ] **Step 8: Add reader coverage**

In `server/tests/rubrics/test_rubrics.py`, add (the `_seed_from_json` helper there already forwards `scoring_rule` from JSON):

```python
def test_active_rubric_scoring_rules_returns_gad_rules(db_session) -> None:
    from server.modules.rubrics.service import get_active_rubric_scoring_rules

    _seed_from_json(db_session)

    rules = get_active_rubric_scoring_rules("gad", db=db_session)
    assert set(rules) == {"GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"}
    assert "unique instance" in rules["GAD-01"]
```

- [ ] **Step 9: Assert the three copies match**

Add to `server/tests/agents/gad/test_gad_dynamic_rules.py`:

```python
def test_seed_json_matches_fallback_constant() -> None:
    import json as _json
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    payload = _json.loads(
        (root / "data" / "rubrics" / "rubrics.json").read_text(encoding="utf-8")
    )
    gad_set = next(s for s in payload["rubric_sets"] if s["agent_id"] == "gad")
    seeded = {
        c["criterion_code"]: c["scoring_rule"]
        for d in gad_set["domains"]
        for c in d["criteria"]
    }
    assert seeded == FALLBACK_GAD_INSTRUCTIONS
```

(The migration's `_GAD_RULES` is checked by eye against `FALLBACK_GAD_INSTRUCTIONS` during review — it is a copy in a file that must not import app code.)

- [ ] **Step 10: Run the rubric + GAD suites**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/rubrics/ server/tests/agents/gad/ -q`
Expected: PASS.

- [ ] **Step 11: Apply the migration to the shared Neon dev DB**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server alembic -c server/alembic.ini upgrade head`
Expected: `Running upgrade 20260829_0001 -> 20260829_0002`. Then verify:
`PYTHONPATH=. uv run --project server python -c "from server.modules.rubrics.service import get_active_rubric_scoring_rules as g; print(sorted(g('gad')))"`
Expected: `['GAD-01', 'GAD-02', 'GAD-03', 'GAD-04', 'GAD-05']`.

- [ ] **Step 12: Lint**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && uv run --project server ruff check server/alembic/versions/20260829_0002_backfill_gad_scoring_rule.py server/tests/migrations/test_gad_scoring_rule_backfill_migration.py`
Expected: clean.

- [ ] **Step 13: Commit**

```bash
git add server/alembic/versions/20260829_0002_backfill_gad_scoring_rule.py \
  server/tests/migrations/test_gad_scoring_rule_backfill_migration.py \
  server/tests/migrations/test_curriculum_map_migration.py \
  server/tests/migrations/test_migration_lineage_bridge.py \
  server/data/rubrics/rubrics.json \
  server/tests/rubrics/test_rubrics.py \
  server/tests/agents/gad/test_gad_dynamic_rules.py
git commit -m "feat(rubrics): backfill and seed GAD criterion counting rules"
```

---

### Task 4: Rubric Editor — treat GAD as a wired agent

**Files:**
- Modify: `client/src/features/admin/rubric-editor/components/RubricTableEditor.tsx:12,112`
- Test: `client/src/features/admin/rubric-editor/components/__tests__/RubricTableEditor.test.tsx`

**Interfaces:**
- Consumes: nothing from backend tasks (pure UI copy change).
- Produces: no exported symbols; GAD rows no longer render the "Stored for reference — not used by this agent's scoring yet." note.

- [ ] **Step 1: Update the failing test**

In `client/src/features/admin/rubric-editor/components/__tests__/RubricTableEditor.test.tsx`:

Add an ITSO rubric set to `mockData.rubric_sets` (after the `set-gad` entry) so there is still a non-wired agent to assert the note on:

```ts
    {
      rubric_set_id: 'set-itso',
      agent_id: 'itso',
      name: 'ITSO Rubric v1',
      version_number: 1,
      status: 'active',
      domains: [
        {
          rubric_domain_id: 'dom-itso',
          code: 'IP',
          title: 'IP Compliance',
          display_order: 1,
          criteria: [
            {
              rubric_criterion_id: 'crit-itso1',
              criterion_code: 'IP-01',
              title: 'Attribution',
              description: 'Sources are attributed.',
              scoring_rule: null,
              display_order: 1,
            },
          ],
        },
      ],
    },
```

Replace the `'shows a "not used yet" note for non-SME agents'` test with:

```ts
  it('shows the "not used yet" note for ITSO but not for GAD', () => {
    render(<RubricTableEditor />);
    const notes = screen.getAllByText(/not used by this agent's scoring yet/i);
    // exactly one note — the ITSO row; GAD no longer shows it
    expect(notes).toHaveLength(1);
  });
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED/client && pnpm vitest run src/features/admin/rubric-editor/components/__tests__/RubricTableEditor.test.tsx`
Expected: FAIL — two notes found (GAD + ITSO), expected 1.

- [ ] **Step 3: Make GAD a wired agent**

In `RubricTableEditor.tsx`, line 12, replace:

```ts
const WIRED_AGENT = 'sme';
```

with:

```ts
const WIRED_AGENTS = new Set(['sme', 'gad']);
```

and line ~112, replace:

```ts
          const isWired = rubricSet.agent_id === WIRED_AGENT;
```

with:

```ts
          const isWired = WIRED_AGENTS.has(rubricSet.agent_id);
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED/client && pnpm vitest run src/features/admin/rubric-editor/`
Expected: PASS.

- [ ] **Step 5: Lint + typecheck**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED/client && pnpm lint && pnpm build`
Expected: clean; build succeeds.

- [ ] **Step 6: Commit**

```bash
git add client/src/features/admin/rubric-editor/components/RubricTableEditor.tsx \
  client/src/features/admin/rubric-editor/components/__tests__/RubricTableEditor.test.tsx
git commit -m "feat(rubric-editor): mark GAD scoring rules as wired"
```

---

### Task 5: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Backend targeted suites**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/agents/gad/ server/tests/rubrics/ server/tests/migrations/ server/tests/agents/integration/ -q`
Expected: PASS except the branch's known pre-existing failures. Compare the failure set to a `git stash && pytest ... && git stash pop` run if anything looks new.

- [ ] **Step 2: Backend full suite**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest -q`
Expected: same pass/fail counts as the branch baseline plus the new GAD/migration tests passing. The 14 pre-existing Windows/env failures (`core/`, `documents/`, `test_coordinator_contract`, `test_sme_dispatch_contract`) are unchanged and unrelated.

- [ ] **Step 3: Frontend full suite**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED/client && pnpm vitest run && pnpm lint && pnpm build`
Expected: all green; build succeeds.

- [ ] **Step 4: Manual smoke (optional, needs the dev stack)**

Start backend + `client` dev server, open the Rubric Editor as an admin, confirm: GAD rows show an editable scoring-rule textarea with the seeded counting guidance and **no** "not used yet" note; Coordinator and ITSO rows still show the note. Edit a GAD rule, save, run an evaluation, and confirm the GAD extraction prompt (log / provenance) carries the edited text.

- [ ] **Step 5: Update the design-tension memory**

Append to `~/.claude/projects/C--Users-Admin-Desktop-PROJECTS-EquipED/memory/sme-dynamic-rubric-dpo-tension.md` a note that GAD's *counting guidance* (not its bands) is now DB-driven via `scoring_rule` + `FALLBACK_GAD_INSTRUCTIONS`, migration `20260829_0002`, and that GAD bands remain hardcoded (structured-bands design still deferred).

---

### Task 6: Trim the managed GAD prompt to framing-only

**Why:** the active managed GAD prompt (`prompt_versions` row for `agent_id='gad'`, seeded by migration `20260716_0001` = `FACT_ONLY_GAD_PROMPT`) is injected into `build_combined_prompt` as `instruction_parts[0]`. It still contains a full `CRITERIA:` section with per-criterion "Count X / Do NOT count Y" for GAD-01..05 — which, after Tasks 1-3, is **also** emitted from `PER-CRITERION DETAILS` using the Rubric Editor's `scoring_rule`. Two editable sources of the same guidance that will drift. This task removes the duplication by trimming the managed prompt to role/task/output-format framing only; the per-criterion "what counts" then lives solely in the Rubric Editor, the structural scaffold + `CRITICAL RULES` solely in `prompt.py`.

**Files:**
- Create: `server/alembic/versions/20260829_0003_trim_gad_managed_prompt.py`
- Create: `server/tests/migrations/test_trim_gad_managed_prompt_migration.py`
- Modify: `server/tests/migrations/test_curriculum_map_migration.py` (`CHAIN_HEAD_REV`)
- Modify: `server/tests/migrations/test_migration_lineage_bridge.py` (head assertion + new down_revision assertion)
- Modify: `server/tests/agents/gad/test_gad_dynamic_rules.py` (add a no-duplication assertion)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: Alembic revision `20260829_0003`, `down_revision = "20260829_0002"`; single head becomes `20260829_0003`.

**Canonical trimmed prompt text** (use verbatim, this is the whole new `prompt_text`):

```
You are a Gender and Development (GAD) fact extractor for Student Learning Materials (SLMs). Your role is to examine the provided document chunks and extract specific factual observations for each GAD criterion. Do not assign numeric scores. Do not write recommendations beyond the required per-criterion summary.

TASK:
Work only from the provided document_chunks. Do not use external knowledge, syllabus, curriculum, or reference materials as factual sources. For each of the five GAD criteria you will be given the specific counting rule to apply and the exact fields to return.

OUTPUT FORMAT:
Return a single JSON object with exactly five keys: 'gad-01', 'gad-02', 'gad-03', 'gad-04', 'gad-05', and nothing else.
```

- [ ] **Step 1: Write the failing migration test**

Create `server/tests/migrations/test_trim_gad_managed_prompt_migration.py`, modeled **exactly** on `server/tests/migrations/test_sme_extraction_prompt_migration.py` (the `importlib.import_module` + `_run` + bare `prompt_versions` table pattern — NOT the alembic-command pattern). Adapt: agent `"gad"`, `BASE, HEAD = "20260829_0002", "20260829_0003"`, the migration module name `server.alembic.versions.20260829_0003_trim_gad_managed_prompt`, and this task's `SEEDED_ID` (pick a fresh fixed UUID, e.g. `"c3d4e5f6-a7b8-9012-cdef-345678901234"`).

```python
"""Verify the GAD managed-prompt trim migration."""

from __future__ import annotations

import importlib

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

BASE, HEAD = "20260829_0002", "20260829_0003"
SEEDED_ID = "c3d4e5f6-a7b8-9012-cdef-345678901234"
MODULE = "server.alembic.versions.20260829_0003_trim_gad_managed_prompt"


def _run(engine, operation):
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            operation()


def _engine(tmp_path, rows):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'gadprompt.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE prompt_versions ("
                "version_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
                "version_number INTEGER NOT NULL, prompt_text TEXT NOT NULL, "
                "is_active BOOLEAN NOT NULL, motivation TEXT, "
                "created_at DATETIME NOT NULL, updated_by TEXT NULL, "
                "CONSTRAINT uq_prompt_versions_agent_version "
                "UNIQUE (agent_id, version_number))"
            )
        )
        conn.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        conn.execute(
            text("INSERT INTO alembic_version VALUES (:r)"), {"r": BASE}
        )
        for vid, agent, number, active, ptext in rows:
            conn.execute(
                text(
                    "INSERT INTO prompt_versions VALUES "
                    "(:id, :agent, :n, :pt, :a, 'seed', '2026-01-01', NULL)"
                ),
                {"id": vid, "agent": agent, "n": number, "pt": ptext, "a": active},
            )
    return engine


def _active(conn, agent="gad"):
    return (
        conn.execute(
            text(
                "SELECT version_id, prompt_text FROM prompt_versions "
                "WHERE agent_id=:a AND is_active=1 ORDER BY version_number"
            ),
            {"a": agent},
        )
        .mappings()
        .all()
    )


def test_upgrade_seeds_trimmed_prompt_and_is_idempotent(tmp_path):
    old = "You are a GAD fact extractor.\n\nCRITERIA:\nGAD-01 ... Count each unique instance ..."
    engine = _engine(tmp_path, [("gad-v1", "gad", 1, 1, old), ("sme-v1", "sme", 1, 1, "x")])
    migration = importlib.import_module(MODULE)
    assert migration.revision == HEAD and migration.down_revision == BASE
    _run(engine, migration.upgrade)
    _run(engine, migration.upgrade)  # idempotent
    with engine.connect() as conn:
        active = _active(conn)
        assert len(active) == 1
        assert active[0]["version_id"] == SEEDED_ID
        text_ = active[0]["prompt_text"]
        assert "OUTPUT FORMAT:" in text_
        assert "CRITERIA:" not in text_
        assert "Count each unique instance" not in text_
        assert "Do NOT count" not in text_
        # SME prompt untouched
        assert _active(conn, "sme")[0]["version_id"] == "sme-v1"
    engine.dispose()


def test_downgrade_restores_previous_active(tmp_path):
    old = "OLD GAD PROMPT WITH CRITERIA SECTION"
    engine = _engine(tmp_path, [("gad-v1", "gad", 1, 1, old)])
    migration = importlib.import_module(MODULE)
    _run(engine, migration.upgrade)
    _run(engine, migration.downgrade)
    with engine.connect() as conn:
        active = _active(conn)
        assert len(active) == 1
        assert active[0]["version_id"] == "gad-v1"
        assert conn.execute(
            text("SELECT 1 FROM prompt_versions WHERE version_id=:id"),
            {"id": SEEDED_ID},
        ).scalar() is None
    engine.dispose()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/migrations/test_trim_gad_managed_prompt_migration.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.alembic.versions.20260829_0003_trim_gad_managed_prompt'`.

- [ ] **Step 3: Write the migration**

Create `server/alembic/versions/20260829_0003_trim_gad_managed_prompt.py`, modeled on `server/alembic/versions/20260716_0001_update_gad_prompt_fact_only.py` (same deactivate-then-insert-active pattern, same downgrade shape). Key parts:

```python
"""Trim the managed GAD prompt to role/task framing only.

Revision ID: 20260829_0003
Revises: 20260829_0002
Create Date: 2026-08-29

The per-criterion "what counts" guidance now lives in
rubric_criteria.scoring_rule (Rubric Editor); the structural scaffold and
CRITICAL RULES live in server/modules/agents/gad/prompt.py. This removes
the duplicate CRITERIA / CRITICAL RULES sections from the managed prompt so
there is one editable source per concern.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

revision: str = "20260829_0003"
down_revision: str | None = "20260829_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRIMMED_GAD_PROMPT = (
    "You are a Gender and Development (GAD) fact extractor for Student "
    "Learning Materials (SLMs). Your role is to examine the provided "
    "document chunks and extract specific factual observations for each "
    "GAD criterion. Do not assign numeric scores. Do not write "
    "recommendations beyond the required per-criterion summary.\n\n"
    "TASK:\n"
    "Work only from the provided document_chunks. Do not use external "
    "knowledge, syllabus, curriculum, or reference materials as factual "
    "sources. For each of the five GAD criteria you will be given the "
    "specific counting rule to apply and the exact fields to return.\n\n"
    "OUTPUT FORMAT:\n"
    "Return a single JSON object with exactly five keys: 'gad-01', "
    "'gad-02', 'gad-03', 'gad-04', 'gad-05', and nothing else."
)

GAD_VERSION_ID = uuid.UUID("c3d4e5f6-a7b8-9012-cdef-345678901234")


def upgrade() -> None:
    conn = op.get_bind()
    op.execute(
        sa.text(
            "UPDATE prompt_versions SET is_active = :inactive "
            "WHERE agent_id = :agent_id AND is_active = :active"
        ).bindparams(inactive=False, agent_id="gad", active=True)
    )
    # Idempotent: if this exact version already exists, just re-activate it.
    existing = conn.execute(
        sa.text(
            "SELECT version_number FROM prompt_versions WHERE version_id = :id"
        ).bindparams(id=GAD_VERSION_ID)
    ).scalar()
    if existing is not None:
        op.execute(
            sa.text(
                "UPDATE prompt_versions SET is_active = :active "
                "WHERE version_id = :id"
            ).bindparams(active=True, id=GAD_VERSION_ID)
        )
        return
    current_max = conn.execute(
        sa.text(
            "SELECT COALESCE(MAX(version_number), 0) FROM prompt_versions "
            "WHERE agent_id = :agent_id"
        ).bindparams(agent_id="gad")
    ).scalar() or 0
    prompt_versions = sa.table(
        "prompt_versions",
        sa.column("version_id", sa.Uuid),
        sa.column("agent_id", sa.String),
        sa.column("version_number", sa.Integer),
        sa.column("prompt_text", sa.Text),
        sa.column("is_active", sa.Boolean),
        sa.column("motivation", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_by", sa.Uuid),
    )
    op.bulk_insert(
        prompt_versions,
        [
            {
                "version_id": GAD_VERSION_ID,
                "agent_id": "gad",
                "version_number": current_max + 1,
                "prompt_text": TRIMMED_GAD_PROMPT,
                "is_active": True,
                "motivation": (
                    "Trimmed managed GAD prompt to framing only; per-criterion "
                    "counting rules now live in rubric_criteria.scoring_rule "
                    "(dynamic GAD counting rules)"
                ),
                "created_at": datetime.utcnow(),
                "updated_by": None,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM prompt_versions "
            "WHERE agent_id = :agent_id AND version_id = :version_id"
        ).bindparams(agent_id="gad", version_id=GAD_VERSION_ID)
    )
    op.execute(
        sa.text(
            "UPDATE prompt_versions SET is_active = :active "
            "WHERE agent_id = :agent_id AND version_number = ("
            "  SELECT MAX(version_number) FROM prompt_versions "
            "  WHERE agent_id = :agent_id2)"
        ).bindparams(active=True, agent_id="gad", agent_id2="gad")
    )
```

Match `20260716_0001`'s exact style for `sa` / `op` imports and the `# type: ignore` comment so ruff (I, UP) stays clean.

- [ ] **Step 4: Run the migration test — GREEN**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/migrations/test_trim_gad_managed_prompt_migration.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Bump the two lineage guards**

`server/tests/migrations/test_curriculum_map_migration.py` — change the `CHAIN_HEAD_REV` comment + value to:

```python
#: managed GAD prompt trim (20260829_0003).
CHAIN_HEAD_REV = "20260829_0003"
```

`server/tests/migrations/test_migration_lineage_bridge.py` — change the head assertion (currently `== ["20260829_0002"]`) to `== ["20260829_0003"]` and add after the existing `20260829_0002` down_revision assertion:

```python
    assert script.get_revision("20260829_0003").down_revision == "20260829_0002"
```

- [ ] **Step 6: Add a no-duplication assertion to `test_gad_dynamic_rules.py`**

```python
def test_trimmed_managed_prompt_does_not_duplicate_criteria(monkeypatch) -> None:
    from server.alembic.versions import (  # noqa: E402
        _20260829_0003_trim_gad_managed_prompt as trim_mod,  # type: ignore
    )
```

If that dotted import name is not usable (leading digit), instead read the constant via `importlib`:

```python
def test_trimmed_managed_prompt_is_framing_only() -> None:
    import importlib

    mod = importlib.import_module(
        "server.alembic.versions.20260829_0003_trim_gad_managed_prompt"
    )
    p = mod.TRIMMED_GAD_PROMPT
    assert "OUTPUT FORMAT:" in p and "TASK:" in p
    assert "CRITERIA:" not in p
    assert "Count each unique instance" not in p
    assert "CRITICAL RULES:" not in p


def test_managed_prompt_and_rules_do_not_both_carry_criteria(monkeypatch) -> None:
    """With the trimmed framing as the managed prompt, per-criterion guidance
    appears once (from the injected rule), not twice."""
    import importlib

    from server.modules.agents.gad.prompt import (
        FALLBACK_GAD_INSTRUCTIONS,
        build_combined_prompt,
    )

    mod = importlib.import_module(
        "server.alembic.versions.20260829_0003_trim_gad_managed_prompt"
    )
    rendered = "\n".join(
        __import__("json").loads(
            build_combined_prompt(
                packed_chunks=[{"chunk_id": "c1", "text": "sample"}],
                prompt_version="v1",
                gad_managed_prompt=mod.TRIMMED_GAD_PROMPT,
            )
        )["instructions"]
    )
    # GAD-01 guidance shows exactly once
    assert rendered.count(FALLBACK_GAD_INSTRUCTIONS["GAD-01"]) == 1
```

Use whichever of the two import approaches ruff/pytest accepts; the module name starts with a digit so `importlib.import_module("server.alembic.versions.20260829_0003_trim_gad_managed_prompt")` is the reliable form.

- [ ] **Step 7: Run the migration + GAD suites**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/migrations/ server/tests/agents/gad/ server/tests/admin/test_prompts.py -q`
Expected: PASS. Single head `20260829_0003` (`test_curriculum_map_migration.py::test_single_head`).

- [ ] **Step 8: Apply to the shared Neon dev DB**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server alembic -c server/alembic.ini upgrade head`
Expected: `Running upgrade 20260829_0002 -> 20260829_0003`. Verify:
`PYTHONPATH=. uv run --project server python -c "from server.core.db import get_session_factory; from server.modules.admin.prompt_service import get_active_prompt; s=get_session_factory()(); p=get_active_prompt('gad', s); print('CRITERIA:' in (p.prompt_text if p else ''), '| len', len(p.prompt_text) if p else None)"`
Expected: `False | len ~520` (no CRITERIA section; short). If `get_active_prompt`'s import path differs, find it via `grep -rn "def get_active_prompt" server/`.

- [ ] **Step 9: Lint**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && uv run --project server ruff check server/alembic/versions/20260829_0003_trim_gad_managed_prompt.py server/tests/migrations/test_trim_gad_managed_prompt_migration.py server/tests/agents/gad/test_gad_dynamic_rules.py`
Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add server/alembic/versions/20260829_0003_trim_gad_managed_prompt.py \
  server/tests/migrations/test_trim_gad_managed_prompt_migration.py \
  server/tests/migrations/test_curriculum_map_migration.py \
  server/tests/migrations/test_migration_lineage_bridge.py \
  server/tests/agents/gad/test_gad_dynamic_rules.py
git commit -m "feat(gad): trim managed prompt to framing; criteria guidance lives in the rubric"
```

---

### Task 7: Make the per-criterion output schema explicit in the scaffold

**Why (root cause):** GAD evaluations fail with `GAD section 'gad-03' field 'instance_count' must be a non-negative integer` (envelope reference `1ee0d3a7f89ac383`). `envelope._validate_section` requires `instance_count` to be a present, real `int` (no coercion). Task 6 removed the managed GAD prompt's per-criterion "Return non-negative integer instance_count, a list of instances …, and a non-empty summary" reinforcement (it existed for all 5 criteria). What remains is the code scaffold's weak `- Count instances with non-negative integer 'instance_count'.`, which reads as an instruction to count, not to emit a typed field. The model now sometimes omits/mistypes `instance_count`; the strict envelope hard-fails the whole GAD agent, and repair (same frozen context) fails identically. `instance_count` is not even used for scoring — the score uses grounded `instances`; the claimed count only appears in the justification string.

**Files:**
- Modify: `server/modules/agents/gad/prompt.py` (`build_combined_prompt`, the `criterion_details` loop)
- Test: `server/tests/agents/gad/test_gad_dynamic_rules.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: no signature change. The per-criterion emitted block's structural-scaffold portion (the `-` bullets after the injected rule) is replaced with an explicit "return EXACTLY these fields" spec.

- [ ] **Step 1: Write the failing test**

Add to `server/tests/agents/gad/test_gad_dynamic_rules.py`:

```python
def test_scaffold_names_required_output_fields_explicitly() -> None:
    text = _instructions(
        build_combined_prompt(packed_chunks=_CHUNKS, prompt_version="v1")
    )
    # instance criteria must spell out the required fields as named JSON keys
    assert '"instance_count"' in text
    assert '"instances"' in text
    assert '"summary"' in text
    assert '"excerpt"' in text and '"chunk_id"' in text
    # balance criterion
    assert '"female_count"' in text and '"male_count"' in text
    # the wording must frame these as REQUIRED output fields, not just a task
    assert "EXACTLY these fields" in text
    # each instance criterion still tells the model to use 0 when none found
    assert "use 0 if none" in text
```

(`_instructions` and `_CHUNKS` already exist at the top of the file from Task 1.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/agents/gad/test_gad_dynamic_rules.py::test_scaffold_names_required_output_fields_explicitly -q`
Expected: FAIL — the current scaffold uses `- Count instances with non-negative integer 'instance_count'.`, not `"instance_count"` / `EXACTLY these fields`.

- [ ] **Step 3: Rewrite the scaffold**

In `build_combined_prompt`, in the `for definition in registry.CRITERIA:` loop, replace the two scaffold strings (the `if definition.balance:` branch and the `else:` branch) so the block appended after `header` is:

Instance branch (`else`):

```python
            criterion_details.append(
                header
                + "    Return a JSON object for this section with EXACTLY "
                "these fields and no others:\n"
                "    - \"instance_count\": a non-negative integer \u2014 the "
                "number of unique instances found; use 0 if none.\n"
                "    - \"instances\": an array (may be empty) of objects, each "
                "with exactly \"excerpt\" (an exact substring of a chunk's "
                "text) and \"chunk_id\" (matching a document_chunks id); at "
                f"most {MAX_INSTANCES_PER_CRITERION}.\n"
                "    - \"summary\": a non-empty string, 1-2 sentences.\n"
                "    Do not include a score, band, rating, or any other field."
            )
```

Balance branch (`if definition.balance:`):

```python
            criterion_details.append(
                header
                + "    Return a JSON object for this section with EXACTLY "
                "these fields and no others:\n"
                "    - \"female_count\": a non-negative integer.\n"
                "    - \"male_count\": a non-negative integer.\n"
                "    - \"summary\": a non-empty string, 1-2 sentences.\n"
                "    Do not include \"instances\", \"instance_count\", a score, "
                "or any other field."
            )
```

Keep `header` exactly as-is (`f"  {code} ({definition.title}):\n    {_rule(code)}\n"`). `MAX_INSTANCES_PER_CRITERION` is already imported in `prompt.py`.

- [ ] **Step 4: Run the new test — GREEN**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/agents/gad/test_gad_dynamic_rules.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full GAD suite and fix fallout**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && PYTHONPATH=. uv run --project server pytest server/tests/agents/gad/ -q`
Expected: PASS. Existing prompt assertions to watch:
- `test_prompt_contains_max_instances_reference` / anything asserting `str(MAX_INSTANCES_PER_CRITERION) in instructions` — still holds (`at most {N}`).
- `test_no_score_fields_in_instructions` / `test_no_score_terms...` — asserts `"score:"` absent (lowercase). New text says "a score, band, rating" — no `"score:"`, no `"criterion_scores"`. Fine. If any test asserts the literal old bullet text `Count instances with non-negative integer`, update it to the new field spec.

- [ ] **Step 6: Lint**

Run: `cd C:/Users/Admin/Desktop/PROJECTS/EquipED && uv run --project server ruff check server/modules/agents/gad/prompt.py server/tests/agents/gad/test_gad_dynamic_rules.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add server/modules/agents/gad/prompt.py server/tests/agents/gad/test_gad_dynamic_rules.py
git commit -m "fix(gad): spell out required per-criterion output fields in the prompt scaffold"
```

---

## Self-Review

**1. Spec coverage:**
- §3 in-scope "semantic counting guidance only" → Task 1 (injection wraps rule with fixed scaffold).
- §3 "backfill the 5 GAD criteria" → Task 3 migration + `rubrics.json`.
- §3 "prompt.build_combined_prompt takes scoring_rules … FALLBACK_GAD_INSTRUCTIONS" → Task 1.
- §3 "_run_gad_scoring reads via get_active_rubric_scoring_rules" → Task 2.
- §3 "Rubric Editor: drop the note for GAD rows only" → Task 4.
- §6.1 preamble + CRITICAL RULES unchanged → Task 1 only touches the per-criterion loop; test `test_structural_scaffold_survives_rule_injection` guards it.
- §6.2 patchable `_rubric_scoring_rules`, db=None in prod → Task 2.
- §6.4 data-only migration scoped to `agent_id='gad'` → Task 3 `_SCOPE`.
- §9 tests: migration up/down (Task 3), reader (Task 3), prompt-injection (Task 1), fallback (Task 1), pipeline wiring (Task 2), editor (Task 4). Snapshot test from §9/§10: covered functionally by `test_prompt_uses_fallback_when_no_rules_supplied` + `test_seed_json_matches_fallback_constant`; a byte-for-byte pinned snapshot is omitted deliberately (brittle across unrelated prompt edits) — the three-copies-match test is the drift guard the spec actually needs.
- §7 bands untouched → no task modifies the `score_*` modules; Task 5 step 1 re-runs `registry` tests.
- §8 DPO unaffected → no task touches SME / `feedback/dpo` / `groups.py`.

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". All code blocks are literal. Migration and constant strings are written out in full in both places they appear.

**3. Type consistency:** `scoring_rules: dict[str, str] | None` (Task 1) matches the `_rubric_scoring_rules(self, db=None) -> dict[str, str]` producer (Task 2) and the `_fit_gad_chunks(..., scoring_rules: dict[str, str])` consumer (Task 2). `resolve_rubric_agent_id("rubric_gad")` returns `"gad"` (verified: `service.py` strips the `rubric_` prefix). `get_active_rubric_scoring_rules` signature `(agent_id, db=None)` matches the call in Task 2. Editor `WIRED_AGENTS` is a `Set<string>`; `.has()` used consistently.
