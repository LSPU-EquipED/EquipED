# Coordinator Independent 10-Criterion Scoring (Phase A, re-implemented)

Date: 2026-09-02
Supersedes: `docs/superpowers/specs/2026-08-18-coordinator-dpo-scoring-design.md`
(that spec's Phase A, written against a pre-#130 `main`, is stale — SME's
scoring pipeline was rewritten on 2026-08-30)

## Problem

Coordinator (`server/modules/agents/coordinator/`) scores exactly **one**
criterion today — A-05 (Objective Gauging), via a single fact-extraction
LLM call (`extraction.py`) plus a deterministic band in `curriculum.py`.
Its capability manifest is hard-locked to A-05
(`max_criteria=1`, `allowed_criterion_codes=("A-05",)`), and its active
rubric (Coordinator v2) contains only that criterion. The other 9
criteria on Coordinator's rubric shape are never scored by Coordinator;
historically SME's scores were spliced in, and that reconciliation step
has since been retired from `main` entirely.

We want Coordinator to score **all 10 criteria independently**, so that:

1. Coordinator produces a full advisory scorecard through a
   curriculum-aware lens rather than leaving 9/10 criteria unscored.
2. Coordinator accumulates its **own** prompt/response records across its
   full rubric — the training material for a Coordinator-specific DPO
   LoRA adapter (Phase B). Per-agent adapters were already decided; an
   adapter trained on 90%-borrowed SME data defeats the purpose.

This is **Phase A only**: independent scoring plus persistence of the
per-envelope prompt/response snapshots. Phase B (DPO export script +
reviewer-edit UI) stays blocked on `feat/sme-dpo-scoring` merging and is
out of scope here.

## Background: why this is a re-implementation, not a rebase

The abandoned `feat/coordinator-dpo-scoring` branch implemented Phase A
against a `main` from before PR #130. Since then:

- **SME's scoring architecture turned over** (commits `52bce78`,
  `2481283`, both 2026-08-30, both on `main`). The old design the branch
  copied — LLM-direct scoring, where the model reads a `scoring_rule` and
  returns a 1-4 band — was replaced with **measurement-extraction +
  deterministic calculators**: the LLM emits only grounded measurements
  (instance excerpts, qualifying-unit lists, or a guidance score), and
  `sme/scoring.py` maps them to a band using thresholds frozen in the
  snapshot's `strategy_config`.
- **SME dropped per-criterion-group semantic slicing.** It now applies a
  single uniform `downsample_source_text` (6 evenly-spaced windows,
  tail-anchored) as a budget fallback only; small documents pass whole.
- `EngineScoredAgent`'s signature changed and its
  `_rubric_titles`/`_rubric_descriptions` helpers were removed (criterion
  metadata is frozen into the snapshot, not fetched at call time).
- The `AgentResult.group_prompts` / `group_responses` columns now exist
  on `main`, so Phase A can persist snapshots directly — the old spec's
  Phase A/B split along that column boundary no longer applies.
- Synthesis (`build_persistable_agent_result`) rejects any agent result
  whose criterion-code set does not exactly equal its snapshot's — so
  **partial results are impossible**; Coordinator returns all 10 or fails
  wholesale.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scoring mechanism | Adopt SME's current measurement-extraction + calculator design | Separates "find evidence" (LLM is good) from "apply threshold" (arithmetic — LLM is unreliable). Reproducible, auditable, and gives clean DPO signal (reviewer corrects measurements, not a smeared score). |
| Text slicing | Uniform `downsample_source_text` only, no semantic slicers | YAGNI for now; the findings that justified semantic slicing were measured against the old LLM-direct SME and are unverified under the new design. Can be added later per-criterion if testing shows evidence clipping. |
| Code sharing with SME | Full copies under `coordinator/`, not imports | SME's pipeline was rewritten 3 days ago by another contributor and `feat/sme-dpo-scoring` is in flight. A one-time copy is lower-risk than coupling to churning code and lets A-05's curriculum path diverge freely. The shared `rubrics/strategies/calculators.py` (rubrics infra, not SME) is used directly. |
| A-05 scoring | Keep the `curriculum_alignment` strategy with hard groundedness | Curriculum grounding is Coordinator's entire reason to exist. A-05 is the only criterion with a literal, quotable claim against curriculum text. |
| Rubric identity | New Coordinator Rubric **v3**, `adapter_version` **2** | The scoring distribution changes; the pending Coordinator DPO adapter must train on the new distribution, not a mix. |
| Failure handling | Any envelope fails twice → whole Coordinator result fails | Forced by synthesis integrity (no partial results). Matches SME. No engine fallback. |
| Grouping | `pack_domains` (domain-based envelopes), copied from SME | Coordinator's OP + A rubric yields 2 envelopes deterministically; A-05 lands with the A criteria. |

## Architecture

Coordinator stays a parallel specialist agent invoked by the Supervisor
via `dispatch.py`. It receives its own frozen `EvaluationFormSnapshotDTO`
(10 criteria once v3 is active), the canonical SLM text, and the
authoritative curriculum context. It packs the snapshot into envelopes,
runs one LLM call per envelope (with one repair retry), scores each
criterion deterministically from the returned measurements, and returns a
single 10-criterion `AgentEvaluationResult`.

### Data flow

```
dispatch.py
  -> Coordinator.run(evaluation_id, document_id, form_snapshot,
                     chunk_infos, canonical_source_text,
                     curriculum_id, curriculum_context, roadmap_context, ...)
       -> validate snapshot (agent_id, evaluation_id, adapter key/version=2,
                             10 criteria)
       -> require canonical_source_text and curriculum_context (hard-fail)
       -> resolve RunLLMClient adapter
       -> packing.pack_domains(domains) -> (env_OP, env_A)
       -> for each envelope idx:
            prompt.build_envelope_prompt_and_source(
                criteria, canonical_source_text, curriculum_context,
                prompt_budget, preamble=roadmap_note)
              - downsample source to fit budget
              - inject curriculum_context block ONLY in the envelope
                containing A-05
            execution.execute_envelope(...)
              - one LLM call; on parse/validation failure, one repair call
              - second failure -> raise AgentExecutionError
            response.parse_and_validate_envelope_response(...)
              - strict shape + verbatim grounding of every excerpt
              - for A-05: demote ungrounded alignment rows, count demotions
            scoring.score_envelope(criteria, parsed)
              - 9 criteria: rubrics/strategies/calculators (score_count / _ratio /
                normalize_llm_guidance_score)
              - A-05: score_curriculum_alignment(alignments) -> ratio_band moderate
       -> assemble AgentEvaluationResult:
            subtotal = mean(10 scores)
            criterion_scores = 10, snapshot order
            summary = build_improvement_summary(criterion_scores)
            metadata = {group_prompts, group_responses}
            provenance = telemetry dict
  -> synthesis.build_persistable_agent_result persists criterion_scores,
     subtotal, group_prompts, group_responses
```

### Module layout (`server/modules/agents/coordinator/`)

| File | Status | Notes |
|---|---|---|
| `agent.py` | rewritten | `Coordinator` class. Snapshot validation, context requirements, envelope orchestration, result assembly. No import from `sme/`. |
| `packing.py` | new | Verbatim copy of `sme/packing.py`; rename error string to "Coordinator snapshot contains no criteria". |
| `prompt.py` | new | Copy-adapted from `sme/prompt.py`. Coordinator preamble; reuse `downsample_source_text` logic; add `CurriculumAlignmentConfig` criterion block; inject `curriculum_context` block into the A-05 envelope only. |
| `response.py` | new | Copy-adapted from `sme/response.py`. Add `curriculum_alignment` schema branch, parsing to `CurriculumAlignmentMeasurement`, and the groundedness demotion pass. Coordinator-labelled error categories. |
| `scoring.py` | new | Copy-adapted from `sme/scoring.py`. 9 criteria delegate to `rubrics/strategies/calculators.py` unchanged. Add `score_curriculum_alignment()` porting `curriculum.py::compute` (distinct aligned objectives -> `ratio_band(scale="moderate")`, 80/50/20). |
| `execution.py` | new | Copy-adapted from `sme/execution.py`. Repair-once; second failure raises. Coordinator telemetry labels and prompt-budget setting. |
| `summary.py` | deleted | Replaced by copied `build_improvement_summary`. |
| `extraction.py` | deleted | Retired fact-extraction path. |
| `curriculum.py` | deleted | `compute` logic ported into `scoring.py`; `format_roadmap_note` moved into `agent.py`. |
| `__init__.py` | unchanged | Still exports `Coordinator`. |

### Rubric / manifest / seed

- **Alembic data migration** (`server/db/alembic/versions/<ts>_coordinator_rubric_v3.py`):
  - insert `RubricSet(agent_id="coordinator", version_number=3,
    status="published", adapter_key="coordinator", adapter_version=2)`
  - insert OP and A `RubricDomain` rows (display_order matching SME's:
    OP then A)
  - insert 10 `RubricCriterion` rows. Titles / descriptions /
    `scoring_rule` copied from SME's seed values
    (`server/data/rubrics/rubrics.json` + `SME_STRATEGY_CONFIGS` in
    `seed_rubrics.py`). `scoring_strategy` / `strategy_config`: A-05 =
    `{"strategy": "curriculum_alignment"}`; the other 9 = SME's configs.
  - insert / update `RubricAgentActivation` to point coordinator at the
    v3 `rubric_set_id`
  - downgrade: re-point activation at v2, delete v3 rows
- **`manifests.py`** — `COORDINATOR_MANIFEST_V1`:
  - `supported_strategies = ("curriculum_alignment", "count_band",
    "ratio_band", "llm_rubric_guidance")`
  - `capabilities` / `supported_measurement_shapes` extended to the
    matching shapes
  - `min_criteria = 1`, `max_criteria = 10`
  - `allowed_criterion_codes = ("A-01","A-02","A-03","A-04","A-05",
    "OP-01","OP-02","OP-03","OP-04","OP-05")`
  - `supported_count_modes` / `supported_ratio_modes` widened to match
    SME's manifest
- **`seed_rubrics.py`**:
  - `_resolve_criterion_strategy`: extend the
    `agent_id == "coordinator"` branch to resolve all 10 codes (A-05 ->
    curriculum_alignment; others -> `SME_STRATEGY_CONFIGS[code]`)
  - `seed_coordinator_v2_if_needed` -> `seed_coordinator_v3_if_needed`:
    idempotent creation + activation of v3, same structure as the
    existing v2 helper; v2 left `published` (not retired — frozen
    historical snapshots reference it)
  - `main()` calls the v3 helper
- **`server/data/rubrics/rubrics.json`** — unchanged (retired coordinator
  v1 entry stays as legacy metadata).

### A-05 curriculum alignment detail

Prompt (A-05 block only):

> Extract every learning objective stated in the SLM as a verbatim
> substring. For each objective, decide whether the CURRICULUM CONTEXT
> addresses it; if so, quote the exact supporting span from the
> curriculum context. Do not assign a score.

Measurement: `CurriculumAlignmentMeasurement`
(`alignments: (ObjectiveAlignmentRow, ...)`, already in
`rubrics/contracts.py`). Each row: `objective_text` (verbatim from SLM),
`is_aligned` (bool), `assessment_excerpt` (here: the curriculum span),
`reasoning`.

Groundedness (in `coordinator/response.py`): for every row with
`is_aligned == true`, `assessment_excerpt.strip()` must be a substring of
`curriculum_context`. Rows failing this are demoted to
`is_aligned = false` with empty excerpt, and a `grounding_rejected_count`
is recorded in provenance. (This is a demotion, not an envelope failure —
matches the retired `curriculum.py`.)

Score (`coordinator/scoring.py::score_curriculum_alignment`):
`aligned = count of distinct objectives with is_aligned == true` (after
demotion); `band = ratio_band(aligned, total_objectives,
scale="moderate")` (thresholds 80 / 50 / 20). Zero objectives, or zero
aligned -> band 1.

### Result & persistence

- `subtotal` = arithmetic mean of the 10 integer scores
- `criterion_scores` = 10 `CriterionScore`, in snapshot order
- `summary` = `build_improvement_summary(criterion_scores)` (copied from
  `sme/pipeline.py`, deterministic)
- `metadata = {"group_prompts": {envelope_key: prompt_text},
  "group_responses": {envelope_key: parsed_dict}}` — persisted to the
  existing `AgentResult.group_prompts` / `group_responses` columns
- `provenance` = `{requested_model, actual_model, fallback_occurred,
  repair_occurred, grouped_calls, logical_calls, physical_attempts,
  input_tokens, output_tokens, truncation_count, cap_hit_count,
  provider_seconds_ms, grounding_rejected_count}`

### Error handling

- Missing / empty `canonical_source_text` -> `AgentExecutionError`
- Missing / empty `curriculum_context` or `curriculum_id` ->
  `AgentExecutionError` (Coordinator is the curriculum agent)
- Snapshot invariant violation (wrong agent_id, evaluation_id,
  adapter_key/version, criterion count != 10, unexpected code) ->
  `AgentExecutionError`
- Envelope parse/validation failure after one repair retry ->
  `AgentExecutionError`
- Any `AgentExecutionError` from `run()` is caught by `dispatch.py`,
  which emits a clean failed `AgentEvaluationResult` (success=False,
  subtotal=0, no criterion_scores, no group payloads). The evaluation as
  a whole still completes with the other agents' results.

## Non-goals

- Phase B: `export_coordinator_dpo_pairs.py`, reviewer-edit UI
  (`AgentReviewModal.tsx`), backend schema for Coordinator corrections.
- Semantic per-criterion text slicing.
- Parameterizing or otherwise modifying `sme/` modules.
- Changing `dispatch.py` / `supervisor.py` (they already pass every
  argument `Coordinator.run` needs).
- Frontend changes (synthesis, scorecard, monitoring matrix, and
  confusion matrix are already generic over an agent's criterion set).
- Retiring Coordinator rubric v2 (kept `published` for frozen snapshots).

## Testing

Delete `server/tests/agents/coordinator/test_coordinator_contract.py`
(tests the retired extraction/compute path).

New tests under `server/tests/agents/coordinator/`:

| File | Covers |
|---|---|
| `test_coordinator_packing.py` | OP+A -> 2 envelopes; order preserved; empty-domain guard |
| `test_coordinator_prompt.py` | preamble present; `curriculum_context` block only in the A-05 envelope; budget overflow raises; downsample applied for oversized text; each strategy's criterion block shape |
| `test_coordinator_response.py` | strict shape validation; verbatim grounding of excerpts; `curriculum_alignment` parsing to `CurriculumAlignmentMeasurement`; ungrounded alignment rows demoted + counted; repair-category labels |
| `test_coordinator_scoring.py` | 9 criteria via shared calculators; `score_curriculum_alignment` band boundaries (0/20/50/80%); zero-objective -> 1 |
| `test_coordinator_agent.py` | 10-criterion result; snapshot-order criterion_scores; subtotal = mean; summary populated; `metadata.group_prompts`/`group_responses` populated; missing curriculum -> fail; envelope double-failure -> failed result contract; provenance fields |
| `test_coordinator_rubric_v3_migration.py` (under `server/tests/migrations/`) | upgrade -> v3 active, 10 criteria, A-05 = curriculum_alignment, adapter_version 2; downgrade -> v2 active |

Update:

- `server/tests/evaluations/test_orchestrator.py` and any integration
  fixtures / helpers that assume a 1-criterion Coordinator snapshot or
  result
- `server/tests/agents/integration/test_provenance_persist.py`,
  `test_synthesis_persist.py` if they pin Coordinator's criterion count
- rubric seed tests (`server/tests/rubrics/`) that assert Coordinator v2
  is the active revision

## Rollout

1. Land the migration + manifest + seed changes together with the agent
   rewrite in one branch (`feat/coordinator-independent-scoring`).
2. `uv run --project server alembic upgrade head` on each environment;
   `uv run --project server python -m server.scripts.seed_rubrics` to
   activate v3 where the migration path is not used.
3. New evaluations pick up the 10-criterion Coordinator snapshot
   automatically once v3 is the active revision. Existing evaluations
   keep their frozen v2 snapshots and are unaffected.
