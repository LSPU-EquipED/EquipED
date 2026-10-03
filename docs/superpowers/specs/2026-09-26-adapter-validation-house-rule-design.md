# Adapter validation: house-rule edits on real SME evaluations — Design

Date: 2026-09-26 (updated 2026-09-30)
Status: approved by the user 2026-09-30, with the updates below for per-agent
adapter versions and the publish safeguard (option A: a written rule only).
Supersedes: Section 5 ("Synthetic self-test dataset") of the 2026-09-23
adapter-compare design. Sections 1-4 of that design are already shipped
(PRs #343 and #349).

## Problem

The trained SME adapter has never been shown to change the model's behavior.
The only training data available is `seed_synthetic_dpo_pairs.py`'s default
mode: 25 fake evaluations, each built from one stub excerpt and one criterion,
with unrelated corrections scattered across about 10 criteria. An adapter
trained on it showed nothing on held-out pairs (2026-09-22: 0 wins, 1 loss,
4 ties, inconclusive). Two flaws stand in the way:

1. **No learnable signal.** A small LoRA needs one repeated, consistent
   correction to pick anything up.
2. **Off-distribution prompts.** The stub excerpt is about 1.4k characters and
   holds a single criterion. A real SME call carries a group of criteria plus
   downsampled source text of up to 15,000 characters, so nothing trained on the
   stub resembles what the model sees at inference.

## What this proves, and what it does not

**Claim this design can support:** the adapter **learned the taught rule** —
on real SLMs its scores shift the way the rule says, the shift carries over to
SLMs it never saw, and criteria the rule did not touch stay put.

**Claim it cannot support:** that the adapter is *better* at scoring. The rule
is invented; being close to it says nothing about being close to a human
reviewer. A "better than base" claim needs human reference scores (see
Follow-up).

## Facts (verified 2026-09-26)

- SME criteria use the `llm_rubric_guidance` strategy: the LLM outputs a 1-4
  score and reasoning per criterion; code only validates it
  (`normalize_llm_guidance_score`). A reviewer "edit" replaces the score
  and/or justification of one criterion.
- `project_criterion_measurements_v1` builds a pair from one stored generation:
  prompt = the generation's `prompt_text`, rejected = its `response_text`,
  chosen = the same response with each corrected criterion replaced. A
  correction with a score and **no justification** leaves the model's own
  reasoning untouched; a generation with no real change is skipped
  (`no_real_change`).
- `get_effective_criterion_corrections_batch` keeps only the **latest** log per
  `(evaluation, agent, criterion)`. A later synthetic row would therefore
  override an earlier real reviewer decision, and deleting the synthetic row
  restores the earlier state.
- The Colab notebook trains with `MAX_SEQ_LENGTH = 2048`,
  `max_prompt_length = 1536`, `learning_rate = 5e-6`, `num_train_epochs = 1`,
  `beta = 0.1`, and already holds out **whole evaluations** from training.
- `SME_TOTAL_PROMPT_BUDGET_CHARS` has a **hard minimum of 15000**
  (`core/config.py`), so real prompts cannot be shrunk to fit the notebook.
- `training/evaluate_adapter.py` compares base and adapter on held-out pairs
  (wins/losses/ties, valid-JSON rate, sign test) and needs at least 20
  decisive pairs (`--min-decisive`) before it returns anything but
  "inconclusive".
- The faculty portal has an SME workspace (`targetAgent` defaults to `sme`), so
  SME-only evaluations can be run there.
- **Added 2026-09-30 (branch `feat/per-agent-adapter-publishing`, PR pending):**
  - Each agent can have several adapter versions on the model server. Files are
    named `<agent>-v<version>.gguf` (for example `sme-v6.gguf`), loaded with
    `--lora-scaled <full path>:0.0`, and the Training Data page shows each
    version as Loaded / Not loaded / Unknown.
  - Model Validation runs ONE agent at a time and offers Model = Base,
    Published, or a specific loaded version (no more "Base vs Adapter" or
    "All agents").
  - An admin can **publish** one version per agent; the published version is
    then used for real faculty scoring. Nothing in the app marks an adapter as
    an experiment (see section 7).
  - The Colab training notebook is Run-all clean on Colab's current Python 3.13
    (new pinned libraries, guards that fail fast, automatic
    `<agent>-v<version>.gguf` naming, converter output visible). The notebook's
    `num_train_epochs` is 1 in cell 7; raising it is a manual edit in Colab.
  - `PUBLIC_BASE_URL` is a real setting, so training-job links work through a
    tunnel.
- The existing seed script already contains the safety rails to reuse:
  environment check, database-fingerprint allowlist, confirmation keywords,
  a dedicated synthetic user, and run-id tagging.

## Goals

1. Turn a set of **real** SME evaluations into a DPO dataset that teaches one
   consistent, visible rule, without exporter, training-flow or notebook-logic
   changes.
2. Keep prompts and "rejected" answers real, so training matches inference.
3. Make the result checkable at two levels: a training SLM (rule absorbed) and
   held-out SLMs (rule generalizes), with untouched criteria as controls.
4. Be safe on the shared development database: nothing is written without an
   explicit confirmation, only explicitly listed evaluations are touched,
   real reviewer decisions are never overridden, and everything is removable.

## Non-goals

- Any claim that the adapter is better. (Follow-up.)
- A new UI, or any change to the exporter, projectors, training-job flow or
  notebook cell logic.
- Triggering evaluations from the script: the admin runs the evaluations
  manually.
- An external "teacher" model. SLM content stays on the local model
  (data residency).
- Changing how the default seed mode (`seed_synthetic_dpo_pairs.py`) works.
- Rewriting the model's reasoning text.
- Enforcing in the app that the experiment adapter is never published. This
  design only states the rule (section 7). A label on the adapter or a hard
  "cannot be published" flag are possible follow-ups if such experiments
  become routine.

## Design

### 1. Workflow

| Step | Who | What |
|---|---|---|
| 1 | Admin | Run SME evaluations on real SLMs (manually). Do not edit, accept or reject any score in the review UI. |
| 2 | Script | Read those evaluations' stored generations and print a report (dry run, the default). |
| 3 | Admin | Read the report: pair count, prompt lengths, skips. Decide notebook limits and whether to scale up. |
| 4 | Script | Write the corrections (explicit confirmation flags). |
| 5 | Admin | Start Training Job, run the Colab notebook (Run all; raise epochs first if pairs < 100). It produces `sme-v<n>.gguf`; the host owner loads it at scale 0.0 and the Training Data page shows it as Loaded. **Never publish it.** |
| 6 | Admin | Validate (section 6). |
| 7 | Script | Clean up the run's corrections. |

### 2. The house rule

- **Rule:** for each **edited criterion**, correct a generation's score `s` to
  `min(4, s + 1)`. A score already at 4 is left alone.
- **Edited vs control criteria:** the edited set defaults to the odd-numbered
  criteria `OP-01, OP-03, OP-05, A-01, A-03, A-05`; every other SME criterion
  in the evaluation is a **control** and is never corrected. Edited and control
  criteria appear in the same prompt and answer, so the adapter has to learn a
  criterion-specific rule, not "score higher everywhere". The set is a
  command-line option.
- **Score-only edits:** the correction row carries `{"score": N}` and no
  justification, so the model's own reasoning stays in both the chosen and
  rejected answers and the only difference is the score.
- **Only score-shaped criteria:** a criterion is edited only if its measurement
  in the stored response is score-shaped and its strategy in the evaluation's
  own snapshot is `llm_rubric_guidance`.

### 3. New script

`apps/server/scripts/seed_house_rule_edits.py`, a separate script that imports
the safety helpers from `seed_synthetic_dpo_pairs.py` instead of copying them
(`validate_environment`, `validate_database_target`,
`compute_target_fingerprint`, the synthetic-user helper).

| Option | Meaning |
|---|---|
| `--train-evaluations IDS` / `--train-evaluations-file FILE` | Evaluations to correct (comma-separated ids, or one id per line). |
| `--reference-evaluations IDS` (or `-file`) | Evaluations to **report on only** (the held-out SLMs); never written. |
| `--edit-criteria CODES` | Override the default edited set. |
| `--report-csv PATH` | Write the expected-scores report (section 4). |
| `--verify-export` | Run the exporter's dry run and print the resulting pair count. |
| `--confirm SEED --confirm-target T` | Required to write. Without them the script is a **dry run**. |
| `--cleanup --run-id ID --confirm CLEANUP --confirm-target T` | Remove a run's corrections. |

Each written row is a `PreferenceLog` with `action = "EDIT"`,
`agent_name = "sme"`, the criterion code, `edited_json = {"score": N}`, the
generation and evaluation ids, the dedicated synthetic user, and
`notes = "house-rule-seed:<run-id>"`.

**Eligibility, fail closed.** The whole run aborts, with no partial writes and
one transaction, if any listed evaluation is missing, is not `COMPLETED`, has
no SME generation with `envelope_status = "ok"` and contract
`criterion_measurements.v1`, or appears in both lists. Individual criteria are
skipped, and counted by reason, when the score is already 4, the measurement is
not score-shaped, or **any** `PreferenceLog` row already exists for that
`(evaluation, sme, criterion)` (so a real reviewer decision is never
overridden).

**Cleanup.** Deletes only rows whose `notes` equal the run's tag, whose user is
the synthetic user, and whose action is `EDIT`; aborts if any matching row is
not for an SME criterion. Because the latest log per criterion wins, this
restores the earlier effective state. The real evaluations, generations and
documents are never modified.

### 4. Report

Printed by every run, dry or not:

- Per evaluation: document title, generations, corrections planned or written,
  skips by reason.
- Totals and the **expected pair count** (from the exporter's dry run when
  `--verify-export` is given).
- **Prompt lengths:** characters and estimated tokens (characters / 4) per
  generation, with the number above the notebook's 1536-token prompt limit
  (about 6,100 characters).
- **Expected-scores table** (`--report-csv`): one row per evaluation and
  criterion with its role (edited or control), the base score of each run, the
  base reference (mean of the runs, rounded), and the rule-applied expected
  score (`min(4, reference + 1)` for edited criteria, the reference for
  controls). This is what the admin types into Model Validation as expected
  scores in step 6, for training and reference (held-out) SLMs alike.

### 5. Prompt length

Real prompts are about 4,000 tokens; the notebook's prompt limit is 1,536. The
prompt budget cannot be lowered (minimum 15,000 characters), so the fix is on
the training side. The step 3 report decides:

- If most prompts are within the limit, train as-is.
- If more than about 20% are over it, raise `MAX_SEQ_LENGTH` and
  `max_prompt_length` in the notebook (values chosen from the report), and
  confirm with a short T4 smoke run that memory holds before the full run.
- Very long SLMs may be dropped from the set if the limit cannot be raised
  enough.

This is a value change inside the notebook, not a new cell, so the tests that
pin cells by index are unaffected.

### 6. Data volume, pilot and validation

**Volume.** 10 real SLMs: 8 for training, 2 held out (never corrected). About
2-3 pairs per evaluation run (one per grouped SME call; confirmed by the
pilot). Roughly 100 pairs needs about 4 runs of each training SLM (about 32
runs at a few minutes each). Held-out SLMs get 2-3 plain base runs each, to
fix their base reference. If pairs stay under 100, train 2-3 epochs.

**Pilot first.** 3 SLMs x 2 runs (about 6 evaluations). Run the script as a dry
run; check pair yield, prompt lengths and skips before spending hours.

**Validation** (after the host owner loads the adapter at scale 0.0), in
order:

1. The Training Data page shows the new version as **Loaded** (and
   `GET /lora-adapters` lists it at scale 0.0).
2. `smoke_test_lora_serving.py`: valid replies with the adapter off and on,
   at least one differing answer.
3. `evaluate_adapter.py` on the adapter zip's held-out pairs: verdict,
   wins/losses/ties, valid-JSON rate.
4. Model Validation, Target = SME, **Model = Base, then Model = the new
   version** (for example v6), each 2-3 times, on a **training SLM** and on a
   **held-out SLM**, entering the report's rule-applied expected scores. This
   step needs the per-agent adapter branch merged (or run locally).

**Acceptance for this experiment** (starting thresholds, adjustable after the
pilot):

- On edited criteria the adapter's mean score is at least 0.5 above the base's,
  on the training SLM **and** on a held-out SLM.
- On control criteria the mean absolute change is at most 0.25.
- The adapter's valid-JSON rate is no lower than the base's.

**Reading failures.** No change: adapter not applied (retry the tool with
`--scale-mode global`) or undertrained (more pairs or epochs). Invalid JSON or
worse scores: overtrained (fewer epochs or a lower learning rate). Controls
shift too: it learned "score higher everywhere"; retrain with more control
criteria.

### 7. Side effects and risks

- The corrections live in the shared development database and will be counted
  by the Training Data readiness card as ordinary pairs. The run-id tag makes
  them findable; a real-versus-synthetic count is a separate follow-up.
- Only the evaluations the admin lists are touched. Run them under a test
  account so they are identifiable.
- The adapter will be trained on an invented rule. It must not be used for real
  faculty evaluations; it is a validation artifact.
- **Publish safeguard (option A, a written rule).** Now that admins can publish
  a version for real scoring, publishing this adapter would make faculty SME
  scores follow the invented rule. The safeguard is procedural: the script's
  final report, the runbook and the training job all state that SME v<n> is a
  test adapter that is never published. If it is published by mistake, the
  damage is bounded: scores are advisory, CID reviewers hold final authority,
  every evaluation records the adapter applied (`adapter_resolution`), and
  Unpublish is one click. A label (recorded on the adapter) or a hard "cannot
  be published" flag are follow-ups if experiments become routine.
- **Export pollution.** The training-data exporter reads ALL corrections for an
  agent. While this run's corrections exist, any other SME training job would
  include them. Do not start another SME training job between the write and the
  cleanup, and run the cleanup as soon as validation is done.

## Testing

Offline, SQLite, following the existing seed-script tests (real snapshots via
`resolve_or_reuse_evaluation_snapshots`; a completed SME evaluation with a stored
generation per test):

- The rule: `s -> min(4, s + 1)`; a score of 4 is skipped; only edited-set
  criteria change; controls never do.
- Eligibility: a missing, non-`COMPLETED` or generation-less evaluation aborts
  with no rows written; a criterion with an existing real log is skipped and
  counted, and the real log is untouched.
- A written row has the expected shape and tag, and the exporter turns it into a
  pair whose chosen answer differs from the rejected one only in the edited
  scores (reasoning identical).
- Dry run writes nothing; writing without both confirmation flags is refused;
  the environment and fingerprint guards refuse an unsafe target.
- Cleanup removes exactly the tagged rows and restores the earlier effective
  corrections; it refuses rows outside the SME scope.
- Report: totals, skip reasons, prompt-length flags and the CSV's expected
  scores.

## Rollout

1. Build the script with tests (dry run and report first).
2. Pilot: 3 SLMs x 2 runs; read the report; decide notebook limits.
3. Full data collection (10 SLMs), write the corrections, verify the pair
   count.
4. Train and load the adapter; validate.
5. Clean up the run.

## Follow-up: a real "better" claim

Use the admin's human expected scores (Model Validation) as the reference.
Train on corrections derived from some benchmarked SLMs, test on others, and
compare base and adapter error with a paired sign test across at least 10 SLMs.
Only that experiment can say the adapter is better; this design only shows it
learned what it was taught.

Related: `[[training-data-readiness-slice1]]`,
`[[model-validation-variant-dropdown-in-progress]]`,
`[[adapter-evaluation-tool]]`.
