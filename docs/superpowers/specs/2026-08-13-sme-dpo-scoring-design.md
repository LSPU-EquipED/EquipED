# SME Scoring Redesign & DPO Feedback Loop — Phase 2a Design

Date: 2026-08-13
Branch: to be created during implementation planning

## Problem

EquipED is moving from provider-hosted, multi-model LLM calls to a single
localized model shared by every agent, sized at 4B parameters for hardware
reasons. That single model will be improved over time via DPO fine-tuning,
using the reviewer-correction loop already built for ITSO
(`docs/superpowers/specs/2026-08-10-dpo-itso-scoring-design.md`).

That ITSO design explicitly deferred SME and Coordinator, for a structural
reason: SME/Coordinator score almost entirely through a deterministic
code-side "engine" (`sme/pipeline.py`, `sme/bands.py`) — the LLM only
extracts facts (`sme/extraction.py`'s 6 "basket" calls), and a separate
`compute()` function converts those facts into a 1–4 score via fixed
thresholds. DPO trains a model's *text generation* behavior from
`(prompt, chosen, rejected)` pairs; it has nothing to act on when the score
comes from arithmetic, not generation. Under the old multi-model
architecture this was a deliberate, validated trade-off (see
`openspec/specs/sme-engine-scoring/spec.md`) — it saved LLM budget and
gave deterministic, auditable scoring. Under the new single-4B-model
constraint, it becomes a liability: the engine can never improve via
fine-tuning, no matter how much reviewer correction data accumulates.

This document scopes to **SME only**. Coordinator's identical redesign is
deferred until SME's results are observed in practice — see Non-goals.

## Goals

- Replace SME's `compute()`/`bands.py` deterministic scoring with direct
  LLM scoring (score + justification + evidence per criterion), so every
  criterion becomes DPO-eligible.
- Reduce SME's per-evaluation LLM call count from today's 6 extraction
  calls (plus separate compute) to 2–3 grouped calls, to fit the shared
  6k-tokens/min budget now that every agent draws from the same model's
  rate limit instead of separate per-agent pools.
- Extend the existing ITSO-pattern review UI (Accept/Reject/Edit,
  `PreferenceLog`) to SME's 10 criteria.
- Extend the existing DPO export script pattern to SME, producing
  preference pairs keyed to SME's actual call structure.
- Lay the groundwork for a dedicated SME LoRA adapter, layered on the same
  shared 4B base model used by every other agent.

## Non-goals (this phase)

- **Coordinator is not touched.** It keeps its current merge design (one
  LLM call scoring only A-05 with curriculum context, reusing SME's scores
  for the other 9 criteria) unchanged. Because Coordinator's shared 9
  criteria are literally copied from SME's output, Coordinator's results
  will reflect SME's new LLM-scored values automatically — but Coordinator
  gets no new review modal, no DPO capture, and no adapter in this phase.
  Revisit once SME's redesign has been observed in production.
- GAD is untouched (already deferred by the ITSO design; still deferred).
- No in-app training trigger, job queue, or experiment tracking — training
  stays a manual, out-of-repo process, same as ITSO.
- No decision on the local model-serving stack (vLLM, Ollama,
  text-generation-webui, or other). How an adapter path is actually wired
  into inference depends on that choice, which has not been made. This
  design only commits to *where* the config hook lives
  (`get_llm_client_for_agent`), not how the underlying server loads the
  adapter file.
- No change to `synthesis/matrix.py`'s `AGENT_WEIGHTS` or the synthesized
  score formula.

## SME Scoring Redesign

### Call structure

Today's 6 single-purpose extraction baskets (`sme/extraction.py`) are the
result of two earlier, empirically rejected attempts: a 2-basket version
that exceeded the token ceiling outright, and a 3-basket version that
appeared to fit the budget but silently dropped secondary categories
(monitoring, enhancement, sections) under real-SLM testing against the
validated oracle — diagnosed as multi-task attention degradation, where a
model gives real effort to the first-listed category in a prompt and
shortchanges the rest.

This phase consolidates to **2–3 grouped calls**, each doing extraction
*and* scoring together (replacing the current extract-then-`compute()`
split). This deliberately reintroduces the same class of risk the 6-basket
design was built to avoid, now compounded by a smaller model and a harder
per-call task (scoring, not just listing facts). This trade-off is
accepted for the budget win, on the condition that the specific grouping
is validated against the existing oracle before shipping — the same
discipline used to arrive at the current 6-basket split. The exact
grouping (which of the 10 criteria share which call) is an implementation
decision, not fixed by this design.

### Output shape

Each grouped call returns, per criterion it covers, the same
`{criterion_id, score, justification, evidence}` shape ITSO's
`response.py` already produces — replacing `compute()`'s band-derived
score with the LLM's direct judgment. `bands.py`'s threshold tables are
retired for LLM-scored criteria.

### Fallback path

`run_criterion` (today's per-criterion fallback for whatever a grouped
extraction pass misses) is kept, now performing LLM scoring directly
instead of extraction-then-compute, for any criterion a grouped call fails
to return or fails to parse.

## DPO Correction Capture & Review UI — SME

Reuses `PreferenceLog` exactly as extended for ITSO — no schema changes.
Every row this phase creates is `agent_name='sme'`; `criterion_id` is one
of SME's 10 rubric codes (A-01–A-05, OP-01–OP-05).

One review modal for SME, covering all 10 criteria, following the same
Accept/Reject/Edit pattern, endpoint shape
(`POST /feedback/{evaluation_id}/criteria/{criterion_id}`), and
"surface prior corrections on reopen" behavior already built for ITSO's
modal. Coordinator's results display unchanged — the merge logic already
pulls SME's 9 non-A-05 scores, so Coordinator's displayed numbers reflect
SME's new LLM-scored values with no code change on Coordinator's side, but
Coordinator gets no editing affordances of its own in this phase.

## DPO Export — SME

Because SME now makes 2–3 grouped calls instead of ITSO's single call,
export is keyed **per group, per evaluation** rather than per evaluation:

1. Query `PreferenceLog` where `agent_name='sme'` and `action='EDIT'`,
   latest row per `(evaluation_id, criterion_id)`.
2. Group edited criteria by which grouped call originally produced them
   (a static mapping from criterion_id to group, not a new DB column).
3. For each `(evaluation_id, group)` with at least one edited criterion:
   reconstruct that group's exact original prompt (slice + template, per
   `sme/extraction.py`), replayed against that evaluation's stored inputs.
   `chosen` = the group's full response with the corrected criteria
   substituted in; `rejected` = the AI's original full response for that
   group. Groups with no corrected criteria produce no row — this differs
   from a synthetic "combine everything into one evaluation-level pair,"
   since no single real SME call ever spans all 10 criteria at once, and
   training on a prompt shape the model will never see at inference time
   would be counterproductive.
4. If a group's original inputs can't be reconstructed, that row is
   logged and skipped, not silently dropped — same convention as the ITSO
   export.
5. Write one JSONL line per pair, same `{"prompt", "chosen", "rejected"}`
   shape as ITSO's export.

## Fine-tuning & Deployment — SME

- SME's exported JSONL trains a dedicated small LoRA adapter, layered on
  the same shared 4B base model every agent uses — not a separate full
  model. Training happens on a standalone, manually-run script/notebook,
  fully outside this repo's runtime, mirroring ITSO's process exactly.
- Promotion/rollback is a config change: the per-agent LLM config
  mechanism (today's `LLM_MODEL_SME` env var, resolved through
  `get_llm_client_for_agent`) is generalized to resolve an **adapter
  reference** for SME rather than a full model name. The precise config
  shape and how it's threaded into the local serving stack is deferred
  until that stack is chosen (see Non-goals) — this design only commits to
  the mechanism living in the same per-agent resolution path that already
  exists, not to new infrastructure.
- No automatic or scheduled retraining, same judgment-call threshold
  ITSO's design used: whether there's "enough" EDIT volume to justify a
  training pass is decided when the export count is visible.

## Phase 2b (captured, not built now)

- **Coordinator**: once SME's redesign is observed in practice, revisit
  whether Coordinator needs its own review modal / DPO capture for A-05
  (its one independently-scored criterion). If so: A-05 corrections tag
  `agent_name='coordinator'`; corrections to the other 9 criteria — even
  if made from a Coordinator-facing view — tag `agent_name='sme'`, since
  those scores are SME's judgment regardless of which domain's modal
  displays them. No new `PreferenceLog` columns anticipated.
- **GAD**: unchanged from the ITSO design's Phase 2 note — needs a
  fact-correction UI, not a score-correction UI, since its score is still
  computed from LLM-extracted facts by deterministic code.
