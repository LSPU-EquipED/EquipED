# Adapter Evaluation Tool ("is this adapter better?") — Design

Date: 2026-09-19
Status: approved 2026-09-19

## Problem

The DPO pipeline can now train an adapter (Colab), store it, convert it to a
GGUF LoRA and serve it on the host's llama.cpp server, and prove the server
still returns valid SME JSON with it (see
`2026-09-19-adapter-gguf-lora-serving-design.md`). Nothing can tell us whether
an adapter is actually **better** than the plain model. Training numbers only
show the adapter fitting the pairs it studied. This is rollout plan step 5 and
the gate before an adapter goes anywhere near production.

Two things are missing:

1. **A real held-out set.** The training notebook holds out 10% of pairs at
   random **by pair** (`train_test_split(test_size=0.1, seed=42)`, cell 5), so
   two pairs from the same evaluation can land on both sides, and the held-out
   set is discarded after training.
2. **A comparison tool** that runs the adapter and the plain model over that
   held-out set and reports a verdict.

## Facts (verified 2026-09-19)

- Each exported pair is `{prompt, chosen, rejected}` (`pairs.jsonl`); the
  positionally aligned `provenance.jsonl` carries `pair_id`, `evaluation_id`,
  `document_id`, `agent_id`, and more. The notebook's cell 2 already validates
  that alignment.
- For the `criterion_measurements.v1` contract (SME, Coordinator), `rejected`
  is the model's original JSON reply and `chosen` is the same reply with the
  reviewer's corrected score/reasoning for the edited criteria.
- The backend accepts extra files inside an uploaded adapter zip: it requires
  only `adapter_config.json` and `training_manifest.json` at the root, checks
  the manifest's `source_job_manifest`, and enforces member-count and size
  limits (`apps/server/modules/training_data/adapter_artifacts.py`).
- The served stack: llama.cpp build 10430, plain `gemma-3-4b-it-q4_0.gguf`,
  alias `gemma-3-4b-it`, API key required, behind a Cloudflare tunnel that
  rejects Python's default User-Agent. An adapter is loaded at scale 0.0 with
  `--lora-scaled <file>:0.0` and switched on per request with
  `"lora": [{"id": 0, "scale": 1.0}]`.
- `training/smoke_test_lora_serving.py` already has the server client: adapter
  discovery, per-request and global scale modes with reset, the custom
  User-Agent, key handling, and reply validation (`validate_sme_reply`). It
  lives on branch `feat/gguf-lora-adapter-serving`; this design builds on it.
- Only synthetic data exists today: 25 fake SME pairs, frozen in the database
  as the dataset of the job that produced the stored adapter.

## Goals

1. Hold out whole evaluations at training time, and ship that held-out set
   inside the adapter zip so an adapter always carries its own exam.
2. Compare adapter vs plain model on the held-out set, on the exact served
   artifact (Q4_0 model + GGUF LoRA), and produce a verdict: better, worse, or
   inconclusive, with the reasons.
3. Say plainly what the verdict does and does not mean, and never call a result
   "better" on too little evidence.

## Non-goals

- Any change under `apps/` (no exporter, database, endpoint or admin UI change,
  no storing reports against `TrainedAdapter`).
- Likelihood-based scoring in Colab. The served-model measurement was chosen;
  a likelihood check can be added later as a second signal.
- Checking for regressions on cases reviewers **accepted** (the exporter only
  exports edited cases). The report states this limit.
- ITSO (`itso_scores.v1`) and GAD (`gad_scores.v1`) reply shapes. Version 1
  supports `criterion_measurements` (SME, Coordinator) only.
- Automatic promotion or any change to what the server serves.
- Judging quality with the current synthetic data; the mechanics are validated,
  the verdict is not meaningful until real corrections exist.

## Design

Four parts: a change to the training notebook (1), the evaluation script (2)
with its verdict rule (3) and report (4), and a short how-to (5).

### 1. Training notebook change — `docs/colab/dpo_training_template.ipynb`

Replace cell 5's random by-pair split with a **grouped split**:

- Group pairs by `evaluation_id` (from the provenance records the notebook
  already validated). Order the distinct ids by
  `sha256(f"{seed}:{evaluation_id}")` (seed 42) and take the first
  `ceil(20% of the groups)` as held-out (integer arithmetic, so no float
  rounding surprises): at least one group, and never all of them. A single
  evaluation cannot be split, so nothing is held out then. The rest is
  training. Deterministic, no randomness library needed.
- Keep the existing guard: with fewer than 20 pairs, hold nothing out (train on
  all, no held-out set) and print a warning that the adapter cannot be
  evaluated.
- `eval_dataset` for `DPOTrainer` and the cell 8 sanity check becomes the
  held-out set, so there is one held-out concept, not two.
- Write `heldout_pairs.jsonl` into the adapter output directory before zipping
  (cell 9). One JSON object per line:
  `{"pair_id", "evaluation_id", "prompt", "chosen", "rejected"}`.
- Record in `training_manifest.json` a `heldout` object:
  `{"method": "group_by_evaluation_id", "seed": 42, "fraction": 0.2,
  "pair_count", "evaluation_count", "sha256"}` (sha256 of the file), or
  `null` when nothing was held out.
- Cell 10's output validation and the adapter zip must accept the extra file.
  The offline contract tests that pin the notebook
  (`apps/server/tests/training_data/test_dpo_colab_contract.py`) are updated to
  match; no other backend file changes.

### 2. Evaluation tool — `training/evaluate_adapter.py`

Stdlib-only command-line script, runnable from any machine that can reach the
server. It imports the server client and reply validation from
`smoke_test_lora_serving.py` (same directory) instead of duplicating them.

Inputs:

- `--adapter-zip PATH`, or `--heldout PATH` for a bare `heldout_pairs.jsonl`.
  From a zip it reads `heldout_pairs.jsonl` and verifies its sha256 against
  `training_manifest.json`; a missing or `null` `heldout` is reported as "this
  adapter has no held-out set" and the run stops.
- Server options as in the smoke test: `--base-url` (or `LLM_API_BASE`),
  `--api-key` (or `LLM_API_KEY`), `--model` (or `LLM_MODEL_NAME`),
  `--adapter-id`, `--scale-mode {request,global}`, `--max-tokens`, `--timeout`.
- Evaluation options: `--limit N`, `--min-decisive` (default 20), `--alpha`
  (default 0.05), `--report-json PATH`.

Per held-out pair:

1. Parse `chosen` and `rejected` as `criterion_measurements` replies. The
   **answer key** is every `criterion_id` present in both with integer scores
   that differ; `gold[id]` is the score in `chosen`. A pair with no such
   criterion is "not scoreable" and is counted and skipped.
2. Send the pair's `prompt` to the server with the adapter off (scale 0.0) and
   again with it on (scale 1.0), temperature 0.
3. For each reply, validate it (`validate_sme_reply`) and read the scores of the
   answer-key criteria. A criterion the reply lacks counts as the worst
   possible error (`MAX_SCORE - MIN_SCORE` = 3). An invalid reply is counted
   as invalid and every answer-key criterion gets that worst error.
4. The pair's error for a model is the mean `|model score - gold score|` over
   the answer-key criteria. Adapter **wins** if its error is lower, **loses** if
   higher, **ties** otherwise.

All requests for the off pass run first, then the on pass, so global scale mode
switches once (same as the smoke test), with the same reset to 0.0 afterwards.

### 3. Verdict rule

In order:

1. `decisive = wins + losses`. If `decisive < --min-decisive`: **inconclusive**,
   reason "too few decisive pairs (N < M)".
2. Exact two-sided sign test on wins vs losses (ties excluded): `p =
   min(1, 2 × P(X <= min(wins, losses)))` with `X ~ Binomial(decisive, 0.5)`,
   computed with `math.comb`.
3. **better** if `wins > losses` and `p < --alpha`; **worse** if `losses >
   wins` and `p < --alpha`; otherwise **inconclusive**.
4. Safety cap: if the adapter's valid-JSON rate is lower than the plain
   model's, a would-be "better" becomes **inconclusive** with the reason
   "adapter returns invalid JSON more often"; "worse" stays "worse".

### 4. Report

A readable summary on stdout and, with `--report-json`, a JSON file:

- `verdict` and `reasons`
- `pairs`: held-out total, scoreable, skipped, wins, losses, ties
- `mean_abs_error`: base and adapter
- `valid_json_rate`: base and adapter
- `sign_test_p`, `parameters` (min-decisive, alpha, scale mode, model alias)
- `heldout`: source, pair count, whether the sha256 was verified
- `adapter`: zip sha256 when `--adapter-zip` is used
- `per_pair`: `pair_id`, gold, base scores, adapter scores, outcome (never the
  prompt or the API key)

The readable summary always ends with the two limits: the held-out pairs are
only cases reviewers **changed**, so this measures fixing known mistakes, not
harm to approved cases; and with few pairs a verdict is weak evidence.

The exit code is 0 for better, 1 for worse or inconclusive, 2 when the run
could not happen (server unreachable, no adapter loaded, no held-out set), so
it can gate a script.

### 5. How-to — `training/evaluating-an-adapter.md`

A short guide: train (new notebook), convert and load the adapter (existing
runbook), run `evaluate_adapter.py`, read the report. Notes that each new
adapter must be converted and loaded by the host before it can be evaluated.

## Data flow

```
export package (pairs + provenance) -> Colab: grouped split by evaluation_id
  -> train on the rest -> adapter zip { adapter files, training_manifest.json
     (with heldout{...}), heldout_pairs.jsonl } -> stored by the backend
  -> convert to GGUF LoRA -> host loads it at scale 0.0
  -> evaluate_adapter.py: for each held-out prompt, adapter off vs on
  -> report + verdict
```

## Error handling and risks

- **Small data.** Below 20 pairs nothing is held out; below `--min-decisive`
  decisive pairs the verdict is inconclusive. The current synthetic data can
  only validate the mechanics.
- **Per-request `lora` ignored:** the same `--scale-mode global` fallback and
  reset as the smoke test. Off and on replies that are byte-identical for every
  pair are reported as a warning ("the adapter may not be applied").
- **Selection bias:** every held-out pair is a case the base model got wrong,
  by construction, so the base starts near its worst; a win here means "fixes
  known mistakes", not "better overall".
- **Held-out leakage:** the split is by `evaluation_id`; the manifest records
  it and its hash so a later run can check the file is the one training left
  out.
- **Server availability:** needs the host's server; each request is a real
  inference call and briefly shares the GPU with live traffic, so runs are
  sized with `--limit`.
- **Editing a merged notebook:** the contract tests pin it; they are part of the
  change, not skipped.

## Testing

- **Offline (no GPU, no server):** unit tests for gold extraction, error and
  win/loss/tie logic, the sign test against known values, verdict rules in
  each branch (too few, better, worse, inconclusive, invalid-JSON cap),
  report shape, zip/`heldout` sha256 verification, and exit codes. The CLI is
  tested end to end against a fake local llama-server, like the smoke test.
  The grouped-split logic is tested by extracting its function from the
  notebook cell, as the conversion notebook's helpers are.
- **Notebook:** updated contract tests in
  `apps/server/tests/training_data/test_dpo_colab_contract.py`; one real Colab
  run of the changed notebook, recorded in the plan (same standard as before).
- **Mechanics against the live server:** the 25 synthetic pairs frozen in the
  database as the dataset of the job that produced the stored adapter are
  dumped to a temporary `heldout_pairs.jsonl` and run through the tool. They
  were used in training, so this proves the plumbing only and says nothing
  about quality.

## Follow-ups (not in this spec)

- A second signal: likelihood preference in Colab.
- Exporting accepted (unedited) cases so regressions can be measured.
- ITSO and GAD reply shapes.
- Storing the report against the `TrainedAdapter` row and showing it in the
  admin panel.
- Gating an automatic promotion step on the verdict (currently strictly
  manual).

## Decisions made while planning

- `heldout_pairs.jsonl` is written and hashed at the top of cell 9, right before
  the `training_manifest` dictionary is built, so the manifest can carry the
  `heldout` block.
- `evaluate_adapter.py` imports the client and reply validation from
  `smoke_test_lora_serving.py` directly (`import smoke_test_lora_serving`); the
  import works both when the script is run from anywhere (Python puts the
  script's own folder first on the path) and from the tests.
