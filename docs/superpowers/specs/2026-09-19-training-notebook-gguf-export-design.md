# Training Notebook GGUF Export — Design

Date: 2026-09-19
Status: draft, pending review

## Problem

Getting a trained adapter into a form the host's llama.cpp can load takes two
notebooks and a manual hand-off today: run the training notebook
(`docs/colab/dpo_training_template.ipynb`), find the stored zip on the backend's
disk, upload it into a second Colab session, and run the standalone conversion
notebook (`docs/colab/adapter_to_gguf_template.ipynb`). The trained adapter is
already sitting in the training session at the moment it is uploaded, so the
second session and the file shuffle are pure friction.

## Goal

After the person pastes `DOWNLOAD_URL` and `UPLOAD_URL` and clicks **Run all**,
the training notebook:

1. trains the DPO LoRA adapter (unchanged),
2. uploads the adapter to the backend (unchanged),
3. converts that adapter to a GGUF LoRA,
4. verifies the GGUF and writes its SHA-256,
5. makes the GGUF, its checksum and a small metadata file available for
   download.

The host still installs and loads the GGUF by hand
(`training/serving-lora-adapter.md`). Nothing is deployed automatically.

## Non-goals

- Any change under `apps/`. The GGUF is not uploaded to the backend and is not
  placed inside the adapter zip.
- Any change to notebook cells 0-10 of the training notebook, or to the
  standalone conversion notebook. The standalone notebook stays for
  re-converting adapters that are already stored.
- Automatic deployment, or loading the GGUF into llama-server.
- Pinning llama.cpp to the host's build. The current default branch is used;
  the exact commit is printed and recorded (see below). The config cell still
  has a `LLAMA_CPP_REF` setting so a pin can be added later without new code.
- Evaluating the adapter. That is `training/evaluate_adapter.py`, and it needs
  the GGUF loaded by the host first.

## Facts (verified 2026-09-19)

- Training notebook: 11 cells (0-10). Cell 10 zips `./trained_adapter` as
  `trained_adapter.zip`, POSTs it to `UPLOAD_URL` and calls
  `raise_for_status()`, so a failed upload stops the run. The offline contract
  tests (`apps/server/tests/training_data/test_dpo_colab_contract.py`) address
  cells 2, 4-10 by index, so cells appended after 10 do not disturb them.
- The saved adapter directory holds `adapter_config.json` (rank `r`,
  `lora_alpha`) and `adapter_model.safetensors`.
- Standalone conversion notebook (8 cells): clones llama.cpp, installs the
  converter's requirements with pip, runs
  `convert_lora_to_gguf.py --base-model-id unsloth/gemma-3-4b-it --outfile adapter-f16.gguf --outtype f16 <adapter dir>`,
  checks the result (`general.type == adapter`, `adapter.type == lora`, alpha,
  lora_a/lora_b tensor pairs of the right rank), writes
  `adapter-f16.gguf.sha256` in `sha256sum` format, and downloads both. Its
  helpers `run`, `sha256_of`, `check_lora_fields` and `verify_gguf_lora` are
  covered by `training/tests/test_adapter_to_gguf_notebook.py`.
- The training notebook installs a pinned stack (`transformers==4.50.0`,
  `peft==0.14.0`, `trl==0.15.2`, `unsloth==2025.3.10`, ...). llama.cpp's
  converter requirements (torch, transformers, sentencepiece, gguf, numpy) may
  not match those pins.
- The converter needs no GPU; the base model's config is fetched from Hugging
  Face by `--base-model-id`.
- The GGUF for the current adapter is about 60 MB.

## Design

Append new cells after cell 10 of `docs/colab/dpo_training_template.ipynb`.
Cells 0-10 are not touched. Because Run all executes cells in order and cell 10
raises if the upload fails, the conversion cells only ever run after a
successful upload, and a conversion failure can never lose the trained
adapter.

### New cells (indices 11 and up)

| # | Type | Purpose |
|---|---|---|
| 11 | markdown | Section header: what the next cells do, that the adapter is already safely uploaded, that this adds roughly 5-10 minutes, that the host loads the GGUF by hand, and that the standalone notebook exists for stored adapters |
| 12 | code | Config and helpers (below) |
| 13 | code | Free GPU memory best-effort, read the adapter's rank and alpha, and fail early if the saved adapter is not a LoRA |
| 14 | code | Clone llama.cpp, print its commit, create the converter virtual environment, install the converter requirements into it |
| 15 | code | Run the converter (`--help` first, so the log records the flags) |
| 16 | code | Verify the GGUF, write the SHA-256 and metadata files, print the summary |
| 17 | code | Offer the three files for download |

Cells 13-17 each run inside `with conversion_step("<name>"):`. If a step raises,
it prints: the trained adapter is already uploaded and safe; re-convert it later
with `adapter_to_gguf_template.ipynb`; then re-raises, so Run all still ends
visibly failed.

### Config and helpers (cell 12)

- Constants: `GGUF_BASE_MODEL_ID = BASE_MODEL_NAME` (`unsloth/gemma-3-4b-it`,
  defined in cell 6; the converter needs the regular instruct model, not the
  4-bit variant named inside `adapter_config.json`), `OUTPUT_GGUF =
  "adapter-f16.gguf"`, `LLAMA_CPP_REPO`, `LLAMA_CPP_REF = None`,
  `CONVERTER_VENV = "converter-venv"`.
- Helpers copied unchanged from the standalone notebook: `run`, `sha256_of`,
  `check_lora_fields`. (`safe_extract` is not needed: the adapter directory
  already exists.)
- New: `conversion_step(name)` (context manager described above),
  `venv_python()` (the interpreter inside `CONVERTER_VENV`, correct for the
  platform layout), and `build_gguf_metadata(...)` (pure function returning the
  metadata dictionary).
- Copies of code across two notebooks are accepted (notebooks must be
  self-contained). A test keeps the copied helpers identical (see Testing).

### Isolation of the converter (decision)

The converter runs in a separate virtual environment so its requirements can
never disturb the pinned training stack:

1. `python -m venv converter-venv`. If that fails (on some Colab images the
   `ensurepip` piece is missing), fall back to `pip install -q virtualenv` and
   `python -m virtualenv converter-venv`.
2. Install llama.cpp's converter requirements with the venv's own pip.
3. Run `convert_lora_to_gguf.py` with the venv's interpreter, so the converter
   and its dependencies never load into the training process.

Verification also avoids importing llama.cpp's `gguf` package into the training
process (another `gguf` may already be loaded there, and a cached module would
win). A small script, kept as a string constant in cell 12, runs in the venv,
imports `GGUFReader` from `llama.cpp/gguf-py`, and prints the three fields and
the tensor names and shapes as JSON. The notebook parses that JSON and hands it
to `check_lora_fields`, the same pure check the standalone notebook uses. The
result is the same verification as the standalone notebook, done in the venv.

### Outputs

Written to the working directory and offered for download:

- `adapter-f16.gguf`.
- `adapter-f16.gguf.sha256`, one line `<hash>  adapter-f16.gguf`, the same
  format the standalone notebook writes and the host runbook expects.
- `adapter-f16.gguf.json`, the record of how it was made:
  `llama_cpp_commit`, `llama_cpp_ref` (the requested ref, or null),
  `converter` (`convert_lora_to_gguf.py`), `outtype` (`f16`),
  `base_model_id`, `lora_rank`, `lora_alpha`, `tensor_pairs`, `gguf_sha256`,
  `gguf_bytes`, `adapter_zip_sha256` (of the `trained_adapter.zip` that cell 10
  uploaded, which is what the backend stores as `file_sha256`, so the GGUF can
  be matched to its stored adapter).

The exact llama.cpp commit is printed in cell 14 and again in the summary, and
recorded in the JSON. The standalone notebook does not write the JSON file (it
is unchanged); the runbook says the file is optional.

### Download

`google.colab.files.download` for each of the three files, with the same
outside-Colab fallback as the standalone notebook (the files stay in the working
directory). The cell prints a note that the browser may ask to allow multiple
downloads.

### Memory

Before converting, cell 13 frees what it can (delete the trainer, run
`gc.collect()`, `torch.cuda.empty_cache()`), inside a try block, because the
Colab runtime has limited RAM and the converter loads the adapter and the base
model's configuration on the CPU. Failure to free memory is not an error.

### Docs

`training/serving-lora-adapter.md` gets one paragraph: the training notebook
now also produces the GGUF, the checksum and an optional JSON record, so there
is usually no need to convert separately. Nothing else in the runbook changes.

## Data flow

```
Run all
  cells 0-10 (unchanged): fetch package -> train -> save -> manifest -> zip -> upload
  cell 11-13: header, config+helpers, adapter rank/alpha, free memory
  cell 14: clone llama.cpp (print commit) -> create venv -> install converter deps
  cell 15: venv python convert_lora_to_gguf.py -> adapter-f16.gguf
  cell 16: venv python reads GGUF -> check_lora_fields -> sha256 + json + summary
  cell 17: download adapter-f16.gguf, .sha256, .json
host (manual): copy the files, verify the hash, load with --lora-scaled <file>:0.0
```

## Error handling and risks

- **Conversion fails after training:** the adapter is already uploaded. The
  step wrapper prints how to re-convert with the standalone notebook.
- **`python -m venv` unavailable:** fall back to `virtualenv`; if that fails,
  the step fails with the wrapper's message. Not verified on a real Colab image
  yet, so the first real run is the check.
- **Long install:** the converter requirements include a CPU torch, roughly a
  few hundred MB and a minute or two; this is why the notebook header states the
  extra time.
- **Version drift:** the default llama.cpp branch can change between runs. The
  commit is recorded so a GGUF can always be traced to the converter version;
  `LLAMA_CPP_REF` can pin it later.
- **Converter layout changes:** as in the standalone notebook, a missing
  requirements file fails with a message naming the directory to check.
- **Session limits:** a very long training run may hit Colab's session limit
  before conversion; the upload happens before, so the adapter is safe, and the
  standalone notebook covers the rest.
- **Browser blocks the downloads:** the files stay in the Colab Files panel.

## Testing

Offline (no GPU, no network), in a new file
`training/tests/test_dpo_notebook_gguf_cells.py`, next to the standalone
notebook's tests:

- The training notebook still has cells 0-10 in place and the new cells follow
  them; every new code cell parses as Python (cell 4 is excluded from any
  such check: it holds a `!pip` line).
- Order: the upload cell (the one that posts to `UPLOAD_URL`) comes before the
  first conversion cell, and the download cell comes after the cell that
  verifies.
- The converter call has the same arguments as the standalone notebook
  (`--base-model-id`, `--outtype f16`, `--outfile`) and uses the venv's
  interpreter, not `sys.executable`, for the converter and for pip.
- The copied helpers (`run`, `sha256_of`, `check_lora_fields`) are
  source-identical to the standalone notebook's, compared with `ast`.
- `conversion_step` prints the re-convert hint and re-raises.
- `build_gguf_metadata` returns every field listed above with the right types.
- The verification script string, run in a subprocess against a stub
  `llama.cpp/gguf-py/gguf` package in a temporary directory, prints JSON in the
  shape the notebook parses.
- The existing 46 contract tests and the standalone notebook's tests keep
  passing untouched.

One real Colab run, done by the person: paste fresh URLs, Run all, confirm the
adapter upload line, the printed llama.cpp commit, the verification summary and
the three downloads; check the `.sha256` against the file and the JSON's
`adapter_zip_sha256` against the stored adapter. This is the only check of the
venv step and of downloads in a real session. It adds one adapter row to the
shared development database, as any training run does.

## Follow-ups (not in this spec)

- Pin `LLAMA_CPP_REF` to the host's exact llama.cpp commit (needs the full hash
  from the host).
- Store the GGUF on the backend, or offer a download button for stored
  adapters (backend change).
- Have `evaluate_adapter.py` read the GGUF metadata JSON to confirm the loaded
  adapter matches.
