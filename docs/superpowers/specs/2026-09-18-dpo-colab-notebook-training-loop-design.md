# DPO Colab Notebook Training Loop — Design

Date: 2026-09-18
Status: approved, pending implementation plan

## Problem

`docs/colab/dpo_training_template.ipynb` already has its fetch cell (download
the frozen `pairs.jsonl`/`provenance.jsonl`/`manifest.json` package via
`DOWNLOAD_URL`) and its push-back cell (zip a trained adapter directory and
`POST` it to `UPLOAD_URL`) built and tested as part of the DPO Colab training
handoff feature. Both were explicitly scoped as transport-only; the actual
LoRA/PEFT training loop in between was left as a `# TODO` placeholder, since
writing it was called out as a data-science decision, not a transport
decision.

That placeholder is now the actual blocker to producing a real adapter: all
four agents (SME, Coordinator, GAD, ITSO) are DPO-ready and exporting real
`pairs.jsonl` data, but there's nowhere for that data to go except a comment
saying "fill this in."

## Goals

1. Replace the `# TODO` cell with a real, runnable LoRA+DPO training loop
   that works inside Colab's free tier (T4/L4, ~16GB VRAM) against the
   `{prompt, chosen, rejected}` shape `export_dpo_package()` already produces.
2. Keep the notebook a single generic template, parameterized only by
   whatever `manifest.json` says (`agent_id`) — not one notebook per agent.
3. Give the admin a visible, honest signal about adapter quality before
   upload, without blocking the one-click "Run all" workflow the original
   design committed to.
4. Carry enough training provenance into the uploaded artifact that a human
   looking at `trained_adapters` later can tell what produced it.

## Non-goals (explicit)

- Wiring the trained adapter into live inference. This notebook produces a
  portable PEFT adapter and nothing more — the same non-goal the original
  Colab-handoff design already established.
- Reconciling the trained adapter's precision/quantization with the
  production serving model (`equiped-gemma3-4b-qat-q4`, a QAT/GGUF-style
  build). Merging the LoRA adapter into base weights and re-running the
  QAT/quantization build for serving is a separate, later, manual step —
  this notebook's output is a standard HF/PEFT adapter directory, not a
  serving-ready artifact.
- Building the rollout plan's step-3/step-5 machinery: a held-out test set
  that's untouched by training and compared against the base model, and
  automated regression detection. The in-notebook validation split added
  here (Goal 3) is a cheap training-time sanity check only, not a substitute
  for that later, more rigorous evaluation step.
- Automating hyperparameter search. Defaults are opinionated and
  Colab-free-tier-shaped, overridable by editing the cell, not tuned
  automatically.
- Any change to `export_dpo_package()`, the download/upload endpoints, or
  the `dpo_training_jobs`/`trained_adapters` tables. This design only fills
  in cells inside the existing notebook file.

## Architecture

Extends the existing 6-cell notebook to 9 cells. Cells 0–2 (intro, config,
fetch) and what is currently the last cell (push-back) are structurally
unchanged; the markdown+TODO training placeholder is replaced by five real
cells.

### Cell 0 — intro (existing, unchanged)

### Cell 1 — config (existing, unchanged)
`DOWNLOAD_URL`, `UPLOAD_URL`.

### Cell 2 — fetch (existing, unchanged)
Downloads and unzips the frozen package; produces `pairs` (list of
`{prompt, chosen, rejected}` dicts) and `manifest` (dict, including
`agent_id`, `model_name`, `pair_count`).

### Cell 3 (new) — dependency install
```
!pip install -q unsloth trl peft bitsandbytes datasets
```
Unsloth pulls compatible `transformers`/`accelerate`/`torch` versions
itself; no manual pinning in the cell beyond what Unsloth's installer
handles, since Colab's preinstalled CUDA/torch stack changes over time and
hardcoding versions here would go stale.

### Cell 4 (new) — data prep
- Build an HF `Dataset` from `pairs` with columns `prompt`, `chosen`,
  `rejected` — already the exact shape TRL's `DPOTrainer` expects, no
  reshaping needed.
- Split 90/10 into train/val via `Dataset.train_test_split(test_size=0.1,
  seed=42)`.
- **Guard:** if `len(pairs) < 20`, skip the split (train on 100%, no eval
  dataset) and print a warning that the pair count is too small for a
  meaningful held-out sanity check — an eval split of a handful of pairs is
  noise, not signal.

### Cell 5 (new) — model + LoRA setup
```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/gemma-3-4b-it",
    max_seq_length=2048,
    load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    lora_alpha=32,
    lora_dropout=0.0,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
)
```
`unsloth/gemma-3-4b-it` is Unsloth's pre-quantization-friendly mirror of
`google/gemma-3-4b-it` — chosen because it's the same base family already in
production (`equiped-gemma3-4b-qat-q4`), loaded 4-bit via bitsandbytes
(QLoRA) specifically because that fits Colab's free-tier T4/L4 VRAM budget
for a 4B model, unlike full fp16 training. Rank/alpha/target-modules are a
standard starting recipe for this model size, not a tuned result — the cell
comment says so and says they're safe to edit.

### Cell 6 (new) — DPOTrainer config + train
```python
from trl import DPOConfig, DPOTrainer

training_args = DPOConfig(
    output_dir="./trained_adapter",
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    learning_rate=5e-6,
    num_train_epochs=1,
    beta=0.1,
    eval_strategy="steps" if eval_dataset is not None else "no",
    eval_steps=20,
    logging_steps=5,
    bf16=True,
)
trainer = DPOTrainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,  # None if the small-dataset guard tripped
    processing_class=tokenizer,
)
trainer.train()
```
Batch size 1 + gradient accumulation 8 is a deliberately conservative
default for T4/L4 headroom; `num_train_epochs=1` matches the small,
frequently-growing correction-log dataset this project will realistically
have early on — more epochs is an easy edit once correction volume is
larger, not a default worth guessing at now.

### Cell 7 (new) — eval / sanity check (soft warning, no gating)
```python
if eval_dataset is not None:
    metrics = trainer.evaluate()
    print(f"eval_loss: {metrics['eval_loss']:.4f}")
    print(f"reward accuracy (chosen > rejected): {metrics.get('eval_rewards/accuracies', 'n/a')}")
    print(
        "NOTE: this is an in-run sanity check on a random 10% split of "
        "THIS training run's own data — it is not the rollout plan's "
        "held-out test set, and does not compare against the base model. "
        "A low accuracy here is a strong signal something went wrong; a "
        "high accuracy is not by itself a green light to deploy."
    )
else:
    print("Skipped eval (too few pairs for a meaningful held-out split).")
```
No `raise`, no blocking: per project decision, "Run all" always reaches the
upload cell — the printed metrics are for the admin to read, not for the
notebook to act on.

### Cell 8 (new) — provenance manifest
Before zipping (replaces the old `ADAPTER_DIR = "./trained_adapter"`
placeholder cell — Unsloth/TRL already save there via `output_dir` above):
```python
import json

training_manifest = {
    "source_job_manifest": manifest,
    "base_model": "unsloth/gemma-3-4b-it",
    "lora_config": {"r": 16, "lora_alpha": 32, "target_modules": [...]},
    "training_args": {
        "learning_rate": 5e-6, "num_train_epochs": 1, "beta": 0.1,
        "per_device_train_batch_size": 1, "gradient_accumulation_steps": 8,
    },
    "pair_count": len(pairs),
    "eval_metrics": metrics if eval_dataset is not None else None,
}
with open(f"{ADAPTER_DIR}/training_manifest.json", "w") as f:
    json.dump(training_manifest, f, indent=2)
```
Written alongside the adapter's own `adapter_config.json`/weight files, so
it rides inside the same zip with no changes needed to the upload endpoint
(which validates only the outer `.zip` extension and size, per
`training_data/adapters.py`) or to `TrainedAdapter`'s schema.

### Cell 9 — push-back (existing, unchanged apart from `ADAPTER_DIR` now
being populated by real training output instead of a placeholder)

## Data flow

```
Cell 2 fetch → pairs (list[{prompt, chosen, rejected}]), manifest (dict)
Cell 4 → train_dataset, eval_dataset (or None if <20 pairs)
Cell 5 → model, tokenizer (4-bit QLoRA-ready, unsloth/gemma-3-4b-it base)
Cell 6 → trainer.train() writes adapter files to ./trained_adapter
Cell 7 → metrics (printed only, never gates execution)
Cell 8 → ./trained_adapter/training_manifest.json (provenance, bundled)
Cell 9 → zip ./trained_adapter (adapter files + training_manifest.json)
        → POST UPLOAD_URL (unchanged endpoint/contract)
```

## Error handling

- Small-dataset guard (Cell 4): skips the eval split rather than producing
  a meaningless one; does not fail the run.
- No new failure modes introduced at the transport boundary — Cells 3–8 are
  entirely local to the Colab runtime; if they raise (OOM, dependency
  conflict, bad HF auth), the notebook simply stops before reaching the
  push-back cell, which is the existing, already-safe failure behavior (no
  partial/corrupt upload, and the job's upload token stays unused so a
  fresh job isn't even needed — the same `upload_url` still works on retry
  within its token's 7-day window).
- No hard gate on eval metrics (project decision) — Cell 7's warning is
  informational only.

## Testing

- No CI coverage possible — this is a GPU-dependent, interactive Colab
  notebook, external to the test suite by nature (same reasoning the
  original Colab-handoff design already accepted for its own cells).
- Validated by hand once, end-to-end, against a real exported package
  (small `pair_count` is fine — validates the guard path too) before
  considering this done.
- No backend/frontend code changes in this design, so no pytest/vitest
  surface is touched.

## Open questions for the implementation plan

- Exact default LoRA rank/alpha and DPO hyperparameters above are a
  starting recipe, not validated against this project's actual data yet —
  flag in the notebook's markdown that these are defaults to revisit once
  real correction volume exists, not tuned results.
- Unsloth's Gemma 3 support and API surface (`FastLanguageModel`,
  `get_peft_model` argument names) should be checked against Unsloth's
  current release at implementation time, since this is a fast-moving
  third-party library and the design was written from current knowledge,
  not a pinned version.
