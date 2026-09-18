# DPO Colab Notebook Training Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `# TODO` training-loop placeholder in
`docs/colab/dpo_training_template.ipynb` with a real, runnable LoRA/DPO
training loop (Unsloth + TRL `DPOTrainer` against `unsloth/gemma-3-4b-it`,
4-bit QLoRA) that consumes the notebook's already-working fetch cell output
and feeds the already-working push-back cell.

**Architecture:** Five new/replaced notebook cells inserted between the
existing fetch cell and push-back cell: dependency install, data prep
(dataset build + 90/10 split with a small-dataset guard), model+LoRA setup,
`DPOTrainer` train, eval/sanity print (soft warning, never blocks), and a
provenance-manifest cell that writes `training_manifest.json` alongside the
trained adapter before it gets zipped. The notebook is edited by a small
Python script (via stdlib `json`) that loads the `.ipynb` as JSON, splices
in new cell dicts, and writes it back — hand-editing raw notebook JSON is
error-prone, and there is no other tooling dependency needed for this.

**Tech Stack:** Jupyter notebook (`.ipynb`, nbformat 4.5) edited via Python
stdlib `json`; Python stdlib `ast` for a syntax-only verification pass (no
GPU/Colab access in this environment, so cells cannot be executed here);
the training code itself targets Unsloth + `trl.DPOTrainer` + `peft` +
`bitsandbytes`, which run only inside Colab.

**Spec:** `docs/superpowers/specs/2026-09-18-dpo-colab-notebook-training-loop-design.md`

## Global Constraints

- Single file changes only: `docs/colab/dpo_training_template.ipynb`. Do
  not modify `export_dpo_package()`, the training-data router/endpoints, or
  the `dpo_training_jobs`/`trained_adapters` tables — this plan is notebook
  content only.
- Base model: `unsloth/gemma-3-4b-it`, loaded 4-bit (QLoRA) via
  `load_in_4bit=True`. Training stack: Unsloth's `FastLanguageModel` +
  `trl.DPOTrainer`.
- No CI test coverage is possible (GPU-dependent, external to this
  environment). Every task's verification step is a syntax/structure check
  run locally via Python stdlib (`json.load` for notebook validity,
  `ast.parse` for each code cell after stripping any `!shell` magic lines)
  — this catches typos and syntax errors but does NOT prove the training
  loop actually trains; a manual end-to-end Colab run (Task 6) is required
  before considering this done.
- Small-dataset guard: if `len(pairs) < 20`, skip the train/val split
  (train on 100%, `eval_dataset = None`) and print a warning instead of
  producing a meaningless few-example "validation" split.
- Eval metrics in Cell 7 are informational only — never raise, never skip
  the push-back cell. This was an explicit user decision during
  brainstorming (soft warning, not a hard gate).
- `docs/colab/dpo_training_template.ipynb` currently has 6 cells (indices
  0-5): 0=intro markdown, 1=config code, 2=fetch code, 3=training-section
  markdown, 4=TODO placeholder code, 5=push-back code. Cells 3 and 4 are
  replaced; cell 5 (push-back) is left byte-for-byte unchanged; cells 0-2
  are left byte-for-byte unchanged.
- Work happens on a new branch `feat/dpo-colab-notebook-training-loop`,
  created off `main` before Task 1.
- Commit after each task, per the Step "Commit" instructions below.

---

## File Structure

```
docs/colab/
  dpo_training_template.ipynb   [modify] insert/replace cells 3-4 with
                                 six new cells (Tasks 1-5); cell that was
                                 index 5 (push-back) shifts to the end,
                                 unchanged in content
```

No other files are created or modified by this plan.

---

### Task 1: Replace training-section markdown + TODO cell with dependency install and data-prep cells

**Files:**
- Modify: `docs/colab/dpo_training_template.ipynb` (cells at index 3-4)

**Interfaces:**
- Consumes: `pairs` (list of `{prompt, chosen, rejected}` dicts) and
  `manifest` (dict), both already produced by existing cell index 2 (the
  fetch cell — unchanged by this plan).
- Produces: `train_dataset` (`datasets.Dataset`), `eval_dataset`
  (`datasets.Dataset | None`) — consumed by Task 3's `DPOTrainer` call.

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
!pip install -q unsloth trl peft bitsandbytes datasets
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
    "!pip install -q unsloth trl peft bitsandbytes datasets",
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
    "\n",
    "ADAPTER_DIR = \"./trained_adapter\"\n",
    "\n",
    "training_args = DPOConfig(\n",
    "    output_dir=ADAPTER_DIR,\n",
    "    per_device_train_batch_size=1,\n",
    "    gradient_accumulation_steps=8,\n",
    "    learning_rate=5e-6,\n",
    "    num_train_epochs=1,\n",
    "    beta=0.1,\n",
    "    eval_strategy=\"steps\" if eval_dataset is not None else \"no\",\n",
    "    eval_steps=20,\n",
    "    logging_steps=5,\n",
    "    bf16=True,\n",
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
    "    metrics = trainer.evaluate()\n",
    "    print(f\"eval_loss: {metrics['eval_loss']:.4f}\")\n",
    "    print(\n",
    "        \"reward accuracy (chosen > rejected): \"\n",
    "        f\"{metrics.get('eval_rewards/accuracies', 'n/a')}\"\n",
    "    )\n",
    "    print(\n",
    "        \"NOTE: this is an in-run sanity check on a random 10% split of \"\n",
    "        \"THIS training run's own data -- it is not the project's \"\n",
    "        \"held-out test set, and does not compare against the base model. \"\n",
    "        \"A low accuracy here is a strong signal something went wrong; a \"\n",
    "        \"high accuracy is not by itself a green light to deploy.\"\n",
    "    )\n",
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

- [ ] **Step 2: Verify notebook validity, syntax, and that the original push-back cell is unchanged**

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

- [ ] **Step 1: Run a real training job end-to-end in Colab**

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

- [ ] **Step 2: Record the outcome**

If any step fails, fix the relevant cell (repeat that task's Step 1 with a
corrected cell source, then its Step 2 verification, then commit a fix),
and re-run this task's Step 1 from a fresh Colab runtime. Do not consider
this plan complete until one full end-to-end run succeeds.

No commit for this task unless a fix was needed (in which case, commit
that fix with a message describing what was wrong, e.g. `fix(colab):
correct DPOConfig argument name found during manual Colab validation`).
