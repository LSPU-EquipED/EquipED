# GAD Dynamic Counting Rules — Design

**Date:** 2026-08-29
**Status:** Approved for planning
**Depends on:** the DB-connected Rubric Editor and the SME dynamic scoring
rules slice (`feat/dynamic-rubric-editor`, commits `27788a6` and `c53bdd6`).
This work extends the same `scoring_rule` column and the same
`get_active_rubric_scoring_rules` reader to a second agent.

## 1. Problem

The SME slice made `rubric_criteria.scoring_rule` a stored, admin-editable
field and wired it into **SME** scoring. For GAD the field is stored but
`NULL`, and the Rubric Editor shows GAD rows with the note *"Stored for
reference — not used by this agent's scoring yet."*

CID admins want GAD's evaluation behavior to respond to rubric edits too —
specifically the part they can meaningfully tune: **what the evaluator
counts** for each GAD criterion (what qualifies as a gender stereotype, what
counts as excluding one gender's life experiences, and so on).

This design makes each GAD criterion's **semantic counting guidance** a
stored, admin-editable `scoring_rule`, injected into the GAD extraction
prompt at evaluation time, with the current wording kept as a code
fallback.

## 2. How GAD scores today (context)

`GAD.run()` → `_run_gad_scoring` (`server/modules/agents/gad/pipeline.py`):

1. Pack document chunks into the prompt budget.
2. `prompt.build_combined_prompt(...)` builds **one** JSON prompt covering
   all five criteria. The per-criterion guidance in that prompt is a
   generic block generated inline from `registry.CRITERIA`
   (`criterion_id`, `title`, `balance`) — *not* from the rich
   `GAD_ROW_*_PROMPT` constants, which are dead code left from an earlier
   five-call version.
3. **One** LLM call (temperature 0, JSON-schema contract), plus at most one
   repair call. The model returns **facts only** — `instance_count` +
   grounded `instances[]` for GAD-01/03/04/05, `female_count` /
   `male_count` for GAD-02. It is explicitly forbidden to emit a score;
   `envelope.parse_combined_response` rejects any score-like field.
4. `registry.score_from_combined(...)`:
   - grounds each instance excerpt against the real chunk text
     (`grounding.ground_instances` — an excerpt that is not an exact
     substring of its cited chunk is rejected and does not count);
   - `grounded_count` → `definition.score(count)` → a band **1–4** via the
     hardcoded Python ladders in `stereotypes.py`, `female_male_count.py`,
     `potential.py`, `life_experiences.py`, `peace_and_equality.py`.
5. `subtotal` = mean of the five bands.

The scoring is deterministic and grounding-protected because Python — not
the LLM — assigns every band.

## 3. Scope

### In scope

- Per-GAD-criterion `scoring_rule` = **semantic counting guidance only**
  (the "count X / do NOT count Y / count each unique instance once" prose).
- Backfill the 5 GAD criteria's `scoring_rule` (column already exists).
- `prompt.build_combined_prompt` takes a `scoring_rules: dict[str, str]`
  and injects the per-criterion rule between the criterion header and the
  fixed structural scaffold. A `FALLBACK_GAD_INSTRUCTIONS` constant (seeded
  from today's effective wording) is used for any criterion with no stored
  rule.
- `_run_gad_scoring` reads the rules via the existing
  `get_active_rubric_scoring_rules` and passes them down.
- Rubric Editor: drop the "not used for scoring yet" note **for GAD rows
  only** (Coordinator and ITSO keep it). No other editor change — the
  existing textarea and PATCH flow already handle the field.

### Out of scope

- **The band ladders.** GAD-01…GAD-05 count→score thresholds stay hardcoded
  in Python. Making them admin-editable needs a structured field and is a
  separate design (see §7).
- **The structural contract.** Field names, types, JSON-only output, exact
  excerpt / `chunk_id` requirements, `MAX_INSTANCES_PER_CRITERION` — all
  stay hardcoded in `prompt.py` / `envelope.py`. An admin editing a
  `scoring_rule` cannot change or break the extraction envelope.
- **Wiring Coordinator or ITSO scoring** to the field.
- **Versioning / history** of rule changes — current-value-only, matching
  the SME slice. Per-evaluation faithfulness is already covered by the
  prompt text persisted on the agent result.
- **The dead `GAD_ROW_*_PROMPT` constants and `CRITERION_KIND`.** Their
  wording seeds the backfill and the fallback constant; whether to then
  delete the now-unreferenced constants is a cleanup call for the plan, not
  a requirement of this design.
- **GAD-02's counting.** GAD-02 is the "equal representation" balance
  criterion; its rule text is about *what to count as a representation*,
  not instances. It gets a `scoring_rule` like the others, injected into
  the balance-type scaffold.

## 4. Why this is safe to wire (unlike a full LLM-scoring conversion)

The brainstorm considered converting GAD to score via the LLM like SME
(rule = counting guidance + band table, all in the prompt). Rejected for
this slice: it would rewrite `envelope.py`, remove grounding from the
scoring path, delete the Python band functions (which are also GAD's only
fallback when an LLM call fails), and give up run-to-run determinism.

This design changes **only the semantic guidance text** the model reads
while doing the same fact-extraction job. The envelope, grounding, bands,
single-call budget, repair path, failure handling, and determinism are all
unchanged.

## 5. Architecture

```
rubric_criteria.scoring_rule  (TEXT NULL, already exists)
        │  backfilled for GAD-01..GAD-05
        │
        │  read at evaluation time (db=None → own short-lived session)
        ▼
rubrics/service.get_active_rubric_scoring_rules("gad", db)  ->  {code: rule}
        │
        ▼
gad/pipeline._run_gad_scoring
        │  builds {code: db_rule or FALLBACK_GAD_INSTRUCTIONS[code]}
        ▼
gad/prompt.build_combined_prompt(packed_chunks, ..., scoring_rules=...)
        │  per criterion:  <header>  +  <resolved rule>  +  <fixed scaffold>
        ▼
   one combined fact-only extraction call   (unchanged downstream)
```

```
rubric_criteria.scoring_rule
        │  read for the editor (already wired by the SME slice)
        ▼
GET /admin/rubrics    ->  GAD criteria already carry scoring_rule
PATCH /admin/rubrics/criteria/{id}  ->  { description, scoring_rule }  (already works)
        │
        ▼
Rubric Editor: GAD rows stop showing the "not used yet" note
```

## 6. Components

### 6.1 Prompt assembly — `server/modules/agents/gad/prompt.py`

Today `build_combined_prompt` iterates `registry.CRITERIA` and, per
criterion, appends a generic instruction block (an `if definition.balance`
branch and an `else` branch). Change:

- New signature parameter `scoring_rules: dict[str, str]` (keyword, default
  `None` treated as `{}` for call-site safety in tests).
- New module constant `FALLBACK_GAD_INSTRUCTIONS: dict[str, str]` — one
  entry per criterion code, holding the semantic guidance. Seeded from the
  effective current wording (drawn from the `GAD_ROW_*_PROMPT` text, minus
  the JSON-shape / "replace placeholder values" lines, which are structural).
- Per criterion, the emitted block becomes:

  ```
  {criterion_id} ({title}):
    {scoring_rules.get(code) or FALLBACK_GAD_INSTRUCTIONS[code]}

    {fixed scaffold for this criterion type}
  ```

  where the **fixed scaffold** is exactly today's structural lines:
  - instance type (GAD-01/03/04/05): "Return non-negative integer
    'instance_count'. List each unique instance with exact 'excerpt' and
    'chunk_id'. Max 10 instances. Include a non-empty 'summary'. Do NOT
    include numeric score fields."
  - balance type (GAD-02): "Return non-negative integer 'female_count' and
    'male_count' and a non-empty 'summary'. Do NOT include 'instances',
    'instance_count', or any numeric score field."

- The preamble ("You are a GAD fact extractor…", "OUTPUT FORMAT: five keys
  gad-01…gad-05") and the trailing "CRITICAL RULES" block are unchanged and
  stay hardcoded.

**Managed-prompt overlap (post-implementation, added Task 6).** The active
managed GAD prompt (`prompt_versions` row, seeded by migration
`20260716_0001` = `FACT_ONLY_GAD_PROMPT`) is injected as
`instruction_parts[0]`. It contains its *own* `CRITERIA:` section with
per-criterion "count X / do NOT count Y" for GAD-01…05 — which is now also
emitted from `PER-CRITERION DETAILS` off the Rubric Editor `scoring_rule`.
Two editable sources of the same guidance. **Task 6** (migration
`20260829_0003`) trims the managed prompt to role / `TASK:` / `OUTPUT
FORMAT:` framing only, so the split is: managed prompt = framing; Rubric
Editor `scoring_rule` = per-criterion "what counts"; `prompt.py` =
structural scaffold + `CRITICAL RULES`. One editable source per concern.
- `build_combined_repair_prompt` is unchanged — it wraps the full initial
  prompt, so it inherits the injected rules automatically.
- `__all__` gains `FALLBACK_GAD_INSTRUCTIONS`.

### 6.2 Pipeline — `server/modules/agents/gad/pipeline.py`

- Import `get_active_rubric_scoring_rules` and `resolve_rubric_agent_id`
  from `server.modules.rubrics.service`, and `FALLBACK_GAD_INSTRUCTIONS`
  from `.prompt`.
- Add a small method on `GADScoredAgent`, mirroring SME's
  `_rubric_scoring_rules`:

  ```python
  def _rubric_scoring_rules(self, db: Any | None = None) -> dict[str, str]:
      return get_active_rubric_scoring_rules(
          resolve_rubric_agent_id(self.rubric_source_type), db=db
      )
  ```

  A method (not a bare call) so tests can patch it without a DB — the SME
  slice hit `InfrastructureUnavailableError` when a bare call reached
  `get_session_factory()` under `DATABASE_URL=""`.
- In `_run_gad_scoring`, before the first `build_combined_prompt` call:

  ```python
  rules = self._rubric_scoring_rules()
  resolved = {
      d.criterion_id: rules.get(d.criterion_id)
      or FALLBACK_GAD_INSTRUCTIONS[d.criterion_id]
      for d in registry.CRITERIA
  }
  ```

  Pass `scoring_rules=resolved` into **both** `build_combined_prompt` call
  sites (`_fit_gad_chunks`'s internal `rendered()` closure and the real
  build) and into `_fit_gad_chunks` itself so budget-fitting sees the true
  prompt size. `_fit_gad_chunks` gains a `scoring_rules` parameter it
  forwards.
- Production dispatch does not pass a DB session to agents
  (`supervision/dispatch.py` builds `kwargs` without one), so
  `_rubric_scoring_rules()` runs with `db=None` and opens its own
  short-lived session — same as SME.

### 6.3 Seed data

- `server/data/rubrics/rubrics.json`: add `"scoring_rule"` to each of the 5
  GAD criteria, verbatim equal to the matching `FALLBACK_GAD_INSTRUCTIONS`
  entry.
- `server/scripts/seed_rubrics.py` already passes
  `scoring_rule=criterion_data.get("scoring_rule")` (from the SME slice) —
  no change.

### 6.4 Migration — backfill only

The `scoring_rule` column already exists (migration `20260829_0001`). This
slice adds a **new** migration whose `upgrade()` runs an `UPDATE` setting
`scoring_rule` for the 5 GAD criterion codes, scoped to criteria whose
domain's rubric set has `agent_id = 'gad'`, using a literal dict embedded
in the migration file (verbatim copy of `FALLBACK_GAD_INSTRUCTIONS`).
`downgrade()` nulls those rows back out (scoped the same way).

Rationale for a data-only migration rather than relying on a re-seed: the
shared Neon dev DB is already seeded; a re-seed would overwrite any admin
edits to other criteria.

### 6.5 Rubric Editor — `client/src/features/admin/rubric-editor/`

`components/RubricTableEditor.tsx`: the non-wired helper note currently
renders for every `agent_id !== 'sme'` row. Change the condition so GAD
rows are treated as wired:

```ts
const WIRED_AGENTS = new Set(['sme', 'gad']);
const isWired = WIRED_AGENTS.has(rubricSet.agent_id);
```

Coordinator and ITSO rows keep the note. No column, payload, or hook
change — `scoring_rule` is already fetched, rendered in the textarea, and
PATCHed by the SME slice.

## 7. Known limitation — bands stay in code

An admin can retune *what counts* but not the count→score mapping (e.g.
"0 stereotype instances → 4, 1 → 3, 2–3 → 2, 4+ → 1"). If a form revision
changes those thresholds, that still needs a code change. Closing this
needs a structured band field (numbers, not prose) and a registry that
reads ladders from the DB — deferred to a later design. Documented so the
gap is explicit.

## 8. DPO / retraining impact

None. GAD is not in DPO scope (`export_sme_dpo_pairs` is SME-only, and the
`GROUP_CODES` grouping it reads is SME's). The
`sme-dynamic-rubric-dpo-tension` memory is unaffected — this slice does not
touch SME, grouping, or criterion codes.

## 9. Testing

### Backend

- **Migration:** after `upgrade`, `GAD-01` in the GAD rubric set has the
  seeded rule text; a non-GAD criterion is untouched; after `downgrade`,
  the 5 GAD rows are `NULL` again.
- **`get_active_rubric_scoring_rules("gad")`:** returns 5 entries after
  seeding; skips NULL/blank; `{}` when no active GAD set.
- **`build_combined_prompt`:** given `scoring_rules={"GAD-01": "EDITED
  RULE …"}`, the rendered prompt contains `EDITED RULE` in the GAD-01
  section and `FALLBACK_GAD_INSTRUCTIONS["GAD-02"]` in the GAD-02 section;
  the fixed scaffold lines ("exact 'excerpt' and 'chunk_id'", "Do NOT
  include numeric score fields") are still present for every criterion; the
  preamble and CRITICAL RULES block are unchanged.
- **`build_combined_prompt` with `scoring_rules={}` / omitted:** every
  criterion falls back to `FALLBACK_GAD_INSTRUCTIONS`; output is
  byte-identical to a pinned snapshot of today's prompt (guards against
  wording drift in the extraction — see §10).
- **Envelope unchanged:** `parse_combined_response` still accepts a valid
  five-section fact envelope and still rejects a `score` field — no test
  change expected, asserted by the existing suite passing.
- **Pipeline wiring:** with `GADScoredAgent._rubric_scoring_rules` patched
  to return `{"GAD-01": "EDITED RULE"}`, run `_run_gad_scoring` against a
  stub LLM client and assert the prompt handed to the client contains
  `EDITED RULE`. With it patched to `{}`, the prompt matches the fallback.
- **Determinism / bands untouched:** an existing `registry`/`score_from_
  combined` test still produces the same bands for the same fact counts.

### Frontend

- **component test:** a GAD rubric row does **not** render the "not used …
  yet" helper line; a Coordinator (or ITSO) row still does; editing a GAD
  row's scoring-rule textarea and clicking the check still fires `PATCH
  /admin/rubrics/criteria/{id}` with `{ description, scoring_rule }`.

## 10. Risk: extraction wording drift

**Correction (post-implementation, 2026-08-29):** an earlier draft of this
section claimed the seeded text "must equal today's behavior on day one."
That holds for **GAD-02 only**. For **GAD-01 / GAD-03 / GAD-04 / GAD-05**
the pre-change live prompt contained *no* semantic counting guidance at all
— only the criterion title plus the structural scaffold (see §2: the rich
`GAD_ROW_*_PROMPT` constants were dead code, never in the live prompt).
Seeding `FALLBACK_GAD_INSTRUCTIONS` from that dead wording (§6.1)
**deliberately adds** a paragraph of "count X / do NOT count Y" instruction
those four criteria never had. This is the intended point of the feature,
but it is a real, unmeasured shift in GAD extraction on *unedited* rubrics,
not a no-op.

**Required before relying on GAD scores:** run one known SLM through GAD on
`main` and on this branch and diff the five bands. If the bands move
materially that is a product decision for CID, not a code bug.

The invariants that *do* hold unconditionally:

1. `FALLBACK_GAD_INSTRUCTIONS`, the JSON seed, and the migration backfill
   hold the **same** strings — one source of truth, copied to three places,
   asserted equal by a test. No further drift after day one.
2. The structural scaffold, preamble, and CRITICAL RULES block stay in code,
   so the parts `envelope.py` depends on cannot change regardless of rule
   text — an admin edit cannot break extraction, only change what is
   counted.

Residual: once an admin edits a rule, extraction quality for that criterion
is their responsibility — the same trade-off already accepted for SME.

### 10a. Auditability gap (post-implementation finding)

§3 said per-evaluation faithfulness is "covered by the prompt text persisted
on the agent result." That was **wrong for GAD** as originally shipped: the
GAD success-path `AgentEvaluationResult` set no `prompt_text` (only ITSO
did). The fix commit sets `prompt_text=combined_prompt` on the GAD result so
a past GAD score can be reconstructed against the rule text in force at the
time. Rule-change *versioning* (a history table) is still out of scope.

## 11. File-by-file summary

| File | Change |
| --- | --- |
| `server/alembic/versions/<rev>_backfill_gad_scoring_rule.py` | **new** — `UPDATE`/`downgrade` the 5 GAD rows |
| `server/modules/agents/gad/prompt.py` | `build_combined_prompt` takes `scoring_rules`; add `FALLBACK_GAD_INSTRUCTIONS`; inject rule between header and fixed scaffold; export the constant |
| `server/modules/agents/gad/pipeline.py` | `_rubric_scoring_rules` method; resolve `{code: db_rule or fallback}`; thread `scoring_rules` through `_fit_gad_chunks` and both `build_combined_prompt` calls |
| `server/data/rubrics/rubrics.json` | `scoring_rule` on the 5 GAD criteria |
| `client/src/features/admin/rubric-editor/components/RubricTableEditor.tsx` | treat `gad` as a wired agent (drop the helper note for GAD rows) |
| `server/tests/agents/gad/…` | migration, reader, prompt-injection, fallback-snapshot, pipeline-wiring tests |
| `server/tests/rubrics/…` | `get_active_rubric_scoring_rules("gad")` cases |
| `client/.../rubric-editor/components/__tests__/RubricTableEditor.test.tsx` | GAD row has no helper note; PATCH still fires |

## 12. Sequencing

`feat/dynamic-rubric-editor` currently holds the Rubric Editor + SME slices
(committed). Options:

1. Continue on `feat/dynamic-rubric-editor` — one more slice on the same
   branch.
2. Branch `feat/gad-dynamic-counting-rules` from it.

The plan does not assume either.
