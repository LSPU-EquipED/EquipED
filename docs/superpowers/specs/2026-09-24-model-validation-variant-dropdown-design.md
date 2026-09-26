# Model Validation: variant dropdown replaces Compare — Design

Date: 2026-09-24
Status: draft, pending user review

## Problem

The Model Validation page has a **Compare** tab that fires two linked runs
(base at LoRA scale 0.0, adapter at 1.0) from a separate form. In use it
turned out to be more than needed: the paired jobs queue back to back through
the single global admission slot (which inflated the second run's latency
2.4x), the flow duplicates most of **+ New Benchmark Run** in a second form,
and the admin wants one run to mean one job.

Decision: remove Compare, and let **+ New Benchmark Run** choose which model
variant a run uses — **Base** or **Fine-tuned adapter** — with a dropdown.

## Facts (verified 2026-09-24 against `main`, after PR #343)

- `create_model_validation` (`modules/admin/model_validation_service.py`)
  already accepts `model_variant`, `compare_group_id` and `lora_scale` as
  keyword arguments and persists them. `create_adapter_comparison` is only a
  wrapper: it runs `check_lora_adapter_loaded()`, then calls
  `create_model_validation` twice with a shared `compare_group_id`.
- `check_lora_adapter_loaded()` (`core/llm.py`) reports whether the LLM
  endpoint has at least one LoRA adapter loaded, and raises
  `InfrastructureUnavailableError` if the endpoint cannot be reached.
- The scale reaches the model per job: `EvaluationJob.lora_scale` is read by
  the orchestrator and passed down; `None` sends no `lora` field at all.
- The compare route is `POST /model-validations/compare` (202) and maps
  `DocumentNotFoundError` → 404, `InvalidEvaluationTargetError` → 422,
  `InfrastructureUnavailableError` → 503.
- `ModelValidationCreateRequest` already has `target_agent` (`all` | `sme` |
  `coordinator` | `gad` | `itso`) and rejects combining a single agent with
  `partial_without_curriculum`.
- **The standard form has no agent picker.** `useModelValidationFormState`
  always sends `partial_without_curriculum: true` with expected scores for
  SME + GAD + ITSO, and requires an acknowledgement checkbox for the partial
  (no-curriculum) run. Only the Compare form let you choose a single agent
  (SME / GAD / ITSO; Coordinator was excluded because it needs a curriculum
  picker).
- History already shows a Base/Adapter badge from `model_variant`
  (`variantLabel` helper, `ValidationDetail`).

## Goals

1. **+ New Benchmark Run** gets a **Model** dropdown: *Base model* or
   *Fine-tuned adapter*. One submit creates one run.
2. *Base* always means the plain model; *Adapter* always means the adapter
   applied. Neither silently depends on host defaults.
3. Adapter runs target exactly one agent. Base runs may target the full
   bundle (today's behavior) or one agent, so a base run and an adapter run
   of the same agent are comparable later.
4. Remove the Compare tab and everything only it used.

## Non-goals

- A side-by-side comparison view. Explicitly deferred to a follow-up; pairing
  base and adapter runs is left to the admin (open two history rows) until
  then.
- Fixing metrics contamination. Analytics stay mixed across variants;
  splitting them is a separate change (see Known limitations).
- Dropping the `compare_group_id` column. It stays, unused and nullable, so
  the follow-up side-by-side view can pair runs without another migration.
- Coordinator in the adapter/single-agent picker (needs a curriculum picker;
  same scope cut Compare had).
- Any change to how adapters are trained, converted, or loaded on the host.

## Design

### 1. Backend contract

`ModelValidationCreateRequest` gains
`model_variant: Literal["base", "adapter"] | None = None`.
`None` keeps today's behavior exactly (no `lora` field); the UI always sends
one of the two values.

Request validation (schema-level `model_validator`):
- `model_variant == "adapter"` requires `target_agent != "all"`; otherwise the
  request is rejected (422).

`create_model_validation` drops its `model_variant`, `compare_group_id` and
`lora_scale` keyword arguments. It reads the variant from the request and
derives the scale in one helper, before any database row is created:

| `model_variant` | Behavior |
|---|---|
| `None` | No scale; unchanged. |
| `"adapter"` | If `check_lora_adapter_loaded()` is false, raise `InvalidEvaluationTargetError` with the existing message ("no adapter is loaded on the server; ask the host owner to load one first — see `training/serving-lora-adapter.md`"). Otherwise scale `1.0`. |
| `"base"` | If an adapter is loaded, scale `0.0` (forces the adapter off even if the host applied it). If none is loaded, no scale is sent — there is nothing to turn off, and sending a `lora` field to a server with no adapter is unverified. The row is still labelled `base`. |

The `model_variant` column stores the variant; `compare_group_id` is written
as `NULL` for all new rows. The scale continues to travel on the job row
(`EvaluationJob.lora_scale`), never a global or context variable, so
concurrent runs cannot leak a scale into each other.

The standard `POST /model-validations` route gains the same
`InfrastructureUnavailableError` → 503 mapping the compare route had
("Could not reach the LLM endpoint to check for a loaded adapter."). It
already returns 422 for `InvalidEvaluationTargetError` and 404 for a missing
document. An unreachable endpoint is already caught earlier by
`probe_local_model_readiness()`; the extra mapping covers the narrow window
between that probe and the adapter check.

Removed from the backend: `create_adapter_comparison`, the
`AdapterComparisonCreateRequest` / `AdapterComparisonResponse` schemas, the
`POST /model-validations/compare` route, and their tests.

### 2. Data

No migration. `model_validations.model_variant`,
`model_validations.compare_group_id` and `evaluation_jobs.lora_scale` all
stay. Existing rows keep their meaning: past compare pairs keep their
Base/Adapter badges (and their now-unused `compare_group_id`), and older
standard runs have a `NULL` variant and no badge.

### 3. Frontend

One form, one tab. `ValidationTab` loses `'compare'`.

`useModelValidationFormState` gains two pieces of state:
- `modelVariant: 'base' | 'adapter'`, default `'base'`.
- `targetAgent: 'all' | 'sme' | 'gad' | 'itso'`, default `'all'`.

**New controls** (top of the form, before the document upload): a **Model**
select and a **Target** select. `Target` is new to this form; it is the
mechanism that makes "adapter needs a single agent" expressible, and it is
what lets a base run target one agent so it can be compared with an adapter
run of the same agent later. (Clarification of the approved design: the
standard form had no target picker before this.)

Behavior:
- Choosing *Fine-tuned adapter* disables the *All agents* option in Target.
  If Target is currently *All agents*, it becomes unselected and submit stays
  disabled until an agent is chosen. Switching back to *Base model* keeps a
  chosen single agent.
- Expected scores are scoped to the target: *All agents* is today's SME + GAD
  + ITSO set; a single agent shows and requires only that agent's criteria.
  Keyboard order for score entry follows the scoped list.
- The partial-run acknowledgement checkbox is shown and required only for
  *All agents*. A single-agent run sends `target_agent` and **no**
  `partial_without_curriculum` (the API forbids the combination).
- The request body always carries `model_variant` and the derived
  `target_agent`.
- Errors (adapter not loaded → 422 text, unreachable endpoint → 503 text) use
  the form's existing error display.

**Removed:** `AdapterComparisonForm.tsx`, `useAdapterComparisonFormState.ts`,
the `compareAdapter` API function, the `AdapterComparison*` types, the
Compare tab button and panel in `ModelValidationPage.tsx`, and their tests.

**Kept:** the `variantLabel` helper and the Base/Adapter badge in
`ValidationDetail`; the single-agent progress panel behavior in
`AgentProgressPanel` (it is driven by `target_agent`, not by Compare).

### 4. Behavior changes to note

- Standard runs created after this change are labelled `base` and, when an
  adapter is loaded on the host, explicitly run with the adapter off. Before,
  they sent no scale and followed the host's default. Results of old runs and
  new base runs are therefore comparable only when the host default was the
  plain model.
- One job per run removes the back-to-back queueing that inflated the second
  compare run's latency. The `execution_started_at` latency work that was
  reverted earlier stays out of scope.

## Error handling

- No adapter loaded + variant `adapter` → 422 before any row exists.
- Adapter + `target_agent: "all"` → 422 (schema validation); the UI prevents
  it.
- LLM endpoint unreachable during the adapter check → 503.
- Base with no adapter loaded → allowed; no scale sent.

## Testing

Backend:
- `model_variant` defaults to `None` and the request payload is byte-identical
  to today's (no `lora` field). Keep the existing `LocalLLMClient`
  regression guard.
- `adapter` + `all` is rejected; `adapter` + a single agent with none loaded
  raises `InvalidEvaluationTargetError` and creates no rows; with one loaded
  it stores `model_variant="adapter"` and `lora_scale=1.0`.
- `base` + adapter loaded stores `lora_scale=0.0`; `base` + none loaded stores
  no scale but `model_variant="base"`.
- `compare_group_id` is `NULL` on new rows; concurrent runs do not share a
  scale.
- The old `/model-validations/compare` route no longer exists; the standard
  route maps `InfrastructureUnavailableError` to 503.
- Delete the compare-specific service, API and migration-behavior tests that
  only exercised the removed wrapper; keep the migration test for the columns
  that remain.

Frontend:
- Model defaults to Base; Target defaults to All agents.
- Selecting Adapter disables All agents and blocks submit until an agent is
  chosen.
- Expected-score inputs are scoped to the target; keyboard order follows it.
- The partial acknowledgement is required only for All agents; single-agent
  bodies omit `partial_without_curriculum`.
- The submitted body carries `model_variant` and `target_agent`.
- The page shows three tabs (no Compare); history badges still render for
  `base`, `adapter` and `null`.

Manual, against the real host: one Base run and one Adapter run on the same
SME document with the same expected scores; confirm each history row's badge
and that the adapter run applies the adapter (as the Compare live test did).

## Known limitations

- **Analytics stay mixed** across variants until a follow-up splits them; a
  Base and an Adapter run both feed the same MAE/latency/toxicity numbers.
  This is the existing metrics-contamination issue, unchanged.
- **No side-by-side view yet.** Comparing means opening two history rows.
- An adapter is only meaningful for the agent it was trained on (SME today).

## Rollout

Single PR, in this order:
1. Backend: request field, scale derivation, route mapping, delete the compare
   wrapper/route/schemas and their tests.
2. Frontend: Model + Target controls and scoped scoring in the standard form;
   delete the Compare form, hook, API function, types, tab and their tests.
3. Docs sweep: search `docs/` and `training/` for references to the Compare
   tab and update them.

Related: `[[compare-ui-next-brainstorm-ideas]]`,
`[[compare-ui-metrics-contamination]]`,
`[[model-validation-adapter-compare-spec]]`.
