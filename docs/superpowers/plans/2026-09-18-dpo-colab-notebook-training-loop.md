# DPO Colab Notebook Training Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `# TODO` training-loop placeholder in
`docs/colab/dpo_training_template.ipynb` with a real, runnable LoRA/DPO
training loop (Unsloth + TRL `DPOTrainer` against `unsloth/gemma-3-4b-it`,
4-bit QLoRA) that consumes the notebook's fetch cell output (which also
validates package integrity) and feeds the hardened push-back cell.

**Architecture:** Six new/replaced notebook cells inserted between the
fetch cell (cell index 2, hardened with archive and package validation)
and the push-back cell (now cell index 10, hardened with client-side output
and relative-path validation): markdown header (cell 3), dependency install
(cell 4), data prep (cell 5: dataset build + 90/10 split with a small-dataset
guard), model+LoRA setup (cell 6), `DPOTrainer` train (cell 7), eval/sanity
print (cell 8: soft warning, never blocks), and a provenance-manifest cell
(cell 9) that writes `training_manifest.json` alongside the trained adapter
before cell 10 verifies and zips the output directory. Total notebook cell
count is 11 cells (cells 0 through 10).

**Tech Stack:** Jupyter notebook (`.ipynb`, nbformat 4.5) edited via Python
stdlib `json`; Python stdlib `ast` for a syntax-only verification pass (no
GPU/Colab access in this environment, so cells cannot be executed here);
the training code itself targets Unsloth + `trl.DPOTrainer` + `peft` +
`bitsandbytes`, which run only inside Colab.

**Spec:** `docs/superpowers/specs/2026-09-18-dpo-colab-notebook-training-loop-design.md`

## Global Constraints

- Scope separation:
  - Notebook workflow in `docs/colab/dpo_training_template.ipynb` covers package fetch & validation, dependency installation, data preparation, model+LoRA setup, DPO training, provenance manifest generation, deterministic relative-path archiving, and push-back upload.
  - Backend upload hardening (zip-slip defense, symlink/corrupt archive rejection, safe staging, checksum validation, and non-empty pair requirements) is treated as prerequisite/separate scope implemented and tested in `apps/server/modules/training_data/` and `apps/server/tests/training_data/`.
  - No live inference auto-promotion: storing an uploaded adapter updates database and filesystem state only; activation remains strictly manual.
- Truthful dependency & revision pinning status:
  - Notebook dependencies and base model revision are pinned to exact versions:
    `unsloth==2025.3.10`, `trl==0.15.2`, `peft==0.14.0`, `bitsandbytes==0.45.3`,
    `datasets==3.3.2`, `transformers==4.50.0`, `accelerate==1.4.0`, and base model
    revision `BASE_MODEL_REVISION = "21bc97b90507086e76f0d256fee672973085d905"`.
    These exact pins and model revision are pinned for late review but have not yet
    been revalidated together in a fresh Colab GPU runtime; they must never be called tested.
- Test coverage & verification:
  - Automated offline contract tests (e.g. in `apps/server/tests/training_data/test_dpo_colab_contract.py`) verify that Cell 2 (package fetch & validation) correctly enforces `DpoPackageManifest` schema, rejects corrupted/missing archive members, enforces positional pair/provenance count alignment, validates strengthened provenance attributes (UUID formats, SHA-256 digests, agent consistency, unique `pair_id`, exporter relationships: `pair_id == generation_id`, `prompt_sha256 == sha256(prompt)`, `response_sha256 == sha256(rejected)`), and that Cell 10 (push-back) validates required outputs and weights and creates deterministic forward-slash relative paths in archives.
  - Prerequisite backend upload hardening suites in `apps/server/tests/training_data/` (`test_adapter_artifacts.py`, `test_adapters.py`, `test_jobs.py`, `test_router.py`) verify zip-slip rejection, symlink safety, staging cleanup, and job token semantics.
  - No synthetic/ast test named `test_notebook_valid_json_and_syntax` exists; notebook syntax verification is conducted via python/pytest passes on the contract test suite and manual end-to-end Colab validation.
  - Interactive GPU training execution is verified manually in Google Colab (Task 6); while earlier end-to-end runs succeeded, the exact pinned dependency versions and model revision have not yet been revalidated together in a fresh Colab GPU runtime and must never be called tested.
- Small-dataset guard: if `len(pairs) < 20`, skip the train/val split
  (train on 100%, `eval_dataset = None`) and print a warning instead of
  producing a meaningless few-example "validation" split.
- Eval metrics in Cell 8 are informational only — never raise, never skip
  the push-back cell (Cell 10). This was an explicit user decision during
  brainstorming (soft warning, not a hard gate). Exception handling ensures
  callback quirks do not interrupt execution.
- Commit after each task, per the Step "Commit" instructions below.

> **Historical execution note:** The task-by-task scripts below preserve the
> intermediate cell counts that existed while the notebook was being built.
> They are an implementation record, not instructions for regenerating the
> current notebook. The checked-in 11-cell notebook and its contract tests are
> authoritative.

---

## File Structure

```
docs/colab/
  dpo_training_template.ipynb   [modify] notebook training workflow (11 cells total):
                                 package fetch & contract validation (cell 2),
                                 dependency install (cell 4), data prep (cell 5),
                                 model+LoRA setup (cell 6), DPOTrainer loop (cell 7),
                                 eval sanity-check (cell 8), provenance manifest (cell 9),
                                 and safe relative-path zip push-back (cell 10)
apps/server/modules/training_data/
  adapter_artifacts.py          [prerequisite/separate backend scope] archive inspection,
                                 zip-slip defenses, symlink rejection, safe staging
  adapters.py                   [prerequisite/separate backend scope] adapter upload ingestion
  jobs.py                       [prerequisite/separate backend scope] empty dataset guard
apps/server/tests/training_data/
  test_dpo_colab_contract.py    [automated contract suite] notebook offline contract tests:
                                 cell 2 package integrity validation and cell 10 adapter
                                 packaging and deterministic relative-path archiving (exact test names/counts flexible)
  test_adapter_artifacts.py     [prerequisite backend test suite] archive security & validation tests
  test_adapters.py              [prerequisite backend test suite] upload handling & ordering tests
  test_jobs.py                  [prerequisite backend test suite] dataset freeze & empty dataset tests
  test_router.py                [prerequisite backend test suite] router token & size rejection tests
```

---

### Task 1: Replace training-section markdown + TODO cell with dependency install and data-prep cells

**Files:**
- Modify: `docs/colab/dpo_training_template.ipynb` (cells at index 3-4)

**Interfaces:**
- Consumes: `pairs` (list of `{prompt, chosen, rejected}` dicts) and
  `manifest` (dict), both produced by cell index 2 (the fetch cell, which
  enforces full package, checksum integrity, and strengthened provenance
  validation: exporter fields, UUID/hash formats, agent consistency, unique
  pair_id, positional pair/provenance count alignment, and exporter
  relationships: `pair_id == generation_id`, `prompt_sha256`, and
  `response_sha256`).
- Produces: `train_dataset` (`datasets.Dataset`), `eval_dataset`
  (`datasets.Dataset | None`) — consumed by Task 3's `DPOTrainer` call (cell 7).

- [ ] **Step 1: Write the notebook-editing script for this task**

Create a scratch script (not committed — run once via Bash, then discard;
or keep inline as a one-off `python -c`) that:
1. Loads `docs/colab/dpo_training_template.ipynb` as JSON.
2. Removes the cell at index 3 (old "## Training" markdown) and the cell
   at index 4 (old `# TODO` code cell).
3. Inserts, at that same position (now index 3 onward), four new cells in
   this exact order:

Cell A (markdown) — replaces the old "## Training" section header:
```markdown
## Training

The cells below install dependencies, build a train/validation split from
the fetched `pairs`, load a 4-bit quantized base model with a LoRA
adapter, run TRL's `DPOTrainer`, print a sanity-check evaluation (this is
NOT the project's held-out test set — see the printed note), and bundle a
small provenance manifest into the adapter before the push-back cell zips
and uploads it.

The LoRA rank/alpha and DPO hyperparameters below are a reasonable
starting recipe for a small model on Colab's free-tier GPU, not a tuned
result — edit them directly in the cells if you have reason to.
```

Cell B (code) — dependency install:
```python
!pip install -q unsloth==2025.3.10 trl==0.15.2 peft==0.14.0 bitsandbytes==0.45.3 datasets==3.3.2 transformers==4.50.0 accelerate==1.4.0
```

Cell C (code) — data prep:
```python
from datasets import Dataset

dataset = Dataset.from_list(pairs)

MIN_PAIRS_FOR_EVAL_SPLIT = 20
if len(pairs) >= MIN_PAIRS_FOR_EVAL_SPLIT:
    split = dataset.train_test_split(test_size=0.1, seed=42)
    train_dataset = split["train"]
    eval_dataset = split["test"]
else:
    train_dataset = dataset
    eval_dataset = None
    print(
        f"Only {len(pairs)} pairs available (< {MIN_PAIRS_FOR_EVAL_SPLIT}) "
        "-- skipping the held-out validation split and training on all of "
        "them. The eval/sanity-check cell below will be skipped too."
    )

print(f"train_dataset: {len(train_dataset)} pairs")
if eval_dataset is not None:
    print(f"eval_dataset: {len(eval_dataset)} pairs")
```

Run this as a single Python invocation, e.g.:

```bash
python - <<'PYEOF'
import json

path = "docs/colab/dpo_training_template.ipynb"
with open(path, encoding="utf-8") as f:
    nb = json.load(f)

def code_cell(source_lines):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source_lines}

def markdown_cell(source_lines):
    return {"cell_type": "markdown", "metadata": {}, "source": source_lines}

cell_a = markdown_cell([
    "## Training\n",
    "\n",
    "The cells below install dependencies, build a train/validation split from\n",
    "the fetched `pairs`, load a 4-bit quantized base model with a LoRA\n",
    "adapter, run TRL's `DPOTrainer`, print a sanity-check evaluation (this is\n",
    "NOT the project's held-out test set -- see the printed note), and bundle a\n",
    "small provenance manifest into the adapter before the push-back cell zips\n",
    "and uploads it.\n",
    "\n",
    "The LoRA rank/alpha and DPO hyperparameters below are a reasonable\n",
    "starting recipe for a small model on Colab's free-tier GPU, not a tuned\n",
    "result -- edit them directly in the cells if you have reason to.",
])

cell_b = code_cell([
    "!pip install -q unsloth==2025.3.10 trl==0.15.2 peft==0.14.0 bitsandbytes==0.45.3 datasets==3.3.2 transformers==4.50.0 accelerate==1.4.0",
])

cell_c = code_cell([
    "from datasets import Dataset\n",
    "\n",
    "dataset = Dataset.from_list(pairs)\n",
    "\n",
    "MIN_PAIRS_FOR_EVAL_SPLIT = 20\n",
    "if len(pairs) >= MIN_PAIRS_FOR_EVAL_SPLIT:\n",
    "    split = dataset.train_test_split(test_size=0.1, seed=42)\n",
    "    train_dataset = split[\"train\"]\n",
    "    eval_dataset = split[\"test\"]\n",
    "else:\n",
    "    train_dataset = dataset\n",
    "    eval_dataset = None\n",
    "    print(\n",
    "        f\"Only {len(pairs)} pairs available (< {MIN_PAIRS_FOR_EVAL_SPLIT}) \"\n",
    "        \"-- skipping the held-out validation split and training on all of \"\n",
    "        \"them. The eval/sanity-check cell below will be skipped too.\"\n",
    "    )\n",
    "\n",
    "print(f\"train_dataset: {len(train_dataset)} pairs\")\n",
    "if eval_dataset is not None:\n",
    "    print(f\"eval_dataset: {len(eval_dataset)} pairs\")",
])

nb["cells"] = nb["cells"][:3] + [cell_a, cell_b, cell_c] + nb["cells"][5:]

with open(path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)
    f.write("\n")
PYEOF
```

- [ ] **Step 2: Verify the notebook is still valid JSON and the new/kept cells parse as Python**

```bash
python - <<'PYEOF'
import ast
import json

with open("docs/colab/dpo_training_template.ipynb", encoding="utf-8") as f:
    nb = json.load(f)

assert len(nb["cells"]) == 7, f"expected 7 cells, got {len(nb['cells'])}"
assert nb["cells"][3]["cell_type"] == "markdown"
assert nb["cells"][4]["cell_type"] == "code"
assert nb["cells"][5]["cell_type"] == "code"
assert nb["cells"][6]["cell_type"] == "code"  # old push-back cell, shifted

for idx in (1, 2, 5, 6):  # skip cell 4: starts with `!pip install`, not valid Python
    source = "".join(nb["cells"][idx]["source"])
    ast.parse(source)

pip_source = "".join(nb["cells"][4]["source"])
assert pip_source.strip().startswith("!pip install")

print("OK: 7 cells, JSON valid, code cells parse")
PYEOF
```

Run: the command above.
Expected: prints `OK: 7 cells, JSON valid, code cells parse`, exit code 0.

- [ ] **Step 3: Commit**

```bash
git checkout -b feat/dpo-colab-notebook-training-loop
git add docs/colab/dpo_training_template.ipynb
git commit -m "feat(colab): add dependency install and data-prep cells to DPO training template"
```

(Run `git checkout -b` only if this is the first task executed on a fresh
checkout of `main` — if the branch already exists from a prior task in
this plan, skip straight to `git add`/`git commit`.)

---

### Task 2: Insert model + LoRA setup cell

**Files:**
- Modify: `docs/colab/dpo_training_template.ipynb` (insert one cell after
  the data-prep cell added in Task 1)

**Interfaces:**
- Consumes: nothing from earlier tasks (loads the base model directly).
- Produces: `model`, `tokenizer` — consumed by Task 3's `DPOTrainer` call.

- [ ] **Step 1: Insert the model+LoRA setup cell**

```bash
python - <<'PYEOF'
import json

path = "docs/colab/dpo_training_template.ipynb"
with open(path, encoding="utf-8") as f:
    nb = json.load(f)

def code_cell(source_lines):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source_lines}

cell = code_cell([
    "from unsloth import FastLanguageModel\n",
    "\n",
    "model, tokenizer = FastLanguageModel.from_pretrained(\n",
    "    model_name=\"unsloth/gemma-3-4b-it\",\n",
    "    max_seq_length=2048,\n",
    "    load_in_4bit=True,\n",
    ")\n",
    "model = FastLanguageModel.get_peft_model(\n",
    "    model,\n",
    "    r=16,\n",
    "    lora_alpha=32,\n",
    "    lora_dropout=0.0,\n",
    "    target_modules=[\n",
    "        \"q_proj\", \"k_proj\", \"v_proj\", \"o_proj\",\n",
    "        \"gate_proj\", \"up_proj\", \"down_proj\",\n",
    "    ],\n",
    ")",
])

# Data-prep cell from Task 1 is now at index 5 (0=intro,1=config,2=fetch,
# 3=training markdown,4=pip install,5=data prep). Insert after it.
nb["cells"] = nb["cells"][:6] + [cell] + nb["cells"][6:]

with open(path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)
    f.write("\n")
PYEOF
```

- [ ] **Step 2: Verify notebook validity and syntax**

```bash
python - <<'PYEOF'
import ast
import json

with open("docs/colab/dpo_training_template.ipynb", encoding="utf-8") as f:
    nb = json.load(f)

assert len(nb["cells"]) == 8, f"expected 8 cells, got {len(nb['cells'])}"
assert nb["cells"][6]["cell_type"] == "code"
source = "".join(nb["cells"][6]["source"])
ast.parse(source)
assert "FastLanguageModel" in source
assert "unsloth/gemma-3-4b-it" in source

print("OK: 8 cells, model+LoRA cell parses")
PYEOF
```

Run: the command above.
Expected: prints `OK: 8 cells, model+LoRA cell parses`, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add docs/colab/dpo_training_template.ipynb
git commit -m "feat(colab): add model and LoRA setup cell to DPO training template"
```

---

### Task 3: Insert DPOTrainer config + train cell

**Files:**
- Modify: `docs/colab/dpo_training_template.ipynb` (insert one cell after
  the model+LoRA cell added in Task 2)

**Interfaces:**
- Consumes: `model`, `tokenizer` (Task 2); `train_dataset`, `eval_dataset`
  (Task 1).
- Produces: `trainer` (`trl.DPOTrainer`), and (via `trainer.train()`'s
  `output_dir`) adapter files written to `./trained_adapter` on disk —
  consumed by Task 5 (provenance manifest) and the existing push-back
  cell, both of which reference the directory via `ADAPTER_DIR`.

- [ ] **Step 1: Insert the DPOTrainer cell**

```bash
python - <<'PYEOF'
import json

path = "docs/colab/dpo_training_template.ipynb"
with open(path, encoding="utf-8") as f:
    nb = json.load(f)

def code_cell(source_lines):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source_lines}

cell = code_cell([
    "from trl import DPOConfig, DPOTrainer\n",
    "from unsloth import is_bfloat16_supported\n",
    "\n",
    "ADAPTER_DIR = \"./trained_adapter\"\n",
    "USE_BF16 = bool(is_bfloat16_supported())\n",
    "USE_FP16 = not USE_BF16\n",
    "\n",
    "training_args = DPOConfig(\n",
    "    output_dir=ADAPTER_DIR,\n",
    "    per_device_train_batch_size=1,\n",
    "    gradient_accumulation_steps=8,\n",
    "    learning_rate=5e-6,\n",
    "    num_train_epochs=1,\n",
    "    beta=0.1,\n",
    "    seed=42,\n",
    "    max_length=2048,\n",
    "    max_prompt_length=1536,\n",
    "    eval_strategy=\"steps\" if eval_dataset is not None else \"no\",\n",
    "    eval_steps=20,\n",
    "    logging_steps=5,\n",
    "    save_strategy=\"no\",\n",
    "    report_to=\"none\",\n",
    "    fp16=USE_FP16,\n",
    "    bf16=USE_BF16,\n",
    ")\n",
    "trainer = DPOTrainer(\n",
    "    model=model,\n",
    "    args=training_args,\n",
    "    train_dataset=train_dataset,\n",
    "    eval_dataset=eval_dataset,\n",
    "    processing_class=tokenizer,\n",
    ")\n",
    "trainer.train()",
])

# model+LoRA cell from Task 2 is now at index 6. Insert after it.
nb["cells"] = nb["cells"][:7] + [cell] + nb["cells"][7:]

with open(path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)
    f.write("\n")
PYEOF
```

- [ ] **Step 2: Verify notebook validity and syntax**

```bash
python - <<'PYEOF'
import ast
import json

with open("docs/colab/dpo_training_template.ipynb", encoding="utf-8") as f:
    nb = json.load(f)

assert len(nb["cells"]) == 9, f"expected 9 cells, got {len(nb['cells'])}"
assert nb["cells"][7]["cell_type"] == "code"
source = "".join(nb["cells"][7]["source"])
ast.parse(source)
assert "DPOTrainer" in source
assert "ADAPTER_DIR = \"./trained_adapter\"" in source

print("OK: 9 cells, DPOTrainer cell parses")
PYEOF
```

Run: the command above.
Expected: prints `OK: 9 cells, DPOTrainer cell parses`, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add docs/colab/dpo_training_template.ipynb
git commit -m "feat(colab): add DPOTrainer config and train cell to DPO training template"
```

---

### Task 4: Insert eval/sanity-check cell (soft warning, no gating)

**Files:**
- Modify: `docs/colab/dpo_training_template.ipynb` (insert one cell after
  the DPOTrainer cell added in Task 3)

**Interfaces:**
- Consumes: `trainer`, `eval_dataset` (Task 3, Task 1).
- Produces: `metrics` (`dict | None`) — consumed by Task 5's provenance
  manifest.

- [ ] **Step 1: Insert the eval/sanity-check cell**

```bash
python - <<'PYEOF'
import json

path = "docs/colab/dpo_training_template.ipynb"
with open(path, encoding="utf-8") as f:
    nb = json.load(f)

def code_cell(source_lines):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source_lines}

cell = code_cell([
    "if eval_dataset is not None:\n",
    "    try:\n",
    "        metrics = trainer.evaluate()\n",
    "        print(f\"eval_loss: {metrics['eval_loss']:.4f}\")\n",
    "        print(\n",
    "            \"reward accuracy (chosen > rejected): \"\n",
    "            f\"{metrics.get('eval_rewards/accuracies', 'n/a')}\"\n",
    "        )\n",
    "    except Exception as exc:\n",
    "        metrics = None\n",
    "        print(f\"Eval sanity check failed ({exc!r}); continuing to upload.\")\n",
    "else:\n",
    "    metrics = None\n",
    "    print(\"Skipped eval (too few pairs for a meaningful held-out split).\")",
])

# DPOTrainer cell from Task 3 is now at index 7. Insert after it.
nb["cells"] = nb["cells"][:8] + [cell] + nb["cells"][8:]

with open(path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)
    f.write("\n")
PYEOF
```

- [ ] **Step 2: Verify notebook validity and syntax**

```bash
python - <<'PYEOF'
import ast
import json

with open("docs/colab/dpo_training_template.ipynb", encoding="utf-8") as f:
    nb = json.load(f)

assert len(nb["cells"]) == 10, f"expected 10 cells, got {len(nb['cells'])}"
assert nb["cells"][8]["cell_type"] == "code"
source = "".join(nb["cells"][8]["source"])
ast.parse(source)
assert "trainer.evaluate()" in source
assert "not the project's" in source

print("OK: 10 cells, eval cell parses")
PYEOF
```

Run: the command above.
Expected: prints `OK: 10 cells, eval cell parses`, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add docs/colab/dpo_training_template.ipynb
git commit -m "feat(colab): add soft-warning eval sanity-check cell to DPO training template"
```

---

### Task 5: Insert provenance-manifest cell before the existing push-back cell

**Files:**
- Modify: `docs/colab/dpo_training_template.ipynb` (insert one cell after
  the eval cell added in Task 4, immediately before the pre-existing
  push-back cell)

**Interfaces:**
- Consumes: `manifest` (Task 1's data-prep cell reuses the fetch cell's
  `manifest` dict directly — no new variable); `metrics` (Task 4);
  `ADAPTER_DIR` (Task 3).
- Produces: `ADAPTER_DIR/training_manifest.json` on disk — read by no
  later cell (it rides inside the zip the push-back cell already builds
  from `ADAPTER_DIR`'s contents; no code change needed to that cell).

- [ ] **Step 1: Insert the provenance-manifest cell**

```bash
python - <<'PYEOF'
import json

path = "docs/colab/dpo_training_template.ipynb"
with open(path, encoding="utf-8") as f:
    nb = json.load(f)

def code_cell(source_lines):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source_lines}

cell = code_cell([
    "import json as _json\n",
    "import os\n",
    "\n",
    "training_manifest = {\n",
    "    \"source_job_manifest\": manifest,\n",
    "    \"base_model\": \"unsloth/gemma-3-4b-it\",\n",
    "    \"lora_config\": {\n",
    "        \"r\": 16,\n",
    "        \"lora_alpha\": 32,\n",
    "        \"target_modules\": [\n",
    "            \"q_proj\", \"k_proj\", \"v_proj\", \"o_proj\",\n",
    "            \"gate_proj\", \"up_proj\", \"down_proj\",\n",
    "        ],\n",
    "    },\n",
    "    \"training_args\": {\n",
    "        \"learning_rate\": 5e-6,\n",
    "        \"num_train_epochs\": 1,\n",
    "        \"beta\": 0.1,\n",
    "        \"per_device_train_batch_size\": 1,\n",
    "        \"gradient_accumulation_steps\": 8,\n",
    "    },\n",
    "    \"pair_count\": len(pairs),\n",
    "    \"eval_metrics\": metrics,\n",
    "}\n",
    "with open(os.path.join(ADAPTER_DIR, \"training_manifest.json\"), \"w\") as f:\n",
    "    _json.dump(training_manifest, f, indent=2)\n",
    "\n",
    "print(f\"Wrote {ADAPTER_DIR}/training_manifest.json\")",
])

# eval cell from Task 4 is now at index 8. Insert after it, before the
# pre-existing push-back cell (which is now at index 9).
nb["cells"] = nb["cells"][:9] + [cell] + nb["cells"][9:]

with open(path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)
    f.write("\n")
PYEOF
```

- [ ] **Step 2: Verify notebook validity, syntax, and that the push-back cell (cell 10) is intact**

```bash
python - <<'PYEOF'
import ast
import json

with open("docs/colab/dpo_training_template.ipynb", encoding="utf-8") as f:
    nb = json.load(f)

assert len(nb["cells"]) == 11, f"expected 11 cells, got {len(nb['cells'])}"
assert nb["cells"][9]["cell_type"] == "code"
manifest_source = "".join(nb["cells"][9]["source"])
ast.parse(manifest_source)
assert "training_manifest.json" in manifest_source

pushback_source = "".join(nb["cells"][10]["source"])
ast.parse(pushback_source)
assert "ADAPTER_ZIP_PATH" in pushback_source
assert "UPLOAD_URL" in pushback_source

print("OK: 11 cells, provenance cell parses, push-back cell intact")
PYEOF
```

Run: the command above.
Expected: prints `OK: 11 cells, provenance cell parses, push-back cell intact`, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add docs/colab/dpo_training_template.ipynb
git commit -m "feat(colab): add provenance manifest cell to DPO training template"
```

---

### Task 6: Manual end-to-end Colab validation (required before considering this done)

**Files:** none (validation only — no code changes).

**Interfaces:** none.

This plan's automated verification (Tasks 1-5, Step 2 of each) only proves
the notebook is valid JSON and each cell's Python parses — it cannot prove
the training loop actually trains, since that requires a GPU runtime this
environment does not have. Per the spec's Testing section, a manual run is
required before this feature is considered complete.

- [ ] **Step 1: Revalidate the exact committed pins end-to-end in fresh Colab**

1. In the EquipED admin panel, go to Training Data for an agent with at
   least a handful of exported DPO pairs, click "Start Training Job", copy
   the resulting `download_url` and `upload_url`.
2. Open `docs/colab/dpo_training_template.ipynb` in Google Colab (upload it
   or open via GitHub), select a GPU runtime (Runtime > Change runtime
   type > T4 GPU, the free tier default).
3. Paste the two URLs into the config cell.
4. Run all cells top to bottom (Runtime > Run all).
5. Confirm: the fetch cell prints a pair count; the dependency-install
   cell completes without error; the data-prep cell prints
   `train_dataset`/`eval_dataset` sizes (or the small-dataset warning if
   `pairs` has fewer than 20 entries); the model+LoRA cell loads without
   an out-of-memory error; `trainer.train()` runs to completion and prints
   a loss curve; the eval cell either prints `eval_loss`/reward accuracy
   or the "Skipped eval" message; the provenance cell prints the
   `training_manifest.json` path; the push-back cell prints "Adapter
   uploaded: ..." with a 2xx response.
6. In the admin panel's adapter list for that agent, confirm a new
   `TrainedAdapter` row appears (version incremented, size/hash populated,
   linked back to the job).

- [x] **Step 2: Record the outcome**

**Historical run completed 2026-09-18.** An end-to-end run succeeded on a
real Colab T4 against 25 synthetic SME DPO pairs and uploaded a registered
adapter through the development backend. The runtime's resolved dependency
versions and model revision were not captured, so that run does not validate
the exact configuration now committed. Automated contract and backend tests
guard package, archive, and staging behavior, but a fresh Colab GPU run is
still required for `unsloth==2025.3.10`, `trl==0.15.2`, `peft==0.14.0`,
`bitsandbytes==0.45.3`, `datasets==3.3.2`, `transformers==4.50.0`,
`accelerate==1.4.0`, and model revision
`21bc97b90507086e76f0d256fee672973085d905`.

Two real, previously-unverified issues surfaced during the live run and
were fixed on this branch:
- First attempt used a CPU-only Colab runtime (user error, not a notebook
  bug) — `NotImplementedError: Unsloth cannot find any torch accelerator`.
  Fixed by selecting a GPU runtime; not a code change.
- The eval sanity-check cell crashed with `RuntimeError: on_train_begin
  must be called before on_evaluate` — a known `transformers`
  `NotebookProgressCallback` quirk on very short training runs (~3
  optimizer steps, matching this project's realistic small-dataset case).
  Left unhandled, this halted Colab's "Run all" before ever reaching the
  push-back cell, defeating the eval cell's own designed "soft warning,
  never blocks execution" behavior. Fixed by wrapping `trainer.evaluate()`
  in a try/except (commit `6411425`).

In that historical runtime, dependency installation, the 22/3 data split,
4-bit model loading, DPO training, adapter saving, provenance generation,
and upload all completed. This is evidence that the workflow shape works,
not evidence that the newly pinned dependency/model matrix is compatible.

Test job/adapter left in place in the shared dev DB per user's explicit
choice (visible proof-of-work in the admin panel), not cleaned up.
