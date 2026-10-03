# Training summary (preference margin) for adapter versions - design

Date: 2026-10-03. Status: approved by the user on 2026-10-03.

## Why

The DPO training notebook computes `rewards/margins`, `rewards/accuracies`, loss and
the held-out equivalents, but none of it is saved. The Colab log is the only copy, and
the notebook's own GGUF cleanup cell (`globals().pop("trainer", ...)`) deletes the
trainer, and with it `trainer.state.log_history`, before the user can read it. The
SME v7 run lost its margin this way. We want every new adapter version to carry a
small training summary that an admin can see next to the version.

The summary is **training evidence** ("the model learned the preference on the
training pairs"). It is not behavior evidence; the Base-vs-adapter benchmark in Model
Validation remains that. The UI says so.

## Scope

In: notebook captures the summary and writes it into the manifest it already uploads;
backend validates and stores it with the adapter; API returns it; admin adapter
Details panel shows it. Out: charts, comparison across versions, backfilling v1-v7.

Versions trained before this change show "Not recorded".

## 1. Summary shape

Stored under `training_manifest.json` -> `training_summary`, and in the database as a
JSON column. All numbers are finite floats; counts are integers.

```json
{
  "version": 1,
  "steps": 12,
  "epochs": 3,
  "first": {"step": 1, "loss": 0.69, "margin": 0.0, "accuracy": 0.5,
            "chosen": 0.0, "rejected": 0.0},
  "last":  {"step": 12, "loss": 0.21, "margin": 1.4, "accuracy": 1.0,
            "chosen": 0.3, "rejected": -1.1},
  "heldout": {"pair_count": 7, "loss": 0.4, "margin": 0.9, "accuracy": 0.86}
}
```

`first`/`last` are the first and last logged training rows. `heldout` comes from
`trainer.evaluate()` and is `null` when nothing was held out or the evaluation failed.
Every field except `version` may be missing; the UI shows only what is present.

## 2. Notebook

- In the training config: `logging_steps=1` (so the last logged row is the real final
  step) and `per_device_eval_batch_size=1` (the default of 8 caused an out-of-memory
  at the evaluation step on a T4).
- A new code cell **directly after the training cell** builds `TRAINING_SUMMARY` from
  `trainer.state.log_history` with a small pure function `build_training_summary(
  log_history, num_train_epochs, heldout_metrics, heldout_pair_count)`, prints a
  readable table (step, loss, margin, accuracy), and never raises: on any problem it
  sets `TRAINING_SUMMARY = None` and prints why.
- The existing evaluation cell passes its `metrics` into the summary
  (`eval_loss`, `eval_rewards/margins`, `eval_rewards/accuracies`).
- The manifest cell adds `"training_summary": TRAINING_SUMMARY` to
  `training_manifest`. This runs before the GGUF cleanup cell, so the data is still
  alive.
- The existing out-of-memory rescue cell (user's latest notebook) stays as is.

## 3. Backend

- `adapter_artifacts.py`: `_validate_archive` already parses `training_manifest.json`.
  It additionally returns `extract_training_summary(manifest)`, a pure function that
  keeps only the known keys, requires finite numbers within sane bounds, and returns
  `None` for anything malformed. **A missing or invalid summary never rejects the
  upload**: the upload link is single-use and the training run is long. It logs a
  warning and stores nothing.
- `StagedAdapterArtifact` gains `training_summary: dict | None`; `store_adapter_upload`
  writes it to the new column.
- Model `TrainedAdapter.training_summary` (`sa.JSON`, nullable). One additive Alembic
  migration; existing rows stay `NULL`.
- Schema: `TrainedAdapterResponse.training_summary: TrainingSummary | None = None`
  (a typed Pydantic model mirroring section 1). No other response changes.

## 4. Admin UI

In `AdapterRow` Details (the expandable row):

- **Top:** "Training summary" with margin, accuracy, loss and steps (last), the
  held-out numbers when present, and one line: "Measured on the training pairs. It
  shows the model learned the preference, not how it scores new documents."
- **Below, collapsed:** "Technical details" with Source run, File SHA-256 and Adapter
  ID (today's three rows). Filename and Uploaded stay visible.
- No summary: "Not recorded".

## 5. Testing

- Backend: `extract_training_summary` (valid, partial, NaN/inf, wrong types, oversized);
  upload with a valid summary stores it; upload with a bad or missing summary still
  succeeds with `NULL`; list endpoint returns the field.
- Frontend: Details shows the numbers, the "Not recorded" state, and the collapsed
  technical section (extend `AdapterRow.test.tsx`).
- Notebook: execute `build_training_summary` against a fake `log_history`
  (extend `server/tests/training_data/test_dpo_colab_contract.py` /
  `training/tests`), including empty history and missing keys.
- Existing checks that the manifest still matches `source_job_manifest` must keep
  passing; the new key does not affect that comparison.

## Decision (approved 2026-10-03)

Apply this feature to the tracked `docs/colab/dpo_training_template.ipynb` and bring
over only the safe memory fixes from the user's `latest_dpo_training_template.ipynb`:
the `expandable_segments` environment variable, `use_logits_to_keep=True` and
`per_device_eval_batch_size=1`. The experiment-specific values (`MAX_SEQ_LENGTH=5888`,
`max_prompt_length=4352`, `num_train_epochs=3`) and the user's out-of-memory rescue
cell stay in the user's own untracked file. The tracked template's defaults are not
changed otherwise.
