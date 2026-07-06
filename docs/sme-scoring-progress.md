# SME Scoring — Build Progress & Skeleton-Pass Draft

> **Status (2026-07-06):** The code-side scoring engine covers all 10 SME
> criteria. 9 of 10 are validated against real SLMs via the CLI. **A-04 is
> WIP** — redesigned, committed, but not yet confirmed against a real
> document (see Part 1, row 9). **The skeleton-extraction pass (Part 3) is
> built and parity-tested against one real SLM** — 6 shared LLM calls
> instead of one call per criterion.
>
> **`SME.run()` now uses the engine unconditionally** (no more
> `sme_use_scoring_engine`/`sme_scoring_grouped` flags — both were removed
> from `server/core/config.py`). SME no longer calls the shared
> `BaseAgent.run()` LLM-guesses-everything flow at all: `run_grouped()` is
> the primary scorer, `run_criterion()` is the per-criterion fallback for any
> code a basket missed, and a code failing both raises `AgentExecutionError`
> like any other agent failure. See `server/modules/agents/sme.py` and
> `server/tests/agents/test_sme_run.py`. Still only parity-tested against one
> real SLM end-to-end — see "Not yet done" below before trusting it broadly.
>
> **Relationship to `docs/sme-scoring-basis.md`:** that document is the
> *design rationale* — why each criterion is measured the way it is, the
> three measurement patterns, the pipeline, and the high-level roadmap
> (§11–§12). **This document is its companion** — a concrete build log (what
> actually got written, in what order, on which commit) plus the as-built
> record of the "skeleton" extraction pass: what was tried, what broke, what
> was measured on a real SLM, and what's still open. Read `sme-scoring-basis.md`
> first for the *why*; this doc is the *what's-built* and *what's-next*.
>
> Written so a new session (no prior context) can pick up from Part 3 without
> re-deriving anything, including *why* the design isn't the original 2-call
> plan.

---

## Part 1 — What we built, in order

All work lives on branch `feat/sme-scoring-basis`. Table is oldest → newest
commit.

| # | Commit | Criterion(s) | Pattern | Module file | Key decision | Status |
|---|---|---|---|---|---|---|
| 1 | `2fb6c9e` | Engine scaffold + **A-05** Objective Gauging | Coverage ratio (moderate) | `bands.py`, `objective_alignment.py`, `registry.py` (new), CLI + tests (new) | Foundation spike; established `compute()`/`evaluate()` split, real-content evidence rule, temp-0 determinism | ✅ validated |
| 2 | `0ff4371` | **OP-02** Interactivity + flag-gated integration | Count | `interactivity.py` | Introduced `SME_USE_SCORING_ENGINE` flag + overlay path; no topic/lesson denominator (unstable) | ✅ validated |
| 3 | `3724de0` | **OP-03** Clear Directions | Coverage ratio (moderate) | `clear_directions.py` | Directions must be quotable, not a bare title | ✅ validated |
| 4 | `ca403fb` | **OP-05** Enhancement Activities | Count | `enhancement_activities.py` | No fixed-type taxonomy (not every SLM uses that vocabulary); bottom-anchored slice | ✅ validated |
| 5 | `1def0e9` | **A-01** Learner Transformation | Coverage ratio (moderate) | `learner_transformation.py` | Grades the **activities**, not the stated objectives (distinct from A-05 — catches promise-vs-delivery gaps) | ✅ validated |
| 6 | `c66bc7a` | **A-02** Varied Assessment Tools | Checklist count (**types**) | `varied_assessment.py` | Fixed 7-type taxonomy; counts distinct types, not instances — "varied" means breadth | ✅ validated |
| 7 | `dda4432` | **A-03** Progress Monitoring (+ wired A-02) | Instance count | `progress_monitoring.py` | Counts **instances**, not types — "on-going" means frequency is the signal (deliberate divergence from A-02) | ✅ validated |
| 8 | `4bc552a` | **OP-01** Topic Coherence + **OP-04** Accurate Sections | Coverage ratio (moderate) | `topic_coherence.py`, `accurate_sections.py`, `slicing.py` (new) | New whole-document `downsample()` helper; OP-04 scoped to internal-consistency-only (no external fact-checking) | ✅ validated |
| 9 | `08ff038` | **A-04** Prescriptive Feedback — **redesign** | Checklist count (types) | `prescriptive_feedback.py` (rewritten) | Replaced per-assessment ratio (collapsed to ~0%) with whole-doc type checklist, mirroring A-02 | ⏳ **pending validation** |
| 10 | `0d57916` | Docs only | — | `docs/sme-scoring-basis.md` §5 | A-04 row updated with explicit "PENDING VALIDATION" caveat | done (doc reflects WIP state) |

### Notes worth carrying into the next session

- **A-01 grades activities, not objectives.** Bloom-level classification
  targets what students actually *do* (in the bottom Performance-Tasks
  section), not the stated Learning Objectives — this is what makes A-01
  distinct from A-05 and lets it catch a module that promises higher-order
  objectives but only delivers recall worksheets.
- **A-02 (types) vs A-03 (instances) is deliberate, not an inconsistency.**
  Each criterion's counting mode was derived from its own rubric wording
  ("varied" → breadth; "on-going" → frequency), not from matching its
  neighbor. Don't "fix" one to match the other without re-reading the rubric
  text.
- **A-04's redesign (row 9) has two unconfirmed judgment calls**, made
  without a user response to clarifying questions at design time (flagged
  explicitly in the plan, approved implicitly on merge):
  1. Counts distinct **types**, not instances (like A-02) — rationale:
     "positive feedback AND prescriptive guides" reads as a variety
     requirement.
  2. Slices the **whole document** via `downsample()`, not the bottom-only
     Performance-Tasks section — rationale: if feedback lives elsewhere
     (front-matter encouragement, a rubric page), the bottom-only slice
     would keep the original zero-score bug alive.

  **Next-session action:** run
  `uv run --project server python server/scripts/score_criterion.py --doc <slm>.pdf --criterion A-04`
  against a real SLM. If it still scores near-zero, revisit whether the
  4-type taxonomy needs broadening (e.g. generic "consult your instructor"
  language as `remediation_referral`) before declaring it fixed. Once
  confirmed, strip the "PENDING VALIDATION" caveat from
  `docs/sme-scoring-basis.md`'s A-04 row (per the standing
  keep-scoring-doc-in-sync rule: that doc only finalizes a row after the
  user confirms a CLI test).
- **OP-01's issue-count fallback.** Fewer than `MIN_TRANSITIONS_FOR_RATIO = 4`
  transitions → score by direct issue count (0→4, 1→3, 2→2, 3+→1), not a
  percentage — a ratio swings too wildly on so few data points. This
  intentionally overrides the generic "empty denominator → 1" rule (a short,
  0-issue module is coherent, not deficient).
- **OP-04 is internal-consistency-only, by explicit scope decision.** It
  flags unclear writing, self-contradiction, and blatant self-evident errors
  — **never** external/domain fact-checking, since the model can't reliably
  verify specialized LSPU content and the system is advisory-only.
- **OP-02 / OP-03's *per-criterion* `evaluate()` still uses the older
  vocabulary/head-anchored slice** (`ACTIVITY_MARKERS` / `TASK_MARKERS`,
  keeping some head/front-matter content), **not** the bottom-only
  `SECTION_ANCHORS` header-anchor that A-01/A-02/A-03/A-05/OP-05 converged
  on. Left as-is by an earlier explicit user decision — the per-criterion
  path and CLI (`score_criterion.py`) are unaffected. **The grouped/skeleton
  path (Part 3) moved OP-02 and OP-03 onto the bottom-anchor slice**, and a
  real-SLM test caught a live bug this fixes: the old slice was labeling
  lecture headings as student tasks (see Part 3's Verdict, OP-03 row).

---

## Part 2 — Shared infrastructure recap

All in `server/modules/agents/scoring/`.

- **`bands.py`** — pure band math, unit-tested, zero LLM/IO:
  - `ratio_band(numerator, denominator, scale="moderate"|"high")` → `RatioBand(numerator, denominator, pct, band)`. Moderate = 80/50/20 → bands 4/3/2, else 1. Empty denominator → band 1 (absence is a real deficiency, not a skip).
  - `count_band(count, thresholds)` → looks up `((min_count, band), ...)`, highest first; below the lowest threshold → 1.
  - `mean_band(scores)` → average + round-half-up; empty → 1.
- **`slicing.py`** — shared whole-document sampler, used by OP-01/OP-04/A-04:
  - `downsample(text, budget=9000, windows=6)` → evenly-spaced windows across the WHOLE document, joined by `GAP_MARKER = "\n\n[...]\n\n"`. The last window is anchored to `text[-chunk_size:]` (not proportional placement) — fixes a bug where the true document tail was never sampled. **Any prompt using this slice must explicitly warn the model not to read a `[...]` gap as evidence of a broken transition / missing content** — it's a sampling artifact, not a real gap in the document.
- **Per-criterion bottom-anchored slices** (`slice_for_*` + `SECTION_ANCHORS`) — A-01, A-02, A-03, OP-05 (and A-04's *old* version) anchor on the earliest occurrence of a strong header (`"performance task"`, `"learning tasks"`, `"enrichment activit"`, etc.), read to the end (capped ~9000 chars), and fall back to the document tail if no header is found. This exists because SLM tasks/assessments concentrate near the PDF **bottom**, not spread through the lecture body — anchoring on vocabulary (not the header) was pulling in mislabeled lecture content (the bug that motivated this design, first caught on OP-05).
- **Older vocabulary/head-anchored slices** (`slice_for_interactivity`, `slice_for_directions`) — OP-02, OP-03. Keep a head chunk + a body chunk found via a **marker word list** (`ACTIVITY_MARKERS`, `TASK_MARKERS`), not a single strong header. Left as-is by explicit prior decision.
- **`registry.py`** — `REGISTERED_CODES: frozenset[str]` (all 10 codes present) is the single source of truth for "which criteria use the engine." `run_criterion(code, client, text)` dispatches to each criterion's `evaluate()`, builds a human-readable `justification` string, and extracts `evidence` quotes. Unregistered codes raise `KeyError`; callers check `is_registered()` first. Engine errors never fail the SME agent (old LLM-picks-score path is the fallback).
- **`scripts/score_criterion.py`** — CLI manual-test harness. `CRITERIA: dict[str, Callable]` maps all 10 codes to their `evaluate()`. `extract_text()` reads a clean PDF via `fitz` (PyMuPDF) — **the engine always reads clean fitz text, never joined DB chunks** (overlap duplication in DB chunks flips scores). Per-criterion `print_*` functions give a readable audit trail (which items were counted/dropped and why).
- **`tests/agents/test_scoring_criteria.py`** — 57 tests, all passing. One `TestXCompute` class per criterion, testing `compute()` directly with hand-built fact lists (no LLM, no IO) — this is what "pure `compute()`, unit-tested" means in practice.
- **Cross-cutting rules baked into every `compute()`:**
  - **Real-content evidence rule** — a fact counts only if a quotable evidence snippet backs it; a bare title/heading is not sufficient.
  - **Dedupe-by-label** — most `compute()`s dedupe distinct units by lowercased label before counting, to prevent double-counting (the bug class that once inflated A-05 to "10/3 = 333%").
  - **Temperature 0** on every LLM call, for determinism (from the A-05 spike findings, `sme-scoring-basis.md` §9).

---

## Part 3 — Skeleton-extraction pass (built; flag-gated OFF; uncommitted)

This is the "collapse the plumbing" step described at a high level in
`sme-scoring-basis.md` §11–§12. It is now **implemented and parity-tested
against one real SLM** (see the Verdict below), but **not yet committed** and
**OFF by default** (`SME_SCORING_GROUPED=false`). The design that shipped is
*not* the original 2-call plan — it evolved twice under real testing, and
each evolution is load-bearing context for anyone touching this next.

### Goal (unchanged from the original plan)

A full evaluation makes roughly 11 SME-side LLM calls per SLM today (the old
big all-criteria prompt + one `evaluate()` call per registered criterion) —
before multiplying by the other 3 agents (Coordinator/GAD/ITSO) sharing the
same ~6,000 tokens/min budget. Every `compute()` stays byte-for-byte
identical throughout — only the *source* of its input facts changes.

### Design history — why 6 calls, not 2

1. **First attempt: 2 baskets.** One call for all 7 assessment/task criteria
   (Basket A), one for all 3 content criteria (Basket B). **Rejected outright
   by the provider** — HTTP 413 "request too large." Basket A measured
   ~9,017 requested tokens against Groq's `on_demand`-tier ceiling (~6k
   tokens/request, the same limit documented in the
   `llm-budget-and-multi-agent` memory) — the merged instructions alone
   (~1,267 tokens) plus a large content slice plus `max_new_tokens=4000` blew
   past it in one shot.
2. **Second attempt: 3 baskets.** Split Basket A into A1 (assessment-centric:
   objectives/assessments/alignment → A-02, A-05) and A2 (task-centric:
   tasks + monitoring + enhancement → A-01, A-03, OP-02, OP-03, OP-05); kept
   Basket B (topics/transitions + sections + feedback → OP-01, OP-04, A-04).
   All three fit the token budget. **But a real-SLM comparison against the
   validated per-criterion oracle (`score_criterion.py`) showed monitoring,
   enhancement, and sections — every one of them a *secondary* category
   bundled alongside others in one prompt — came back completely empty**,
   while the oracle found real content in the same document region (5
   monitoring instances, 6 enhancement activities, 16 clean sections). The
   *primary* category in each multi-category prompt (tasks; topics/
   transitions) extracted fine. This looks like ordinary multi-task LLM
   attention degradation, not a slicing bug: the model gives real effort to
   whatever is listed first and shortchanges the rest.
3. **Current design: 6 baskets.** The three categories that failed when
   bundled — monitoring, enhancement, sections — each got their own
   dedicated, single-purpose call, reusing the exact validated prompt text
   from their original per-criterion modules. Everything that demonstrably
   worked when bundled stayed bundled. Net: **6 calls instead of ~10** — a
   smaller win than the original 2-call hope, but the one that held up under
   testing.
4. **A second real bug surfaced during testing, orthogonal to the above**:
   firing all 6 basket calls back-to-back with no pacing tripped the
   provider's per-minute rate limiter (HTTP 429), even though each
   individual call fit the per-request size limit. `run_grouped()` now takes
   a `delay` parameter and sleeps between calls (mirroring the pacing
   `_overlay_engine_scores` already used for the per-criterion path,
   `SME_SCORING_CALL_DELAY_SECONDS`) — this was **not** in the original
   design and is easy to forget if this code is rewritten later.

### Final grouping (6 calls)

| Basket | Slice | Extracts | Feeds |
|---|---|---|---|
| **A1** | objectives head (4000 chars) + bottom `SECTION_ANCHORS` section (7000 chars) | `objectives`, `assessments` (+type+evidence), `alignment` | A-02, A-05 |
| **A2** | bottom `SECTION_ANCHORS` section only (9000 chars, no head) | `tasks` (+bloom_level, directions, has_clear_directions, evidence) | A-01, OP-02, OP-03 |
| **A3** | bottom `SECTION_ANCHORS` section only (single-purpose) | `monitoring_mechanisms` (+type+evidence) | A-03 |
| **A4** | bottom `SECTION_ANCHORS` section only (single-purpose) | `enhancement_activities` (+evidence) | OP-05 |
| **B1** | whole-doc `downsample()` (9000 chars) | `topics`, `transitions`, `feedback_mechanisms` (+type+evidence) | OP-01, A-04 |
| **B2** | whole-doc `downsample()` (9000 chars, single-purpose) | `sections` (+is_clean+issue) | OP-04 |

A single `tasks` list in A2 carries `bloom_level` (A-01), `directions`/
`has_clear_directions` (OP-03), and is also reused as-is for OP-02's
`interactivity.compute(elements)` — same list, three consumers, each reading
only the keys it needs. **This is also where OP-02/OP-03 moved off their
older vocabulary/head-anchored slice onto the bottom-anchor** (per Part 1's
note and a user-approved decision) — and the real-SLM test caught a live
instance of exactly the bug that motivated the move: the oracle's OP-03 run
labeled lecture headings ("CUNIEFORM", "URUK CITY", "THE GREAT ZIGGURAT OF
UR") as student tasks with directions, because its old slice pulls in
vocabulary-matched lecture content. The bottom-anchored A2 slice doesn't.

### Skeleton → `compute()` field mapping

| Basket | Field(s) | Consumed by | `compute()` call |
|---|---|---|---|
| A1 | `objectives`, `assessments`, `alignment` | A-05 | `objective_alignment.compute(objectives, assessments, alignment)` |
| A1 | `assessments` | A-02 | `varied_assessment.compute(assessments)` |
| A2 | `tasks` (bloom_level) | A-01 | `learner_transformation.compute(tasks)` |
| A2 | `tasks` (has_clear_directions) | OP-03 | `clear_directions.compute(tasks)` |
| A2 | `tasks` (as elements) | OP-02 | `interactivity.compute(tasks)` |
| A3 | `monitoring_mechanisms` | A-03 | `progress_monitoring.compute(mechanisms)` |
| A4 | `enhancement_activities` | OP-05 | `enhancement_activities.compute(elements)` |
| B1 | `topics`, `transitions` | OP-01 | `topic_coherence.compute(topics, transitions)` |
| B1 | `feedback_mechanisms` | A-04 | `prescriptive_feedback.compute(mechanisms)` |
| B2 | `sections` | OP-04 | `accurate_sections.compute(sections)` |

### What actually got built

- **`server/modules/agents/scoring/skeleton.py`** (new) — all 6 prompts
  (`BASKET_A1_PROMPT` … `BASKET_B2_PROMPT`), their slice functions
  (`slice_for_basket_a1` … `slice_for_basket_b2`), and their extractors
  (`extract_basket_a1` … `extract_basket_b2`, one `client.generate()` call
  each). Full design-history docstring lives at the top of this file.
- **`server/modules/agents/scoring/registry.py`** — `_render(code, result)`
  extracted out of `run_criterion` so both the per-criterion path and the
  grouped path produce identical justification/evidence text. `run_grouped
  (client, text, *, delay=0.0)` drives a `_BASKETS` table (name, codes,
  extractor, compute-router) — each basket's extraction and every criterion's
  `compute()` call is wrapped in its own `try/except`, so one basket failing
  (or one `compute()` raising) never takes down criteria fed by a different
  basket. A criterion simply **absent** from the returned dict signals
  "fall back" to the caller.
- **`server/core/config.py`** — `sme_scoring_grouped: bool = False`
  (env `SME_SCORING_GROUPED`), independent of `sme_use_scoring_engine`; both
  must be true for the grouped path to run.
- **`server/modules/agents/sme.py`** — `_overlay_engine_scores` calls
  `registry.run_grouped(client, full_text, delay=delay)` **once** up front
  (reusing the same `sme_scoring_call_delay_seconds` setting that already
  paced the per-criterion path) when both flags are on; its existing
  per-criterion loop then checks `grouped` first and only falls through to
  `run_criterion` for codes missing from it. This means grouped mode can
  **never regress below today's behavior** — worst case, every criterion
  falls through and it behaves exactly like today.
- **`server/scripts/score_grouped.py`** (new) — CLI parity-testing harness,
  the grouped-mode counterpart to `score_criterion.py`. Takes `--doc` and
  `--delay` (default 15s), prints every criterion's grouped score/
  justification/evidence, and flags any code missing from the result.
- **`server/tests/agents/test_scoring_skeleton.py`** (new) — 34 tests:
  one `_compute_basket_*` adapter test per criterion (pure, hand-built facts,
  no LLM), slice-fallback tests, and `run_grouped` end-to-end tests via a
  routing `FakeClient` (success case, and each basket failing independently
  to confirm isolation).

### Verdict — real-SLM parity test (2026-07-05)

Ran both paths against the same real SLM
(`900956a0-ca3c-418d-b68b-19bd8441d0cb.pdf`, a Science/Tech/Society module,
32,411 chars): `score_criterion.py` per-criterion (the validated oracle) vs.
`score_grouped.py` (6 paced basket calls).

| Criterion | Oracle | Grouped | Verdict |
|---|---|---|---|
| A-03 | 4 | 4 | ✅ **fixed** — was 1 (empty) before the A3 split |
| OP-05 | 4 | 4 | ✅ **fixed** — was 1 (empty) before the A4 split |
| A-05 | 4 | 4 | ✅ match |
| OP-01 | 4 | 4 | ✅ match |
| OP-02 | 4 | 4 | ✅ match |
| OP-04 | 4 | 4 | ✅ match (17/18 vs 16/16 — same band; also fixed from empty in the 3-basket attempt) |
| OP-03 | 4 | 3 | ⚠️ **expected, not a regression** — the oracle's own (old) slice inflated its score by mislabeling lecture headings as tasks (see above); the lower grouped score reflects the *real* Performance-Task section |
| A-01 | 1 | 3 | ⚠️ likely a **pre-existing, orthogonal bug**, not a grouped-pass regression — the oracle's own raw output this run used non-conforming Bloom labels ("explain", "compare", "justify", "list") instead of the required 6-level enum; `_normalize_level`'s strict prefix match silently drops all of them to lower-order (note "compare" is literally the example verb for "analyze" in the module's own docstring). Worth fixing in `learner_transformation.py` independent of the skeleton pass. |
| A-02 | 3 | 2 | ⚠️ minor — grouped missed one assessment type ("reflection", the "Questions for Reflection" item) that the oracle caught; a single classification miss, not a category-wide failure |
| A-04 | 1 | 2 | ⚠️ **new finding, needs attention before trusting A-04 in grouped mode** — grouped classified one item as `positive_reinforcement`, but the quoted evidence is a copyright/fair-use legal disclaimer ("Under section Sec. 185 of RA 8293..."), not encouragement text. This looks like a genuine misclassification by Basket B1's prompt, not a real signal — the prompt likely needs an explicit "don't count legal/administrative boilerplate" exclusion. |

**Net: 6 of 10 clean matches, 1 expected/beneficial divergence (OP-03), 3
smaller divergences** — one pre-existing and orthogonal (A-01), one minor
(A-02), and one real quality gap worth fixing before relying on A-04 in
grouped mode.

### Not yet done

- **Only tested on one SLM.** Before trusting `SME.run()` broadly in
  production, run the same oracle-vs-grouped comparison
  (`score_criterion.py` × 10 vs. `score_grouped.py`) on 2–3 more real SLMs of
  different length/structure to confirm the pattern holds.
- **A-04's misclassification** (legal disclaimer tagged as
  `positive_reinforcement`) should be investigated — likely a prompt fix in
  `skeleton.BASKET_B1_PROMPT`, not a scope change.
- **A-01's Bloom-enum-compliance issue** is a separate, pre-existing bug in
  `learner_transformation.py` (and its prompt), unrelated to the skeleton
  pass — worth a dedicated look, since it also affects the per-criterion
  oracle path today.
- **Nothing is committed.** `skeleton.py`, the `registry.py`/`sme.py`/
  `config.py` changes, `score_grouped.py`, and the test files are all
  currently uncommitted working-tree changes.
- The old per-criterion `evaluate()` wrappers, prompts, and CLI are
  untouched and now double as `SME.run()`'s per-criterion fallback path (in
  addition to remaining the parity oracle) — see Part 3.5 below.
- **Separate, still-unfixed issue:** a real Neon Postgres "SSL connection
  closed unexpectedly" crash was hit while testing an evaluation through the
  actual app — `orchestrator.py` holds one DB session idle through the whole
  4-agent loop, and Neon's auto-suspend can kill it. Shortening SME's phase
  (this change removes its wasted base LLM call) helps but doesn't fix the
  root cause. Not addressed by this change.

### Part 3.5 — Making the engine SME's primary scoring path (2026-07-06)

Previously, `SME.run()` called `super().run()` (the shared
LLM-guesses-everything path) first, then `_overlay_engine_scores()` threw
away and recomputed every score via the engine — since the engine covers
100% of SME's rubric 1:1, that first call was pure wasted latency/tokens and
SME's single longest phase. `SME.run()` now:

1. Loads the full clean-PDF text (`_load_document_text()`, unchanged
   fallback chain).
2. Calls `registry.run_grouped()` once (the 6-basket pass).
3. For any of the 10 codes missing from that result, falls back to
   `registry.run_criterion(code, ...)` for just that code.
4. If a code fails both, raises `AgentExecutionError` (same all-or-nothing
   failure contract every other agent has — the Supervisor already handles
   a raised agent by marking it failed and excluding it from synthesis).

Criterion titles now come from a new `get_active_rubric_criteria(agent_id,
db=None) -> dict[str, str]` in `server/modules/rubrics/service.py` (mirrors
`get_active_rubric_context`'s query, returns `{code: title}`) — SME no
longer needs the LLM to echo titles back since it never sends a rubric
prompt. `_overlay_engine_scores()` is deleted. `sme_use_scoring_engine` and
`sme_scoring_grouped` are removed from `server/core/config.py` — the engine
is unconditional, no toggle.

Not touched: `base.py`/`coordinator.py`/`gad.py`/`itso.py` (only SME
overrides `run()`); `registry.run_criterion`/per-criterion `evaluate()`/the
CLI (kept, now doubles as SME's fallback in addition to the parity oracle);
`registry.run_grouped`/`skeleton.py` (unchanged).

Tests: SME was removed from `test_base.py`'s shared `[SME, Coordinator, GAD,
ITSO]` loop (that test asserts a plain-base-agent shape SME no longer has);
three `test_prompt_packing.py` tests that exercised the base LLM path via a
concrete `SME` instance were switched to `ITSO` (chunk-packing behavior is
agent-agnostic, only the domain keywords differ, and `ITSO`'s keywords
matched those tests' existing fixture data). `test_sme_engine_overlay.py`
was replaced by `server/tests/agents/test_sme_run.py`, testing the new
`run()` directly via a `SequencedFakeClient` (full success, partial-basket
fallback, total failure, empty-input guards).

### Registry mechanics (for anyone extending this)

`run_criterion()` (per-criterion path) and `run_grouped()` (basket path) both
end in `_render(code, result)`, so justification/evidence text is identical
regardless of which path produced the score. Adding a new registered
criterion means: write its `compute()` as usual, add a `_render` branch, add
it to `run_criterion`'s dispatch, and — if it should join the grouped path —
add it to the right basket's code-set and its `_compute_basket_*` router (or
give it a new single-purpose basket if it doesn't share a slice with
anything else).

### Open questions (carried over, still unresolved)

- A-05 objective granularity — SLMs list both broad Intended Learning
  Outcomes and specific Targets; whether to count both (risk of
  double-counting) or only Targets is still undecided.
- Whether the Program Coordinator agent reuses this same skeleton/engine
  machinery later (currently out of scope — SME only).
- Whether further real-SLM testing surfaces more bundling failures (e.g. if
  a longer/differently-structured SLM makes A1's assessments+alignment
  bundle or A2's tasks bundle degrade the way A2's old monitoring/enhancement
  did) — the 6-basket split fixed the failures *observed on one document*,
  not a proof that no other category will need isolating.

---

## Part 4 — References

- `docs/sme-scoring-basis.md` — design rationale (read first): §3 (SLM
  template + bottom-slice anchor rule), §6 (edge-case rules: empty
  denominator, OP-01 fallback, referenced-but-not-contained), §9 (A-05 spike
  findings — why temperature 0 and evidence quotes matter), §10 (current
  pipeline architecture — orchestrator/Supervisor/agent flow), §11–§12
  (integration invariants, call-budget rule, and the original high-level
  roadmap this document builds on).
- `docs/AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/TDD.md` — broader repo
  context (reference only, not a fixed spec, per `CLAUDE.md`'s Working Style
  section).
- Persistent memory files (`~/.claude/projects/.../memory/`):
  - `llm-budget-and-multi-agent.md` — the ~6k tokens/min shared-across-4-agents
    constraint that motivates the skeleton pass in the first place.
  - `engine-input-must-be-clean-pdf.md` — why the engine reads clean fitz
    text, never joined DB chunks.
  - `keep-scoring-doc-in-sync.md` — the rule that `sme-scoring-basis.md` §5
    rows only finalize after a user-confirmed CLI test (governs when A-04's
    "pending validation" caveat comes off).
  - `a02-a03-types-vs-instances.md` — the types-vs-instances design fork,
    and why it's derived per-rubric, not for cross-criterion consistency.
  - `op01-op04-downsample-and-scope.md` — the `downsample()` tail-anchor bug
    fix, and OP-04's internal-consistency-only scope decision.
  - `slm-activities-under-performance-tasks.md` — why activity-based
    criteria anchor on the bottom section header, not activity vocabulary.
  - `a01-grades-activities-not-objectives.md` — why A-01 targets tasks
    students actually do, not stated objectives.
