# Dynamic Scoring Rules (criterion "basis") — Design

**Date:** 2026-08-29
**Status:** Approved for planning
**Depends on:** the DB-connected Rubric Editor (`feat/dynamic-rubric-editor`,
uncommitted at time of writing — this work edits the same files).

## 1. Problem

Each SME rubric criterion has a **scoring rule** — the "count X, band into
1–4" text that tells the scorer how to turn evidence into a score. Today
those rules live hardcoded in `server/modules/agents/sme/group_prompt.py`
(`_SCORING_RULES`). LSPU SCC periodically issues updated evaluation forms,
and CID admins need to change the scoring rules themselves — see them in
the Rubric Editor and edit them — without a code change or redeploy.

This design makes the scoring rule a **stored, admin-editable field on each
rubric criterion**, surfaced in the Rubric Editor, and — for SME — wired
into the scoring prompt so edits actually change how scoring works.

## 2. Scope

### In scope

- New nullable `scoring_rule` column on `rubric_criteria`.
- Backfill SME + Coordinator criteria from the current `_SCORING_RULES`.
- A read helper mirroring `get_active_rubric_descriptions`.
- **SME only:** wire the stored rule into the grouped-LLM scoring prompt,
  with the current hardcoded rules kept as a fallback.
- Rubric Editor: replace the "Field" (title) column with a "Scoring rule"
  column. Editor table becomes **Criterion ID · Entry · Scoring rule ·
  Action**.
- All four agents' criteria get the editable field. For Coordinator, GAD,
  and ITSO it is **stored and displayed only** — not wired to their
  scoring — with a UI note saying so.

### Out of scope

- Wiring the rule into Coordinator / GAD / ITSO scoring. Those agents score
  via Python engines (`curriculum.compute`, `gad` registry, `itso`
  registry); driving them from a text rule is a separate project to be
  brainstormed later.
- Versioning / history of scoring-rule changes. Edits are **current-value
  only** (overwrite in place). Per-evaluation prompt snapshots
  (`AgentResult.group_prompts`) remain the historical record.
- Structured / machine-readable bands (numerator, denominator, thresholds).
  Free text only, matching what the prompt already consumes.
- Any change to criterion `title` editing — the title stays in the data,
  the API, prompts, and reports, but is no longer editable from the editor
  UI (the "Field" column is removed).
- Changes to the per-criterion engine **fallback** thresholds (see §6).

## 3. Why only SME's scoring changes

Investigation of the current wiring:

| Agent | How its 10 criteria are scored | Does a stored rule change behavior? |
| --- | --- | --- |
| **SME** | 3 grouped LLM calls that follow `_SCORING_RULES` prose (`build_group_prompt`), with a per-criterion engine fallback on group-call failure | **Yes** — the grouped calls follow the rule text |
| Coordinator | `run()` computes **only A-05** via `curriculum.compute` (Python, curriculum-grounded); the other 9 criteria are spliced in from SME's result by `merge_with_sme()` | No |
| GAD | Pure-Python deterministic engine (`gad` registry, `female_male_count`, …) | No |
| ITSO | Pure-Python deterministic engine (`itso` registry, evidence tools) | No |

So the stored field is universal (all four agents), but the **wiring** in
this slice is SME-only, and the editor is explicit about that.

## 4. Architecture

Approach A from brainstorming: one nullable column, mirroring the existing
criterion-description flow end to end.

```
rubric_criteria.scoring_rule  (TEXT NULL)
        │
        │  read at evaluation time
        ▼
rubrics/service.get_active_rubric_scoring_rules(agent_id, db)  ->  {code: rule}
        │
        │  SME only
        ▼
sme/pipeline._run_full_llm_scoring
        │  builds {code: db_rule or FALLBACK_SCORING_RULES[code]}
        ▼
sme/group_execution.execute_group  ->  sme/group_prompt.build_group_prompt
        │  criteria[code]["scoring_rule"] = <resolved rule>
        ▼
   grouped LLM scoring call
```

```
rubric_criteria.scoring_rule
        │  read for the editor
        ▼
rubrics/service.get_rubric_sets_for_editor  ->  RubricSetOut (nested)
        │
        ▼
GET /admin/rubrics                    ->  editor renders the "Scoring rule" column
PATCH /admin/rubrics/criteria/{id}    ->  { description, scoring_rule }
        │
        ▼
rubrics/service.update_criterion  ->  UPDATE rubric_criteria SET description, scoring_rule
```

## 5. Components

### 5.1 Schema & seed data

**Alembic migration** `<rev>_add_rubric_criterion_scoring_rule.py`:

- `op.add_column("rubric_criteria", sa.Column("scoring_rule", sa.Text(), nullable=True))`
- Data backfill in the same migration: `UPDATE rubric_criteria SET
  scoring_rule = :rule` for each `criterion_code` in the SME and
  Coordinator rubric sets, using a **literal dict embedded in the migration
  file** (migrations must not import app code that can change). The dict is
  a verbatim copy of today's `_SCORING_RULES` (10 entries: `A-01`–`A-05`,
  `OP-01`–`OP-05`). GAD/ITSO criteria are left `NULL`.
  - Scope the `UPDATE` to criteria whose domain's rubric set has
    `agent_id IN ('sme', 'coordinator')` so an `OP-01` in some future
    unrelated rubric set is not touched.
- `downgrade()` drops the column.

**Model** `server/modules/rubrics/models.py`:

```python
scoring_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Seed data** `server/data/rubrics/rubrics.json`: add `"scoring_rule"` to
each SME and Coordinator criterion (same 10 texts). `seed_rubrics.py`:
`scoring_rule=criterion_data.get("scoring_rule")` in the `RubricCriterion`
construction.

### 5.2 Read helper

`server/modules/rubrics/service.py` — new function, exact structural mirror
of `get_active_rubric_descriptions`:

```python
def get_active_rubric_scoring_rules(agent_id: str, db: Any | None = None) -> dict[str, str]:
    """Return {criterion_code: scoring_rule} for the active rubric set.

    Skips criteria whose scoring_rule is NULL or blank. Returns {} when no
    active rubric set exists.
    """
```

Add to `__all__`.

### 5.3 SME prompt wiring

`server/modules/agents/sme/group_prompt.py`:

- Rename module constant `_SCORING_RULES` → `FALLBACK_SCORING_RULES`; add
  it to `__all__` (it already sits beside `FALLBACK_DESCRIPTIONS`, which is
  already exported and used the same way).
- `build_group_prompt(...)` gains a `scoring_rules: dict[str, str]`
  parameter (positional, alongside `descriptions`). Per criterion:
  `"scoring_rule": scoring_rules.get(code) or FALLBACK_SCORING_RULES[code]`.

`server/modules/agents/sme/group_execution.py`:

- `execute_group(...)` gains `scoring_rules: dict[str, str]` and forwards it
  to `build_group_prompt`.

`server/modules/agents/sme/pipeline.py` — `_run_full_llm_scoring`:

- Fetch once: `scoring_rules = get_active_rubric_scoring_rules(
  resolve_rubric_agent_id(self.rubric_source_type), db=db)`.
- Per group, build
  `group_scoring_rules = {code: scoring_rules.get(code) or FALLBACK_SCORING_RULES[code] for code in codes}`
  and pass it into `execute_group`.
- Import `FALLBACK_SCORING_RULES` alongside the existing
  `FALLBACK_DESCRIPTIONS as _FALLBACK_DESCRIPTIONS` import.

This path is reached only by `SME.run()`. `Coordinator.run()` has its own
A-05-only path and does not call `_run_full_llm_scoring`, so Coordinator is
unaffected even though it subclasses `EngineScoredAgent`.

### 5.4 Editor API

Builds directly on the not-yet-committed Rubric Editor module
(`server/modules/rubrics/{schemas,service,router}.py`).

`schemas.py`:

- `RubricCriterionOut`: add `scoring_rule: str | None`.
- `RubricCriterionUpdate`: **remove `title`**; keep `description` (required,
  blank rejected, trimmed); add `scoring_rule: str | None` (**required key,
  nullable value** — the editor always sends it). A non-blank value is
  trimmed and stored; `null` or a blank/whitespace string is stored as SQL
  `NULL` ("no rule"). Remove the now-unused title validator.

`service.py`:

- Rename `update_criterion_text` → `update_criterion(db, criterion_id, *,
  description, scoring_rule)`. Sets `description` and `scoring_rule`
  (storing `None` when the incoming value is blank/None). Still raises
  `LookupError` on a missing id.
- `get_rubric_sets_for_editor`: include `scoring_rule` in each criterion
  dict.

`router.py`:

- `patch_criterion`: body is `RubricCriterionUpdate` (no title); pass
  `description` and `scoring_rule` to `update_criterion`; response
  `RubricCriterionOut` includes `scoring_rule`.

### 5.5 Editor UI

`client/src/features/admin/rubric-editor/`:

`types.ts`:

- `RubricCriterion` gains `scoring_rule: string | null`.
- The update payload type becomes `{ description: string; scoring_rule: string | null }`
  (drop `title`).

`components/RubricTableEditor.tsx`:

- Table header/columns: **Criterion ID · Entry · Scoring rule · Action**.
  Remove the "Field" column.
- Per-row draft state: `{ description: string; scoring_rule: string }`.
  Drop `title` from the draft.
- Criterion ID input: read-only always (unchanged).
- Entry (description): text input, read-only until the row's edit toggle
  is on (unchanged behaviour).
- Scoring rule: `<textarea>` (≈3 rows), read-only until the edit toggle is
  on. Longer content than the description, hence a textarea.
- On finish-editing (the check button), fire one PATCH:
  `{ description, scoring_rule }` (scoring_rule sent as `null` when blank).
- For rubric sets whose `agent_id !== 'sme'`, render the scoring-rule cell
  with a muted helper line beneath it: *"Stored for reference — not used by
  this agent's scoring yet."*
- Structural buttons (Add Table / Add Row / Delete) stay disabled with the
  existing tooltip.

`hooks/useRubrics.ts`: no shape change — the mutation already passes a
`body` object straight through; only the type narrows.

## 6. Known limitation: engine fallback thresholds

`registry.run_criterion` / the per-criterion `evaluate()` functions compute
a band from extracted facts using thresholds hardcoded in Python (e.g.
`varied_assessment.evaluate` uses `5+ types -> 4`). This path runs **only
when a grouped LLM call fails outright**. After an admin edits a rule, a
subsequent group-call failure would score that criterion by the old Python
threshold, not the edited rule.

Decision: **accept and document.** The fallback is rare, and keeping the
Python thresholds in sync with free-text rules is not mechanically
possible. A future structured-bands design (Approach B) is the way to close
this if it becomes a real problem.

## 7. DPO / retraining impact

No code change required.

- `export_sme_dpo_pairs` (`server/modules/feedback/dpo/sme.py`) uses
  `AgentResult.group_prompts` — the **prompt text snapshotted at evaluation
  time** — as the training `prompt`. It does not rebuild the prompt from
  current rubric text or `_SCORING_RULES`, and it only reads the *grouping*
  (`GROUP_CODES`) from code, which this design does not touch. Historical
  faithfulness is preserved.
- Residual risk: a LoRA adapter is tuned on a specific prompt distribution.
  If scoring-rule text changes between adapter versions, later evaluations
  drift from the adapter's training distribution with no error, just
  quality drift. This is the concern recorded in the
  `sme-dynamic-rubric-dpo-tension` memory. Decision: **accept and
  monitor**; revisit when structural rubric changes (regrouped or
  added/removed criteria) are on the table.

## 8. Testing

### Backend

- **Migration:** after `upgrade`, an SME criterion (`A-02`) has the seeded
  rule text and a GAD criterion (`GAD-01`) has `scoring_rule IS NULL`;
  after `downgrade`, the column is gone.
- **`get_active_rubric_scoring_rules`:** returns 10 entries for `sme`;
  entries with NULL/blank are skipped; `{}` when no active set.
- **`build_group_prompt`:** when `scoring_rules` contains a code, the
  prompt carries that text; when it does not, the prompt carries
  `FALLBACK_SCORING_RULES[code]`.
- **SME pipeline contract:** with `get_active_rubric_scoring_rules` patched
  to return an edited rule for one code, the string reaches the built group
  prompt (assert on the captured prompt text).
- **Editor API:** `GET /admin/rubrics` includes `scoring_rule` per
  criterion; `PATCH /admin/rubrics/criteria/{id}` with
  `{ description, scoring_rule }` persists both; `PATCH` with
  `scoring_rule: null` stores NULL; `PATCH` body containing `title` does
  not change the title (field removed from the model); blank `description`
  still 422s; unknown id still 404s; `require_admin` still enforced.

### Frontend

- **api test:** `updateCriterion` issues `PATCH
  /admin/rubrics/criteria/{id}` with body `{ description, scoring_rule }`.
- **component test:** the table renders **Criterion ID · Entry · Scoring
  rule · Action** and no "Field" column; toggling edit on a row, changing
  the scoring-rule textarea, and clicking the check fires the PATCH with
  both fields; a Coordinator/GAD/ITSO row shows the
  "not used ... yet" helper line; an SME row does not.

## 9. Sequencing

This edits files introduced by the uncommitted Rubric Editor work.
Recommended order:

1. Commit the Rubric Editor work as `feat/dynamic-rubric-editor`.
2. Branch `feat/dynamic-scoring-rules` from it and implement this design.

Folding both into one branch also works; the plan does not assume either.

## 10. File-by-file summary

| File | Change |
| --- | --- |
| `server/alembic/versions/<rev>_add_rubric_criterion_scoring_rule.py` | **new** — add column + backfill SME/Coordinator |
| `server/modules/rubrics/models.py` | add `scoring_rule` mapped column |
| `server/modules/rubrics/service.py` | add `get_active_rubric_scoring_rules`; `update_criterion_text` → `update_criterion` (+ `scoring_rule`); `get_rubric_sets_for_editor` returns `scoring_rule` |
| `server/modules/rubrics/schemas.py` | `RubricCriterionOut.scoring_rule`; `RubricCriterionUpdate` drop `title`, add `scoring_rule` |
| `server/modules/rubrics/router.py` | `patch_criterion` new body / response fields |
| `server/data/rubrics/rubrics.json` | `scoring_rule` on SME + Coordinator criteria |
| `server/scripts/seed_rubrics.py` | read `scoring_rule` from JSON |
| `server/modules/agents/sme/group_prompt.py` | `_SCORING_RULES` → `FALLBACK_SCORING_RULES` (exported); `build_group_prompt` takes `scoring_rules` |
| `server/modules/agents/sme/group_execution.py` | thread `scoring_rules` through `execute_group` |
| `server/modules/agents/sme/pipeline.py` | fetch rules via new reader; pass per-group dict into `execute_group` |
| `client/src/features/admin/rubric-editor/types.ts` | `scoring_rule` on criterion; update payload shape |
| `client/src/features/admin/rubric-editor/components/RubricTableEditor.tsx` | replace Field column with Scoring rule textarea; drop title from drafts; non-SME helper note |
| `server/tests/rubrics/…`, `server/tests/agents/sme/…`, `client/.../rubric-editor/…` | tests per §8 |
