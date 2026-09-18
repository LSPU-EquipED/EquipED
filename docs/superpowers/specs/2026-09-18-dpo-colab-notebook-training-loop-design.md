# DPO Colab Notebook Training Loop — Design

Date: 2026-09-18
Status: approved, pending implementation plan

## Problem

`docs/colab/dpo_training_template.ipynb` already has its fetch cell (download
the frozen `pairs.jsonl`/`provenance.jsonl`/`manifest.json` package via
`DOWNLOAD_URL`) and its push-back cell (zip a trained adapter directory and
`POST` it to `UPLOAD_URL`) implemented as part of the DPO Colab training
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
- Any change to `export_dpo_package()` or the core `dpo_training_jobs`/`trained_adapters`
  table schemas. Note: Backend upload-archive hardening (unpacking/zip-slip
  defenses, checksum & structure verification, symlink/corrupt archive
  rejection, and staging-path cleanup in `adapter_artifacts.py`) and zero-pair
  guards are handled as a prerequisite backend scope and validated via
  dedicated contract tests, rather than being an unvalidated "unchanged
  endpoint" assumption.
- Automatic model promotion. Storing an uploaded adapter persists metadata and
  files only; live inference wiring and model promotion remain strictly manual,
  preserving the system's no-auto-promotion invariant.

## Architecture

Extends the notebook to 11 cells (cells 0–10). Cell 2 (package fetch) was updated
to enforce strict package and checksum contract checks, and Cell 10 (push-back) was
updated to enforce output validation and deterministic relative-path archiving.
The markdown+TODO training placeholder is replaced by real training cells.

### Cell 0 — intro (markdown)

### Cell 1 — config (code)
`DOWNLOAD_URL`, `UPLOAD_URL`.

### Cell 2 — fetch & contract validation (code)
Downloads the frozen package; unzips and validates archive integrity:
- Verifies exact required archive members (`manifest.json`, `pairs.jsonl`, `provenance.jsonl`).
- Validates manifest schema, version (`equiped.dpo-package.v1`), and supported agent ID (`sme`, `coordinator`, `gad`, `itso`).
- Computes and checks SHA-256 hashes and byte lengths for `pairs.jsonl` and `provenance.jsonl` against manifest declarations.
- Validates JSONL syntax and schema for every pair (`prompt`, `chosen`, `rejected`), ensuring non-empty distinct preference targets (`chosen != rejected`) and non-zero pair count matching `manifest.pair_count`.
- Strengthens provenance validation against exporter fields, UUID/hash formats, agent consistency, unique pair_id, and positional pair/provenance count alignment:
  - Exact positional record-by-record correspondence: checks that `len(provenance_records) == len(pairs) == manifest.pair_count`.
  - Exporter field presence & schema typing: each provenance entry contains `pair_id`, `generation_id`, `evaluation_id`, `document_id`, `agent_id`, `unit_key`, `model_name`, `response_contract_key`, `response_contract_version`, `criterion_ids`, `reviewer_ids`, `prompt_sha256`, `response_sha256`, and `created_at`.
  - Strict format checks: valid UUIDs (`generation_id`, `evaluation_id`, `document_id`, each `reviewer_id`), valid 64-character hex format for SHA-256 digests (`prompt_sha256`, `response_sha256`), and non-empty required strings. `created_at` remains optional provenance metadata and is type-checked when present.
  - Consistency invariants: validates that provenance `agent_id` strictly matches `manifest.agent_id`, provenance `pair_id` is unique across all rows (no duplicate pairs), and positional pairing between each pair and provenance entry is preserved.
  - Exporter relationships: for each positionally paired pair and provenance record, enforces `pair_id == generation_id`, `prompt_sha256 == sha256(pair['prompt'].encode('utf-8')).hexdigest()`, and `response_sha256 == sha256(pair['rejected'].encode('utf-8')).hexdigest()`.
Produces `pairs` (list of validated `{prompt, chosen, rejected}` dicts) and `manifest` (dict).

### Cell 3 — section header (markdown)
Training section header and note on configurable parameters.

### Cell 4 — dependency install (code)
```
!pip install -q unsloth==2025.3.10 trl==0.15.2 peft==0.14.0 bitsandbytes==0.45.3 datasets==3.3.2 transformers==4.50.0 accelerate==1.4.0
```
Dependency pinning status: Package versions in the notebook are pinned to exact
reproducible release versions (`unsloth==2025.3.10`, `trl==0.15.2`, `peft==0.14.0`,
`bitsandbytes==0.45.3`, `datasets==3.3.2`, `transformers==4.50.0`, `accelerate==1.4.0`)
for late review. Base model revision is pinned to commit SHA
`BASE_MODEL_REVISION = "21bc97b90507086e76f0d256fee672973085d905"`. Note that these exact
dependency pins and model revision have not yet been revalidated together in a fresh Colab
GPU runtime and must never be called tested until revalidated.

### Cell 5 — data prep (code)
- Build an HF `Dataset` from `pairs` with columns `prompt`, `chosen`,
  `rejected` — already the exact shape TRL's `DPOTrainer` expects, no
  reshaping needed.
- Split 90/10 into train/val via `Dataset.train_test_split(test_size=0.1,
  seed=42)`.
- **Guard:** if `len(pairs) < 20`, skip the split (train on 100%, no eval
  dataset) and print a warning that the pair count is too small for a
  meaningful held-out sanity check — an eval split of a handful of pairs is
  noise, not signal.

### Cell 6 — model + LoRA setup (code)
```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/gemma-3-4b-it",
    revision="21bc97b90507086e76f0d256fee672973085d905",
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

### Cell 7 — DPOTrainer config + train (code)
```python
from trl import DPOConfig, DPOTrainer
from unsloth import is_bfloat16_supported

USE_BF16 = bool(is_bfloat16_supported())
USE_FP16 = not USE_BF16

training_args = DPOConfig(
    output_dir="./trained_adapter",
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    learning_rate=5e-6,
    num_train_epochs=1,
    beta=0.1,
    seed=42,
    max_length=2048,
    max_prompt_length=1536,
    eval_strategy="steps" if eval_dataset is not None else "no",
    eval_steps=20,
    logging_steps=5,
    save_strategy="no",
    report_to="none",
    fp16=USE_FP16,
    bf16=USE_BF16,
)
trainer = DPOTrainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    processing_class=tokenizer,
)
trainer.train()
```
Batch size 1 + gradient accumulation 8 is a deliberately conservative
default for T4/L4 headroom; `num_train_epochs=1` matches the small,
frequently-growing correction-log dataset this project will realistically
have early on — more epochs is an easy edit once correction volume is
larger, not a default worth guessing at now.

### Cell 8 — eval / sanity check (soft warning, no gating) (code)
```python
if eval_dataset is not None:
    try:
        metrics = trainer.evaluate()
        print(f"eval_loss: {metrics['eval_loss']:.4f}")
        print(
            "reward accuracy (chosen > rejected): "
            f"{metrics.get('eval_rewards/accuracies', 'n/a')}"
        )
    except Exception as exc:
        metrics = None
        print(f"Eval sanity check failed ({exc!r}); continuing to upload.")
else:
    metrics = None
    print("Skipped eval (too few pairs for a meaningful held-out split).")
```
The evaluation is explicitly exception-safe and non-blocking: "Run all"
always reaches the upload cell. Metrics are informational, not an automatic
deployment gate. The exception boundary covers short-run notebook callback quirks.

### Cell 9 — provenance manifest (code)
Before zipping, the notebook writes the manifest beside the adapter weights.
The following is an abbreviated shape; the executable cell additionally records
exact dependency versions, model revision, source hashes, random seed, resolved
precision, sequence length, and live-derived LoRA/training configuration.
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
or to `TrainedAdapter`'s schema.

### Cell 10 — push-back (code)
Before uploading, Cell 10 enforces client-side archive contract checks:
- Verifies output directory exists and contains required files (`adapter_config.json`, `training_manifest.json`) and supported adapter weights (`adapter_model.safetensors` or `adapter_model.bin`).
- Traverses the directory deterministically and archives entries using normalized relative paths (`arcname=rel_path.replace(os.sep, "/")`) rather than flattening basenames or emitting absolute paths.
- Posts the resulting zip to `UPLOAD_URL` only after passing validation, preserving the single-use token against malformed payloads.

## Data flow

```
Cell 2 fetch → validate archive members, SHA-256, JSONL & manifest contract
             → pairs (list[{prompt, chosen, rejected}]), manifest (dict)
Cell 5 → train_dataset, eval_dataset (or None if <20 pairs)
Cell 6 → model, tokenizer (4-bit QLoRA-ready, unsloth/gemma-3-4b-it base)
Cell 7 → trainer.train() writes adapter files to ./trained_adapter
Cell 8 → metrics (printed only, never gates execution)
Cell 9 → ./trained_adapter/training_manifest.json (provenance, bundled)
Cell 10 → validate output contents, archive with relative paths
        → POST UPLOAD_URL (hardened backend validation endpoint)
```

## Error handling

- Small-dataset guard (Cell 5): skips the eval split rather than producing
  a meaningless one; does not fail the run.
- No new failure modes introduced at the transport boundary — Cells 4–9 are
  entirely local to the Colab runtime; if they raise (OOM, dependency
  conflict, bad HF auth), the notebook simply stops before reaching the
  push-back cell, which is the existing, already-safe failure behavior (no
  partial/corrupt upload, and the job's upload token stays unused so a
  fresh job isn't even needed — the same `upload_url` still works on retry
  within its token's 7-day window).
- No hard gate on eval metrics (project decision) — Cell 8's warning is
  informational only.

## Testing

- Unit & Contract Test Coverage:
  - Notebook contract tests (such as `apps/server/tests/training_data/test_dpo_colab_contract.py`)
    verify Cell 2 package validation logic and Cell 10 deterministic packaging / relative
    paths offline without network or GPU access.
  - Backend upload hardening tests in `apps/server/tests/training_data/`
    (`test_adapter_artifacts.py`, `test_adapters.py`, `test_router.py`) cover zip-slip
    attacks, symlinks, duplicate archive members, CRC validation, manifest reconciliation,
    and single-use token lifecycle.
- Manual end-to-end Colab validation: Earlier interactive training execution on Colab GPU
  (T4) verified training convergence and PyTorch/TRL integration against real/synthetic
  packages. However, the exact pinned dependency versions and model revision have not yet
  been revalidated together in a fresh Colab GPU runtime and must never be called tested
  until fresh live validation is executed.
- Backend/frontend integration: No live model inference or auto-promotion is triggered;
  adapter records are registered and validated in the database and filesystem storage.

## Open questions for the implementation plan

- Exact default LoRA rank/alpha and DPO hyperparameters above are a
  starting recipe, not validated against this project's actual data yet —
  flag in the notebook's markdown that these are defaults to revisit once
  real correction volume exists, not tuned results.
- Unsloth's Gemma 3 support and API surface (`FastLanguageModel`,
  `get_peft_model` argument names) and exact pinned library versions/model revision
  have not yet been revalidated together in a fresh Colab GPU runtime and must not be
  referred to as tested until verified in an end-to-end run.
