# DPO-Based Scoring Feedback Loop — ITSO Phase 1 Design

Date: 2026-08-10
Branch: `feat/dpo-itso-scoring`

## Problem

EquipED's four domain agents (SME, Coordinator, GAD, ITSO) score SLMs
against institutional rubrics, but there is no mechanism for CID reviewers'
corrections to ever improve future evaluations. `PreferenceLog`
(`server/modules/feedback/models.py`) exists as a scaffold for human
ACCEPT/REJECT/EDIT feedback, but nothing writes to it: the `feedback`
router has no routes, and the frontend's `useSubmitFeedback` hook is
defined but unused. Feedback is also currently modeled at the whole
-evaluation level, with no way to attribute a correction to a specific
agent or criterion.

The long-term goal is a reinforcement-learning loop (DPO) that trains
agents to produce judgments closer to what CID reviewers actually want,
using reviewer corrections as preference data.

## Why ITSO first

The four agents are not architecturally uniform, and DPO — which trains a
model's *text generation* behavior from `(prompt, chosen, rejected)`
pairs — only cleanly applies where an agent's score and justification are
themselves produced by one LLM generation:

- **ITSO** (`itso/execution.py`, `itso/response.py`) is a single LLM call
  that returns `{criterion_id, score, justification, evidence}` per
  criterion. This is the one agent where "reviewer edits the score and
  justification" maps directly onto a DPO pair.
- **GAD** (`gad/prompt.py`) uses its LLM call only for *fact extraction*
  ("do not assign scores"); the actual score is computed afterward by
  deterministic code (`female_male_count.py`, `stereotypes.py`, etc.)
  applying bands to those facts. A score correction here really means a
  *fact* correction, which is a different edit shape and a different DPO
  pairing (corrected facts vs. original facts, not corrected scores).
- **SME / Coordinator** (`sme/pipeline.py`) score almost entirely through
  a deterministic code-side engine; the LLM is invoked only as a narrow
  grouped-basket/fallback path. Most corrections here aren't attributable
  to any LLM generation at all, so most of what a reviewer edits couldn't
  become DPO data.

Building all four at once means guessing at GAD's fact-correction UX and
SME/Coordinator's engine-vs-fallback attribution before the basic
collect-train-deploy loop has ever been proven. This design scopes to
ITSO only. GAD and SME/Coordinator are captured as Phase 2 (see below) but
not built now.

## Goals

- Let a CID reviewer Accept, Reject, or Edit each ITSO criterion's score +
  justification on the evaluation Scorecard.
- Persist that feedback per-agent, per-criterion (not just per-evaluation).
- Provide an export path that turns EDIT actions into DPO-formatted
  `(prompt, chosen, rejected)` training pairs.
- Keep model training and deployment fully decoupled from the running
  app — no GPU job infrastructure added to the FastAPI monolith.

## Non-goals (this phase)

- No editing UI or feedback attribution for SME, Coordinator, or GAD.
- No in-app training trigger, job queue, or experiment tracking.
- No automatic/scheduled retraining or automatic model promotion.
- No change to the synthesized/weighted score formula
  (`synthesis/matrix.py`'s `AGENT_WEIGHTS`) — that's plain arithmetic over
  agent subtotals, not something DPO (a generation-preference method) can
  act on.

## Data Model

`PreferenceLog` (`server/modules/feedback/models.py`) gains two columns:

```python
agent_name: Mapped[str] = mapped_column(String(32), nullable=False)
criterion_id: Mapped[str] = mapped_column(String(32), nullable=False)
```

- `agent_name` is `"itso"` for every row created by this phase. The column
  is added now (not deferred) so Phase 2 doesn't require another
  migration.
- `criterion_id` matches ITSO's rubric criterion codes (e.g. `"itso-03"`).
- `edited_json` (existing JSON column) holds `{"score": int,
  "justification": str}` for `EDIT` rows. Unused for `ACCEPT`/`REJECT`.
- `action` stays `ACCEPT | REJECT | EDIT` (existing check constraint,
  unchanged).
- No new uniqueness constraint. A reviewer may submit multiple rows for
  the same `(evaluation_id, agent_name, criterion_id)` (e.g. revising
  their own edit); the export step takes the latest by `created_at`.

## Backend API

Replaces the empty `feedback` router scaffold with:

```
POST /feedback/{evaluation_id}/criteria/{criterion_id}
Body: {
  agent_name: "itso",
  action: "ACCEPT" | "REJECT" | "EDIT",
  score?: int,          # required when action == "EDIT"
  justification?: str,  # required when action == "EDIT"
  notes?: str            # optional, any action
}
```

- **Amended during manual testing** (2026-08-10): originally restricted to
  `UserRole.ADMIN` only, matching `GET /admin/preferences`'s gating. Manual
  testing showed this silently 403'd the faculty users who actually submit
  and would realistically review their own SLM evaluations. Access is now
  admin-or-owning-faculty: any authenticated user may act on an evaluation
  they submitted (`EvaluationJob.submitted_by`), and admins may act on any
  evaluation. A non-owner faculty request is masked as `404 Not Found`
  (not `403`) so it can't be used to probe which evaluation IDs exist —
  matching `evaluations.service._check_ownership_or_404`'s existing
  convention elsewhere in the app. Unauthenticated requests still get
  `401`.
  - This reopens the self-review conflict-of-interest question the
    original admin-only scoping was meant to avoid: nothing stops a
    faculty member from Accepting everything or Editing their own low
    scores upward on their own submission, which would bias any future
    DPO training data toward self-interested corrections rather than
    genuine QA judgment. Deliberately accepted for now — flagged here for
    whoever designs the eventual training pipeline to account for (e.g.
    weighting or filtering self-reviewed EDITs differently, or building a
    real reviewer role later).
- `EDIT` requires both `score` and `justification` — a reviewer cannot
  submit a corrected number with the AI's stale justification still
  attached, since that would produce an internally inconsistent DPO pair
  (score changed, reasoning unchanged).
- `ACCEPT`/`REJECT` ignore `score`/`justification` if present; they exist
  for the audit trail and reviewer-agreement visibility, not for DPO
  pairing.
- Each call inserts one `PreferenceLog` row (append-only).

`GET /admin/preferences` (existing, `admin/router.py`) is extended to
surface the new `agent_name`/`criterion_id` fields in
`PreferenceLogResponse` — no new endpoint, no behavior change to
pagination/filtering.

## Frontend

On the evaluation Scorecard/Report view, only the ITSO domain section
gains editing affordances; SME/Coordinator/GAD sections remain read-only
in this phase.

- Each ITSO criterion row shows the AI's score + justification (existing
  render path via criteria data) plus **Accept**, **Reject**, **Edit**
  actions.
- **Accept** — submits immediately (`action: "ACCEPT"`).
- **Reject** — submits immediately (`action: "REJECT"`), with an optional
  notes field.
- **Edit** — expands an inline form: score selector (0–4) and a
  justification textarea pre-filled with the AI's original text (so the
  reviewer edits rather than writes from scratch), then submits
  (`action: "EDIT"`).
- `useSubmitFeedback` (`client/src/features/evaluation/hooks/`) is
  repointed from the unused evaluation-level endpoint to the new
  criterion-scoped one.
- A small per-criterion badge indicates feedback already given this
  session, so reviewers don't lose track across a long scorecard.

## Export & Dataset Construction

A repo-local script (e.g. `server/scripts/export_dpo_pairs.py`) — reads
from the DB only, does not train anything:

1. Query `PreferenceLog` where `agent_name = "itso"` and
   `action = "EDIT"`, latest row per `(evaluation_id, criterion_id)`.
2. Reconstruct the exact prompt ITSO originally received for that
   evaluation/criterion via `itso/prompt.py`'s `build_prompt`, replayed
   against that evaluation's stored inputs (chunk_infos, rubric,
   reference context — via `AgentResult`/provenance). If the original
   inputs can't be reconstructed for a row, that row is logged and
   skipped, not silently dropped.
3. `chosen` = the reviewer's `{score, justification}`, serialized in the
   same JSON shape ITSO's prompt asks the model to return.
   `rejected` = the AI's original `{score, justification}` for that
   criterion.
4. Write one JSONL line per pair: `{"prompt": ..., "chosen": ...,
   "rejected": ...}`.

## Training & Deployment

Deliberately kept outside this repo's runtime:

- A standalone script/notebook (run manually, on a GPU machine) consumes
  the exported JSONL and runs a LoRA DPO fine-tune against the base ITSO
  model (whatever `LLM_MODEL_ITSO` currently resolves to).
- The resulting checkpoint is evaluated manually against a held-out slice
  of pairs (not used in training) plus a handful of real SLMs, comparing
  old-vs-new ITSO output against reviewer expectations.
- Promotion is a manual `LLM_MODEL_ITSO` env var change. Rollback is
  reverting that same env var — no data migration involved either way.
- No automatic or scheduled retraining. Whether there's "enough" EDIT
  volume to justify a training pass is a judgment call made when the
  export count is visible, not a hard-coded threshold — DPO on very few
  examples risks overfitting/degrading a small (2B-class) model's general
  behavior.

## Phase 2 (captured, not built now)

- **GAD**: needs a fact-correction UI (reviewer corrects extracted facts,
  not the score directly) and its own export logic pairing
  corrected-vs-original fact extractions. Deterministic banding then
  recomputes the score from corrected facts.
- **SME / Coordinator**: needs per-evaluation, per-criterion attribution
  of which path (engine vs. LLM fallback) produced a score, since only
  the LLM-fallback path is DPO-eligible. Corrections to engine-scored
  criteria need a separate, non-RL path (e.g. a backlog for tuning the
  engine's rules/thresholds by hand).
- Both reuse the `agent_name`/`criterion_id` columns added in this phase
  — no further `PreferenceLog` schema changes anticipated.
