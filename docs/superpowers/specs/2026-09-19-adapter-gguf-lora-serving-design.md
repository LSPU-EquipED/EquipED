# Serving a Trained Adapter as a GGUF LoRA — Design

Date: 2026-09-19
Status: draft, pending review

## Problem

The DPO Colab pipeline now produces real, stored LoRA adapters (PEFT format,
`adapter_model.safetensors` + `adapter_config.json`). Nothing can use one yet.
The production-style model server is **llama.cpp**, which does not load PEFT
adapters directly.

An earlier idea was to merge the adapter into the model and requantize it.
Checking the real setup (see Facts) shows that is unnecessary and costly:
llama.cpp can load a LoRA adapter on top of the model file it already serves,
if the adapter is first converted to GGUF LoRA format.

## Facts (verified 2026-09-19)

Reported by the host owner and cross-checked against this repo's `.env`:

- Server: llama.cpp, native Windows CUDA build, `llama-server` version
  0.1.0-dev, build 10430 (commit 4c1a0af40), started by `start-gemma.bat`
  with `--ctx-size 24576 --parallel 3 --n-gpu-layers 99 -ctk q8_0 -ctv q8_0
  --host 127.0.0.1 --port 8080 --offline`, alias `--alias gemma-3-4b-it`,
  exposed through a Cloudflare named tunnel at the `LLM_API_BASE` in `.env`.
- Served model file: a plain `gemma-3-4b-it-q4_0.gguf` (Q4_0). It is **not** a
  QAT build; the download source is not recorded.
- Hardware: RTX 3060 Ti, 8 GiB VRAM, about 16 GB system RAM. Model files live
  on drive F:. This dev machine has no GPU and about 3.9 GB free disk, so
  heavy steps run in Colab.
- `.env` sets `LLM_MODEL_NAME` and every `LLM_MODEL_*` to `gemma-3-4b-it`.
- The stored adapter (SME, from the 2026-09-18 Colab run): rank 16, alpha 32,
  targets the language-model attention and MLP projections, about 114 MB
  zipped. Its `adapter_config.json` names
  `unsloth/gemma-3-4b-it-unsloth-bnb-4bit` as its base, a 4-bit variant of the
  same instruct model.

## Goals

1. Turn a stored PEFT adapter into a GGUF LoRA file that the existing served
   model can load.
2. Give the host owner a short, safe procedure to load it, switch it on and
   off, and roll back.
3. Prove with a smoke test that the served model still returns valid SME JSON
   with the adapter off and on.

## Non-goals

- Merging the adapter into the model or requantizing (Approach B). Rejected:
  needs several GB of new files, and the source model is already the same
  instruct model the adapter was trained on.
- Retraining on a different base (Approach C). Revisit only if evaluation
  shows the adapter does not transfer.
- Any change under `apps/`: no "active adapter" flag, no database field, no
  admin UI, no adapter download endpoint, no automatic promotion. Activation
  stays a manual decision by the host owner.
- Judging whether an adapter is *better* than the base model. That is a
  separate evaluation tool (rollout plan step 5).
- Deciding for the host owner to restart or change their server.
- Fixing the stale "QAT" wording in other docs (see Follow-ups).

## Design

Three deliverables, all outside `apps/`.

### 1. Conversion notebook — `docs/colab/adapter_to_gguf_template.ipynb`

Runs in Colab (no GPU required; needs more disk than this machine has).

- Input: the adapter zip, uploaded by hand into the Colab session. The backend
  has no adapter download endpoint and this design does not add one.
- Steps: unzip; clone llama.cpp and install only the converter's Python
  requirements; run llama.cpp's `convert_lora_to_gguf.py` on the adapter
  directory with f16 output, pointing its base at the regular
  `unsloth/gemma-3-4b-it` config (the adapter's own base reference is the
  bnb variant, which the converter cannot use). Exact flag names are read from
  the script's `--help` in the notebook rather than assumed.
- Output: one `*.gguf` LoRA file (about 100–150 MB) and its SHA-256, matching
  the checksum habit of the existing adapter pipeline.
- Self-check before finishing: read the GGUF metadata back and assert it is a
  LoRA adapter with the expected rank and alpha, and that the tensor count is
  non-zero.

### 2. Serving how-to — `training/serving-lora-adapter.md`

A short runbook for the host owner:

- Copy the `.gguf` LoRA to a drive with space (F:), never over the base model.
- Add `--lora <path>` and `--lora-init-without-apply` to the `llama-server`
  command in `start-gemma.bat`, so the adapter is loaded but starts switched
  off.
- Confirm it loaded with the server's `GET /lora-adapters`.
- Switch it on for a request with the per-request `lora` scale field
  (scale 1.0 on, 0.0 off); no restart needed to compare.
- Roll back: remove the two flags and restart. The base model file is never
  modified.
- Memory note: the current settings (24k context, 3 slots, q8 KV cache) are
  estimated at about 5 of 8 GiB VRAM, so a second concurrent server is not
  expected to fit. Measure with `nvidia-smi` before and after adding the
  adapter.

### 3. Smoke test — `training/smoke_test_lora_serving.py`

A small client script runnable from any machine that can reach the server:

- Input: an exported `pairs.jsonl`; it uses the first N `prompt` values (these
  are real SME prompts built by the production prompt builder).
- For each prompt, calls the OpenAI-compatible chat endpoint twice: adapter
  scale 0, then scale 1.
- Validates each reply: parses as JSON, has `summary` and a non-empty
  `criterion_measurements` list, each entry has a `criterion_id` and an
  integer `score` from 1 to 4.
- Prints, per prompt and in total: valid/invalid counts for off and on, and
  whether the score changed. Exit code is non-zero if any reply is invalid.
- Endpoint and key come from arguments or the environment
  (`LLM_API_BASE`, `LLM_API_KEY`); the key is never printed.

## Data flow

```
stored adapter zip (backend disk)
  -> manual upload to Colab
  -> convert_lora_to_gguf -> adapter.gguf (+ sha256)
  -> manual copy to host (drive F:)
  -> llama-server --lora adapter.gguf --lora-init-without-apply
  -> smoke test: same prompts, scale 0 vs scale 1, validate JSON
```

## Error handling and risks

- **Converter may not know Gemma 3's multimodal tensor names.** The adapter
  targets the language-model layers only. If conversion fails or produces zero
  tensors, the notebook stops with the converter's message; we then decide
  between a converter patch and Approach B.
- **LoRA applied over a Q4_0 base** behaves slightly differently from training
  against a 4-bit-on-the-fly base. Expected to be minor; the future evaluation
  tool is what measures it.
- **Per-request `lora` on the chat endpoint** is assumed from llama-server
  behavior; the smoke test checks it. If the field is ignored there, fall back
  to setting the scale once through the server's adapter endpoint.
- **Batching:** requests with different LoRA settings may not batch together,
  which could reduce throughput under `--parallel 3`. Measure, do not assume.
- **VRAM headroom** is an estimate until measured on the real GPU.
- **Meaningless behavior change:** the stored adapter was trained on 25
  synthetic pairs. This design proves the mechanism only; it says nothing
  about adapter quality.

## Testing

- Notebook: validated by hand once in Colab (GPU-independent, but external to
  CI), same standard as the training notebook.
- Smoke test: the JSON-validation and reporting logic is unit-tested offline
  with canned replies; no server or GPU needed.
- End to end: requires the host owner's server; run once after they load the
  adapter, recorded in the plan like Task 6 of the training-notebook plan.

## Follow-ups (not in this spec)

- **Stale "QAT" wording.** `training/README.md`, `training/train_dpo_lora.py`
  and the 2026-09-18 Colab design spec describe the served model as QAT.
  Also, the repo's default model name `equiped-gemma3-4b-qat-q4` matches no real
  alias. Needs a decision: rename the repo default to `gemma-3-4b-it`, or
  rename the server alias. Small, separate change.
- **Adapter-vs-base evaluation tool** (rollout plan step 5).
- **Recording which GGUF LoRA came from which stored adapter** (database
  field), only if the manual process proves too error-prone.

## Open questions for the implementation plan

- Whether the smoke test's offline tests live under `training/` or reuse the
  backend test tree (the `training/` directory has no test setup today).
- Whether the converter needs the base weights or only the base config once
  its real `--help` is read in Colab.
