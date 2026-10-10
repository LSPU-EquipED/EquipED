# Semi-Automatic Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a one-time setup, training a fine-tuned model needs only "Run all in Colab" and one model-server restart: the app hands out a ready-to-run notebook, shows live run status, and a host script delivers the finished GGUF.

**Architecture:** Four slices on one branch. (A) the training notebook gets the generic fixes from the gentle copy plus the already-planned measured lengths and dose. (B) the server fills the job's links into the notebook template and returns it with the "start run" response. (C) a job-scoped status token, a status endpoint and four-column run record feed a live "Training runs" table. (D) a read-only host key, two host endpoints and a standard-library script `training/host_sync.py` pull new GGUFs to the model server's adapters folder.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (Python 3.12, pytest, ruff), Jupyter notebook JSON (Colab), React 18 + TanStack Query 5 + Vitest, Python standard library for the host script.

**Spec:** `docs/superpowers/specs/2026-10-10-semi-automatic-training-design.md`

## Global Constraints

- Work on the existing branch `feat/plain-language-model-training` (the PR carries the plain-language changes and this work together). Do NOT create a new branch. Commit per task. **No `Co-Authored-By` or `Claude-Session` trailers** in commit messages (CLAUDE.md).
- Backend: run from `apps/` with `uv run --project server ...`; ruff line length 88; absolute `server.*` imports; per-module layout (`router.py`, `service`-style modules, `models.py`, `schemas.py`, `exceptions.py`). Keep business rules in `modules/training_data`, not `core/`.
- Frontend (`apps/admin`): TypeScript, no new dependencies, no component kits, features must not import from sibling features. Format with `npx prettier --single-quote --print-width 100 --trailing-comma all --end-of-line lf --write <files>` (the repo has no committed prettier config; this matches the existing style). Run vitest from `apps/admin`.
- `docs/colab/dpo_training_template.ipynb` is CRLF, no trailing newline, and addressed by cell index in tests. Edit it ONLY with the round-trip-safe helper in **Appendix A** (kept outside the repo). Locate cells by a unique text marker, never by hard-coded index. Do NOT touch the untracked experiment notebooks (`latest_dpo_training_template`, `sme_retrain_gentle`, `sme_retrain_stronger`) or any other untracked file.
- Migrations are additive and nullable. Revision chain: current head is `20261006_0001`. **Never run `alembic upgrade` against the shared Neon database**; validate with offline SQL (`uv run alembic upgrade 20261006_0001:head --sql`). The user applies migrations.
- Token rules (match the existing job tokens): store only SHA-256 hashes, compare with `secrets.compare_digest`, invalid/expired/foreign tokens return 404 `"not found"`, never 403.
- A notebook, status, or host-sync failure must never block starting a run, training, or uploading. Status reporting is best-effort everywhere.
- The status endpoint accepts exactly these stages: `starting`, `training`, `sending_model`, `converting`, `sending_file`, `finished`, `failed`. Stale threshold: 15 minutes. Poll interval: 10 seconds, only while a run is active. Host defaults: `keep_latest = 2` versions per agent plus the published one; the script never restarts the server, never deletes files, never publishes.
- Do not run `git commit` unless the task step says so; the user opens the PR themselves (`gh` is not installed).

## Execution Order

Run the tasks in this order: **A1, A2, B1, B2, B3, C1, C3, C2, C4, D1, D2, D3, D4, Z**. C3 runs before C2 because C2's two status-link builder tests need the `STATUS_URL = ""` line that C3 adds to the template. Task numbers in the headings are unchanged.

## Review Focus

1. A job created before this change (no status token, no stage columns): the jobs list, the Training runs table and every endpoint must still work and show the old Waiting / In progress / Finished status (Tasks C1, C2, C4).
2. A late or out-of-order status post (for example `training` arriving after the server already set `converting`, or `failed` after `finished`): the stage must not move backwards (Task C1).
3. Colab disconnects mid-training: the row must show the "no update" warning and polling must stop once no run is active, not poll forever (Task C4).
4. A host file whose checksum does not match, or that downloads partially: nothing partial is ever left under the final name, and the next run retries (Task D2).
5. A hostile or malformed manifest (path-like filename, huge size): the host script must reject it instead of writing outside the adapters folder (Task D2).
6. The notebook template missing, edited, or with a duplicated placeholder: job creation still succeeds and the response says no notebook is available, instead of failing the whole request or sending an unfilled notebook (Task B1, B2).

## File Structure

**Slice A (notebook):** modify `docs/colab/dpo_training_template.ipynb`; new `apps/server/tests/training_data/test_notebook_merge.py`; update index-based tests in `apps/server/tests/training_data/` and `training/tests/`.

**Slice B:** new `apps/server/modules/training_data/notebook.py` (fills the template); modify `exceptions.py`, `schemas.py` (`TrainingJobCreateResponse`), `router.py`; admin: new `utils/downloadTextFile.ts`, modify `types.ts`, `TrainingJobCredentials.tsx`; tests `tests/training_data/test_notebook_builder.py`, `test_router.py`, `TrainingJobCredentials.test.tsx`.

**Slice C:** modify `models.py`, `jobs.py`, `schemas.py`, `router.py`, `notebook.py`; new migration `alembic/versions/20261010_0001_add_run_status_to_training_jobs.py`; the notebook; admin `types.ts`, `utils/trainingData.utils.ts`, `components/TrainingJobRow.tsx`, `hooks/useTrainingJobs.ts`; tests `test_run_status.py`, `test_notebook_status.py`, admin tests.

**Slice D:** new `modules/training_data/host_keys.py`; modify `models.py`, `exceptions.py`, `schemas.py`, `router.py`; migration `20261010_0002_add_host_sync_keys.py`; new `training/host_sync.py`, `training/host_sync.example.ini`, `docs/host-sync-setup.md`; admin new `components/HostSyncPanel.tsx`, `hooks/useHostSync.ts`, modify `api/trainingData.api.ts`, `types.ts`, `TrainingDataWorkspace.tsx`; tests `test_host_keys.py`, `training/tests/test_host_sync.py`, `HostSyncPanel.test.tsx`.

---

## Appendix A: round-trip-safe notebook editor

Create this file OUTSIDE the repo (use the scratchpad directory) as `nbedit.py`. Every notebook-editing step below imports it and is run from the repo root (`C:\Users\Admin\Desktop\PROJECTS\EquipED`) with `python <script>.py`.

```python
import json
from pathlib import Path

NB_PATH = Path("docs/colab/dpo_training_template.ipynb")


def load():
    raw = NB_PATH.read_bytes().decode("utf-8")
    nb = json.loads(raw)
    expected = json.dumps(nb, indent=1).replace("\n", "\r\n")
    assert expected == raw, "notebook is not round-trip safe; stop and investigate"
    return nb


def get(nb, index):
    return "".join(nb["cells"][index]["source"])


def find(nb, marker):
    hits = [i for i, c in enumerate(nb["cells"]) if marker in "".join(c["source"])]
    assert len(hits) == 1, (marker, hits)
    return hits[0]


def put(nb, index, text):
    nb["cells"][index]["source"] = text.splitlines(keepends=True)


def replace_once(text, old, new):
    assert text.count(old) == 1, (old[:70], text.count(old))
    return text.replace(old, new)


def insert_code_cell(nb, index, text):
    nb["cells"].insert(
        index,
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": text.splitlines(keepends=True),
        },
    )


def save(nb):
    NB_PATH.write_bytes(json.dumps(nb, indent=1).replace("\n", "\r\n").encode("utf-8"))
```

After any edit run `git diff --stat docs/colab/dpo_training_template.ipynb`. If the whole file shows as changed, `git checkout docs/colab/dpo_training_template.ipynb` and redo.

---

# SLICE A: Notebook

### Task A1: Execute the existing measured-plan notebook plan

**Files:** per `docs/superpowers/plans/2026-10-07-notebook-training-plan.md` (Tasks 1 to 3).

**Interfaces:**
- Produces (used by later tasks): cells 6 and 7 contain `plan_lengths` / `plan_dose` helper blocks between the markers `# --- planning helpers (tested) ---` and `# --- end planning helpers ---`; cell 7 contains `LEARNING_RATE = 2e-5`, `GRAD_ACCUM = 4`, `trainer = DPOTrainer(` ... `trainer.train()`; cell 9 writes `training_plan` into the manifest.

- [ ] **Step 1: Run that plan's Tasks 1, 2 and 3 exactly as written**, with one change: ignore its "Branch `feat/notebook-training-plan`" constraint. Stay on `feat/plain-language-model-training`. Its own rule "do not add or remove notebook cells" stays in force until Task A2.
- [ ] **Step 2: Verify the whole suite is green**

Run: `cd apps && uv run --project server pytest server/tests/training_data -q`
Expected: all pass (the plan's tests included).

- [ ] **Step 3: Confirm the commits exist** (`git log --oneline -5` shows that plan's three task commits). Nothing else to do here.

### Task A2: Merge the generic improvements from the gentle notebook

Adds Gemma chat-format training rows, a chat-format guard, the early stop, and an out-of-memory rescue cell. **This is the only task that adds a cell** (rescue cell at index 8; every cell from the old index 8 onward moves down by one).

**Files:**
- Modify: `docs/colab/dpo_training_template.ipynb` (cells: split, trainer, new rescue cell, header markdown)
- Create: `apps/server/tests/training_data/test_notebook_merge.py`
- Modify: every test that indexes notebook cells (see Step 5)

**Interfaces:**
- Consumes: cell 5 defines `_training_row`; cell 7 contains `from unsloth import is_bfloat16_supported`, `processing_class=tokenizer,` and `trainer.train()`.
- Produces: cell 5 defines `_chat_row(pair)`; cell 7 defines `class StopIfChosenCollapses(TrainerCallback)` and passes `callbacks=[StopIfChosenCollapses()]`; cell 8 is the rescue cell; all later cells are +1.

- [ ] **Step 1: Write the failing tests**

Create `apps/server/tests/training_data/test_notebook_merge.py`:

```python
"""Checks for the gentle-notebook improvements merged into the template."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[4]
NOTEBOOK_PATH = REPO_ROOT / "docs" / "colab" / "dpo_training_template.ipynb"


def _cells() -> list[str]:
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in nb["cells"]]


def _find(marker: str) -> tuple[int, str]:
    hits = [(i, s) for i, s in enumerate(_cells()) if marker in s]
    assert len(hits) == 1, (marker, [i for i, _ in hits])
    return hits[0]


def _extract(source: str, node_type, name: str, namespace: dict):
    tree = ast.parse(source)
    node = next(
        n
        for n in tree.body
        if isinstance(n, node_type) and getattr(n, "name", None) == name
    )
    exec(ast.get_source_segment(source, node), namespace)  # noqa: S102
    return namespace[name]


def test_chat_row_wraps_each_field_in_a_chat_message():
    _, source = _find("def _chat_row(pair):")
    chat_row = _extract(source, ast.FunctionDef, "_chat_row", {})
    row = chat_row({"prompt": "P", "chosen": "C", "rejected": "R", "extra": 1})
    assert row == {
        "prompt": [{"role": "user", "content": "P"}],
        "chosen": [{"role": "assistant", "content": "C"}],
        "rejected": [{"role": "assistant", "content": "R"}],
    }


def test_training_and_eval_datasets_use_chat_rows_but_heldout_stays_raw():
    _, source = _find("def _chat_row(pair):")
    assert "Dataset.from_list([_chat_row(pair) for pair, _ in train_items])" in source
    assert "Dataset.from_list([_chat_row(pair) for pair, _ in heldout_items])" in source
    # heldout_pairs.jsonl keeps raw strings for the evaluation tool.
    assert "**_training_row(pair)," in source


def _callback():
    _, source = _find("class StopIfChosenCollapses")
    return _extract(
        source,
        ast.ClassDef,
        "StopIfChosenCollapses",
        {"TrainerCallback": object},
    )


def test_early_stop_triggers_below_minus_five_only():
    callback = _callback()()
    control = SimpleNamespace(should_training_stop=False)
    callback.on_log(None, None, control, logs={"rewards/chosen": -4.9})
    assert control.should_training_stop is False
    callback.on_log(None, None, control, logs={"rewards/chosen": -5.1})
    assert control.should_training_stop is True


def test_early_stop_ignores_missing_or_non_numeric_values():
    callback = _callback()()
    control = SimpleNamespace(should_training_stop=False)
    callback.on_log(None, None, control, logs=None)
    callback.on_log(None, None, control, logs={"loss": 0.2})
    callback.on_log(None, None, control, logs={"rewards/chosen": "nan"})
    assert control.should_training_stop is False


def test_trainer_cell_wires_the_callback_and_the_chat_format_guard():
    _, source = _find("trainer = DPOTrainer(")
    assert "callbacks=[StopIfChosenCollapses()]" in source
    assert '"<start_of_turn>user" not in _probe' in source
    assert source.index("_probe") < source.index("trainer.train()")


def test_rescue_cell_follows_the_trainer_cell_and_saves_the_adapter():
    cells = _cells()
    trainer_index, _ = _find("trainer = DPOTrainer(")
    rescue = cells[trainer_index + 1]
    assert rescue.startswith("# Rescue cell")
    assert "model.save_pretrained(ADAPTER_DIR)" in rescue
    assert "torch.cuda.empty_cache()" in rescue


def test_header_explains_the_rescue_cell():
    assert "out-of-memory" in _cells()[0]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_notebook_merge.py -q`
Expected: FAIL (no `_chat_row`, no callback, no rescue cell).

- [ ] **Step 3: Create the edit script and apply it**

Create `edit_a2.py` outside the repo, in the same directory as `nbedit.py`, and run it from the repo root: `python <path>/edit_a2.py`

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nbedit as nb_

nb = nb_.load()

# --- cell: dataset split (chat-format rows) ---
i = nb_.find(nb, "def _training_row(pair):")
s = nb_.get(nb, i)
s = nb_.replace_once(
    s,
    'def _training_row(pair):\n    return {key: pair[key] for key in ("prompt", "chosen", "rejected")}\n',
    'def _training_row(pair):\n    return {key: pair[key] for key in ("prompt", "chosen", "rejected")}\n'
    "\n\n"
    "def _chat_row(pair):\n"
    '    """Chat-format row for TRL, so Gemma\'s template (BOS, turn markers) is applied.\n'
    "\n"
    "    The server answers through /chat/completions, which wraps the prompt in that\n"
    "    template; training on raw text taught the adapter a context it never sees.\n"
    "    heldout_pairs.jsonl keeps the raw strings (see _training_row): the evaluation\n"
    "    tool sends them through the chat endpoint itself.\n"
    '    """\n'
    "    return {\n"
    '        "prompt": [{"role": "user", "content": pair["prompt"]}],\n'
    '        "chosen": [{"role": "assistant", "content": pair["chosen"]}],\n'
    '        "rejected": [{"role": "assistant", "content": pair["rejected"]}],\n'
    "    }\n",
)
s = nb_.replace_once(
    s,
    "train_dataset = Dataset.from_list([_training_row(pair) for pair, _ in train_items])",
    "train_dataset = Dataset.from_list([_chat_row(pair) for pair, _ in train_items])",
)
s = nb_.replace_once(
    s,
    "    eval_dataset = Dataset.from_list([_training_row(pair) for pair, _ in heldout_items])",
    "    eval_dataset = Dataset.from_list([_chat_row(pair) for pair, _ in heldout_items])",
)
nb_.put(nb, i, s)

# --- cell: trainer (early stop + chat-format guard) ---
i = nb_.find(nb, "trainer = DPOTrainer(")
s = nb_.get(nb, i)
s = nb_.replace_once(
    s,
    "from unsloth import is_bfloat16_supported\n",
    "from unsloth import is_bfloat16_supported\n"
    "from transformers import TrainerCallback\n"
    "\n\n"
    "class StopIfChosenCollapses(TrainerCallback):\n"
    '    """Stop early if the chosen reward falls too far below zero (a sign of overtraining).\n'
    "\n"
    "    See training/acceptance-thresholds.md: the chosen reward must stay above -5.\n"
    '    """\n'
    "\n"
    "    LIMIT = -5.0\n"
    "\n"
    "    def on_log(self, args, state, control, logs=None, **kwargs):\n"
    '        value = (logs or {}).get("rewards/chosen")\n'
    "        if isinstance(value, (int, float)) and value < self.LIMIT:\n"
    '            print(f"Stopping early: chosen reward {value:.1f} is below {self.LIMIT}.")\n'
    "            control.should_training_stop = True\n"
    "\n",
)
s = nb_.replace_once(
    s,
    "    processing_class=tokenizer,\n)\ntrainer.train()",
    "    processing_class=tokenizer,\n"
    "    callbacks=[StopIfChosenCollapses()],\n"
    ")\n"
    '_probe = tokenizer.decode(trainer.train_dataset[0]["prompt_input_ids"][:40])\n'
    'if "<start_of_turn>user" not in _probe:\n'
    "    raise RuntimeError(\n"
    '        "The training prompts are not in Gemma\'s chat format (no <start_of_turn>user "\n'
    '        f"at the start: {_probe!r}). Stopping before training."\n'
    "    )\n"
    'print("Chat-template check passed:", repr(_probe[:80]))\n'
    "trainer.train()",
)
nb_.put(nb, i, s)

# --- new rescue cell right after the trainer cell ---
nb_.insert_code_cell(
    nb,
    i + 1,
    "# Rescue cell: run ONLY if the training cell above ended with an out-of-memory error.\n"
    "# It frees GPU memory and saves the adapter that is already in memory.\n"
    "import gc, sys, torch\n"
    "sys.last_traceback = None; sys.last_value = None\n"
    "gc.collect(); torch.cuda.empty_cache()\n"
    "\n"
    "model.save_pretrained(ADAPTER_DIR)\n"
    "tokenizer.save_pretrained(ADAPTER_DIR)",
)

# --- header note ---
s = nb_.get(nb, 0)
s = s.rstrip("\n") + (
    "\n\n> **If training ends with an out-of-memory error:** run the rescue cell right "
    "below the training cell, then use Runtime > Run after on the cell after it.\n"
)
nb_.put(nb, 0, s)

nb_.save(nb)
print("done")
```

- [ ] **Step 4: Run the new tests**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_notebook_merge.py -q`
Expected: PASS. Then `git diff --stat docs/colab/dpo_training_template.ipynb` must show a small diff.

- [ ] **Step 5: Fix every index-based notebook test (+1 for old index 8 and up)**

Run: `grep -rnE "cells(\(\))?\[[0-9]+\]|_cell\([0-9]+\)|_helpers\([0-9]+\)" apps/server/tests/training_data training/tests`

For every hit whose index is 8 or higher, add 1 (for example `_cells()[17]` becomes `_cells()[18]`, `_cell(9)` becomes `_cell(10)`). Indices 0 to 7 stay. Also fix any docstrings or comments that name an index. Do not weaken any assertion.

Then run: `cd apps && uv run --project server pytest server/tests/training_data ../training/tests -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/colab/dpo_training_template.ipynb apps/server/tests/training_data training/tests
git commit -m "feat(colab): chat-format rows, early stop and OOM rescue cell in the template"
```

---

# SLICE B: Download notebook

### Task B1: Notebook builder

**Files:**
- Create: `apps/server/modules/training_data/notebook.py`
- Modify: `apps/server/modules/training_data/exceptions.py`
- Test: `apps/server/tests/training_data/test_notebook_builder.py`

**Interfaces:**
- Produces: `NotebookTemplateError(TrainingDataError)`; `TEMPLATE_PATH: Path`; `build_job_notebook(download_url: str, upload_url: str, *, template_path: Path = TEMPLATE_PATH) -> str` returns notebook JSON text with both placeholders replaced. (Task C2 adds a `status_url` keyword.)

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for filling a job's links into the notebook template."""

from __future__ import annotations

import json

import pytest
from server.modules.training_data.exceptions import NotebookTemplateError
from server.modules.training_data.notebook import TEMPLATE_PATH, build_job_notebook

DOWNLOAD = "https://app.example/api/v1/admin/training-data/jobs/j/download?token=aaa"
UPLOAD = "https://app.example/api/v1/admin/training-data/jobs/j/adapter?token=bbb"


def _links_cell(text: str) -> str:
    return "".join(json.loads(text)["cells"][1]["source"])


def test_fills_both_links_and_leaves_no_placeholder():
    cell = _links_cell(build_job_notebook(DOWNLOAD, UPLOAD))
    assert f'DOWNLOAD_URL = "{DOWNLOAD}"' in cell
    assert f'UPLOAD_URL = "{UPLOAD}"' in cell
    assert "PASTE_" not in cell


def test_every_other_cell_is_unchanged():
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    built = json.loads(build_job_notebook(DOWNLOAD, UPLOAD))
    assert len(built["cells"]) == len(template["cells"])
    for index, (a, b) in enumerate(zip(template["cells"], built["cells"])):
        if index != 1:
            assert a == b
    assert built["metadata"] == template["metadata"]


def test_output_is_valid_json_with_the_same_notebook_format():
    built = json.loads(build_job_notebook(DOWNLOAD, UPLOAD))
    assert built["nbformat"] == 4


def test_urls_with_quotes_are_escaped_not_injected():
    nasty = 'https://x/y?token="; import os #'
    cell = _links_cell(build_job_notebook(nasty, UPLOAD))
    compile(cell, "cell", "exec")  # still valid Python
    assert '\\"; import os #' in cell


def _write_template(tmp_path, source: str):
    path = tmp_path / "t.ipynb"
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": ["x"]},
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": source.splitlines(keepends=True),
            },
        ],
    }
    path.write_text(json.dumps(nb), encoding="utf-8")
    return path


def test_missing_placeholder_fails_loudly(tmp_path):
    path = _write_template(tmp_path, 'DOWNLOAD_URL = "PASTE_DOWNLOAD_URL_HERE"\n')
    with pytest.raises(NotebookTemplateError):
        build_job_notebook(DOWNLOAD, UPLOAD, template_path=path)


def test_duplicated_placeholder_fails_loudly(tmp_path):
    line = 'DOWNLOAD_URL = "PASTE_DOWNLOAD_URL_HERE"\n'
    path = _write_template(
        tmp_path, line + line + 'UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"\n'
    )
    with pytest.raises(NotebookTemplateError):
        build_job_notebook(DOWNLOAD, UPLOAD, template_path=path)


def test_unreadable_template_raises_template_error(tmp_path):
    with pytest.raises(NotebookTemplateError):
        build_job_notebook(DOWNLOAD, UPLOAD, template_path=tmp_path / "missing.ipynb")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_notebook_builder.py -q`
Expected: FAIL (ImportError: no `notebook` module / `NotebookTemplateError`).

- [ ] **Step 3: Implement**

Add to `exceptions.py` (after `GgufInUseError`):

```python
class NotebookTemplateError(TrainingDataError):
    """The Colab notebook template could not be read or filled in."""
```

Create `notebook.py`:

```python
"""apps/server/modules/training_data/notebook.py"""

from __future__ import annotations

import json
from pathlib import Path

from server.modules.training_data.exceptions import NotebookTemplateError

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATE_PATH = _PROJECT_ROOT / "docs" / "colab" / "dpo_training_template.ipynb"

_LINKS_CELL = 1
_DOWNLOAD_PLACEHOLDER = 'DOWNLOAD_URL = "PASTE_DOWNLOAD_URL_HERE"'
_UPLOAD_PLACEHOLDER = 'UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"'


def _fill(source: str, placeholder: str, name: str, value: str) -> str:
    if source.count(placeholder) != 1:
        raise NotebookTemplateError(
            f"the {name} placeholder must appear exactly once in the template"
        )
    return source.replace(placeholder, f"{name} = {json.dumps(value)}")


def build_job_notebook(
    download_url: str, upload_url: str, *, template_path: Path = TEMPLATE_PATH
) -> str:
    """Return the template notebook (JSON text) with this job's links filled in.

    Nothing is written to disk. The links hold one-time tokens, so the result
    must only be sent to the admin who just created the job.
    """
    try:
        notebook = json.loads(template_path.read_text(encoding="utf-8"))
        cell = notebook["cells"][_LINKS_CELL]
        source = "".join(cell["source"])
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise NotebookTemplateError("the notebook template could not be read") from exc

    source = _fill(source, _DOWNLOAD_PLACEHOLDER, "DOWNLOAD_URL", download_url)
    source = _fill(source, _UPLOAD_PLACEHOLDER, "UPLOAD_URL", upload_url)
    cell["source"] = source.splitlines(keepends=True)
    return json.dumps(notebook, indent=1)


__all__ = ["TEMPLATE_PATH", "NotebookTemplateError", "build_job_notebook"]
```

- [ ] **Step 4: Run to verify pass**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_notebook_builder.py -q && uv run --project server ruff check server/modules/training_data && uv run --project server ruff format --check server/modules/training_data`
Expected: PASS, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add apps/server/modules/training_data/notebook.py apps/server/modules/training_data/exceptions.py apps/server/tests/training_data/test_notebook_builder.py
git commit -m "feat(training-data): fill a job's links into the Colab notebook template"
```

### Task B2: Return the notebook when a run is started

**Files:**
- Modify: `apps/server/modules/training_data/schemas.py` (`TrainingJobCreateResponse`)
- Modify: `apps/server/modules/training_data/router.py` (`start_training_job`)
- Test: `apps/server/tests/training_data/test_router.py`

**Interfaces:**
- Consumes: `build_job_notebook` (B1).
- Produces: `TrainingJobCreateResponse` gains `notebook: str | None = None` and `notebook_filename: str | None = None`.

- [ ] **Step 1: Write the failing tests** (append to `test_router.py`)

```python
def test_start_job_returns_a_filled_notebook(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)

    body = client.post("/api/v1/admin/training-data/gad/jobs").json()

    notebook = json.loads(body["notebook"])
    cell = "".join(notebook["cells"][1]["source"])
    assert body["download_url"] in cell
    assert body["upload_url"] in cell
    assert "PASTE_" not in cell
    assert body["notebook_filename"] == (
        f"equiped-gad-run-{body['job_id'][:8]}.ipynb"
    )


def test_start_job_still_succeeds_when_the_notebook_cannot_be_built(
    client: TestClient, auth_cookies_admin, admin_user, db_session, monkeypatch
):
    from server.modules.training_data.exceptions import NotebookTemplateError

    def boom(*args, **kwargs):
        raise NotebookTemplateError("broken template")

    monkeypatch.setattr("server.modules.training_data.router.build_job_notebook", boom)
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)

    response = client.post("/api/v1/admin/training-data/gad/jobs")

    assert response.status_code == 201
    body = response.json()
    assert body["notebook"] is None
    assert body["notebook_filename"] is None
    assert "token=" in body["download_url"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_router.py -k "notebook" -q`
Expected: FAIL (`KeyError: 'notebook'`).

- [ ] **Step 3: Implement**

In `schemas.py`, extend `TrainingJobCreateResponse`:

```python
class TrainingJobCreateResponse(BaseModel):
    job_id: uuid.UUID
    agent_id: str
    status: str
    download_url: str
    upload_url: str
    download_expires_at: datetime
    upload_expires_at: datetime
    created_at: datetime
    notebook: str | None = None
    notebook_filename: str | None = None
```

In `router.py` add the import `from server.modules.training_data.notebook import build_job_notebook`, then replace the tail of `start_training_job` (from `return TrainingJobCreateResponse(` on):

```python
    download_url = _build_url(request, download_path)
    upload_url = _build_url(request, upload_path)

    notebook: str | None = None
    notebook_filename: str | None = None
    try:
        notebook = build_job_notebook(download_url, upload_url)
        notebook_filename = (
            f"equiped-{result.job.agent_id}-run-{str(result.job.job_id)[:8]}.ipynb"
        )
    except Exception:
        # The notebook is a convenience; the links alone are enough to train.
        logger.warning("could not build the training notebook", exc_info=True)
        notebook = None

    return TrainingJobCreateResponse(
        job_id=result.job.job_id,
        agent_id=result.job.agent_id,
        status=result.job.status,
        download_url=download_url,
        upload_url=upload_url,
        download_expires_at=result.job.download_expires_at,
        upload_expires_at=result.job.upload_expires_at,
        created_at=result.job.created_at,
        notebook=notebook,
        notebook_filename=notebook_filename,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_router.py -q && uv run --project server ruff check server/modules/training_data && uv run --project server ruff format --check server/modules/training_data`
Expected: PASS, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add apps/server/modules/training_data apps/server/tests/training_data/test_router.py
git commit -m "feat(training-data): return a ready-to-run notebook when a run is started"
```

### Task B3: Download notebook button

**Files:**
- Create: `apps/admin/src/features/training-data/utils/downloadTextFile.ts`
- Modify: `apps/admin/src/features/training-data/types.ts` (`TrainingJobCreateResponse`)
- Modify: `apps/admin/src/features/training-data/components/TrainingJobCredentials.tsx`
- Test: `apps/admin/src/features/training-data/components/__tests__/TrainingJobCredentials.test.tsx`

**Interfaces:**
- Produces: `downloadTextFile(filename: string, text: string, mime?: string): void`; `TrainingJobCreateResponse` gains `notebook?: string | null; notebook_filename?: string | null`.

- [ ] **Step 1: Write the failing tests** (add to `TrainingJobCredentials.test.tsx`; also add `vi.mock('../../utils/downloadTextFile');` at the top and `import { downloadTextFile } from '../../utils/downloadTextFile';`)

```tsx
  it('offers the filled notebook as a download when the server sent one', () => {
    const withNotebook = {
      ...credentials,
      notebook: '{"cells":[]}',
      notebook_filename: 'equiped-gad-run-12345678.ipynb',
    };
    render(<TrainingJobCredentials credentials={withNotebook} onSaved={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /download notebook/i }));
    expect(downloadTextFile).toHaveBeenCalledWith(
      'equiped-gad-run-12345678.ipynb',
      '{"cells":[]}',
    );
  });

  it('hides the download button when no notebook was built', () => {
    render(<TrainingJobCredentials credentials={credentials} onSaved={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /download notebook/i })).toBeNull();
  });
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/admin && npx vitest run src/features/training-data/components/__tests__/TrainingJobCredentials.test.tsx`
Expected: FAIL (module `downloadTextFile` not found).

- [ ] **Step 3: Implement**

`utils/downloadTextFile.ts`:

```ts
export function downloadTextFile(
  filename: string,
  text: string,
  mime = 'application/x-ipynb+json',
): void {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
```

In `types.ts`, add to `TrainingJobCreateResponse`:

```ts
  notebook?: string | null;
  notebook_filename?: string | null;
```

In `TrainingJobCredentials.tsx` import the util and add, inside the header block under the paragraph:

```tsx
        {credentials.notebook && credentials.notebook_filename ? (
          <div className="pt-1.5">
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                downloadTextFile(credentials.notebook_filename!, credentials.notebook!)
              }
            >
              Download notebook
            </Button>
            <p className="mt-1.5 text-xs leading-4 text-text-muted">
              Open it in Colab (File &gt; Upload notebook), choose the T4 GPU, then Run all.
              The file contains your single-use links, so do not share it.
            </p>
          </div>
        ) : null}
```

- [ ] **Step 4: Run to verify pass, format, lint**

Run: `cd apps/admin && npx prettier --single-quote --print-width 100 --trailing-comma all --end-of-line lf --write src/features/training-data/utils/downloadTextFile.ts src/features/training-data/components/TrainingJobCredentials.tsx src/features/training-data/components/__tests__/TrainingJobCredentials.test.tsx && npx vitest run src/features/training-data && npx eslint src/features/training-data`
Expected: PASS, no ESLint errors.

- [ ] **Step 5: Commit**

```bash
git add apps/admin/src/features/training-data
git commit -m "feat(admin): download a ready-to-run Colab notebook for a training run"
```

---

# SLICE C: Live status

### Task C1: Run record, status token and stage rules

**Files:**
- Modify: `apps/server/modules/training_data/models.py` (`DpoTrainingJob`)
- Create: `apps/server/alembic/versions/20261010_0001_add_run_status_to_training_jobs.py`
- Modify: `apps/server/modules/training_data/jobs.py`
- Test: `apps/server/tests/training_data/test_run_status.py`

**Interfaces:**
- Produces in `jobs.py`: `RUN_STAGES: tuple[str, ...]`; `TrainingJobCreated.raw_status_token: str`; `report_run_status(session, job_id, raw_token, stage, *, step=None, total=None, message=None) -> None` (raises `TrainingJobNotFoundError` for any bad token); `mark_run_stage(session, job_id, stage) -> None` (server-side, never raises).
- New columns on `DpoTrainingJob`: `status_token_hash`, `status_expires_at`, `run_stage`, `run_step`, `run_total`, `run_message`, `run_reported_at` (all nullable).

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the run-status record on training jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from server.modules.training_data.exceptions import TrainingJobNotFoundError
from server.modules.training_data.jobs import (
    create_training_job,
    mark_run_stage,
    report_run_status,
)
from server.modules.training_data.models import DpoTrainingJob
from server.modules.training_data.tokens import hash_token

from .conftest import seed_eligible_dpo_pair


@pytest.fixture
def created(db_session, admin_user):
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    return create_training_job(db_session, "gad", admin_user.user_id)


def _job(db_session, created) -> DpoTrainingJob:
    db_session.expire_all()
    return db_session.get(DpoTrainingJob, created.job.job_id)


def test_new_jobs_get_a_status_token_that_expires_with_the_upload_token(
    db_session, created
):
    job = _job(db_session, created)
    assert job.status_token_hash == hash_token(created.raw_status_token)
    assert job.status_expires_at is not None
    assert job.run_stage is None


def test_report_stores_stage_step_total_and_time(db_session, created):
    report_run_status(
        db_session,
        created.job.job_id,
        created.raw_status_token,
        "training",
        step=14,
        total=30,
    )
    job = _job(db_session, created)
    assert (job.run_stage, job.run_step, job.run_total) == ("training", 14, 30)
    assert job.run_reported_at is not None


def test_message_is_truncated_to_500_characters(db_session, created):
    report_run_status(
        db_session,
        created.job.job_id,
        created.raw_status_token,
        "failed",
        message="x" * 900,
    )
    assert len(_job(db_session, created).run_message) == 500


@pytest.mark.parametrize("bad", ["wrong", ""])
def test_wrong_token_is_rejected_as_not_found(db_session, created, bad):
    with pytest.raises(TrainingJobNotFoundError):
        report_run_status(db_session, created.job.job_id, bad, "training")


def test_unknown_job_is_rejected_as_not_found(db_session, created):
    with pytest.raises(TrainingJobNotFoundError):
        report_run_status(
            db_session, uuid.uuid4(), created.raw_status_token, "training"
        )


def test_expired_token_is_rejected(db_session, created):
    job = _job(db_session, created)
    job.status_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    with pytest.raises(TrainingJobNotFoundError):
        report_run_status(
            db_session, created.job.job_id, created.raw_status_token, "training"
        )


def test_old_job_without_a_status_token_cannot_report(db_session, created):
    job = _job(db_session, created)
    job.status_token_hash = None
    job.status_expires_at = None
    db_session.commit()
    with pytest.raises(TrainingJobNotFoundError):
        report_run_status(
            db_session, created.job.job_id, created.raw_status_token, "training"
        )


def test_stage_never_moves_backwards(db_session, created):
    mark_run_stage(db_session, created.job.job_id, "converting")
    report_run_status(
        db_session, created.job.job_id, created.raw_status_token, "training", step=3
    )
    assert _job(db_session, created).run_stage == "converting"


def test_same_stage_repeats_update_the_counter(db_session, created):
    for step in (1, 2):
        report_run_status(
            db_session,
            created.job.job_id,
            created.raw_status_token,
            "training",
            step=step,
            total=10,
        )
    assert _job(db_session, created).run_step == 2


def test_failed_is_recorded_but_not_after_finished(db_session, created):
    report_run_status(
        db_session, created.job.job_id, created.raw_status_token, "failed", message="OOM"
    )
    assert _job(db_session, created).run_stage == "failed"
    mark_run_stage(db_session, created.job.job_id, "finished")
    assert _job(db_session, created).run_stage == "finished"
    report_run_status(
        db_session, created.job.job_id, created.raw_status_token, "failed", message="late"
    )
    assert _job(db_session, created).run_stage == "finished"


def test_a_run_can_restart_after_failing(db_session, created):
    report_run_status(
        db_session, created.job.job_id, created.raw_status_token, "failed"
    )
    report_run_status(
        db_session, created.job.job_id, created.raw_status_token, "training", step=1
    )
    assert _job(db_session, created).run_stage == "training"


def test_mark_run_stage_never_raises_for_an_unknown_job(db_session):
    mark_run_stage(db_session, uuid.uuid4(), "finished")  # must not raise
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_run_status.py -q`
Expected: FAIL (ImportError: `mark_run_stage`).

- [ ] **Step 3: Add the columns and migration**

In `models.py`, add to `DpoTrainingJob` after `upload_used_at`:

```python
    status_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    run_stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    run_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_reported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

Create `20261010_0001_add_run_status_to_training_jobs.py`:

```python
"""Add run-status columns and a status token to dpo_training_jobs.

Revision ID: 20261010_0001
Revises: 20261006_0001
Create Date: 2026-10-10 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261010_0001"
down_revision: str | None = "20261006_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    sa.Column("status_token_hash", sa.String(64), nullable=True),
    sa.Column("status_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("run_stage", sa.String(24), nullable=True),
    sa.Column("run_step", sa.Integer(), nullable=True),
    sa.Column("run_total", sa.Integer(), nullable=True),
    sa.Column("run_message", sa.Text(), nullable=True),
    sa.Column("run_reported_at", sa.DateTime(timezone=True), nullable=True),
)


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column("dpo_training_jobs", column.copy())


def downgrade() -> None:
    for column in reversed(_COLUMNS):
        op.drop_column("dpo_training_jobs", column.name)
```

- [ ] **Step 4: Implement the service in `jobs.py`**

Add imports `import logging`, `import secrets`, and add `logger = logging.getLogger(__name__)` below the imports. Add after `_UPLOAD_TOKEN_LIFETIME`:

```python
_STATUS_TOKEN_LIFETIME = _UPLOAD_TOKEN_LIFETIME
_RUN_STAGE_ORDER = {
    "starting": 0,
    "training": 1,
    "sending_model": 2,
    "converting": 3,
    "sending_file": 4,
    "finished": 5,
}
RUN_STAGES = (*_RUN_STAGE_ORDER, "failed")
_MESSAGE_LIMIT = 500
```

Extend the dataclass and `create_training_job`:

```python
@dataclass(frozen=True, slots=True)
class TrainingJobCreated:
    job: DpoTrainingJob
    raw_download_token: str
    raw_upload_token: str
    raw_status_token: str
```

In `create_training_job`: add `raw_status_token = generate_raw_token()`, add to the `DpoTrainingJob(...)` call

```python
        status_token_hash=hash_token(raw_status_token),
        status_expires_at=now + _STATUS_TOKEN_LIFETIME,
```

and `raw_status_token=raw_status_token` in the returned `TrainingJobCreated`. Add the new service functions before `list_training_jobs`:

```python
def _apply_run_stage(
    job: DpoTrainingJob,
    stage: str,
    *,
    step: int | None,
    total: int | None,
    message: str | None,
    now: datetime,
) -> bool:
    """Apply a stage if it is allowed; return whether anything changed."""
    current = job.run_stage
    if current == "finished":
        return False
    if (
        stage != "failed"
        and current in _RUN_STAGE_ORDER
        and _RUN_STAGE_ORDER[stage] < _RUN_STAGE_ORDER[current]
    ):
        return False
    job.run_stage = stage
    job.run_step = step
    job.run_total = total
    job.run_message = message[:_MESSAGE_LIMIT] if message else None
    job.run_reported_at = now
    return True


def _verify_status_token(job: DpoTrainingJob, raw_token: str) -> bool:
    if not job.status_token_hash or job.status_expires_at is None:
        return False
    if _utc(job.status_expires_at) < datetime.now(UTC):
        return False
    return secrets.compare_digest(job.status_token_hash, hash_token(raw_token))


def report_run_status(
    session: Session,
    job_id: uuid.UUID,
    raw_token: str,
    stage: str,
    *,
    step: int | None = None,
    total: int | None = None,
    message: str | None = None,
) -> None:
    """Record a progress report from the notebook. Raises
    TrainingJobNotFoundError for any invalid-token condition (map to 404)."""
    job = session.get(DpoTrainingJob, job_id)
    if job is None or not _verify_status_token(job, raw_token):
        raise TrainingJobNotFoundError("invalid or expired status token")
    if _apply_run_stage(
        job, stage, step=step, total=total, message=message, now=datetime.now(UTC)
    ):
        session.commit()


def mark_run_stage(session: Session, job_id: uuid.UUID, stage: str) -> None:
    """Server-observed stage (adapter or GGUF stored). Never raises: a status
    problem must not turn a stored upload into an error."""
    try:
        job = session.get(DpoTrainingJob, job_id)
        if job is not None and _apply_run_stage(
            job,
            stage,
            step=None,
            total=None,
            message=None,
            now=datetime.now(UTC),
        ):
            session.commit()
    except Exception:
        logger.warning("could not record run stage %s", stage, exc_info=True)
        try:
            session.rollback()
        except Exception:
            logger.warning("rollback failed", exc_info=True)
```

Add `"RUN_STAGES"`, `"mark_run_stage"`, `"report_run_status"` to `__all__`.

- [ ] **Step 5: Run tests, migration SQL check, lint**

Run:
```
cd apps && uv run --project server pytest server/tests/training_data -q
cd server && uv run alembic upgrade 20261006_0001:head --sql | tail -20
cd .. && uv run --project server ruff check server/modules/training_data server/alembic && uv run --project server ruff format --check server/modules/training_data server/alembic
```
Expected: tests PASS; the SQL output shows seven `ALTER TABLE dpo_training_jobs ADD COLUMN ...` lines and an `UPDATE alembic_version` to `20261010_0001`; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add apps/server/modules/training_data apps/server/alembic apps/server/tests/training_data/test_run_status.py
git commit -m "feat(training-data): record run status and issue a status token per job"
```

### Task C2: Status endpoint, server-observed stages, list fields, notebook status link

**Files:**
- Modify: `schemas.py`, `router.py`, `notebook.py`
- Test: `tests/training_data/test_run_status_api.py`, `tests/training_data/test_notebook_builder.py`

**Interfaces:**
- Consumes: `report_run_status`, `mark_run_stage`, `TrainingJobCreated.raw_status_token` (C1).
- Produces: `RunStatusRequest` schema; `POST /admin/training-data/jobs/{job_id}/status?token=` returning 204; `TrainingJobListItem` gains `run_stage`, `run_step`, `run_total`, `run_message`, `run_reported_at`, `seconds_since_report`; `build_job_notebook(..., status_url: str | None = None)` which fills a `STATUS_URL = ""` line when `status_url` is given (that line is added to the template in Task C3).

- [ ] **Step 1: Write the failing tests**

`tests/training_data/test_run_status_api.py`:

```python
"""HTTP tests for run status reporting and its server-observed stages."""

from __future__ import annotations

import io
import json
import uuid
import zipfile

from fastapi.testclient import TestClient
from server.modules.training_data.jobs import create_training_job
from server.modules.training_data.models import DpoTrainingJob
from server.tests.admin.conftest import _auth

from .conftest import make_adapter, seed_eligible_dpo_pair

BASE = "/api/v1/admin/training-data"


def _created(db_session, admin_user):
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    return create_training_job(db_session, "gad", admin_user.user_id)


def _post(client, created, body, token=None):
    token = created.raw_status_token if token is None else token
    return client.post(
        f"{BASE}/jobs/{created.job.job_id}/status?token={token}", json=body
    )


def test_status_post_needs_no_login_but_a_valid_token(
    client: TestClient, db_session, admin_user
):
    created = _created(db_session, admin_user)
    ok = _post(client, created, {"stage": "training", "step": 4, "total": 30})
    assert ok.status_code == 204
    assert _post(client, created, {"stage": "training"}, token="nope").status_code == 404


def test_status_post_rejects_unknown_stage_and_bad_numbers(
    client: TestClient, db_session, admin_user
):
    created = _created(db_session, admin_user)
    for body in (
        {"stage": "exploding"},
        {"stage": "training", "step": -1},
        {"stage": "training", "step": 5, "total": 3},
        {"stage": "training", "total": 0},
        {"stage": "failed", "message": "x" * 501},
    ):
        assert _post(client, created, body).status_code == 422, body


def test_a_token_for_one_job_does_not_work_on_another(
    client: TestClient, db_session, admin_user
):
    first = _created(db_session, admin_user)
    second = create_training_job(db_session, "gad", admin_user.user_id)
    response = client.post(
        f"{BASE}/jobs/{second.job.job_id}/status?token={first.raw_status_token}",
        json={"stage": "training"},
    )
    assert response.status_code == 404


def test_jobs_list_shows_progress_and_age(
    client: TestClient, auth_cookies_admin, db_session, admin_user
):
    created = _created(db_session, admin_user)
    _post(client, created, {"stage": "training", "step": 14, "total": 30})
    _auth(client, auth_cookies_admin)

    item = client.get(f"{BASE}/gad/jobs").json()["jobs"][0]

    assert item["run_stage"] == "training"
    assert (item["run_step"], item["run_total"]) == (14, 30)
    assert 0 <= item["seconds_since_report"] < 60


def test_jobs_list_for_a_job_with_no_report_has_null_progress(
    client: TestClient, auth_cookies_admin, db_session, admin_user
):
    _created(db_session, admin_user)
    _auth(client, auth_cookies_admin)
    item = client.get(f"{BASE}/gad/jobs").json()["jobs"][0]
    assert item["run_stage"] is None
    assert item["seconds_since_report"] is None


def _adapter_zip(manifest: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("adapter_config.json", json.dumps({"base_model_name_or_path": "m"}))
        zf.writestr(
            "training_manifest.json", json.dumps({"source_job_manifest": manifest})
        )
        zf.writestr("adapter_model.safetensors", b"w")
    return buffer.getvalue()


def test_adapter_upload_marks_the_job_converting(
    client: TestClient, auth_cookies_admin, admin_user, db_session, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT", tmp_path
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)
    body = client.post(f"{BASE}/gad/jobs").json()
    job = db_session.get(DpoTrainingJob, uuid.UUID(body["job_id"]))
    upload_path = body["upload_url"].split("/api/v1", 1)[1]
    client.cookies.clear()

    response = client.post(
        f"/api/v1{upload_path}",
        files={"file": ("adapter.zip", _adapter_zip(job.manifest_json), "application/zip")},
    )

    assert response.status_code == 201
    db_session.expire_all()
    assert db_session.get(DpoTrainingJob, job.job_id).run_stage == "converting"


def test_gguf_upload_marks_the_job_finished(
    client: TestClient, auth_cookies_admin, admin_user, db_session, fake_storage, monkeypatch
):
    monkeypatch.setattr(
        "server.modules.training_data.gguf_files.get_storage_backend",
        lambda: fake_storage,
    )
    adapter = make_adapter(db_session, "sme", 1)
    _auth(client, auth_cookies_admin)

    response = client.post(
        f"{BASE}/sme/adapters/{adapter.adapter_id}/gguf",
        files={"file": ("a.gguf", b"GGUF" + b"x" * 100, "application/octet-stream")},
    )

    assert response.status_code == 201
    db_session.expire_all()
    assert db_session.get(DpoTrainingJob, adapter.job_id).run_stage == "finished"
```

Append to `tests/training_data/test_notebook_builder.py`:

```python
STATUS = "https://app.example/api/v1/admin/training-data/jobs/j/status?token=ccc"


def test_status_link_is_filled_when_given():
    cell = _links_cell(build_job_notebook(DOWNLOAD, UPLOAD, status_url=STATUS))
    assert f'STATUS_URL = "{STATUS}"' in cell


def test_status_link_stays_empty_when_not_given():
    cell = _links_cell(build_job_notebook(DOWNLOAD, UPLOAD))
    assert 'STATUS_URL = ""' in cell
```

(These two tests need the template line from Task C3. Add them now, expect them to fail until C3 Step 4, and mark that in the C2 commit message. If you prefer strict ordering, run C3 Steps 1-4 before C2 Step 5.)

- [ ] **Step 2: Run to verify failure**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_run_status_api.py -q`
Expected: FAIL (404 for the status route / missing fields).

- [ ] **Step 3: Implement schemas**

In `schemas.py` add `Field` and `model_validator` to the pydantic import and define:

```python
RunStage = Literal[
    "starting",
    "training",
    "sending_model",
    "converting",
    "sending_file",
    "finished",
    "failed",
]


class RunStatusRequest(BaseModel):
    stage: RunStage
    step: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=1)
    message: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _step_within_total(self) -> RunStatusRequest:
        if self.step is not None and self.total is not None and self.step > self.total:
            raise ValueError("step cannot be greater than total")
        return self
```

Extend `TrainingJobListItem` with these optional fields and fill them in `from_job`:

```python
    run_stage: str | None = None
    run_step: int | None = None
    run_total: int | None = None
    run_message: str | None = None
    run_reported_at: datetime | None = None
    seconds_since_report: int | None = None
```

In `from_job`, before `return cls(...)`:

```python
        reported = getattr(job, "run_reported_at", None)
        seconds_since: int | None = None
        if reported is not None:
            if reported.tzinfo is None:
                reported = reported.replace(tzinfo=UTC)
            seconds_since = max(0, int((datetime.now(UTC) - reported).total_seconds()))
```

and pass `run_stage=getattr(job, "run_stage", None)`, `run_step=...`, `run_total=...`, `run_message=...`, `run_reported_at=reported`, `seconds_since_report=seconds_since`. Add `UTC` to the `datetime` import.

- [ ] **Step 4: Implement the router changes**

Add `RunStatusRequest` to the schemas import and `mark_run_stage, report_run_status` to the `jobs` import in `router.py`.

New endpoint (next to the other job-token routes):

```python
@router.post("/jobs/{job_id}/status", status_code=status.HTTP_204_NO_CONTENT)
def report_training_status(
    job_id: uuid.UUID,
    body: RunStatusRequest,
    token: str = Query(...),
    db: Session = Depends(get_db_session),
) -> Response:
    try:
        report_run_status(
            db,
            job_id,
            token,
            body.stage,
            step=body.step,
            total=body.total,
            message=body.message,
        )
    except TrainingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

In `start_training_job`, build the status link and pass it to the notebook builder:

```python
    status_path = (
        f"/admin/training-data/jobs/{result.job.job_id}/status"
        f"?token={result.raw_status_token}"
    )
    status_url = _build_url(request, status_path)
    ...
        notebook = build_job_notebook(download_url, upload_url, status_url=status_url)
```

In `upload_trained_adapter`, immediately before the final `return TrainedAdapterUploadResponse(...)`:

```python
    mark_run_stage(db, job_id, "converting")
```

In both `upload_gguf_with_token` and `upload_gguf_as_admin`, after `store_gguf(...)` succeeds and before the `return`:

```python
    mark_run_stage(db, adapter.job_id, "finished")
```

In `notebook.py` add the constants and the parameter:

```python
_STATUS_PLACEHOLDER = 'STATUS_URL = ""'

def build_job_notebook(
    download_url: str,
    upload_url: str,
    *,
    status_url: str | None = None,
    template_path: Path = TEMPLATE_PATH,
) -> str:
    ...
    if status_url is not None:
        source = _fill(source, _STATUS_PLACEHOLDER, "STATUS_URL", status_url)
```

(Place the `status_url` fill right after the upload fill.)

- [ ] **Step 5: Run tests and lint**

Run: `cd apps && uv run --project server pytest server/tests/training_data -q && uv run --project server ruff check server/modules/training_data && uv run --project server ruff format --check server/modules/training_data`
Expected: PASS (the two status-link builder tests pass once Task C3 added the template line; if running C2 before C3, only those two fail and are fixed in C3). Ruff clean.

- [ ] **Step 6: Commit**

```bash
git add apps/server/modules/training_data apps/server/tests/training_data
git commit -m "feat(training-data): add the status endpoint, server-observed stages and list fields"
```

### Task C3: Notebook status reporting

**Files:**
- Modify: `docs/colab/dpo_training_template.ipynb`
- Create: `apps/server/tests/training_data/test_notebook_status.py`
- Modify: `apps/server/tests/training_data/test_notebook_gguf_upload.py` (inject a recording `report`)

**Interfaces:**
- Consumes: placeholder lines `UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"` (cell 1), `trainer = DPOTrainer(` cell, `upload_response = requests.post(` cell, `def conversion_step(name):` cell, `with conversion_step("upload the GGUF to EquipED"):` cell.
- Produces: cell 1 defines `STATUS_URL = ""` and `report(stage, step=None, total=None, message=None)`; the training cell defines `class ReportTrainingProgress(TrainerCallback)`.

- [ ] **Step 1: Write the failing tests**

```python
"""Checks for the notebook's status reporting (no Colab, no network)."""

from __future__ import annotations

import ast
import json
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
NOTEBOOK_PATH = REPO_ROOT / "docs" / "colab" / "dpo_training_template.ipynb"
START = "# --- status helper (tested) ---"
END = "# --- end status helper ---"


def _cells() -> list[str]:
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in nb["cells"]]


def _find(marker: str) -> str:
    hits = [s for s in _cells() if marker in s]
    assert len(hits) == 1, (marker, len(hits))
    return hits[0]


class _FakeRequests(types.ModuleType):
    def __init__(self, raises=False):
        super().__init__("requests")
        self.calls: list[dict] = []
        self.raises = raises

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if self.raises:
            raise RuntimeError("network down")


def _report(monkeypatch, status_url, *, raises=False):
    source = _find(START)
    block = source[source.index(START) : source.index(END)]
    fake = _FakeRequests(raises=raises)
    monkeypatch.setitem(sys.modules, "requests", fake)
    namespace = {"STATUS_URL": status_url}
    exec(block, namespace)  # noqa: S102
    return namespace["report"], fake


def test_report_posts_stage_step_total_with_a_short_timeout(monkeypatch):
    report, fake = _report(monkeypatch, "https://app/status?token=t")
    report("training", step=14, total=30)
    assert fake.calls == [
        {
            "url": "https://app/status?token=t",
            "json": {"stage": "training", "step": 14, "total": 30},
            "timeout": 5,
        }
    ]


def test_report_does_nothing_without_a_status_link(monkeypatch):
    for value in ("", "PASTE_ME", None):
        report, fake = _report(monkeypatch, value)
        report("training")
        assert fake.calls == []


def test_report_swallows_network_errors(monkeypatch):
    report, fake = _report(monkeypatch, "https://app/status?token=t", raises=True)
    report("failed", message="boom")  # must not raise
    assert len(fake.calls) == 1


def test_report_truncates_long_messages(monkeypatch):
    report, fake = _report(monkeypatch, "https://app/status?token=t")
    report("failed", message="x" * 900)
    assert len(fake.calls[0]["json"]["message"]) == 500


def test_links_cell_declares_the_status_link_and_reports_start():
    cell = _find(START)
    assert 'STATUS_URL = ""' in cell
    assert cell.rstrip().endswith('report("starting")')


def _progress_class(clock):
    source = _find("class ReportTrainingProgress")
    tree = ast.parse(source)
    node = next(
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "ReportTrainingProgress"
    )
    sent: list[tuple] = []
    namespace = {
        "TrainerCallback": object,
        "time": types.SimpleNamespace(monotonic=clock),
        "report": lambda stage, **kw: sent.append((stage, kw)),
    }
    exec(ast.get_source_segment(source, node), namespace)  # noqa: S102
    return namespace["ReportTrainingProgress"], sent


def test_progress_callback_throttles_to_one_post_per_30_seconds():
    now = [100.0]
    cls, sent = _progress_class(lambda: now[0])
    callback = cls()
    state = types.SimpleNamespace(global_step=3, max_steps=30)
    callback.on_log(None, state, None)
    now[0] = 110.0
    callback.on_log(None, state, None)
    now[0] = 131.0
    state.global_step = 9
    callback.on_log(None, state, None)
    assert sent == [
        ("training", {"step": 3, "total": 30}),
        ("training", {"step": 9, "total": 30}),
    ]


def test_trainer_cell_wires_progress_and_reports_a_failed_training():
    cell = _find("trainer = DPOTrainer(")
    assert "ReportTrainingProgress()" in cell
    assert 'report("failed"' in cell


def test_upload_cell_reports_before_posting_the_adapter():
    cell = _find("upload_response = requests.post(")
    assert cell.index('report("sending_model")') < cell.index("upload_response = requests")


def test_conversion_failures_are_reported_without_masking_the_error():
    cell = _find("def conversion_step(name):")
    assert 'globals().get("report")' in cell
    assert '"failed"' in cell


def test_gguf_upload_cell_reports_sending_file_first():
    cell = _find('with conversion_step("upload the GGUF to EquipED"):')
    assert cell.startswith('report("sending_file")')
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_notebook_status.py -q`
Expected: FAIL (`AssertionError: ... len(hits) == 0`).

- [ ] **Step 3: Edit the notebook**

Create `edit_c3.py` outside the repo and run it from the repo root:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nbedit as nb_

nb = nb_.load()

# --- links cell: STATUS_URL line + report helper + first report ---
i = nb_.find(nb, 'UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"')
s = nb_.get(nb, i)
s = nb_.replace_once(
    s,
    'UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"\n',
    'UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"\nSTATUS_URL = ""\n',
)
s = s.rstrip("\n") + (
    "\n\n"
    "# --- status helper (tested) ---\n"
    "def report(stage, step=None, total=None, message=None):\n"
    '    """Tell EquipED where this run is. Never raises; does nothing without STATUS_URL."""\n'
    '    if not isinstance(STATUS_URL, str) or not STATUS_URL.startswith(\n'
    '            ("http://", "https://")):\n'
    "        return\n"
    "    try:\n"
    "        import requests\n"
    "\n"
    '        body = {"stage": stage}\n'
    "        if step is not None:\n"
    '            body["step"] = int(step)\n'
    "        if total is not None:\n"
    '            body["total"] = int(total)\n'
    "        if message:\n"
    '            body["message"] = str(message)[:500]\n'
    "        requests.post(STATUS_URL, json=body, timeout=5)\n"
    "    except Exception:\n"
    "        pass\n"
    "# --- end status helper ---\n"
    "\n"
    'report("starting")'
)
nb_.put(nb, i, s)

# --- training cell: progress callback, wiring, failure report ---
i = nb_.find(nb, "trainer = DPOTrainer(")
s = nb_.get(nb, i)
s = nb_.replace_once(
    s,
    "from transformers import TrainerCallback\n",
    "import time\n\nfrom transformers import TrainerCallback\n",
)
s = nb_.replace_once(
    s,
    "\n\nclass StopIfChosenCollapses(TrainerCallback):",
    "\n\nclass ReportTrainingProgress(TrainerCallback):\n"
    '    """Tell EquipED how far training has got, at most once every 30 seconds."""\n'
    "\n"
    "    INTERVAL_SECONDS = 30\n"
    "\n"
    "    def __init__(self):\n"
    "        self._last = None\n"
    "\n"
    "    def on_log(self, args, state, control, logs=None, **kwargs):\n"
    "        now = time.monotonic()\n"
    "        if self._last is not None and now - self._last < self.INTERVAL_SECONDS:\n"
    "            return\n"
    "        self._last = now\n"
    '        report("training", step=state.global_step, total=state.max_steps)\n'
    "\n\nclass StopIfChosenCollapses(TrainerCallback):",
)
s = nb_.replace_once(
    s,
    "callbacks=[StopIfChosenCollapses()],",
    "callbacks=[StopIfChosenCollapses(), ReportTrainingProgress()],",
)
s = nb_.replace_once(
    s,
    "trainer.train()",
    "try:\n"
    "    trainer.train()\n"
    "except BaseException as _exc:\n"
    '    report("failed", message=f"training stopped: {type(_exc).__name__}")\n'
    "    raise",
)
nb_.put(nb, i, s)

# --- adapter upload cell ---
i = nb_.find(nb, "upload_response = requests.post(")
s = nb_.get(nb, i)
s = nb_.replace_once(
    s,
    "# POST to upload URL only after validating output files\n",
    '# POST to upload URL only after validating output files\nreport("sending_model")\n',
)
nb_.put(nb, i, s)

# --- conversion_step: report a failure without ever masking the real error ---
i = nb_.find(nb, "def conversion_step(name):")
s = nb_.get(nb, i)
s = nb_.replace_once(
    s,
    "    except Exception:\n        print(\n            f\"\\nGGUF conversion step",
    "    except Exception:\n"
    '        _report = globals().get("report")\n'
    "        if callable(_report):\n"
    '            _report("failed", message=f"GGUF step \'{name}\' failed")\n'
    "        print(\n            f\"\\nGGUF conversion step",
)
nb_.put(nb, i, s)

# --- GGUF upload cell ---
i = nb_.find(nb, 'with conversion_step("upload the GGUF to EquipED"):')
s = nb_.get(nb, i)
nb_.put(nb, i, 'report("sending_file")\n\n' + s)

nb_.save(nb)
print("done")
```

- [ ] **Step 4: Update the GGUF-cell harness and the A2 test, then run everything**

In `test_notebook_merge.py` (Task A2), `test_trainer_cell_wires_the_callback_and_the_chat_format_guard` asserts the exact text `callbacks=[StopIfChosenCollapses()]`. This task changes that line to `callbacks=[StopIfChosenCollapses(), ReportTrainingProgress()],`. Change the assertion to `assert "StopIfChosenCollapses()" in source` (keep the other two assertions). Do not delete the test.

In `test_notebook_gguf_upload.py`, wherever the last cell is executed (search for the `exec(` that runs `_last_cell()`), add to its namespace a recorder: `"report": lambda stage, **kw: reported.append(stage)` with `reported: list[str] = []` in the test helper, and add one test asserting `reported[0] == "sending_file"`. Keep every existing assertion.

Run: `cd apps && uv run --project server pytest server/tests/training_data ../training/tests -q`
Expected: all PASS, including the two status-link builder tests from C2. `git diff --stat docs/colab/dpo_training_template.ipynb` stays small.

- [ ] **Step 5: Commit**

```bash
git add docs/colab/dpo_training_template.ipynb apps/server/tests/training_data
git commit -m "feat(colab): report run status (stage, step counter, failures) to EquipED"
```

### Task C4: Show live status in the Training runs table

**Files:**
- Modify: `apps/admin/src/features/training-data/types.ts` (`TrainingJobItem`)
- Modify: `apps/admin/src/features/training-data/utils/trainingData.utils.ts`
- Modify: `apps/admin/src/features/training-data/components/TrainingJobRow.tsx`
- Modify: `apps/admin/src/features/training-data/hooks/useTrainingJobs.ts`
- Tests: `utils/__tests__/trainingData.utils.test.ts`, `components/__tests__/TrainingJobsPanel.test.tsx`, new `hooks/__tests__/useTrainingJobs.test.ts`

**Interfaces:**
- Produces: `TrainingJobItem` gains optional `run_stage`, `run_step`, `run_total`, `run_message`, `run_reported_at`, `seconds_since_report`; utils `STALE_AFTER_SECONDS`, `isRunActive(job)`, `describeRunProgress(job)` returning `{ label: string; detail: string | null; stale: boolean; failed: boolean } | null`.

- [ ] **Step 1: Write the failing tests**

Add to `trainingData.utils.test.ts`:

```ts
import { describeRunProgress, isRunActive, STALE_AFTER_SECONDS } from '../trainingData.utils';

const base = { job_id: 'j', agent_id: 'sme', status: 'downloaded' as const, created_at: '2026-10-10T00:00:00Z' };

describe('describeRunProgress', () => {
  it('returns null for runs without a reported stage', () => {
    expect(describeRunProgress(base)).toBeNull();
    expect(isRunActive(base)).toBe(false);
  });

  it('shows the step counter while training', () => {
    const p = describeRunProgress({ ...base, run_stage: 'training', run_step: 14, run_total: 30, seconds_since_report: 120 });
    expect(p).toEqual({ label: 'Training', detail: 'step 14 of 30 · updated 2 min ago', stale: false, failed: false });
  });

  it('flags a quiet active run as stale after 15 minutes', () => {
    const p = describeRunProgress({ ...base, run_stage: 'training', seconds_since_report: STALE_AFTER_SECONDS });
    expect(p?.stale).toBe(true);
  });

  it('never marks finished or failed runs stale', () => {
    for (const run_stage of ['finished', 'failed']) {
      const p = describeRunProgress({ ...base, run_stage, seconds_since_report: 99999 });
      expect(p?.stale).toBe(false);
      expect(isRunActive({ ...base, run_stage })).toBe(false);
    }
  });

  it('shows the failure reason', () => {
    const p = describeRunProgress({ ...base, run_stage: 'failed', run_message: 'OOM', seconds_since_report: 5 });
    expect(p).toMatchObject({ label: 'Failed', failed: true });
    expect(p?.detail).toContain('OOM');
  });

  it('says just now for fresh reports and hours for old ones', () => {
    expect(describeRunProgress({ ...base, run_stage: 'converting', seconds_since_report: 10 })?.detail).toBe('updated just now');
    expect(describeRunProgress({ ...base, run_stage: 'converting', seconds_since_report: 7300 })?.detail).toBe('updated 2 h ago');
  });
});
```

Add to `TrainingJobsPanel.test.tsx`:

```tsx
  it('shows the live stage, counter and a disconnect warning', () => {
    renderJobs([
      { ...job, job_id: 'a', status: 'downloaded', run_stage: 'training', run_step: 14, run_total: 30, seconds_since_report: 120 },
      { ...job, job_id: 'b', status: 'downloaded', run_stage: 'training', run_step: 2, run_total: 30, seconds_since_report: 1000 },
    ]);
    expect(screen.getAllByText('Training')).toHaveLength(2);
    expect(screen.getByText(/step 14 of 30/)).toBeDefined();
    expect(screen.getAllByText(/colab may have disconnected/i)).toHaveLength(1);
  });

  it('falls back to the old status for runs without a stage', () => {
    renderJobs([{ ...job, status: 'pending' }]);
    expect(screen.getByText('Waiting to start')).toBeDefined();
  });
```

New `hooks/__tests__/useTrainingJobs.test.ts` (test the pure interval function by exporting it):

```ts
import { describe, expect, it } from 'vitest';
import { jobsRefetchInterval } from '../useTrainingJobs';

const data = (stages: (string | undefined)[]) => ({
  agent_id: 'sme',
  jobs: stages.map((run_stage, i) => ({ job_id: String(i), agent_id: 'sme', status: 'downloaded', created_at: 'x', run_stage })),
});

describe('jobsRefetchInterval', () => {
  it('polls every 10 seconds while a run is active', () => {
    expect(jobsRefetchInterval(data(['finished', 'training']) as never)).toBe(10_000);
  });
  it('stops polling when nothing is active', () => {
    expect(jobsRefetchInterval(data(['finished', 'failed', undefined]) as never)).toBe(false);
    expect(jobsRefetchInterval(undefined)).toBe(false);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/admin && npx vitest run src/features/training-data`
Expected: FAIL (missing exports).

- [ ] **Step 3: Implement**

`types.ts`: add to `TrainingJobItem`:

```ts
  run_stage?: string | null;
  run_step?: number | null;
  run_total?: number | null;
  run_message?: string | null;
  run_reported_at?: string | null;
  seconds_since_report?: number | null;
```

`trainingData.utils.ts` (import `TrainingJobItem` in the type import):

```ts
export const STALE_AFTER_SECONDS = 15 * 60;

const RUN_STAGE_LABELS: Record<string, string> = {
  starting: 'Starting',
  training: 'Training',
  sending_model: 'Sending model',
  converting: 'Converting file',
  sending_file: 'Sending file',
  finished: 'Finished',
  failed: 'Failed',
};

export function isRunActive(job: Pick<TrainingJobItem, 'run_stage'>): boolean {
  return !!job.run_stage && job.run_stage !== 'finished' && job.run_stage !== 'failed';
}

function formatAge(seconds: number): string {
  if (seconds < 60) return 'updated just now';
  if (seconds < 3600) return `updated ${Math.floor(seconds / 60)} min ago`;
  return `updated ${Math.floor(seconds / 3600)} h ago`;
}

export interface RunProgress {
  label: string;
  detail: string | null;
  stale: boolean;
  failed: boolean;
}

export function describeRunProgress(job: TrainingJobItem): RunProgress | null {
  if (!job.run_stage) return null;
  const parts: string[] = [];
  if (job.run_stage === 'training' && job.run_step != null && job.run_total != null) {
    parts.push(`step ${job.run_step} of ${job.run_total}`);
  }
  if (job.run_stage === 'failed' && job.run_message) parts.push(job.run_message);
  if (job.seconds_since_report != null) parts.push(formatAge(job.seconds_since_report));
  return {
    label: RUN_STAGE_LABELS[job.run_stage] ?? job.run_stage,
    detail: parts.length > 0 ? parts.join(' · ') : null,
    stale: isRunActive(job) && (job.seconds_since_report ?? 0) >= STALE_AFTER_SECONDS,
    failed: job.run_stage === 'failed',
  };
}
```

`useTrainingJobs.ts`:

```ts
import { useQuery } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';
import type { TrainingJobListResponse } from '../types';
import { isRunActive } from '../utils/trainingData.utils';

export function jobsRefetchInterval(data: TrainingJobListResponse | undefined): number | false {
  return data?.jobs.some(isRunActive) ? 10_000 : false;
}

export function useTrainingJobs(agentId: string) {
  return useQuery({
    queryKey: ['trainingJobs', agentId],
    queryFn: () => trainingDataApi.listJobs(agentId),
    refetchInterval: (query) => jobsRefetchInterval(query.state.data),
    refetchIntervalInBackground: false,
  });
}
```

`TrainingJobRow.tsx`: replace the `status` badge cell content so the badge shows the live label when present, with a detail line and a stale warning:

```tsx
  const progress = describeRunProgress(job);
  ...
        <td className="px-4 py-2">
          <Badge
            variant={progress?.failed ? 'danger' : status.variant}
            className="whitespace-normal tracking-normal"
          >
            {progress ? progress.label : status.label}
          </Badge>
          {progress?.detail ? (
            <span className="mt-1 block text-xs leading-4 text-text-muted">{progress.detail}</span>
          ) : null}
          {progress?.stale ? (
            <span className="mt-1 block text-xs leading-4 text-warning">
              No update for 15 minutes. Colab may have disconnected.
            </span>
          ) : null}
        </td>
```

(Import `describeRunProgress` from `../utils/trainingData.utils`. If `Badge` has no `danger` variant, use whichever `StatusVariant` the file already uses for errors; check `libs/ui` `StatusVariant`. If `text-warning` is not a token, use the warning text class already used elsewhere in `apps/admin`, found with `grep -rn "text-warning" apps/admin/src | head -3`.)

- [ ] **Step 4: Run, format, lint**

Run: `cd apps/admin && npx prettier --single-quote --print-width 100 --trailing-comma all --end-of-line lf --write src/features/training-data && npx vitest run src/features/training-data && npx eslint src/features/training-data`
Expected: PASS, no ESLint errors. (`git diff --stat` after prettier should show only files you touched; revert any others with `git checkout -- <file>`.)

- [ ] **Step 5: Commit**

```bash
git add apps/admin/src/features/training-data
git commit -m "feat(admin): show live run stage, step counter and stale warning"
```

---

# SLICE D: Host sync

### Task D1: Host sync key and read-only host endpoints

**Files:**
- Modify: `models.py`, `exceptions.py`, `schemas.py`, `router.py`
- Create: `apps/server/modules/training_data/host_keys.py`
- Create: `apps/server/alembic/versions/20261010_0002_add_host_sync_keys.py`
- Test: `apps/server/tests/training_data/test_host_keys.py`

**Interfaces:**
- Produces: model `HostSyncKey`; `HostKeyInvalidError`; in `host_keys.py`: `create_host_key(session, created_by) -> tuple[HostSyncKey, str]`, `get_active_key(session) -> HostSyncKey | None`, `revoke_host_key(session) -> bool`, `authenticate_host_key(session, raw_key) -> HostSyncKey`, `list_host_manifest(session) -> list[HostManifestEntry]`; schemas `HostStateResponse(has_active_key, created_at, last_seen_at)`, `HostKeyCreatedResponse(key, created_at)`, `HostManifestEntry(adapter_id, agent_id, version, filename, sha256, size_bytes, published)`, `HostManifestResponse(adapters)`; routes `GET /host`, `POST /host/key`, `DELETE /host/key` (admin) and `GET /host/manifest`, `GET /host/gguf/{adapter_id}` (header `X-Host-Sync-Key`).

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the host sync key and the read-only host endpoints."""

from __future__ import annotations

import hashlib
import io

import pytest
from fastapi.testclient import TestClient
from server.modules.training_data import gguf_files
from server.modules.training_data.models import AgentAdapterPublication
from server.tests.admin.conftest import _auth

from .conftest import make_adapter

BASE = "/api/v1/admin/training-data"
PAYLOAD = b"GGUF" + b"\x02" * 64


@pytest.fixture
def stored(db_session, admin_user, fake_storage, monkeypatch):
    monkeypatch.setattr(
        "server.modules.training_data.gguf_files.get_storage_backend",
        lambda: fake_storage,
    )
    adapter = make_adapter(db_session, "sme", 3)
    gguf_files.store_gguf(db_session, adapter, io.BytesIO(PAYLOAD), storage=fake_storage)
    return adapter


def _make_key(client, auth_cookies_admin) -> str:
    _auth(client, auth_cookies_admin)
    response = client.post(f"{BASE}/host/key")
    assert response.status_code == 201
    client.cookies.clear()
    return response.json()["key"]


def _hdr(key):
    return {"X-Host-Sync-Key": key}


def test_key_endpoints_require_admin(client: TestClient, auth_cookies_faculty):
    _auth(client, auth_cookies_faculty)
    assert client.post(f"{BASE}/host/key").status_code == 403
    assert client.get(f"{BASE}/host").status_code == 403
    assert client.delete(f"{BASE}/host/key").status_code == 403


def test_create_shows_the_key_once_and_state_never_shows_it(
    client: TestClient, auth_cookies_admin
):
    _auth(client, auth_cookies_admin)
    created = client.post(f"{BASE}/host/key").json()
    assert created["key"].startswith("hsk_")
    state = client.get(f"{BASE}/host").json()
    assert state["has_active_key"] is True
    assert state["last_seen_at"] is None
    assert created["key"] not in str(state)


def test_state_without_a_key(client: TestClient, auth_cookies_admin):
    _auth(client, auth_cookies_admin)
    assert client.get(f"{BASE}/host").json()["has_active_key"] is False


def test_creating_a_new_key_revokes_the_old_one(
    client: TestClient, auth_cookies_admin, stored
):
    old = _make_key(client, auth_cookies_admin)
    new = _make_key(client, auth_cookies_admin)
    assert client.get(f"{BASE}/host/manifest", headers=_hdr(old)).status_code == 404
    assert client.get(f"{BASE}/host/manifest", headers=_hdr(new)).status_code == 200


def test_manifest_lists_stored_ggufs_and_touches_last_seen(
    client: TestClient, auth_cookies_admin, stored, db_session
):
    key = _make_key(client, auth_cookies_admin)

    body = client.get(f"{BASE}/host/manifest", headers=_hdr(key)).json()

    assert body["adapters"] == [
        {
            "adapter_id": str(stored.adapter_id),
            "agent_id": "sme",
            "version": 3,
            "filename": "sme-v3.gguf",
            "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
            "size_bytes": len(PAYLOAD),
            "published": False,
        }
    ]
    _auth(client, auth_cookies_admin)
    assert client.get(f"{BASE}/host").json()["last_seen_at"] is not None


def test_manifest_marks_the_published_version(
    client: TestClient, auth_cookies_admin, admin_user, stored, db_session
):
    db_session.add(
        AgentAdapterPublication(
            agent_id="sme",
            adapter_id=stored.adapter_id,
            published_by=admin_user.user_id,
        )
    )
    db_session.commit()
    key = _make_key(client, auth_cookies_admin)
    body = client.get(f"{BASE}/host/manifest", headers=_hdr(key)).json()
    assert body["adapters"][0]["published"] is True


def test_manifest_skips_adapters_without_a_gguf(
    client: TestClient, auth_cookies_admin, stored, db_session
):
    make_adapter(db_session, "sme", 4)  # no GGUF stored
    key = _make_key(client, auth_cookies_admin)
    body = client.get(f"{BASE}/host/manifest", headers=_hdr(key)).json()
    assert [a["version"] for a in body["adapters"]] == [3]


@pytest.mark.parametrize("headers", [{}, {"X-Host-Sync-Key": "hsk_wrong"}])
def test_host_endpoints_reject_missing_or_wrong_keys_with_404(
    client: TestClient, auth_cookies_admin, stored, headers
):
    _make_key(client, auth_cookies_admin)
    assert client.get(f"{BASE}/host/manifest", headers=headers).status_code == 404
    path = f"{BASE}/host/gguf/{stored.adapter_id}"
    assert client.get(path, headers=headers).status_code == 404


def test_host_download_streams_the_file(
    client: TestClient, auth_cookies_admin, stored
):
    key = _make_key(client, auth_cookies_admin)
    response = client.get(f"{BASE}/host/gguf/{stored.adapter_id}", headers=_hdr(key))
    assert response.status_code == 200
    assert response.content == PAYLOAD
    assert 'filename="sme-v3.gguf"' in response.headers["content-disposition"]


def test_host_download_of_an_unknown_adapter_is_404(
    client: TestClient, auth_cookies_admin
):
    import uuid

    key = _make_key(client, auth_cookies_admin)
    path = f"{BASE}/host/gguf/{uuid.uuid4()}"
    assert client.get(path, headers=_hdr(key)).status_code == 404


def test_revoke_stops_the_key_working(client: TestClient, auth_cookies_admin, stored):
    key = _make_key(client, auth_cookies_admin)
    _auth(client, auth_cookies_admin)
    assert client.delete(f"{BASE}/host/key").status_code == 204
    client.cookies.clear()
    assert client.get(f"{BASE}/host/manifest", headers=_hdr(key)).status_code == 404


def test_host_key_cannot_use_admin_endpoints(
    client: TestClient, auth_cookies_admin, stored
):
    key = _make_key(client, auth_cookies_admin)
    assert client.get(f"{BASE}/sme/adapters", headers=_hdr(key)).status_code in (401, 403)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_host_keys.py -q`
Expected: FAIL (404s on the new routes).

- [ ] **Step 3: Model, migration, exceptions, schemas**

`models.py`: add

```python
class HostSyncKey(Base):
    """A read-only key the model-server host script uses to pull GGUF files."""

    __tablename__ = "host_sync_keys"

    key_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

Migration `20261010_0002_add_host_sync_keys.py` (revision `20261010_0002`, down_revision `20261010_0001`):

```python
def upgrade() -> None:
    op.create_table(
        "host_sync_keys",
        sa.Column("key_id", sa.Uuid(), primary_key=True),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("host_sync_keys")
```

(Same header/imports as the C1 migration.)

`exceptions.py`:

```python
class HostKeyInvalidError(TrainingDataError):
    """The host sync key is missing, wrong, or revoked."""
```

`schemas.py`:

```python
class HostStateResponse(BaseModel):
    has_active_key: bool
    created_at: datetime | None = None
    last_seen_at: datetime | None = None


class HostKeyCreatedResponse(BaseModel):
    key: str
    created_at: datetime


class HostManifestEntry(BaseModel):
    adapter_id: uuid.UUID
    agent_id: str
    version: int
    filename: str
    sha256: str
    size_bytes: int
    published: bool


class HostManifestResponse(BaseModel):
    adapters: list[HostManifestEntry]
```

- [ ] **Step 4: Service and routes**

`host_keys.py`:

```python
"""apps/server/modules/training_data/host_keys.py"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from server.modules.training_data.exceptions import HostKeyInvalidError
from server.modules.training_data.gguf_files import gguf_filename
from server.modules.training_data.models import (
    AgentAdapterPublication,
    HostSyncKey,
    TrainedAdapter,
)
from server.modules.training_data.schemas import HostManifestEntry
from server.modules.training_data.tokens import generate_raw_token, hash_token
from sqlalchemy.orm import Session

KEY_PREFIX = "hsk_"


def create_host_key(session: Session, created_by: uuid.UUID) -> tuple[HostSyncKey, str]:
    """Create the one active key (revoking any older one); return the raw key once."""
    now = datetime.now(UTC)
    session.query(HostSyncKey).filter(HostSyncKey.revoked_at.is_(None)).update(
        {"revoked_at": now}, synchronize_session=False
    )
    raw = KEY_PREFIX + generate_raw_token()
    row = HostSyncKey(
        key_id=uuid.uuid4(), key_hash=hash_token(raw), created_by=created_by, created_at=now
    )
    session.add(row)
    session.commit()
    return row, raw


def get_active_key(session: Session) -> HostSyncKey | None:
    return (
        session.query(HostSyncKey)
        .filter(HostSyncKey.revoked_at.is_(None))
        .order_by(HostSyncKey.created_at.desc())
        .first()
    )


def revoke_host_key(session: Session) -> bool:
    count = (
        session.query(HostSyncKey)
        .filter(HostSyncKey.revoked_at.is_(None))
        .update({"revoked_at": datetime.now(UTC)}, synchronize_session=False)
    )
    session.commit()
    return count > 0


def authenticate_host_key(session: Session, raw_key: str | None) -> HostSyncKey:
    """Return the active key row for raw_key and record that the host called."""
    if not raw_key:
        raise HostKeyInvalidError("missing host key")
    wanted = hash_token(raw_key)
    row = get_active_key(session)
    if row is None or not secrets.compare_digest(row.key_hash, wanted):
        raise HostKeyInvalidError("invalid host key")
    row.last_seen_at = datetime.now(UTC)
    session.commit()
    return row


def list_host_manifest(session: Session) -> list[HostManifestEntry]:
    published = {
        p.agent_id: p.adapter_id for p in session.query(AgentAdapterPublication).all()
    }
    rows = (
        session.query(TrainedAdapter)
        .filter(TrainedAdapter.gguf_storage_key.isnot(None))
        .order_by(TrainedAdapter.agent_id, TrainedAdapter.version)
        .all()
    )
    return [
        HostManifestEntry(
            adapter_id=a.adapter_id,
            agent_id=a.agent_id,
            version=a.version,
            filename=gguf_filename(a.agent_id, a.version),
            sha256=a.gguf_sha256 or "",
            size_bytes=a.gguf_size_bytes or 0,
            published=published.get(a.agent_id) == a.adapter_id,
        )
        for a in rows
    ]
```

Routes in `router.py` (imports: `Header` from fastapi; the new schemas; `HostKeyInvalidError`; the `host_keys` functions; `HostSyncKey` not needed). Add near the other admin routes, **above** any `/{agent_id}/...` route of the same method that could capture `host`:

```python
def _host_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")


def _require_host_key(
    db: Session = Depends(get_db_session),
    x_host_sync_key: str | None = Header(default=None, alias="X-Host-Sync-Key"),
):
    try:
        return authenticate_host_key(db, x_host_sync_key)
    except HostKeyInvalidError as exc:
        raise _host_not_found() from exc


@router.get("/host", response_model=HostStateResponse)
def get_host_state(
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> HostStateResponse:
    key = get_active_key(db)
    if key is None:
        return HostStateResponse(has_active_key=False)
    return HostStateResponse(
        has_active_key=True, created_at=key.created_at, last_seen_at=key.last_seen_at
    )


@router.post(
    "/host/key", response_model=HostKeyCreatedResponse, status_code=status.HTTP_201_CREATED
)
def create_host_sync_key(
    current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> HostKeyCreatedResponse:
    row, raw = create_host_key(db, current_user.id)
    return HostKeyCreatedResponse(key=raw, created_at=row.created_at)


@router.delete("/host/key", status_code=status.HTTP_204_NO_CONTENT)
def revoke_host_sync_key(
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> Response:
    revoke_host_key(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/host/manifest", response_model=HostManifestResponse)
def get_host_manifest(
    _key=Depends(_require_host_key),
    db: Session = Depends(get_db_session),
) -> HostManifestResponse:
    return HostManifestResponse(adapters=list_host_manifest(db))


@router.get("/host/gguf/{adapter_id}")
def stream_host_gguf(
    adapter_id: uuid.UUID,
    _key=Depends(_require_host_key),
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    adapter = db.get(TrainedAdapter, adapter_id)
    if adapter is None or not adapter.gguf_storage_key:
        raise _host_not_found()
    try:
        chunks, size = open_gguf_stream(adapter)
    except (GgufNotFoundError, FileNotFoundError) as exc:
        raise _host_not_found() from exc
    name = gguf_filename(adapter.agent_id, adapter.version)
    headers = {"Content-Disposition": f'attachment; filename="{name}"'}
    if size is not None:
        headers["Content-Length"] = str(size)
    return StreamingResponse(chunks, media_type="application/octet-stream", headers=headers)
```

If the authenticated-user object's id attribute is not `id`, copy exactly what `start_training_job` passes to `create_training_job` (`current_user.id`).

- [ ] **Step 5: Run tests, SQL check, lint**

Run:
```
cd apps && uv run --project server pytest server/tests/training_data -q
cd server && uv run alembic upgrade 20261006_0001:head --sql | tail -30
cd .. && uv run --project server ruff check server/modules/training_data server/alembic && uv run --project server ruff format --check server/modules/training_data server/alembic
```
Expected: PASS; the SQL shows both revisions and `CREATE TABLE host_sync_keys`; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add apps/server/modules/training_data apps/server/alembic apps/server/tests/training_data/test_host_keys.py
git commit -m "feat(training-data): add a read-only host sync key and host download endpoints"
```

### Task D2: The host sync script

**Files:**
- Create: `training/host_sync.py`, `training/host_sync.example.ini`
- Test: `training/tests/test_host_sync.py`

**Interfaces:**
- Consumes: `GET {server_url}/api/v1/admin/training-data/host/manifest` and `/host/gguf/{adapter_id}` with header `X-Host-Sync-Key` (D1). Manifest shape: `{"adapters": [{"adapter_id", "agent_id", "version", "filename", "sha256", "size_bytes", "published"}]}`.
- Produces (importable): `load_config(path) -> Config`, `select_loaded(entries, keep_latest) -> list[dict]`, `sync(config, *, notify=...) -> SyncResult`, `main(argv=None) -> int`. `Config` fields: `server_url, key, adapters_dir (Path), flags_file (Path), log_file (Path), keep_latest (int), notify (bool)`. `SyncResult` fields: `downloaded: list[str]`, `errors: list[str]`, `flags_changed: bool`.

- [ ] **Step 1: Write the failing tests** (`training/tests/test_host_sync.py`)

```python
"""Tests for training/host_sync.py against a fake local server."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "host_sync.py"
spec = importlib.util.spec_from_file_location("host_sync", SCRIPT)
host_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host_sync)

KEY = "hsk_test"


def _entry(agent, version, payload, *, published=False, filename=None, adapter_id=None):
    return {
        "adapter_id": adapter_id or f"{agent}-{version}-id",
        "agent_id": agent,
        "version": version,
        "filename": filename or f"{agent}-v{version}.gguf",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "published": published,
    }


class _Server:
    """A fake EquipED serving a manifest and files."""

    def __init__(self, entries, files, *, corrupt=()):
        self.entries, self.files, self.corrupt = entries, files, set(corrupt)
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                outer.requests.append((self.path, self.headers.get("X-Host-Sync-Key")))
                if self.headers.get("X-Host-Sync-Key") != KEY:
                    self.send_error(404)
                    return
                if self.path.endswith("/host/manifest"):
                    body = json.dumps({"adapters": outer.entries}).encode()
                else:
                    adapter_id = self.path.rsplit("/", 1)[1]
                    body = outer.files[adapter_id]
                    if adapter_id in outer.corrupt:
                        body = body[:-1] + b"X"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def make_server():
    servers = []

    def make(entries, files, **kwargs):
        server = _Server(entries, files, **kwargs)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def _config(tmp_path, server, **overrides):
    values = dict(
        server_url=server.url,
        key=KEY,
        adapters_dir=tmp_path / "adapters",
        flags_file=tmp_path / "adapters" / "lora-flags.txt",
        log_file=tmp_path / "host_sync.log",
        keep_latest=2,
        notify=False,
    )
    values.update(overrides)
    return host_sync.Config(**values)


P3, P4, P5 = (b"GGUF" + bytes([n]) * 40 for n in (3, 4, 5))


def _three(make_server):
    entries = [_entry("sme", 3, P3), _entry("sme", 4, P4), _entry("sme", 5, P5)]
    files = {"sme-3-id": P3, "sme-4-id": P4, "sme-5-id": P5}
    return make_server(entries, files)


def test_downloads_new_files_and_writes_flags(tmp_path, make_server):
    server = _three(make_server)
    config = _config(tmp_path, server)

    result = host_sync.sync(config)

    assert sorted(result.downloaded) == ["sme-v3.gguf", "sme-v4.gguf", "sme-v5.gguf"]
    assert (config.adapters_dir / "sme-v5.gguf").read_bytes() == P5
    assert not list(config.adapters_dir.glob("*.part"))
    flags = config.flags_file.read_text(encoding="utf-8").splitlines()
    # keep_latest = 2 -> v4 and v5 only; v3 stays on disk but is not listed
    assert len(flags) == 2
    assert all(line.startswith("--lora-scaled ") and line.endswith(':0.0"') for line in flags)
    assert "sme-v5.gguf" in flags[-1] or "sme-v5.gguf" in "".join(flags)
    assert "sme-v3.gguf" not in "".join(flags)


def test_second_run_downloads_nothing_and_changes_nothing(tmp_path, make_server):
    server = _three(make_server)
    config = _config(tmp_path, server)
    host_sync.sync(config)
    before = config.flags_file.read_text(encoding="utf-8")
    server.requests.clear()

    result = host_sync.sync(config)

    assert result.downloaded == [] and result.flags_changed is False
    assert config.flags_file.read_text(encoding="utf-8") == before
    assert [p for p, _ in server.requests if "/host/gguf/" in p] == []


def test_checksum_mismatch_leaves_no_file_and_is_reported(tmp_path, make_server):
    entries = [_entry("sme", 3, P3)]
    server = make_server(entries, {"sme-3-id": P3}, corrupt={"sme-3-id"})
    config = _config(tmp_path, server)

    result = host_sync.sync(config)

    assert result.downloaded == []
    assert result.errors and "sme-v3.gguf" in result.errors[0]
    assert not (config.adapters_dir / "sme-v3.gguf").exists()
    assert not list(config.adapters_dir.glob("*.part"))


def test_published_version_is_always_listed_even_if_old(tmp_path, make_server):
    entries = [
        _entry("sme", 1, P3, published=True, adapter_id="sme-1-id"),
        _entry("sme", 4, P4), _entry("sme", 5, P5),
    ]
    server = make_server(entries, {"sme-1-id": P3, "sme-4-id": P4, "sme-5-id": P5})
    config = _config(tmp_path, server)
    host_sync.sync(config)
    flags = "".join(config.flags_file.read_text(encoding="utf-8").splitlines())
    assert "sme-v1.gguf" in flags and "sme-v4.gguf" in flags and "sme-v5.gguf" in flags


def test_keep_latest_applies_per_agent(tmp_path, make_server):
    entries = [_entry("sme", 1, P3), _entry("gad", 1, P4)]
    server = make_server(entries, {"sme-1-id": P3, "gad-1-id": P4})
    config = _config(tmp_path, server, keep_latest=1)
    host_sync.sync(config)
    flags = "".join(config.flags_file.read_text(encoding="utf-8").splitlines())
    assert "sme-v1.gguf" in flags and "gad-v1.gguf" in flags


def test_unsafe_filenames_are_rejected(tmp_path, make_server):
    bad = _entry("sme", 3, P3, filename="..\\..\\evil.gguf")
    server = make_server([bad], {"sme-3-id": P3})
    config = _config(tmp_path, server)
    result = host_sync.sync(config)
    assert result.downloaded == [] and result.errors
    assert not (tmp_path / "evil.gguf").exists()


def test_a_failed_file_does_not_stop_the_others(tmp_path, make_server):
    entries = [_entry("sme", 3, P3), _entry("sme", 4, P4)]
    server = make_server(entries, {"sme-3-id": P3, "sme-4-id": P4}, corrupt={"sme-3-id"})
    config = _config(tmp_path, server)
    result = host_sync.sync(config)
    assert result.downloaded == ["sme-v4.gguf"]
    assert len(result.errors) == 1


def test_new_files_are_logged_and_notified_once(tmp_path, make_server):
    server = make_server([_entry("sme", 3, P3)], {"sme-3-id": P3})
    config = _config(tmp_path, server, notify=True)
    sent = []
    host_sync.sync(config, notify=lambda title, message: sent.append((title, message)))
    assert sent and "sme-v3" in sent[0][1]
    assert "restart the model server" in sent[0][1]
    assert "sme-v3" in config.log_file.read_text(encoding="utf-8")
    sent.clear()
    host_sync.sync(config, notify=lambda title, message: sent.append((title, message)))
    assert sent == []


def test_a_failing_notification_is_ignored(tmp_path, make_server):
    server = make_server([_entry("sme", 3, P3)], {"sme-3-id": P3})
    config = _config(tmp_path, server, notify=True)

    def boom(title, message):
        raise OSError("no desktop")

    result = host_sync.sync(config, notify=boom)
    assert result.downloaded == ["sme-v3.gguf"]


def test_wrong_key_is_a_clear_error(tmp_path, make_server):
    server = make_server([], {})
    config = _config(tmp_path, server, key="hsk_wrong")
    result = host_sync.sync(config)
    assert result.errors and "key" in result.errors[0].lower()


def test_unreachable_server_is_a_clear_error(tmp_path, make_server):
    server = make_server([], {})
    config = _config(tmp_path, server)
    server.close()
    result = host_sync.sync(config)
    assert result.errors


def test_load_config_reads_the_ini_file(tmp_path):
    ini = tmp_path / "host_sync.ini"
    ini.write_text(
        "[host_sync]\nserver_url = https://app.example\nkey = hsk_x\n"
        f"adapters_dir = {tmp_path / 'adapters'}\nkeep_latest = 3\nnotify = false\n",
        encoding="utf-8",
    )
    config = host_sync.load_config(ini)
    assert config.server_url == "https://app.example"
    assert config.keep_latest == 3 and config.notify is False
    assert config.flags_file == tmp_path / "adapters" / "lora-flags.txt"


def test_main_returns_nonzero_when_something_failed(tmp_path, make_server):
    server = make_server([_entry("sme", 3, P3)], {"sme-3-id": P3}, corrupt={"sme-3-id"})
    ini = tmp_path / "host_sync.ini"
    ini.write_text(
        f"[host_sync]\nserver_url = {server.url}\nkey = {KEY}\n"
        f"adapters_dir = {tmp_path / 'adapters'}\nnotify = false\n",
        encoding="utf-8",
    )
    assert host_sync.main(["--config", str(ini)]) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps && uv run --project server pytest ../training/tests/test_host_sync.py -q`
Expected: FAIL (cannot load `host_sync.py`).

- [ ] **Step 3: Implement `training/host_sync.py`**

```python
#!/usr/bin/env python3
"""EquipED host sync: pull finished fine-tuned models onto the model server.

Run on the computer that runs the model server (Windows, llama.cpp). It asks
EquipED which GGUF files exist, downloads missing or changed ones into the
adapters folder, checks each against the SHA-256 EquipED recorded, rewrites
lora-flags.txt, and says what is new. It never restarts the server, never
deletes files, and never publishes. Standard library only.

    python host_sync.py --config host_sync.ini
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_API = "/api/v1/admin/training-data/host"
_SAFE_NAME = re.compile(r"^[a-z0-9]+-v[0-9]+\.gguf$")
_CHUNK = 1024 * 1024
_MAX_BYTES = 2 * 1024**3
_TIMEOUT = 60


class SyncError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    server_url: str
    key: str
    adapters_dir: Path
    flags_file: Path
    log_file: Path
    keep_latest: int = 2
    notify: bool = True


@dataclass
class SyncResult:
    downloaded: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    flags_changed: bool = False


def load_config(path: Path) -> Config:
    parser = configparser.ConfigParser()
    if not parser.read(path, encoding="utf-8"):
        raise SyncError(f"config file not found: {path}")
    try:
        section = parser["host_sync"]
        adapters_dir = Path(section["adapters_dir"])
        return Config(
            server_url=section["server_url"].rstrip("/"),
            key=section["key"],
            adapters_dir=adapters_dir,
            flags_file=Path(section.get("flags_file", str(adapters_dir / "lora-flags.txt"))),
            log_file=Path(section.get("log_file", str(Path(path).parent / "host_sync.log"))),
            keep_latest=section.getint("keep_latest", 2),
            notify=section.getboolean("notify", True),
        )
    except KeyError as exc:
        raise SyncError(f"missing setting in {path}: {exc}") from exc


def _open(config: Config, path: str):
    request = urllib.request.Request(
        config.server_url + _API + path, headers={"X-Host-Sync-Key": config.key}
    )
    return urllib.request.urlopen(request, timeout=_TIMEOUT)  # noqa: S310


def _fetch_manifest(config: Config) -> list[dict]:
    try:
        with _open(config, "/manifest") as response:
            return json.loads(response.read().decode("utf-8"))["adapters"]
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise SyncError("EquipED rejected the host key (revoked or wrong key)") from exc
        raise SyncError(f"EquipED returned HTTP {exc.code} for the manifest") from exc
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        raise SyncError(f"could not read the manifest from EquipED: {exc}") from exc


def _valid(entry: dict) -> bool:
    return (
        isinstance(entry.get("filename"), str)
        and _SAFE_NAME.match(entry["filename"]) is not None
        and isinstance(entry.get("sha256"), str)
        and isinstance(entry.get("size_bytes"), int)
        and 0 < entry["size_bytes"] <= _MAX_BYTES
        and isinstance(entry.get("adapter_id"), str)
    )


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _up_to_date(target: Path, entry: dict) -> bool:
    return (
        target.is_file()
        and target.stat().st_size == entry["size_bytes"]
        and _sha256_of(target) == entry["sha256"]
    )


def _download(config: Config, entry: dict, target: Path) -> None:
    part = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    try:
        with _open(config, f"/gguf/{entry['adapter_id']}") as response, open(part, "wb") as out:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != entry["sha256"]:
            raise SyncError(f"{entry['filename']}: checksum does not match; discarded")
        os.replace(part, target)
    except SyncError:
        part.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError) as exc:
        part.unlink(missing_ok=True)
        raise SyncError(f"{entry['filename']}: download failed ({exc})") from exc


def select_loaded(entries: list[dict], keep_latest: int) -> list[dict]:
    """Latest keep_latest versions per agent, plus every published version."""
    by_agent: dict[str, list[dict]] = {}
    for entry in entries:
        by_agent.setdefault(entry["agent_id"], []).append(entry)
    chosen: list[dict] = []
    for agent in sorted(by_agent):
        ordered = sorted(by_agent[agent], key=lambda e: e["version"])
        keep = {e["adapter_id"] for e in ordered[-keep_latest:]}
        keep |= {e["adapter_id"] for e in ordered if e.get("published")}
        chosen.extend(e for e in ordered if e["adapter_id"] in keep)
    return chosen


def _write_flags(config: Config, entries: list[dict]) -> bool:
    lines = [
        f'--lora-scaled "{config.adapters_dir / e["filename"]}:0.0"' for e in entries
    ]
    text = "\n".join(lines) + ("\n" if lines else "")
    old = config.flags_file.read_text(encoding="utf-8") if config.flags_file.exists() else None
    if old == text:
        return False
    temp = config.flags_file.with_name(config.flags_file.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, config.flags_file)
    return True


def _log(config: Config, message: str) -> None:
    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config.log_file, "a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")


def notify_desktop(title: str, message: str) -> None:
    """Best-effort Windows balloon notification (needs a logged-in desktop)."""

    def quote(value: str) -> str:
        return value.replace("'", "''")

    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; "
        f"$n.ShowBalloonTip(10000, '{quote(title)}', '{quote(message)}', 'Info'); "
        "Start-Sleep -Seconds 12; $n.Dispose()"
    )
    subprocess.Popen(  # noqa: S603
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def sync(
    config: Config, *, notify: Callable[[str, str], None] = notify_desktop
) -> SyncResult:
    result = SyncResult()
    try:
        manifest = _fetch_manifest(config)
    except SyncError as exc:
        result.errors.append(str(exc))
        _log(config, f"ERROR {exc}")
        return result

    config.adapters_dir.mkdir(parents=True, exist_ok=True)
    available: list[dict] = []
    for entry in manifest:
        if not _valid(entry):
            result.errors.append(f"ignored an unsafe or malformed entry: {entry!r}")
            continue
        target = config.adapters_dir / entry["filename"]
        try:
            if not _up_to_date(target, entry):
                _download(config, entry, target)
                result.downloaded.append(entry["filename"])
            available.append(entry)
        except SyncError as exc:
            result.errors.append(str(exc))

    result.flags_changed = _write_flags(config, select_loaded(available, config.keep_latest))

    for error in result.errors:
        _log(config, f"ERROR {error}")
    if result.downloaded:
        names = ", ".join(n.removesuffix(".gguf") for n in result.downloaded)
        message = f"New model {names} ready, restart the model server to load it"
        _log(config, message)
        print(message)
        if config.notify:
            try:
                notify("EquipED: new fine-tuned model", message)
            except Exception as exc:  # a missing desktop must never break the sync
                _log(config, f"notification failed: {exc}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pull new EquipED models to this host.")
    parser.add_argument("--config", default="host_sync.ini")
    args = parser.parse_args(argv)
    try:
        config = load_config(Path(args.config))
    except SyncError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    result = sync(config)
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`training/host_sync.example.ini`:

```ini
[host_sync]
# Address of the EquipED server (no trailing slash)
server_url = https://equiped.example
# The key from Admin > Model Training > Host sync (shown once)
key = hsk_paste_the_key_here
# Folder the model server loads adapters from
adapters_dir = F:\Dev\Models\gemma\adapters
# How many newest versions per agent to load (the published one is always loaded)
keep_latest = 2
# Show a Windows notification when a new model arrives (needs a logged-in desktop)
notify = true
```

- [ ] **Step 4: Run to verify pass**

Run: `cd apps && uv run --project server pytest ../training/tests/test_host_sync.py -q && uv run --project server ruff check ../training/host_sync.py ../training/tests/test_host_sync.py`
Expected: PASS. Fix ruff findings in `host_sync.py` (it is a standalone script, so keep it standard-library only). If ruff flags the `noqa: S` codes as unknown, delete those comments.

- [ ] **Step 5: Commit**

```bash
git add training/host_sync.py training/host_sync.example.ini training/tests/test_host_sync.py
git commit -m "feat(training): add the host sync script that pulls new GGUF files"
```

### Task D3: Host sync panel in the admin page

**Files:**
- Modify: `apps/admin/src/features/training-data/types.ts`, `api/trainingData.api.ts`, `components/TrainingDataWorkspace.tsx`
- Create: `hooks/useHostSync.ts`, `components/HostSyncPanel.tsx`
- Test: `components/__tests__/HostSyncPanel.test.tsx`

**Interfaces:**
- Consumes: `GET /admin/training-data/host`, `POST /host/key`, `DELETE /host/key` (D1).
- Produces: types `HostSyncState { has_active_key: boolean; created_at?: string | null; last_seen_at?: string | null }`, `HostKeyCreated { key: string; created_at: string }`; api `getHostSync()`, `createHostKey()`, `revokeHostKey()`; hooks `useHostSync()`, `useCreateHostKey()`, `useRevokeHostKey()`.

- [ ] **Step 1: Write the failing test**

```tsx
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HostSyncPanel } from '../HostSyncPanel';
import { trainingDataApi } from '../../api/trainingData.api';

vi.mock('../../api/trainingData.api', () => ({
  trainingDataApi: {
    getHostSync: vi.fn(),
    createHostKey: vi.fn(),
    revokeHostKey: vi.fn(),
  },
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <HostSyncPanel />
    </QueryClientProvider>,
  );
}

describe('HostSyncPanel', () => {
  it('offers to create a key when none exists', async () => {
    vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({ has_active_key: false });
    renderPanel();
    expect(await screen.findByRole('button', { name: /create host key/i })).toBeDefined();
    expect(screen.getByText(/no key yet/i)).toBeDefined();
  });

  it('shows the new key once after creating it', async () => {
    vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({ has_active_key: false });
    vi.mocked(trainingDataApi.createHostKey).mockResolvedValue({
      key: 'hsk_secret123',
      created_at: '2026-10-10T00:00:00Z',
    });
    renderPanel();
    fireEvent.click(await screen.findByRole('button', { name: /create host key/i }));
    expect(((await screen.findByLabelText('Host key')) as HTMLInputElement).value).toBe(
      'hsk_secret123',
    );
    expect(screen.getByText(/shown once/i)).toBeDefined();
  });

  it('shows when the host last checked and can revoke the key', async () => {
    vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({
      has_active_key: true,
      created_at: '2026-10-09T00:00:00Z',
      last_seen_at: new Date(Date.now() - 4 * 60_000).toISOString(),
    });
    vi.mocked(trainingDataApi.revokeHostKey).mockResolvedValue(undefined);
    renderPanel();
    expect(await screen.findByText(/last checked 4 min ago/i)).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /revoke key/i }));
    await waitFor(() => expect(trainingDataApi.revokeHostKey).toHaveBeenCalled());
  });

  it('says the host has not checked in yet', async () => {
    vi.mocked(trainingDataApi.getHostSync).mockResolvedValue({
      has_active_key: true,
      created_at: '2026-10-09T00:00:00Z',
      last_seen_at: null,
    });
    renderPanel();
    expect(await screen.findByText(/has not checked in yet/i)).toBeDefined();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/admin && npx vitest run src/features/training-data/components/__tests__/HostSyncPanel.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

`types.ts`: add

```ts
export interface HostSyncState {
  has_active_key: boolean;
  created_at?: string | null;
  last_seen_at?: string | null;
}

export interface HostKeyCreated {
  key: string;
  created_at: string;
}
```

`api/trainingData.api.ts`: import the two types and add

```ts
  getHostSync: () => requestJson<HostSyncState>('/admin/training-data/host'),
  createHostKey: () =>
    requestJson<HostKeyCreated>('/admin/training-data/host/key', { method: 'POST' }),
  revokeHostKey: () =>
    requestJson<void>('/admin/training-data/host/key', { method: 'DELETE' }),
```

`hooks/useHostSync.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

const KEY = ['hostSync'] as const;

export function useHostSync() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => trainingDataApi.getHostSync(),
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });
}

export function useCreateHostKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => trainingDataApi.createHostKey(),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

export function useRevokeHostKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => trainingDataApi.revokeHostKey(),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
```

`components/HostSyncPanel.tsx`:

```tsx
import { useState } from 'react';
import { Button, Input, TYPOGRAPHY } from '@equiped/ui';
import { useCreateHostKey, useHostSync, useRevokeHostKey } from '../hooks/useHostSync';

function checkedText(lastSeen?: string | null): string {
  if (!lastSeen) return 'The host has not checked in yet.';
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(lastSeen).getTime()) / 60_000));
  if (minutes < 1) return 'Host last checked just now.';
  if (minutes < 60) return `Host last checked ${minutes} min ago.`;
  return `Host last checked ${Math.floor(minutes / 60)} h ago.`;
}

export function HostSyncPanel() {
  const { data, isLoading, isError } = useHostSync();
  const create = useCreateHostKey();
  const revoke = useRevokeHostKey();
  const [newKey, setNewKey] = useState<string | null>(null);

  async function onCreate() {
    const created = await create.mutateAsync();
    setNewKey(created.key);
  }

  return (
    <section aria-labelledby="host-sync-title" className="min-w-0 space-y-3">
      <h2 id="host-sync-title" className={TYPOGRAPHY.headingSm}>
        Host sync
      </h2>
      <p className="max-w-3xl text-[13px] leading-5 text-text-muted">
        A small script on the model server&apos;s computer uses this key to download new
        fine-tuned models. It cannot publish, delete or change anything.
      </p>
      {isLoading ? (
        <p className="text-sm text-text-muted">Checking host sync…</p>
      ) : isError || !data ? (
        <p role="alert" className="text-sm text-destructive">
          Could not load host sync status.
        </p>
      ) : (
        <div className="space-y-3 rounded-md border border-border bg-surface p-4">
          <p className="text-sm text-text">
            {data.has_active_key ? checkedText(data.last_seen_at) : 'No key yet.'}
          </p>
          {newKey ? (
            <div className="space-y-1.5">
              <label htmlFor="host-key" className="block text-[13px] font-medium text-text">
                Host key
              </label>
              <Input
                id="host-key"
                value={newKey}
                readOnly
                className="font-mono text-sm"
                onFocus={(event) => event.currentTarget.select()}
              />
              <p className="text-xs text-text-muted">
                Shown once. Copy it into the script&apos;s settings now.
              </p>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={create.isPending}
              onClick={() => void onCreate()}
            >
              {data.has_active_key ? 'Replace host key' : 'Create host key'}
            </Button>
            {data.has_active_key ? (
              <Button
                type="button"
                variant="secondary"
                disabled={revoke.isPending}
                onClick={() => {
                  setNewKey(null);
                  revoke.mutate();
                }}
              >
                Revoke key
              </Button>
            ) : null}
          </div>
          {create.isError || revoke.isError ? (
            <p role="alert" className="text-sm text-destructive">
              That did not work. Try again.
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}
```

`TrainingDataWorkspace.tsx`: import `HostSyncPanel` and render `<HostSyncPanel />` directly after `<AdapterListTable agentId={agentId} />`.

Also reword `AdapterLoadHint.tsx`'s first paragraph to add a leading sentence: `If the host sync script is set up, it downloads this file for you; then restart the model server.` Update `AdapterRow`/`AdapterListTable` tests only if they assert the old paragraph text.

- [ ] **Step 4: Run, format, lint**

Run: `cd apps/admin && npx prettier --single-quote --print-width 100 --trailing-comma all --end-of-line lf --write src/features/training-data && npx vitest run src/features/training-data && npx eslint src/features/training-data`
Expected: PASS, no ESLint errors. Revert any unrelated files prettier touched.

- [ ] **Step 5: Commit**

```bash
git add apps/admin/src/features/training-data
git commit -m "feat(admin): add the Host sync panel (create, revoke, last checked)"
```

### Task D4: Host setup guide and batch-file loop check

**Files:**
- Create: `docs/host-sync-setup.md`
- Modify: `training/serving-lora-adapter.md` (one short pointer paragraph near the top)

- [ ] **Step 1: Verify the batch loop that reads `lora-flags.txt` really works (Windows `cmd`)**

Create a scratch folder with a fake flags file and run the loop; do not touch the real `start-gemma.bat`:

```powershell
$d = Join-Path $env:TEMP "hostsync-bat-check"; New-Item -ItemType Directory -Force $d | Out-Null
Set-Content -Path "$d\lora-flags.txt" -Encoding ascii -Value @('--lora-scaled "F:\Dev\Models\gemma\adapters\sme-v10.gguf:0.0"', '--lora-scaled "F:\Dev\Models\gemma\adapters\sme-v11.gguf:0.0"')
Set-Content -Path "$d\check.bat" -Encoding ascii -Value @('@echo off','setlocal EnableDelayedExpansion','set "LORA_FLAGS="','for /f "usebackq delims=" %%L in ("%~dp0lora-flags.txt") do set "LORA_FLAGS=!LORA_FLAGS! %%L"','echo [!LORA_FLAGS!]')
cmd /c "$d\check.bat"
```

Expected: one line `[ --lora-scaled "F:\Dev\Models\gemma\adapters\sme-v10.gguf:0.0" --lora-scaled "F:\Dev\Models\gemma\adapters\sme-v11.gguf:0.0"]` with the quotes intact. If the quotes are lost or the line is mangled, change the loop (for example drop the outer quotes around the `set` value) until this output is right, and use the working version in the guide.

- [ ] **Step 2: Write `docs/host-sync-setup.md`** for the host owner, in plain language: what the script does and does not do; the four one-time setup steps (create the key in the admin page; copy `training/host_sync.py` and `host_sync.example.ini` to the host as `host_sync.ini` and fill it in; edit `start-gemma.bat` with the verified loop from Step 1, showing where `!LORA_FLAGS!` goes on the `llama-server` command line; schedule it in Task Scheduler every 5 to 10 minutes with **"Run only when user is logged on"** so the desktop notification can appear); the routine after a run ("when the admin page says Finished and the log or notification says a model is ready, restart the model server when no evaluation is running"); a short troubleshooting list (key rejected; checksum mismatch retried next run; model still shows Not loaded because the server was not restarted; where `host_sync.log` is).

- [ ] **Step 3: Add the pointer to `training/serving-lora-adapter.md`**: under the first paragraph add: `With host sync set up, steps 1 to 3 below are done by the script; see docs/host-sync-setup.md. The manual steps stay valid as a fallback.`

- [ ] **Step 4: Commit**

```bash
git add docs/host-sync-setup.md training/serving-lora-adapter.md
git commit -m "docs: host sync setup guide"
```

---

### Task Z: Final verification

- [ ] **Step 1: Full backend and script tests**

Run: `cd apps && uv run --project server pytest server/tests/training_data ../training/tests -q && uv run --project server ruff check && uv run --project server ruff format --check`
Expected: all PASS, ruff clean. (If `ruff format --check` flags files you did not touch, leave them.)

- [ ] **Step 2: Migration chain**

Run: `cd apps/server && uv run alembic heads && uv run alembic upgrade 20261006_0001:head --sql | grep -E "ALTER TABLE|CREATE TABLE|alembic_version"`
Expected: single head `20261010_0002`; the SQL adds the seven job columns and creates `host_sync_keys`. Do NOT run `alembic upgrade` against Neon; tell the user to apply it.

- [ ] **Step 3: Admin tests, lint**

Run: `cd apps/admin && npx vitest run src/features/training-data src/features/model-validation src/app && npx eslint src/features/training-data`
Expected: all PASS, no ESLint errors. (The existing `pdf-lib` typecheck errors in `monitoring-matrix` are unrelated.)

- [ ] **Step 4: Manual smoke test (needs a running backend; report honestly if skipped)**

Start the backend and admin dev servers, start a training run for an agent with pairs, and confirm: the Download notebook button appears and the downloaded `.ipynb` has no `PASTE_`, with three filled links; posting a status with `curl -X POST "<status_url>" -H "Content-Type: application/json" -d "{\"stage\":\"training\",\"step\":3,\"total\":10}"` makes the row show "Training · step 3 of 10" within 10 seconds; creating a host key shows it once and the panel then reads "has not checked in yet"; running `python training/host_sync.py --config <ini>` against the dev server downloads a stored GGUF and writes `lora-flags.txt`. State which of these were actually run.

- [ ] **Step 5: Report to the user** with the branch name (`feat/plain-language-model-training`), the commit list, the migration they must apply (`20261010_0001`, `20261010_0002`), the real-Colab run still needed to validate Slice A and C notebook changes, and the host-side setup steps.

---

## Self-Review Notes

- **Spec coverage:** Slice A (A1 existing plan, A2 merge) covers chat rows, guard, rescue cell, early stop and the measured plan; Slice B (B1-B3) covers the filled notebook, template-failure tolerance and the button; Slice C (C1-C4) covers the token, columns, endpoint, validation, server-observed stages, list fields, notebook reporting, polling and the stale warning; Slice D (D1-D4) covers the key, manifest and stream endpoints, the script (checksum, atomic writes, `keep_latest`, published always, flags, log, notification, never restart/delete), the panel and the setup doc. The spec's "Open items" (15 min, `keep_latest = 2`, logged-on Task Scheduler, -5 limit) are encoded as constants or documented.
- **Known ordering coupling:** Task C2's two `status_url` builder tests depend on the `STATUS_URL = ""` line added in Task C3. They are written in C2 and pass after C3; the plan says so explicitly.
- **Unverified on real hardware:** the notebook changes in A2 and C3 are tested offline only (extracted cells run against fakes). The `prompt_input_ids` chat-format guard, the training callbacks under TRL 0.24, and the live status flow need one real Colab run. The `start-gemma.bat` loop is checked with a local `cmd` run (Task D4 Step 1) but not against a real `llama-server`.
