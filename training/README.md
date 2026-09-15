# DPO/LoRA training (standalone)

This directory is intentionally **separate from `server/`** — it runs in
a different environment (a GPU machine or cloud instance), never inside
the FastAPI server's own process. Its dependencies (PyTorch,
`transformers`, `peft`, `trl`) are large and GPU-oriented; keeping them
out of `server/pyproject.toml` keeps the API server's own install light.

## What's here

- `train_dpo_lora.py` — the training script itself.
- `requirements.txt` — its own, isolated dependency set.

## Prerequisites before a real (non-smoke-test) run

1. **A JSONL export.** Produced by either:
   - `uv run --project server python -m server.scripts.export_score_level_dpo_pairs <output>.jsonl` (SME)
   - `uv run --project server python -m server.scripts.export_item_level_dpo_pairs <output>.jsonl` (Coordinator)

   Copy the resulting file to the training machine.

2. **An unresolved question: the correct base checkpoint.** The server
   serves a quantized model (`equiped-gemma3-4b-qat-q4`) for inference.
   This script needs the corresponding **unquantized, fine-tunable**
   checkpoint (e.g. a standard HuggingFace `transformers` checkpoint) --
   confirm which one that is before pointing `--base-model` at anything
   you intend to actually deploy an adapter from. For a pure wiring
   smoke test, any small public causal LM works fine as a stand-in.

3. **Enough real volume.** See the project's DPO-readiness discussion —
   a handful of pairs only proves the pipeline runs, not that the
   resulting adapter is any good.

## Usage

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

python train_dpo_lora.py \
    --base-model <hf-checkpoint-or-local-path> \
    --data score_level_dpo_pairs.jsonl \
    --output-dir ./adapters/sme-v1 \
    --max-steps 5
```

Use `--max-steps` for a quick smoke test; use `--num-train-epochs`
instead for a real training run over the full dataset (the two are
mutually exclusive — the script requires exactly one).

## What the script actually does

1. Validates the JSONL file up front (every line has `prompt`, `chosen`,
   `rejected`) — fails with a clear message before touching any model,
   rather than a cryptic error deep inside the trainer. Warns if there
   are fewer than 20 pairs (smoke-test territory, not a real run).
2. Loads the base model + tokenizer, attaches a LoRA adapter via `peft`.
3. Runs `trl`'s `DPOTrainer`.
4. Saves the LoRA adapter (not a merged model) to `--output-dir`.
5. Reloads the saved adapter onto a fresh copy of the base model, to
   confirm it's genuinely loadable — not just that saving didn't error.

## Known risk: `trl` API drift

`DPOTrainer`'s constructor signature has changed across `trl` versions
(e.g. the `tokenizer` vs. `processing_class` keyword). If training
fails with a `TypeError` on your installed version, check
`DPOTrainer.__init__`'s actual signature and adjust that one keyword —
everything else in the script (data validation, LoRA config, save/
reload) is version-independent.

## Verification status

The argument parsing and JSONL validation logic have been exercised
directly (valid file, missing key, empty file) and behave correctly.
**The actual model-loading/training/save-reload path has not been run**
— that requires the ML dependencies and a real (or stand-in) base model,
neither of which are available in the environment this script was
written in. Run it on your target machine and confirm before trusting
it further.
