# Adapter Evaluation Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let EquipED answer "is this trained adapter better than the plain model?" by holding out whole evaluations at training time and comparing adapter vs plain model on them through the served llama.cpp server.

**Architecture:** The Colab training notebook holds out ~20% of evaluations (grouped by `evaluation_id`, deterministic) and ships them inside the adapter zip as `heldout_pairs.jsonl`, hashed in `training_manifest.json`. A new stdlib-only script, `training/evaluate_adapter.py`, reads that file, sends each prompt to the server with the adapter off then on (reusing the client in `training/smoke_test_lora_serving.py`), scores replies against the reviewer's corrected scores, runs an exact sign test on wins vs losses, and prints a verdict plus an optional JSON report.

**Tech Stack:** Python 3.11+ standard library (script), pytest (offline tests, fake local llama-server), Jupyter notebook JSON (Colab), existing `apps/server` contract tests.

**Spec:** `docs/superpowers/specs/2026-09-19-adapter-evaluation-tool-design.md`

## Global Constraints

- Nothing under `apps/` changes except `apps/server/tests/training_data/test_dpo_colab_contract.py` (spec: "Any change under `apps/`" is a non-goal). Do not touch the exporter, models, endpoints or admin UI.
- `training/evaluate_adapter.py` uses only the Python standard library and imports the server client from `training/smoke_test_lora_serving.py` with `import smoke_test_lora_serving as smoke`. Do not copy client code.
- Version 1 supports only the `criterion_measurements` reply shape (SME, Coordinator). No ITSO/GAD support.
- Held-out split: group by `evaluation_id`; deterministic (order by `sha256(f"{seed}:{evaluation_id}")`, seed 42); hold out ceil(20% of evaluations) using integer arithmetic; at least one and never all; fewer than 20 pairs or a single evaluation means hold nothing out.
- `heldout_pairs.jsonl` rows: `{"pair_id", "evaluation_id", "prompt", "chosen", "rejected"}`. `training_manifest.json` gets `"heldout": {"method": "group_by_evaluation_id", "seed": 42, "fraction": 0.2, "pair_count", "evaluation_count", "sha256"}` or `null`.
- Verdict rule: fewer than `--min-decisive` (default 20) decisive pairs is inconclusive; exact two-sided sign test, alpha default 0.05; an adapter whose valid-JSON rate is lower than the plain model's can never be "better".
- Exit codes: 0 better, 1 worse or inconclusive, 2 could not run.
- The report and console output never contain prompts or the API key. Console output is plain ASCII (the Windows console is cp1252).
- The notebook file is serialised as `json.dumps(nb, indent=1, ensure_ascii=False)` with CRLF line endings and no trailing newline; keep that so diffs stay small.
- Commits: **do not add `Co-Authored-By` or `Claude-Session` trailers** (repo rule in CLAUDE.md). Commit only when the controller has confirmed the user allowed commits this turn; otherwise leave the tree dirty and say so.
- Test commands. Training tests, from the repo root: `python -m pytest training/tests -q`. Notebook contract tests: `cd apps && uv run --project server pytest server/tests/training_data/test_dpo_colab_contract.py -q`.
- Baselines before this plan: `python -m pytest training/tests -q` reports 59 passed; the contract test file reports 37 passed.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `docs/colab/dpo_training_template.ipynb` | modify (cells 3, 5, 8, 9) | grouped held-out split; write and hash `heldout_pairs.jsonl` |
| `apps/server/tests/training_data/test_dpo_colab_contract.py` | modify (append + `import sys`) | pin the new split and held-out artifact offline |
| `training/evaluate_adapter.py` | create | scoring, sign test, verdict, held-out loading, run, report, CLI |
| `training/tests/test_evaluate_adapter.py` | create | offline tests incl. a fake llama-server |
| `training/evaluating-an-adapter.md` | create | how-to for running an evaluation |
| `training/README.md` | modify (append) | point at the evaluation tool |

`evaluate_adapter.py` is built up across Tasks 2-5 by appending; each task adds a self-contained section and the tests for it. The final file is about 670 lines, the same shape as `smoke_test_lora_serving.py`.

Two tasks are manual and need the user (Task 7): a run against the host's live server, and one real Colab run of the changed notebook. Tasks 1-6 need neither GPU nor network.

---

### Task 1: Notebook holds out whole evaluations and ships the held-out file

**Files:**
- Modify: `docs/colab/dpo_training_template.ipynb` (cells 3, 5, 8, 9, via a one-off script)
- Modify: `apps/server/tests/training_data/test_dpo_colab_contract.py` (add `import sys`; append tests)

**Interfaces:**
- Consumes: cell 2 already defines `pairs` and `pair_provenance_records` (a list of `(pair, provenance_record)`), each provenance record having `pair_id` and `evaluation_id`. Cell 7's `trainer`/`model` and cell 9's `training_args`, `manifest`, `metrics`, `ADAPTER_DIR` are unchanged.
- Produces: cell 5 defines `train_dataset`, `eval_dataset` (or `None`), `train_items`, `heldout_items`, `heldout_rows` (list of row dicts, `[]` when nothing held out), and the constants `HELDOUT_PERCENT = 20`, `HELDOUT_SEED = 42`, `HELDOUT_METHOD = "group_by_evaluation_id"`. Cell 9 writes `<ADAPTER_DIR>/heldout_pairs.jsonl` (one `json.dumps(row, ensure_ascii=False, sort_keys=True)` line each, UTF-8, `\n` endings) and adds `"heldout"` to `training_manifest.json`. Task 3 reads exactly this format.

- [ ] **Step 1: Add `import sys` to the contract test file**

In `apps/server/tests/training_data/test_dpo_colab_contract.py`, add `import sys` on its own line directly after `import json` in the import block (the block reads `import hashlib`, `import io`, `import json`, `import tempfile`, `import zipfile`; `sys` goes between `json` and `tempfile`).

- [ ] **Step 2: Append the failing tests**

Append this to the end of `apps/server/tests/training_data/test_dpo_colab_contract.py`:

```python


# --- grouped held-out split (cell 5) and held-out artifact (cells 8-10) -------


class _FakeDatasetsModule:
    """Stands in for `datasets` (not installed in the CPU test environment)."""

    class Dataset:
        @staticmethod
        def from_list(rows):
            return list(rows)


def _pairs_and_provenance(n_evaluations: int, pairs_per_evaluation: int):
    pairs: list[dict[str, str]] = []
    records: list[dict[str, Any]] = []
    for e in range(n_evaluations):
        for p in range(pairs_per_evaluation):
            n = e * pairs_per_evaluation + p
            pair = {
                "prompt": f"prompt {n}",
                "chosen": f"chosen {n}",
                "rejected": f"rejected {n}",
            }
            pairs.append(pair)
            records.append(
                {
                    "pair_id": f"{n + 1:08x}-1111-1111-1111-111111111111",
                    "evaluation_id": f"{e + 1:08x}-2222-2222-2222-222222222222",
                }
            )
    return pairs, list(zip(pairs, records, strict=True))


def _run_split_cell(monkeypatch, pairs, pair_provenance_records) -> dict[str, Any]:
    monkeypatch.setitem(sys.modules, "datasets", _FakeDatasetsModule)
    ctx: dict[str, Any] = {
        "pairs": pairs,
        "pair_provenance_records": pair_provenance_records,
    }
    exec(_get_notebook_cell_code(5), ctx)  # noqa: S102
    return ctx


def test_split_cell_holds_out_whole_evaluations(monkeypatch):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=3)
    ctx = _run_split_cell(monkeypatch, pairs, records)

    heldout_rows = ctx["heldout_rows"]
    heldout_evals = {row["evaluation_id"] for row in heldout_rows}
    assert len(heldout_evals) == 2  # ceil(20% of 10 evaluations)
    assert len(heldout_rows) == 6  # every pair of a held-out evaluation
    assert len(ctx["train_dataset"]) == 24
    assert len(ctx["eval_dataset"]) == 6
    train_evals = {
        prov["evaluation_id"] for _, prov in ctx["train_items"]
    }
    assert train_evals.isdisjoint(heldout_evals)


def test_split_cell_rows_carry_ids_and_datasets_carry_only_training_columns(
    monkeypatch,
):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=3)
    ctx = _run_split_cell(monkeypatch, pairs, records)

    for row in ctx["heldout_rows"]:
        assert set(row) == {
            "pair_id",
            "evaluation_id",
            "prompt",
            "chosen",
            "rejected",
        }
    for row in [*ctx["train_dataset"], *ctx["eval_dataset"]]:
        assert set(row) == {"prompt", "chosen", "rejected"}


def test_split_cell_is_deterministic(monkeypatch):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=3)
    first = _run_split_cell(monkeypatch, pairs, records)["heldout_rows"]
    second = _run_split_cell(monkeypatch, pairs, records)["heldout_rows"]
    assert first == second


def test_split_cell_holds_out_one_of_two_evaluations(monkeypatch):
    pairs, records = _pairs_and_provenance(n_evaluations=2, pairs_per_evaluation=10)
    ctx = _run_split_cell(monkeypatch, pairs, records)

    assert len({row["evaluation_id"] for row in ctx["heldout_rows"]}) == 1
    assert len(ctx["heldout_rows"]) == 10
    assert len(ctx["train_dataset"]) == 10


def test_split_cell_holds_nothing_out_below_twenty_pairs(monkeypatch, capsys):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=1)
    ctx = _run_split_cell(monkeypatch, pairs, records)

    assert ctx["eval_dataset"] is None
    assert ctx["heldout_rows"] == []
    assert len(ctx["train_dataset"]) == 10
    assert "Holding nothing out" in capsys.readouterr().out


def test_split_cell_holds_nothing_out_for_a_single_evaluation(monkeypatch, capsys):
    pairs, records = _pairs_and_provenance(n_evaluations=1, pairs_per_evaluation=25)
    ctx = _run_split_cell(monkeypatch, pairs, records)

    assert ctx["eval_dataset"] is None
    assert ctx["heldout_rows"] == []
    assert len(ctx["train_dataset"]) == 25
    assert "single evaluation" in capsys.readouterr().out


class _FakePeftConfig:
    def to_dict(self):
        return {
            "r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0,
            "target_modules": {"q_proj", "v_proj"},
        }


class _FakeModel:
    peft_config = {"default": _FakePeftConfig()}


class _FakeTrainingArgs:
    seed = 42
    learning_rate = 5e-6
    num_train_epochs = 1
    beta = 0.1
    per_device_train_batch_size = 1
    gradient_accumulation_steps = 8


def _run_manifest_cell(split_ctx: dict[str, Any], adapter_dir: Path) -> dict[str, Any]:
    ctx = dict(split_ctx)
    ctx.update(
        {
            "ADAPTER_DIR": str(adapter_dir),
            "manifest": {"pairs_sha256": "a" * 64, "provenance_sha256": "b" * 64},
            "BASE_MODEL_NAME": "unsloth/gemma-3-4b-it",
            "BASE_MODEL_REVISION": "rev",
            "training_args": _FakeTrainingArgs(),
            "TRAINING_SEED": 42,
            "PRECISION_NAME": "float16",
            "USE_FP16": True,
            "USE_BF16": False,
            "MAX_SEQ_LENGTH": 2048,
            "model": _FakeModel(),
            "metrics": None,
        }
    )
    exec(_get_notebook_cell_code(9), ctx)  # noqa: S102
    return ctx


def test_manifest_cell_writes_heldout_file_and_records_its_hash(
    monkeypatch, tmp_path
):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=3)
    split_ctx = _run_split_cell(monkeypatch, pairs, records)
    adapter_dir = tmp_path / "trained_adapter"
    adapter_dir.mkdir()

    _run_manifest_cell(split_ctx, adapter_dir)

    heldout_path = adapter_dir / "heldout_pairs.jsonl"
    heldout_bytes = heldout_path.read_bytes()
    lines = heldout_bytes.decode("utf-8").splitlines()
    assert [json.loads(line) for line in lines] == split_ctx["heldout_rows"]

    training_manifest = json.loads(
        (adapter_dir / "training_manifest.json").read_text(encoding="utf-8")
    )
    assert training_manifest["heldout"] == {
        "method": "group_by_evaluation_id",
        "seed": 42,
        "fraction": 0.2,
        "pair_count": 6,
        "evaluation_count": 2,
        "sha256": hashlib.sha256(heldout_bytes).hexdigest(),
    }


def test_manifest_cell_records_null_heldout_when_nothing_was_held_out(
    monkeypatch, tmp_path
):
    pairs, records = _pairs_and_provenance(n_evaluations=5, pairs_per_evaluation=1)
    split_ctx = _run_split_cell(monkeypatch, pairs, records)
    adapter_dir = tmp_path / "trained_adapter"
    adapter_dir.mkdir()

    _run_manifest_cell(split_ctx, adapter_dir)

    assert not (adapter_dir / "heldout_pairs.jsonl").exists()
    training_manifest = json.loads(
        (adapter_dir / "training_manifest.json").read_text(encoding="utf-8")
    )
    assert training_manifest["heldout"] is None


def test_packaging_cell_archives_the_heldout_file(monkeypatch, tmp_path):
    pairs, records = _pairs_and_provenance(n_evaluations=10, pairs_per_evaluation=3)
    split_ctx = _run_split_cell(monkeypatch, pairs, records)
    adapter_dir = tmp_path / "trained_adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"weights")
    _run_manifest_cell(split_ctx, adapter_dir)

    mock_requests = (
        "class _MockRequests:\n"
        "    @staticmethod\n"
        "    def post(url, files=None):\n"
        "        class _Resp:\n"
        "            def raise_for_status(self): pass\n"
        "            def json(self): return {}\n"
        "        return _Resp()\n"
        "requests = _MockRequests()\n"
    )
    code = _get_notebook_cell_code(10).replace("import requests\n", mock_requests)
    zip_path = tmp_path / "out.zip"
    code = code.replace(
        'ADAPTER_ZIP_PATH = "trained_adapter.zip"',
        f"ADAPTER_ZIP_PATH = {str(zip_path)!r}",
    )
    exec(code, {"ADAPTER_DIR": str(adapter_dir), "UPLOAD_URL": "http://mock"})  # noqa: S102

    with zipfile.ZipFile(zip_path) as zf:
        assert "heldout_pairs.jsonl" in zf.namelist()
        assert "training_manifest.json" in zf.namelist()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_dpo_colab_contract.py -q`
Expected: `9 failed, 37 passed`. The 9 failures are the new `test_split_cell_*`, `test_manifest_cell_*` and `test_packaging_cell_archives_the_heldout_file` tests (the old notebook has no `heldout_rows`, no `heldout` block).

- [ ] **Step 4: Apply the notebook edit**

Write the script below to a file outside the repo (for example your scratchpad directory as `edit_notebook.py`), then run it from the repo root with `python <path-to>/edit_notebook.py`. It rewrites cell 5 and edits cells 3, 8 and 9 in place, asserting every original snippet exists exactly once, and keeps the file's CRLF/indent-1/no-trailing-newline serialisation. Run it exactly once.

```python
"""One-off: apply the grouped held-out split to docs/colab/dpo_training_template.ipynb.

Run from the repo root:  python <this file>
Idempotence is NOT supported: it asserts each original snippet exists exactly once.
"""

import json
from pathlib import Path

NOTEBOOK = Path("docs/colab/dpo_training_template.ipynb")

CELL_3_OLD = """The cells below install dependencies, build a train/validation split from
the fetched and verified `pairs`, load a 4-bit quantized base model with a LoRA
adapter, run TRL's `DPOTrainer`, print a sanity-check evaluation (this is
NOT the project's held-out test set -- see the printed note), and bundle a
reproducible provenance training manifest into the adapter before the push-back
cell zips and uploads it."""

CELL_3_NEW = """The cells below install dependencies, hold out whole evaluations (split by
`evaluation_id`) from the fetched and verified `pairs`, load a 4-bit quantized
base model with a LoRA adapter, run TRL's `DPOTrainer`, print a sanity-check
evaluation on the held-out set (the real adapter-vs-base comparison is
`training/evaluate_adapter.py`), and bundle a reproducible provenance training
manifest plus the held-out pairs (`heldout_pairs.jsonl`) into the adapter before
the push-back cell zips and uploads it."""

CELL_5_NEW = r'''import hashlib

from datasets import Dataset

MIN_PAIRS_FOR_EVAL_SPLIT = 20
HELDOUT_PERCENT = 20
HELDOUT_SEED = 42
HELDOUT_METHOD = "group_by_evaluation_id"


def split_by_evaluation(pair_provenance, percent, seed):
    """Hold out whole evaluations so none is on both sides of the split.

    pair_provenance is a list of (pair, provenance_record). Evaluations are
    ordered by sha256("<seed>:<evaluation_id>") -- deterministic, no RNG -- and
    the first ceil(percent% of them) are held out: at least one, and never all
    of them. A single evaluation cannot be split, so nothing is held out then.
    Returns (train_items, heldout_items), each keeping the original order.
    """
    evaluation_ids = {prov["evaluation_id"] for _, prov in pair_provenance}
    if len(evaluation_ids) < 2:
        return list(pair_provenance), []
    ordered = sorted(
        evaluation_ids,
        key=lambda eid: hashlib.sha256(f"{seed}:{eid}".encode("utf-8")).hexdigest(),
    )
    count = (len(ordered) * percent + 99) // 100
    count = min(max(1, count), len(ordered) - 1)
    heldout_ids = set(ordered[:count])
    train = [item for item in pair_provenance if item[1]["evaluation_id"] not in heldout_ids]
    heldout = [item for item in pair_provenance if item[1]["evaluation_id"] in heldout_ids]
    return train, heldout


def _training_row(pair):
    return {key: pair[key] for key in ("prompt", "chosen", "rejected")}


if len(pairs) >= MIN_PAIRS_FOR_EVAL_SPLIT:
    train_items, heldout_items = split_by_evaluation(
        pair_provenance_records, HELDOUT_PERCENT, HELDOUT_SEED
    )
else:
    train_items, heldout_items = list(pair_provenance_records), []

train_dataset = Dataset.from_list([_training_row(pair) for pair, _ in train_items])
if heldout_items:
    eval_dataset = Dataset.from_list([_training_row(pair) for pair, _ in heldout_items])
    # Saved into the adapter zip by the manifest cell so the adapter can be
    # evaluated later on pairs it never trained on.
    heldout_rows = [
        {
            "pair_id": prov["pair_id"],
            "evaluation_id": prov["evaluation_id"],
            **_training_row(pair),
        }
        for pair, prov in heldout_items
    ]
else:
    eval_dataset = None
    heldout_rows = []
    reason = (
        f"only {len(pairs)} pairs are available (< {MIN_PAIRS_FOR_EVAL_SPLIT})"
        if len(pairs) < MIN_PAIRS_FOR_EVAL_SPLIT
        else "every pair comes from a single evaluation"
    )
    print(
        f"Holding nothing out: {reason}. Training on all pairs; the eval "
        "sanity-check cell below will be skipped and this adapter will carry "
        "no held-out set, so it cannot be evaluated later."
    )

print(
    f"train_dataset: {len(train_dataset)} pairs from "
    f"{len({prov['evaluation_id'] for _, prov in train_items})} evaluation(s)"
)
if eval_dataset is not None:
    print(
        f"held-out: {len(heldout_rows)} pairs from "
        f"{len({row['evaluation_id'] for row in heldout_rows})} evaluation(s), "
        "saved with the adapter so it can be evaluated later"
    )'''

CELL_8_OLD = '''            "NOTE: this is an in-run sanity check on a random 10% split of "
            "THIS training run's own data -- it is not the project's "
            "held-out test set, and does not compare against the base model. "
            "A low accuracy here is a strong signal something went wrong; a "
            "high accuracy is not by itself a green light to deploy."'''

CELL_8_NEW = '''            "NOTE: this is an in-run sanity check on the evaluations held out "
            "of THIS training run (split by evaluation_id). It does not "
            "compare against the base model. The held-out pairs are saved in "
            "the adapter zip as heldout_pairs.jsonl; run "
            "training/evaluate_adapter.py against the served adapter for the "
            "real adapter-vs-base comparison. A low accuracy here is a strong "
            "signal something went wrong; a high accuracy is not by itself a "
            "green light to deploy."'''

CELL_9_IMPORT_OLD = "import importlib.metadata\nimport json as _json\nimport os\n"
CELL_9_IMPORT_NEW = "import hashlib\nimport importlib.metadata\nimport json as _json\nimport os\n"

CELL_9_HELDOUT_ANCHOR = "training_manifest = {\n    \"source_job_manifest\": manifest,\n"
CELL_9_HELDOUT_BLOCK = '''HELDOUT_FILENAME = "heldout_pairs.jsonl"
if heldout_rows:
    heldout_bytes = "".join(
        _json.dumps(row, ensure_ascii=False, sort_keys=True) + "\\n"
        for row in heldout_rows
    ).encode("utf-8")
    with open(os.path.join(ADAPTER_DIR, HELDOUT_FILENAME), "wb") as f:
        f.write(heldout_bytes)
    heldout_manifest = {
        "method": HELDOUT_METHOD,
        "seed": HELDOUT_SEED,
        "fraction": HELDOUT_PERCENT / 100,
        "pair_count": len(heldout_rows),
        "evaluation_count": len({row["evaluation_id"] for row in heldout_rows}),
        "sha256": hashlib.sha256(heldout_bytes).hexdigest(),
    }
else:
    heldout_manifest = None

'''

CELL_9_FIELD_OLD = '    "pair_count": len(pairs),\n    "eval_metrics": metrics,\n}'
CELL_9_FIELD_NEW = (
    '    "pair_count": len(pairs),\n    "heldout": heldout_manifest,\n'
    '    "eval_metrics": metrics,\n}'
)


def to_source(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def replace_once(cell: dict, old: str, new: str) -> None:
    text = "".join(cell["source"])
    assert text.count(old) == 1, f"expected exactly one match for: {old[:60]!r}"
    cell["source"] = to_source(text.replace(old, new))


raw = NOTEBOOK.read_bytes()
notebook = json.loads(raw.decode("utf-8"))
cells = notebook["cells"]

replace_once(cells[3], CELL_3_OLD, CELL_3_NEW)
cells[5]["source"] = to_source(CELL_5_NEW)
replace_once(cells[8], CELL_8_OLD, CELL_8_NEW)
replace_once(cells[9], CELL_9_IMPORT_OLD, CELL_9_IMPORT_NEW)
replace_once(cells[9], CELL_9_HELDOUT_ANCHOR, CELL_9_HELDOUT_BLOCK + CELL_9_HELDOUT_ANCHOR)
replace_once(cells[9], CELL_9_FIELD_OLD, CELL_9_FIELD_NEW)

# Same serialisation the file already uses: indent=1, CRLF, no trailing newline.
out = json.dumps(notebook, indent=1, ensure_ascii=False).replace("\n", "\r\n")
NOTEBOOK.write_bytes(out.encode("utf-8"))
print("notebook updated")
```

Expected output: `notebook updated`.

- [ ] **Step 5: Run the contract tests to verify they pass**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_dpo_colab_contract.py -q`
Expected: `46 passed` (37 existing + 9 new; one unrelated `Duplicate name` UserWarning is normal).

- [ ] **Step 6: Check the diff is only what you meant**

Run: `git diff --stat`
Expected: exactly two files: `docs/colab/dpo_training_template.ipynb` (about 108 insertions, 22 deletions) and the contract test file. If the notebook shows thousands of changed lines, the CRLF/indent serialisation was lost: run `git checkout docs/colab/dpo_training_template.ipynb` and redo Step 4.

- [ ] **Step 7: Commit**

```bash
git add docs/colab/dpo_training_template.ipynb apps/server/tests/training_data/test_dpo_colab_contract.py
git commit -m "feat(colab): hold out whole evaluations and ship heldout_pairs.jsonl with the adapter"
```

---

### Task 2: Scoring, sign test and verdict

**Files:**
- Create: `training/evaluate_adapter.py`
- Create: `training/tests/test_evaluate_adapter.py`

**Interfaces:**
- Consumes: from `training/smoke_test_lora_serving.py`: `validate_sme_reply(text) -> ValidationResult(valid, reason, scores)`, `MIN_SCORE`, `MAX_SCORE` (already in the repo).
- Produces (later tasks rely on these exact names): constants `HELDOUT_FILENAME`, `TRAINING_MANIFEST_FILENAME`, `DEFAULT_MIN_DECISIVE = 20`, `DEFAULT_ALPHA = 0.05`, `DEFAULT_MAX_TOKENS = 2048`, `WORST_ERROR = 3`, `MAX_MEMBER_BYTES`, `LIMITS_NOTE`; `answer_key(chosen: str, rejected: str) -> dict[str, int] | None`; `error_total(key, scores | None) -> int`; frozen dataclass `PairScore(pair_id, gold, base_scores, adapter_scores, base_error: float, adapter_error: float, outcome: "win"|"loss"|"tie")`; `score_pair(pair_id, key, base_scores, adapter_scores) -> PairScore`; `sign_test_p(wins, losses) -> float`; frozen dataclass `Verdict(verdict: "better"|"worse"|"inconclusive", reasons: tuple[str, ...], p_value: float)`; `decide(wins, losses, base_valid_rate, adapter_valid_rate, *, min_decisive, alpha) -> Verdict`. The module header imports everything the later tasks need (`argparse`, `hashlib`, `http.client`, `json`, `math`, `os`, `sys`, `zipfile`, `Callable`, `Sequence`, `dataclass`, `Path`).

- [ ] **Step 1: Write the failing tests**

Create `training/tests/test_evaluate_adapter.py`:

```python
"""Offline tests for training/evaluate_adapter.py (no server, no GPU)."""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

TRAINING_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_DIR))

import evaluate_adapter as ev  # noqa: E402


def _reply(scores: dict[str, int], summary: str = "ok") -> str:
    return json.dumps(
        {
            "summary": summary,
            "criterion_measurements": [
                {"criterion_id": criterion_id, "score": score}
                for criterion_id, score in scores.items()
            ],
        }
    )


# --- answer_key ---------------------------------------------------------------


def test_answer_key_holds_only_criteria_the_reviewer_changed():
    rejected = _reply({"A-01": 1, "A-02": 3, "A-03": 2})
    chosen = _reply({"A-01": 3, "A-02": 3, "A-03": 4})
    assert ev.answer_key(chosen, rejected) == {"A-01": 3, "A-03": 4}


def test_answer_key_is_none_when_no_score_changed():
    same = _reply({"A-01": 2})
    assert ev.answer_key(same, same) is None


def test_answer_key_is_none_when_a_reply_is_unparsable():
    assert ev.answer_key("not json", _reply({"A-01": 1})) is None
    assert ev.answer_key(_reply({"A-01": 1}), "not json") is None


def test_answer_key_ignores_criteria_missing_from_the_other_reply():
    assert ev.answer_key(_reply({"A-01": 3, "A-02": 2}), _reply({"A-01": 1})) == {
        "A-01": 3
    }


# --- error_total and score_pair -------------------------------------------------


def test_error_total_sums_absolute_differences():
    assert ev.error_total({"A": 3, "B": 1}, {"A": 1, "B": 1, "C": 4}) == 2


def test_error_total_counts_a_missing_criterion_as_the_worst_error():
    assert ev.error_total({"A": 3, "B": 1}, {"A": 3}) == ev.WORST_ERROR


def test_error_total_counts_an_invalid_reply_as_the_worst_error():
    assert ev.error_total({"A": 3, "B": 1}, None) == 2 * ev.WORST_ERROR


def test_worst_error_is_the_score_range():
    assert ev.WORST_ERROR == 3


def test_score_pair_win_loss_and_tie():
    key = {"A": 3}
    win = ev.score_pair("p1", key, {"A": 1}, {"A": 3})
    loss = ev.score_pair("p2", key, {"A": 3}, {"A": 1})
    tie = ev.score_pair("p3", key, {"A": 2}, {"A": 4})
    assert (win.outcome, loss.outcome, tie.outcome) == ("win", "loss", "tie")
    assert (win.base_error, win.adapter_error) == (2.0, 0.0)
    assert win.gold == {"A": 3}
    assert win.pair_id == "p1"


def test_score_pair_a_valid_but_wrong_adapter_beats_an_invalid_base():
    result = ev.score_pair("p", {"A": 3}, None, {"A": 1})
    assert result.outcome == "win"
    assert result.base_scores is None


# --- sign test ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wins", "losses", "expected"),
    [
        (0, 0, 1.0),
        (5, 5, 1.0),
        (9, 1, 0.021484375),
        (1, 9, 0.021484375),
        (15, 5, 0.04138946533203125),
        (14, 6, 0.115318298339844),
        (20, 0, 2 / 2**20),
    ],
)
def test_sign_test_matches_exact_binomial_values(wins, losses, expected):
    assert ev.sign_test_p(wins, losses) == pytest.approx(expected, rel=1e-6)


# --- verdict --------------------------------------------------------------------


def _decide(wins, losses, base_rate=1.0, adapter_rate=1.0, **overrides):
    params = {"min_decisive": 20, "alpha": 0.05, **overrides}
    return ev.decide(wins, losses, base_rate, adapter_rate, **params)


def test_verdict_too_few_decisive_pairs_is_inconclusive_even_if_all_wins():
    result = _decide(19, 0)
    assert result.verdict == "inconclusive"
    assert "too few decisive pairs (19 < 20)" in result.reasons[0]


def test_verdict_better_when_wins_dominate():
    result = _decide(20, 4)
    assert result.verdict == "better"
    assert result.p_value < 0.05


def test_verdict_worse_when_losses_dominate():
    assert _decide(4, 20).verdict == "worse"


def test_verdict_inconclusive_when_not_significant():
    result = _decide(13, 9)
    assert result.verdict == "inconclusive"
    assert "not statistically significant" in result.reasons[0]


def test_verdict_better_is_capped_when_adapter_returns_more_invalid_json():
    result = _decide(24, 2, base_rate=1.0, adapter_rate=0.9)
    assert result.verdict == "inconclusive"
    assert "invalid JSON" in result.reasons[0]


def test_verdict_worse_is_not_capped_by_validity():
    assert _decide(2, 24, base_rate=1.0, adapter_rate=0.9).verdict == "worse"


def test_verdict_respects_custom_min_decisive_and_alpha():
    assert _decide(9, 1, min_decisive=10).verdict == "better"
    assert _decide(9, 1, min_decisive=10, alpha=0.01).verdict == "inconclusive"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest training/tests/test_evaluate_adapter.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'evaluate_adapter'`.

- [ ] **Step 3: Write the implementation**

Create `training/evaluate_adapter.py`:

```python
"""Compare a GGUF LoRA adapter with the plain model on held-out DPO pairs.

Each held-out pair is a case a reviewer corrected: `rejected` is the model's
original SME/Coordinator reply and `chosen` is the same reply with the
reviewer's scores. This script sends every held-out prompt to a running
llama-server twice -- adapter off (scale 0) and adapter on (scale 1) -- and
checks which reply lands closer to the reviewer's corrected scores. A
two-sided sign test on the per-pair wins and losses turns that into a verdict:
better, worse or inconclusive.

Usage:
    python training/evaluate_adapter.py --adapter-zip adapter.zip \
        --base-url http://127.0.0.1:8080/v1 --report-json report.json

The held-out set comes from `heldout_pairs.jsonl` inside the adapter zip (the
DPO training notebook writes it) or from a bare file via --heldout.

Server options, environment fallbacks (LLM_API_BASE, LLM_API_KEY,
LLM_MODEL_NAME), the scale modes and the global-scale reset all work as in
training/smoke_test_lora_serving.py, whose client this script reuses.

Exit code: 0 the adapter is better, 1 worse or inconclusive, 2 could not run
(server unreachable, no adapter loaded, no held-out set, bad input).

What a verdict means: the held-out pairs are only cases reviewers CHANGED, so
this measures whether the adapter fixes known mistakes, not whether it harms
cases reviewers approved. Only the criterion_measurements reply shape (SME and
Coordinator) is supported.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import sys
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import smoke_test_lora_serving as smoke

HELDOUT_FILENAME = "heldout_pairs.jsonl"
TRAINING_MANIFEST_FILENAME = "training_manifest.json"
DEFAULT_MIN_DECISIVE = 20
DEFAULT_ALPHA = 0.05
DEFAULT_MAX_TOKENS = 2048
# A missing, unparsable or out-of-range answer is as wrong as a score can be.
WORST_ERROR = smoke.MAX_SCORE - smoke.MIN_SCORE
# Refuse to read absurdly large members out of a zip.
MAX_MEMBER_BYTES = 64 * 1024 * 1024

LIMITS_NOTE = (
    "Limits: the held-out pairs are only cases reviewers CHANGED, so this "
    "measures fixing known mistakes, not harm to cases reviewers approved. "
    "With few pairs a verdict is weak evidence."
)


def answer_key(chosen: str, rejected: str) -> dict[str, int] | None:
    """The reviewer's score for every criterion they changed, else None.

    A criterion is in the key when it appears in both replies and its score
    differs; the value is the score in `chosen`. None means the pair cannot be
    scored (an unparsable reply, or no changed score).
    """
    chosen_result = smoke.validate_sme_reply(chosen)
    rejected_result = smoke.validate_sme_reply(rejected)
    if not (chosen_result.valid and rejected_result.valid):
        return None
    key = {
        criterion_id: score
        for criterion_id, score in chosen_result.scores.items()
        if criterion_id in rejected_result.scores
        and rejected_result.scores[criterion_id] != score
    }
    return key or None


def error_total(key: dict[str, int], scores: dict[str, int] | None) -> int:
    """Sum of |score - reviewer's score| over the key.

    `scores` is None for an invalid reply; a criterion the reply lacks is also
    counted at the worst error.
    """
    if scores is None:
        return WORST_ERROR * len(key)
    return sum(
        abs(scores[criterion_id] - gold)
        if criterion_id in scores
        else WORST_ERROR
        for criterion_id, gold in key.items()
    )


@dataclass(frozen=True)
class PairScore:
    pair_id: str
    gold: dict[str, int]
    base_scores: dict[str, int] | None
    adapter_scores: dict[str, int] | None
    base_error: float
    adapter_error: float
    outcome: str  # "win" | "loss" | "tie" -- from the adapter's point of view


def score_pair(
    pair_id: str,
    key: dict[str, int],
    base_scores: dict[str, int] | None,
    adapter_scores: dict[str, int] | None,
) -> PairScore:
    base_total = error_total(key, base_scores)
    adapter_total = error_total(key, adapter_scores)
    if adapter_total < base_total:
        outcome = "win"
    elif adapter_total > base_total:
        outcome = "loss"
    else:
        outcome = "tie"
    return PairScore(
        pair_id=pair_id,
        gold=dict(key),
        base_scores=base_scores,
        adapter_scores=adapter_scores,
        base_error=base_total / len(key),
        adapter_error=adapter_total / len(key),
        outcome=outcome,
    )


def sign_test_p(wins: int, losses: int) -> float:
    """Exact two-sided sign test p-value; ties are not part of the input."""
    decisive = wins + losses
    if decisive == 0:
        return 1.0
    tail = sum(math.comb(decisive, i) for i in range(min(wins, losses) + 1))
    return min(1.0, 2 * tail / 2**decisive)


@dataclass(frozen=True)
class Verdict:
    verdict: str  # "better" | "worse" | "inconclusive"
    reasons: tuple[str, ...]
    p_value: float


def decide(
    wins: int,
    losses: int,
    base_valid_rate: float,
    adapter_valid_rate: float,
    *,
    min_decisive: int,
    alpha: float,
) -> Verdict:
    decisive = wins + losses
    p_value = sign_test_p(wins, losses)
    if decisive < min_decisive:
        return Verdict(
            "inconclusive",
            (f"too few decisive pairs ({decisive} < {min_decisive})",),
            p_value,
        )
    if p_value >= alpha:
        return Verdict(
            "inconclusive",
            (
                f"the difference is not statistically significant "
                f"(p={p_value:.4f}, alpha={alpha})",
            ),
            p_value,
        )
    if losses > wins:
        return Verdict(
            "worse",
            (f"adapter lost {losses} and won {wins} decisive pairs (p={p_value:.4f})",),
            p_value,
        )
    if adapter_valid_rate < base_valid_rate:
        return Verdict(
            "inconclusive",
            (
                f"adapter won {wins} and lost {losses} decisive pairs "
                f"(p={p_value:.4f}) but returns invalid JSON more often than "
                "the plain model",
            ),
            p_value,
        )
    return Verdict(
        "better",
        (f"adapter won {wins} and lost {losses} decisive pairs (p={p_value:.4f})",),
        p_value,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest training/tests/test_evaluate_adapter.py -q`
Expected: `24 passed`.

- [ ] **Step 5: Commit**

```bash
git add training/evaluate_adapter.py training/tests/test_evaluate_adapter.py
git commit -m "feat(training): score adapter vs base replies with a sign-test verdict"
```

---

### Task 3: Load the held-out set from an adapter zip or a bare file

**Files:**
- Modify: `training/evaluate_adapter.py` (append)
- Modify: `training/tests/test_evaluate_adapter.py` (append)

**Interfaces:**
- Consumes: `HELDOUT_FILENAME`, `TRAINING_MANIFEST_FILENAME`, `MAX_MEMBER_BYTES` (Task 2). The zip layout Task 1 produces: root `training_manifest.json` containing `heldout` (`pair_count`, `sha256`, ...) and root `heldout_pairs.jsonl`.
- Produces: frozen dataclass `HeldoutPair(pair_id, evaluation_id, prompt, chosen, rejected)` (all `str`); frozen dataclass `HeldoutSet(pairs: tuple[HeldoutPair, ...], source: str, sha256: str, sha256_verified: bool, adapter_zip_sha256: str | None = None)`; `parse_heldout(data: bytes) -> tuple[HeldoutPair, ...]` (raises `ValueError`); `load_heldout_file(path) -> HeldoutSet`; `load_heldout_zip(path) -> HeldoutSet` (raises `ValueError` with "no held-out set" when the manifest has no `heldout` object, and `zipfile.BadZipFile` for a non-zip).

- [ ] **Step 1: Append the failing tests**

Append to the end of `training/tests/test_evaluate_adapter.py`:

```python


# --- loading the held-out set ----------------------------------------------------


def _heldout_row(n: int, **overrides) -> dict:
    row = {
        "pair_id": f"pair-{n}",
        "evaluation_id": f"eval-{n // 2}",
        "prompt": f"PROMPT-{n}",
        "chosen": _reply({"A-01": 3}),
        "rejected": _reply({"A-01": 1}),
    }
    row.update(overrides)
    return row


def _jsonl(rows: list[dict]) -> bytes:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()


def _make_adapter_zip(
    tmp_path: Path,
    rows: list[dict] | None = None,
    *,
    heldout: dict | None | str = "auto",
    include_file: bool = True,
    file_bytes: bytes | None = None,
) -> Path:
    rows = rows if rows is not None else [_heldout_row(n) for n in range(4)]
    data = file_bytes if file_bytes is not None else _jsonl(rows)
    if heldout == "auto":
        heldout = {
            "method": "group_by_evaluation_id",
            "seed": 42,
            "fraction": 0.2,
            "pair_count": len(rows),
            "evaluation_count": len({row["evaluation_id"] for row in rows}),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    path = tmp_path / "adapter.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("adapter_config.json", "{}")
        archive.writestr("adapter_model.safetensors", b"weights")
        archive.writestr("training_manifest.json", json.dumps({"heldout": heldout}))
        if include_file:
            archive.writestr("heldout_pairs.jsonl", data)
    return path


def test_load_heldout_zip_reads_and_verifies_the_file(tmp_path):
    path = _make_adapter_zip(tmp_path)
    heldout = ev.load_heldout_zip(path)

    assert [pair.pair_id for pair in heldout.pairs] == [f"pair-{n}" for n in range(4)]
    assert heldout.pairs[0].prompt == "PROMPT-0"
    assert heldout.sha256_verified is True
    assert heldout.adapter_zip_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert str(path) in heldout.source


def test_load_heldout_zip_without_a_heldout_block_says_so(tmp_path):
    for heldout in (None, "missing"):
        path = _make_adapter_zip(tmp_path, heldout=heldout)
        with pytest.raises(ValueError, match="no held-out set"):
            ev.load_heldout_zip(path)


def test_load_heldout_zip_rejects_a_file_that_does_not_match_its_hash(tmp_path):
    path = _make_adapter_zip(tmp_path, heldout={"pair_count": 4, "sha256": "0" * 64})
    with pytest.raises(ValueError, match="sha256"):
        ev.load_heldout_zip(path)


def test_load_heldout_zip_rejects_a_pair_count_mismatch(tmp_path):
    rows = [_heldout_row(n) for n in range(4)]
    data = _jsonl(rows)
    path = _make_adapter_zip(
        tmp_path,
        rows,
        heldout={"pair_count": 9, "sha256": hashlib.sha256(data).hexdigest()},
    )
    with pytest.raises(ValueError, match="9 held-out pairs but"):
        ev.load_heldout_zip(path)


def test_load_heldout_zip_reports_a_missing_heldout_file(tmp_path):
    path = _make_adapter_zip(tmp_path, include_file=False)
    with pytest.raises(ValueError, match="heldout_pairs.jsonl is not in the adapter"):
        ev.load_heldout_zip(path)


def test_load_heldout_zip_rejects_a_file_that_is_not_a_zip(tmp_path):
    bogus = tmp_path / "bogus.zip"
    bogus.write_text("not a zip")
    with pytest.raises(zipfile.BadZipFile):
        ev.load_heldout_zip(bogus)


def test_load_heldout_file_reads_a_bare_jsonl_unverified(tmp_path):
    path = tmp_path / "heldout_pairs.jsonl"
    path.write_bytes(_jsonl([_heldout_row(0), _heldout_row(1)]))
    heldout = ev.load_heldout_file(path)

    assert len(heldout.pairs) == 2
    assert heldout.sha256_verified is False
    assert heldout.adapter_zip_sha256 is None


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        (b"", "no pairs"),
        (b"{not json}\n", "line 1: not valid JSON"),
        (b"[1]\n", "line 1: not a JSON object"),
        (_jsonl([{k: v for k, v in _heldout_row(0).items() if k != "prompt"}]), "'prompt'"),
        (_jsonl([_heldout_row(0, chosen="  ")]), "'chosen'"),
        (_jsonl([_heldout_row(0), _heldout_row(1, pair_id=5)]), "line 2"),
    ],
)
def test_parse_heldout_rejects_malformed_files(data, fragment):
    with pytest.raises(ValueError, match=fragment):
        ev.parse_heldout(data)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest training/tests/test_evaluate_adapter.py -q`
Expected: the new tests fail with `AttributeError: module 'evaluate_adapter' has no attribute ...`; the 24 from Task 2 still pass.

- [ ] **Step 3: Append the implementation**

Append to the end of `training/evaluate_adapter.py`:

```python


@dataclass(frozen=True)
class HeldoutPair:
    pair_id: str
    evaluation_id: str
    prompt: str
    chosen: str
    rejected: str


@dataclass(frozen=True)
class HeldoutSet:
    pairs: tuple[HeldoutPair, ...]
    source: str
    sha256: str
    sha256_verified: bool
    adapter_zip_sha256: str | None = None


_HELDOUT_FIELDS = ("pair_id", "evaluation_id", "prompt", "chosen", "rejected")


def parse_heldout(data: bytes) -> tuple[HeldoutPair, ...]:
    """Parse the bytes of a heldout_pairs.jsonl file."""
    pairs: list[HeldoutPair] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        where = f"{HELDOUT_FILENAME} line {line_number}"
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{where}: not valid JSON: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{where}: not a JSON object")
        for name in _HELDOUT_FIELDS:
            value = row.get(name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{where}: missing or empty {name!r}")
        pairs.append(HeldoutPair(**{name: row[name] for name in _HELDOUT_FIELDS}))
    if not pairs:
        raise ValueError(f"{HELDOUT_FILENAME} contains no pairs")
    return tuple(pairs)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_heldout_file(path: Path) -> HeldoutSet:
    """A bare heldout_pairs.jsonl: nothing to verify it against."""
    data = Path(path).read_bytes()
    return HeldoutSet(
        pairs=parse_heldout(data),
        source=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        sha256_verified=False,
    )


def _read_member(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError:
        raise ValueError(f"{name} is not in the adapter zip") from None
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"{name} in the adapter zip is too large to read")
    return archive.read(name)


def load_heldout_zip(path: Path) -> HeldoutSet:
    """The held-out set of an adapter zip, checked against its manifest."""
    with zipfile.ZipFile(path) as archive:
        manifest_bytes = _read_member(archive, TRAINING_MANIFEST_FILENAME)
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except ValueError as exc:
            raise ValueError(
                f"{TRAINING_MANIFEST_FILENAME} in the adapter zip is not valid JSON"
            ) from exc
        heldout = manifest.get("heldout") if isinstance(manifest, dict) else None
        if not isinstance(heldout, dict):
            raise ValueError(
                "this adapter has no held-out set (it was trained on fewer than "
                "20 pairs, from a single evaluation, or with a notebook that "
                "predates the grouped split); pass --heldout to use another file"
            )
        data = _read_member(archive, HELDOUT_FILENAME)
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != heldout.get("sha256"):
        raise ValueError(
            f"{HELDOUT_FILENAME} does not match the sha256 recorded in "
            f"{TRAINING_MANIFEST_FILENAME}; the adapter zip was modified"
        )
    pairs = parse_heldout(data)
    if heldout.get("pair_count") != len(pairs):
        raise ValueError(
            f"{TRAINING_MANIFEST_FILENAME} says {heldout.get('pair_count')} "
            f"held-out pairs but {HELDOUT_FILENAME} has {len(pairs)}"
        )
    return HeldoutSet(
        pairs=pairs,
        source=f"{path}!{HELDOUT_FILENAME}",
        sha256=actual_sha256,
        sha256_verified=True,
        adapter_zip_sha256=_file_sha256(Path(path)),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest training/tests/test_evaluate_adapter.py -q`
Expected: `37 passed`.

- [ ] **Step 5: Commit**

```bash
git add training/evaluate_adapter.py training/tests/test_evaluate_adapter.py
git commit -m "feat(training): load and verify the held-out set from an adapter zip"
```

---

### Task 4: Run the evaluation and build the report

**Files:**
- Modify: `training/evaluate_adapter.py` (append)
- Modify: `training/tests/test_evaluate_adapter.py` (append)

**Interfaces:**
- Consumes: `HeldoutPair` (Task 3); `answer_key`, `score_pair`, `PairScore`, `decide`, `Verdict`, `LIMITS_NOTE`, `DEFAULT_MIN_DECISIVE`, `DEFAULT_ALPHA` (Task 2); `smoke.validate_sme_reply`.
- Produces: frozen dataclass `Evaluation(total_pairs, skipped, scores: tuple[PairScore, ...], base_valid, adapter_valid, identical_replies, verdict, min_decisive, alpha)` with properties `scoreable`, `wins`, `losses`, `ties`, `base_valid_rate`, `adapter_valid_rate`, `mean_base_error`, `mean_adapter_error`, `warnings`; `run_evaluation(pairs, complete: Callable[[str, float], str], *, min_decisive=20, alpha=0.05) -> Evaluation` (raises `ValueError` "nothing to evaluate" when no pair is scoreable; sends all scale-0.0 requests before any scale-1.0 request); `build_report(evaluation, *, parameters: dict, heldout: dict, adapter: dict | None) -> dict`; `format_report(evaluation) -> str`; `exit_code(evaluation) -> int` (0 only for "better"). `complete` has the same signature as the callable `smoke.make_complete(...)` returns.

- [ ] **Step 1: Append the failing tests**

Append to the end of `training/tests/test_evaluate_adapter.py`:

```python


# --- running the evaluation and reporting ------------------------------------------


def _pairs(count: int) -> list[ev.HeldoutPair]:
    """Pairs whose reviewer score for A-01 is 3 (the plain model said 1)."""
    return [
        ev.HeldoutPair(
            pair_id=f"pair-{n}",
            evaluation_id=f"eval-{n}",
            prompt=f"P{n}",
            chosen=_reply({"A-01": 3}),
            rejected=_reply({"A-01": 1}),
        )
        for n in range(count)
    ]


def _complete(base_score: int, adapter_score: int, calls: list | None = None):
    """A stand-in for the server: every reply carries one fixed A-01 score."""

    def complete(prompt: str, scale: float) -> str:
        if calls is not None:
            calls.append((prompt, scale))
        return _reply({"A-01": adapter_score if scale > 0 else base_score})

    return complete


def test_run_evaluation_all_wins_is_better():
    evaluation = ev.run_evaluation(_pairs(25), _complete(base_score=1, adapter_score=3))

    assert (evaluation.wins, evaluation.losses, evaluation.ties) == (25, 0, 0)
    assert evaluation.total_pairs == 25 and evaluation.skipped == 0
    assert evaluation.verdict.verdict == "better"
    assert evaluation.mean_base_error == 2.0
    assert evaluation.mean_adapter_error == 0.0
    assert evaluation.base_valid_rate == evaluation.adapter_valid_rate == 1.0
    assert evaluation.warnings == []
    assert ev.exit_code(evaluation) == 0


def test_run_evaluation_all_losses_is_worse():
    evaluation = ev.run_evaluation(_pairs(25), _complete(base_score=3, adapter_score=1))
    assert evaluation.losses == 25
    assert evaluation.verdict.verdict == "worse"
    assert ev.exit_code(evaluation) == 1


def test_run_evaluation_sends_all_off_requests_before_any_on_request():
    calls: list = []
    ev.run_evaluation(_pairs(3), _complete(1, 3, calls))
    assert [scale for _, scale in calls] == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    assert [prompt for prompt, _ in calls[:3]] == ["P0", "P1", "P2"]


def test_run_evaluation_skips_unscoreable_pairs_without_sending_them():
    unscoreable = ev.HeldoutPair(
        "skip", "eval-x", "SKIPPED-PROMPT", _reply({"A-01": 2}), _reply({"A-01": 2})
    )
    calls: list = []
    evaluation = ev.run_evaluation(
        [*_pairs(2), unscoreable], _complete(1, 3, calls)
    )

    assert evaluation.total_pairs == 3
    assert evaluation.skipped == 1
    assert evaluation.scoreable == 2
    assert all(prompt != "SKIPPED-PROMPT" for prompt, _ in calls)


def test_run_evaluation_with_nothing_scoreable_raises():
    same = _reply({"A-01": 2})
    pair = ev.HeldoutPair("p", "e", "P", same, same)
    with pytest.raises(ValueError, match="nothing to evaluate"):
        ev.run_evaluation([pair], _complete(1, 3))


def test_run_evaluation_invalid_adapter_reply_is_a_loss_and_lowers_validity():
    def complete(prompt: str, scale: float) -> str:
        if scale > 0:
            return "not json"
        return _reply({"A-01": 3})

    evaluation = ev.run_evaluation(_pairs(25), complete)
    assert evaluation.losses == 25
    assert evaluation.adapter_valid_rate == 0.0
    assert evaluation.base_valid_rate == 1.0
    assert evaluation.verdict.verdict == "worse"


def test_run_evaluation_warns_when_adapter_replies_equal_base_replies():
    evaluation = ev.run_evaluation(_pairs(25), _complete(2, 2))

    assert evaluation.ties == 25
    assert evaluation.verdict.verdict == "inconclusive"
    assert "too few decisive pairs (0 < 20)" in evaluation.verdict.reasons[0]
    assert "may not be applied" in evaluation.warnings[0]


def test_run_evaluation_passes_thresholds_through():
    evaluation = ev.run_evaluation(
        _pairs(10), _complete(1, 3), min_decisive=10, alpha=0.05
    )
    assert evaluation.verdict.verdict == "better"
    assert (evaluation.min_decisive, evaluation.alpha) == (10, 0.05)


def test_build_report_is_json_serialisable_and_holds_no_prompts():
    evaluation = ev.run_evaluation(_pairs(25), _complete(1, 3))
    report = ev.build_report(
        evaluation,
        parameters={"min_decisive": 20, "alpha": 0.05},
        heldout={"source": "x", "pair_count": 25},
        adapter={"zip_sha256": "abc"},
    )
    text = json.dumps(report)

    assert report["verdict"] == "better"
    assert report["pairs"] == {
        "heldout_total": 25,
        "scoreable": 25,
        "skipped": 0,
        "wins": 25,
        "losses": 0,
        "ties": 0,
    }
    assert report["mean_abs_error"] == {"base": 2.0, "adapter": 0.0}
    assert report["valid_json_rate"] == {"base": 1.0, "adapter": 1.0}
    assert report["sign_test_p"] == pytest.approx(2 / 2**25)
    assert report["per_pair"][0] == {
        "pair_id": "pair-0",
        "gold": {"A-01": 3},
        "base_scores": {"A-01": 1},
        "adapter_scores": {"A-01": 3},
        "outcome": "win",
    }
    assert len(report["per_pair"]) == 25
    assert "P0" not in text  # prompts never appear in the report


def test_format_report_shows_counts_verdict_and_the_limits_note():
    evaluation = ev.run_evaluation(_pairs(25), _complete(1, 3))
    text = ev.format_report(evaluation)

    assert "25 held-out pair(s), 25 scoreable" in text
    assert "valid JSON       base 25/25   adapter 25/25" in text
    assert "adapter 25 win(s), 0 loss(es), 0 tie(s)" in text
    assert "VERDICT: BETTER" in text
    assert ev.LIMITS_NOTE in text


def test_format_report_mentions_skipped_pairs_and_warnings():
    same = _reply({"A-01": 2})
    skip = ev.HeldoutPair("skip", "e", "S", same, same)
    evaluation = ev.run_evaluation([*_pairs(2), skip], _complete(2, 2))
    text = ev.format_report(evaluation)

    assert "1 skipped" in text
    assert "WARNING:" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest training/tests/test_evaluate_adapter.py -q`
Expected: 11 new failures (`AttributeError ... 'run_evaluation'` / `'build_report'` / `'format_report'`); 37 pass.

- [ ] **Step 3: Append the implementation**

Append to the end of `training/evaluate_adapter.py`:

```python


@dataclass(frozen=True)
class Evaluation:
    total_pairs: int
    skipped: int
    scores: tuple[PairScore, ...]
    base_valid: int
    adapter_valid: int
    identical_replies: bool
    verdict: Verdict
    min_decisive: int
    alpha: float

    @property
    def scoreable(self) -> int:
        return len(self.scores)

    def _count(self, outcome: str) -> int:
        return sum(1 for score in self.scores if score.outcome == outcome)

    @property
    def wins(self) -> int:
        return self._count("win")

    @property
    def losses(self) -> int:
        return self._count("loss")

    @property
    def ties(self) -> int:
        return self._count("tie")

    @property
    def base_valid_rate(self) -> float:
        return self.base_valid / self.scoreable

    @property
    def adapter_valid_rate(self) -> float:
        return self.adapter_valid / self.scoreable

    @property
    def mean_base_error(self) -> float:
        return sum(score.base_error for score in self.scores) / self.scoreable

    @property
    def mean_adapter_error(self) -> float:
        return sum(score.adapter_error for score in self.scores) / self.scoreable

    @property
    def warnings(self) -> list[str]:
        if not self.identical_replies:
            return []
        return [
            "the adapter's replies are identical to the plain model's for every "
            "pair; the adapter may not be applied (check GET /lora-adapters and "
            "try --scale-mode global)"
        ]


def run_evaluation(
    pairs: Sequence[HeldoutPair],
    complete: Callable[[str, float], str],
    *,
    min_decisive: int = DEFAULT_MIN_DECISIVE,
    alpha: float = DEFAULT_ALPHA,
) -> Evaluation:
    """Send every scoreable held-out prompt with the adapter off, then on.

    All "off" requests come first so a server that needs a global scale change
    between the two passes only has to switch once.
    """
    keyed = []
    for pair in pairs:
        key = answer_key(pair.chosen, pair.rejected)
        if key is not None:
            keyed.append((pair, key))
    if not keyed:
        raise ValueError(
            "no held-out pair has a reviewer-changed score in the "
            "criterion_measurements reply shape; nothing to evaluate"
        )
    base_replies = [complete(pair.prompt, 0.0) for pair, _ in keyed]
    adapter_replies = [complete(pair.prompt, 1.0) for pair, _ in keyed]
    base_results = [smoke.validate_sme_reply(text) for text in base_replies]
    adapter_results = [smoke.validate_sme_reply(text) for text in adapter_replies]
    scores = tuple(
        score_pair(
            pair.pair_id,
            key,
            base.scores if base.valid else None,
            adapter.scores if adapter.valid else None,
        )
        for (pair, key), base, adapter in zip(
            keyed, base_results, adapter_results, strict=True
        )
    )
    base_valid = sum(1 for result in base_results if result.valid)
    adapter_valid = sum(1 for result in adapter_results if result.valid)
    wins = sum(1 for score in scores if score.outcome == "win")
    losses = sum(1 for score in scores if score.outcome == "loss")
    verdict = decide(
        wins,
        losses,
        base_valid / len(keyed),
        adapter_valid / len(keyed),
        min_decisive=min_decisive,
        alpha=alpha,
    )
    return Evaluation(
        total_pairs=len(pairs),
        skipped=len(pairs) - len(keyed),
        scores=scores,
        base_valid=base_valid,
        adapter_valid=adapter_valid,
        identical_replies=base_replies == adapter_replies,
        verdict=verdict,
        min_decisive=min_decisive,
        alpha=alpha,
    )


def build_report(
    evaluation: Evaluation,
    *,
    parameters: dict,
    heldout: dict,
    adapter: dict | None,
) -> dict:
    """The JSON report. Holds scores and ids only: never prompts or the API key."""
    return {
        "verdict": evaluation.verdict.verdict,
        "reasons": list(evaluation.verdict.reasons),
        "warnings": evaluation.warnings,
        "pairs": {
            "heldout_total": evaluation.total_pairs,
            "scoreable": evaluation.scoreable,
            "skipped": evaluation.skipped,
            "wins": evaluation.wins,
            "losses": evaluation.losses,
            "ties": evaluation.ties,
        },
        "mean_abs_error": {
            "base": evaluation.mean_base_error,
            "adapter": evaluation.mean_adapter_error,
        },
        "valid_json_rate": {
            "base": evaluation.base_valid_rate,
            "adapter": evaluation.adapter_valid_rate,
        },
        "sign_test_p": evaluation.verdict.p_value,
        "parameters": parameters,
        "heldout": heldout,
        "adapter": adapter,
        "per_pair": [
            {
                "pair_id": score.pair_id,
                "gold": score.gold,
                "base_scores": score.base_scores,
                "adapter_scores": score.adapter_scores,
                "outcome": score.outcome,
            }
            for score in evaluation.scores
        ],
    }


def format_report(evaluation: Evaluation) -> str:
    n = evaluation.scoreable
    header = f"Adapter evaluation: {evaluation.total_pairs} held-out pair(s), {n} scoreable"
    if evaluation.skipped:
        header += f", {evaluation.skipped} skipped (no reviewer-changed score)"
    lines = [
        header,
        "",
        f"  valid JSON       base {evaluation.base_valid}/{n}   "
        f"adapter {evaluation.adapter_valid}/{n}",
        f"  mean abs error   base {evaluation.mean_base_error:.3f}   "
        f"adapter {evaluation.mean_adapter_error:.3f}",
        f"  per pair         adapter {evaluation.wins} win(s), "
        f"{evaluation.losses} loss(es), {evaluation.ties} tie(s); "
        f"sign test p={evaluation.verdict.p_value:.4f}",
        "",
        f"VERDICT: {evaluation.verdict.verdict.upper()}",
    ]
    lines.extend(f"  - {reason}" for reason in evaluation.verdict.reasons)
    lines.extend(f"WARNING: {warning}" for warning in evaluation.warnings)
    lines.extend(["", LIMITS_NOTE])
    return "\n".join(lines)


def exit_code(evaluation: Evaluation) -> int:
    return 0 if evaluation.verdict.verdict == "better" else 1
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest training/tests/test_evaluate_adapter.py -q`
Expected: `48 passed`.

- [ ] **Step 5: Commit**

```bash
git add training/evaluate_adapter.py training/tests/test_evaluate_adapter.py
git commit -m "feat(training): run the adapter-vs-base evaluation and build the report"
```

---

### Task 5: Command line

**Files:**
- Modify: `training/evaluate_adapter.py` (append; this task adds the `if __name__ == "__main__"` block, so it must be the last thing in the file)
- Modify: `training/tests/test_evaluate_adapter.py` (append)

**Interfaces:**
- Consumes: `load_heldout_zip`, `load_heldout_file`, `run_evaluation`, `build_report`, `format_report`, `exit_code`, `DEFAULT_*` (Tasks 2-4); from the smoke-test client: `smoke.list_adapters(base_url, api_key, timeout)`, `smoke.choose_adapter_id(adapters, requested)`, `smoke.make_complete(base_url=..., api_key=..., model=..., adapter_id=..., scale_mode=..., max_tokens=..., timeout=..., scale_touched=...)`, `smoke.reset_global_scale(base_url, api_key, adapter_id, timeout)`, `smoke.describe_error(exc)`, `smoke.DEFAULT_MODEL`.
- Produces: `parse_args(argv) -> argparse.Namespace` (exits with code 2 on bad arguments) and `main(argv=None) -> int` returning 0 / 1 / 2 as in Global Constraints.

- [ ] **Step 1: Append the failing tests**

Append to the end of `training/tests/test_evaluate_adapter.py`:

```python


# --- command line, against a fake llama-server ------------------------------------


@pytest.fixture
def fake_server(monkeypatch):
    """A stand-in for llama-server whose replies depend on the prompt and scale."""
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL_NAME", raising=False)
    state = {
        "adapters": [{"id": 0, "path": "adapter.gguf", "scale": 0.0}],
        "requests": [],
        "global_scale": 0.0,
        "chat_400": False,
        # adapter improves every pair unless a test swaps this out
        "reply_for": lambda prompt, scale: _reply({"A-01": 3 if scale > 0 else 1}),
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def _send(self, status, body):
            data = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _record(self, payload):
            state["requests"].append(
                {
                    "method": self.command,
                    "path": self.path,
                    "auth": self.headers.get("Authorization"),
                    "user_agent": self.headers.get("User-Agent"),
                    "body": payload,
                }
            )

        def do_GET(self):
            self._record(None)
            if self.path == "/lora-adapters":
                self._send(200, state["adapters"])
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"null")
            self._record(payload)
            if self.path == "/lora-adapters":
                state["global_scale"] = payload[0]["scale"]
                self._send(200, {"success": True})
            elif self.path == "/v1/chat/completions":
                if state["chat_400"]:
                    self._send(400, {"error": {"message": "context too long"}})
                    return
                scale = state["global_scale"]
                if "lora" in payload:
                    scale = payload["lora"][0]["scale"]
                prompt = payload["messages"][0]["content"]
                content = state["reply_for"](prompt, scale)
                self._send(200, {"choices": [{"message": {"content": content}}]})
            else:
                self._send(404, {"error": "not found"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state["base_url"] = f"http://127.0.0.1:{server.server_address[1]}/v1"
    yield state
    server.shutdown()
    server.server_close()


def _zip_with_pairs(tmp_path: Path, count: int = 25) -> Path:
    rows = [_heldout_row(n) for n in range(count)]
    return _make_adapter_zip(tmp_path, rows)


def _chats(state) -> list[dict]:
    return [r for r in state["requests"] if r["path"] == "/v1/chat/completions"]


def _run_cli(argv, capsys):
    code = ev.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_cli_better_adapter_exits_0_and_writes_the_report(
    fake_server, tmp_path, capsys
):
    zip_path = _zip_with_pairs(tmp_path)
    report_path = tmp_path / "report.json"
    code, out, err = _run_cli(
        [
            "--adapter-zip",
            str(zip_path),
            "--base-url",
            fake_server["base_url"],
            "--report-json",
            str(report_path),
        ],
        capsys,
    )

    assert code == 0, err
    assert "VERDICT: BETTER" in out
    assert "sha256 verified" in out
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["verdict"] == "better"
    assert report["pairs"]["wins"] == 25
    assert report["heldout"]["sha256_verified"] is True
    assert report["adapter"]["zip_sha256"] == hashlib.sha256(
        zip_path.read_bytes()
    ).hexdigest()
    assert report["parameters"]["model"] == "gemma-3-4b-it"
    chats = _chats(fake_server)
    assert [c["body"]["lora"] for c in chats] == (
        [[{"id": 0, "scale": 0.0}]] * 25 + [[{"id": 0, "scale": 1.0}]] * 25
    )
    assert all(c["body"]["temperature"] == 0.0 for c in chats)
    assert all(c["body"]["max_tokens"] == ev.DEFAULT_MAX_TOKENS for c in chats)


def test_cli_worse_adapter_exits_1(fake_server, tmp_path, capsys):
    fake_server["reply_for"] = lambda prompt, scale: _reply(
        {"A-01": 1 if scale > 0 else 3}
    )
    code, out, _ = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            fake_server["base_url"],
        ],
        capsys,
    )
    assert code == 1
    assert "VERDICT: WORSE" in out


def test_cli_too_few_pairs_is_inconclusive_and_exits_1(fake_server, tmp_path, capsys):
    code, out, _ = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path, count=4)),
            "--base-url",
            fake_server["base_url"],
        ],
        capsys,
    )
    assert code == 1
    assert "VERDICT: INCONCLUSIVE" in out
    assert "too few decisive pairs (4 < 20)" in out


def test_cli_limit_and_thresholds_are_honoured(fake_server, tmp_path, capsys):
    code, out, _ = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            fake_server["base_url"],
            "--limit",
            "6",
            "--min-decisive",
            "6",
        ],
        capsys,
    )
    assert code == 0
    assert "(6 of 25 pair(s) used" in out
    assert len(_chats(fake_server)) == 12
    assert "VERDICT: BETTER" in out


def test_cli_accepts_a_bare_heldout_file(fake_server, tmp_path, capsys):
    path = tmp_path / "heldout_pairs.jsonl"
    path.write_bytes(_jsonl([_heldout_row(n) for n in range(25)]))
    code, out, err = _run_cli(
        ["--heldout", str(path), "--base-url", fake_server["base_url"]], capsys
    )
    assert code == 0, err
    assert "sha256 not checked" in out


def test_cli_global_mode_switches_scale_once_and_resets_it(
    fake_server, tmp_path, capsys
):
    code, out, err = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            fake_server["base_url"],
            "--scale-mode",
            "global",
        ],
        capsys,
    )

    assert code == 0, err
    assert "VERDICT: BETTER" in out
    assert all("lora" not in c["body"] for c in _chats(fake_server))
    scale_posts = [
        r["body"][0]["scale"]
        for r in fake_server["requests"]
        if r["method"] == "POST" and r["path"] == "/lora-adapters"
    ]
    assert scale_posts == [0.0, 1.0, 0.0]
    assert fake_server["global_scale"] == 0.0
    assert "adapter scale reset to 0.0" in out


def test_cli_sends_bearer_key_and_user_agent_and_never_prints_the_key(
    fake_server, tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("LLM_API_KEY", "secret-key-123")
    code, out, err = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path, count=2)),
            "--base-url",
            fake_server["base_url"],
        ],
        capsys,
    )

    assert code == 1, err  # only 2 pairs: inconclusive
    assert all(r["auth"] == "Bearer secret-key-123" for r in fake_server["requests"])
    assert {r["user_agent"] for r in fake_server["requests"]} == {ev.smoke.USER_AGENT}
    assert "secret-key-123" not in out + err


def test_cli_adapter_without_heldout_set_exits_2_before_touching_the_server(
    fake_server, tmp_path, capsys
):
    zip_path = _make_adapter_zip(tmp_path, heldout=None)
    code, _, err = _run_cli(
        ["--adapter-zip", str(zip_path), "--base-url", fake_server["base_url"]], capsys
    )
    assert code == 2
    assert "no held-out set" in err
    assert fake_server["requests"] == []


def test_cli_no_adapter_loaded_exits_2(fake_server, tmp_path, capsys):
    fake_server["adapters"] = []
    code, _, err = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            fake_server["base_url"],
        ],
        capsys,
    )
    assert code == 2
    assert "no LoRA adapter is loaded" in err


def test_cli_server_error_exits_2(fake_server, tmp_path, capsys):
    fake_server["chat_400"] = True
    code, _, err = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            fake_server["base_url"],
        ],
        capsys,
    )
    assert code == 2
    assert "context too long" in err


def test_cli_unreachable_server_exits_2(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    code, _, err = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            "http://127.0.0.1:9/v1",
            "--timeout",
            "2",
        ],
        capsys,
    )
    assert code == 2
    assert err.startswith("error:")


def test_cli_without_a_base_url_exits_2(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    code, _, err = _run_cli(
        ["--adapter-zip", str(_zip_with_pairs(tmp_path))], capsys
    )
    assert code == 2
    assert "LLM_API_BASE" in err


@pytest.mark.parametrize(
    "bad_args",
    [
        ["--alpha", "1.5"],
        ["--alpha", "0"],
        ["--limit", "0"],
        ["--min-decisive", "0"],
        [],  # neither --adapter-zip nor --heldout
    ],
)
def test_cli_rejects_bad_arguments(bad_args, tmp_path):
    argv = list(bad_args)
    if bad_args:
        argv = ["--adapter-zip", str(tmp_path / "x.zip"), *bad_args]
    with pytest.raises(SystemExit) as excinfo:
        ev.parse_args(argv)
    assert excinfo.value.code == 2


def test_cli_adapter_and_heldout_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit):
        ev.parse_args(["--adapter-zip", "a.zip", "--heldout", "b.jsonl"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest training/tests/test_evaluate_adapter.py -q`
Expected: 18 new failures (`AttributeError ... 'main'` / `'parse_args'`); 48 pass.

- [ ] **Step 3: Append the implementation**

Append to the end of `training/evaluate_adapter.py`:

```python


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare a GGUF LoRA adapter with the plain model on held-out "
        "DPO pairs."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--adapter-zip",
        type=Path,
        help="adapter zip from the training notebook (holds heldout_pairs.jsonl)",
    )
    source.add_argument(
        "--heldout", type=Path, help="a bare heldout_pairs.jsonl file instead"
    )
    parser.add_argument("--base-url", default=None, help="default: $LLM_API_BASE")
    parser.add_argument("--api-key", default=None, help="default: $LLM_API_KEY")
    parser.add_argument("--model", default=None, help="default: $LLM_MODEL_NAME")
    parser.add_argument(
        "--adapter-id",
        type=int,
        default=None,
        help="adapter id to evaluate (default: the first loaded adapter)",
    )
    parser.add_argument(
        "--scale-mode",
        choices=("request", "global"),
        default="request",
        help="request: send the scale in each chat request (default). global: "
        "set it through POST /lora-adapters; this changes the server-wide "
        "scale, and the script resets it to 0.0 afterwards",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"max tokens per reply (default: {DEFAULT_MAX_TOKENS})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="seconds to wait for each HTTP request (default: 300)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="evaluate only the first N held-out pairs (default: all)",
    )
    parser.add_argument(
        "--min-decisive",
        type=int,
        default=DEFAULT_MIN_DECISIVE,
        help="fewest decisive (win or loss) pairs for a verdict other than "
        f"inconclusive (default: {DEFAULT_MIN_DECISIVE})",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=DEFAULT_ALPHA,
        help=f"significance level of the sign test (default: {DEFAULT_ALPHA})",
    )
    parser.add_argument(
        "--report-json", type=Path, default=None, help="also write a JSON report here"
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.min_decisive < 1:
        parser.error("--min-decisive must be at least 1")
    if not 0 < args.alpha < 1:
        parser.error("--alpha must be between 0 and 1")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    base_url = args.base_url or os.environ.get("LLM_API_BASE")
    if not base_url:
        print(
            "error: no server base URL; pass --base-url or set LLM_API_BASE",
            file=sys.stderr,
        )
        return 2
    api_key = args.api_key or os.environ.get("LLM_API_KEY")
    model = args.model or os.environ.get("LLM_MODEL_NAME") or smoke.DEFAULT_MODEL
    adapter_id: int | None = None
    scale_touched: list[bool] = []
    try:
        try:
            if args.adapter_zip:
                heldout = load_heldout_zip(args.adapter_zip)
            else:
                heldout = load_heldout_file(args.heldout)
            pairs = heldout.pairs[: args.limit] if args.limit else heldout.pairs
            adapters = smoke.list_adapters(base_url, api_key, args.timeout)
            adapter_id = smoke.choose_adapter_id(adapters, args.adapter_id)
            complete = smoke.make_complete(
                base_url=base_url,
                api_key=api_key,
                model=model,
                adapter_id=adapter_id,
                scale_mode=args.scale_mode,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                scale_touched=scale_touched,
            )
            evaluation = run_evaluation(
                pairs, complete, min_decisive=args.min_decisive, alpha=args.alpha
            )
        except (
            OSError,
            ValueError,
            http.client.HTTPException,
            zipfile.BadZipFile,
        ) as exc:
            print(f"error: {smoke.describe_error(exc)}", file=sys.stderr)
            return 2
        checked = "verified" if heldout.sha256_verified else "not checked"
        print(
            f"Held-out set: {heldout.source} ({len(pairs)} of "
            f"{len(heldout.pairs)} pair(s) used, sha256 {checked})"
        )
        print(format_report(evaluation))
        if args.report_json:
            report = build_report(
                evaluation,
                parameters={
                    "min_decisive": args.min_decisive,
                    "alpha": args.alpha,
                    "scale_mode": args.scale_mode,
                    "model": model,
                    "max_tokens": args.max_tokens,
                    "limit": args.limit,
                },
                heldout={
                    "source": heldout.source,
                    "sha256": heldout.sha256,
                    "sha256_verified": heldout.sha256_verified,
                    "pairs_in_file": len(heldout.pairs),
                    "pairs_used": len(pairs),
                },
                adapter={
                    "adapter_id": adapter_id,
                    "zip_sha256": heldout.adapter_zip_sha256,
                },
            )
            try:
                args.report_json.write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8"
                )
            except OSError as exc:
                print(f"error: could not write the report: {exc}", file=sys.stderr)
                return 2
            print(f"report written to {args.report_json}")
        return exit_code(evaluation)
    finally:
        if args.scale_mode == "global" and scale_touched and adapter_id is not None:
            smoke.reset_global_scale(base_url, api_key, adapter_id, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest training/tests/test_evaluate_adapter.py -q`
Expected: `66 passed` (the CLI tests start a local fake server; they take about 15 seconds).

- [ ] **Step 5: Check the script runs standalone and the whole suite is green**

Run: `python training/evaluate_adapter.py --help`
Expected: usage text listing `--adapter-zip`/`--heldout`, `--base-url`, `--limit`, `--min-decisive`, `--alpha`, `--report-json` (proves `import smoke_test_lora_serving` resolves when run as a script).

Run: `python -m pytest training/tests -q`
Expected: `125 passed` (59 baseline + 66 new).

- [ ] **Step 6: Commit**

```bash
git add training/evaluate_adapter.py training/tests/test_evaluate_adapter.py
git commit -m "feat(training): add evaluate_adapter command line"
```

---

### Task 6: How-to and README pointer

**Files:**
- Create: `training/evaluating-an-adapter.md`
- Modify: `training/README.md` (append a section)

**Interfaces:**
- Consumes: the option names and exit codes from Task 5.
- Produces: docs only.

- [ ] **Step 1: Create the how-to**

Create `training/evaluating-an-adapter.md` with exactly this content:

````markdown
# Evaluating an adapter: is it better than the plain model?

`evaluate_adapter.py` answers one question: on cases a reviewer corrected, does
the served model with the adapter land closer to the reviewer's scores than the
same model without it? It prints a verdict (better, worse or inconclusive) and
can write a JSON report.

It needs a running llama-server with the adapter loaded at scale 0.0 (see
`training/serving-lora-adapter.md`). It uses only the Python standard library.

## What you need

1. **An adapter zip trained with the grouped-split notebook.** The training
   notebook (`docs/colab/dpo_training_template.ipynb`) holds out whole
   evaluations, prints how many, and saves them inside the zip as
   `heldout_pairs.jsonl`. An adapter trained with fewer than 20 pairs, or from a
   single evaluation, has no held-out set and cannot be evaluated.
2. **The adapter loaded on the server.** Convert the zip to a GGUF LoRA
   (`docs/colab/adapter_to_gguf_template.ipynb`) and ask the host owner to load
   it with `--lora-scaled <file>.gguf:0.0`. Every new adapter needs this step
   before it can be evaluated; the evaluation runs on the exact served
   artifact, not on the Colab copy.
3. **The server URL and API key**, in `LLM_API_BASE` and `LLM_API_KEY` (or
   `--base-url` / `--api-key`; the environment is safer, arguments end up in
   shell history). The key is never printed or written to the report.

## Run it

From the repo root, PowerShell:

```powershell
$env:LLM_API_BASE = "https://<host>/v1"
$env:LLM_API_KEY  = "<key>"
python training/evaluate_adapter.py --adapter-zip path\to\adapter.zip `
    --report-json report.json
```

Useful options:

| Option | Default | Meaning |
|---|---|---|
| `--limit N` | all | evaluate only the first N held-out pairs (each pair is 2 real requests on the host's GPU) |
| `--min-decisive N` | 20 | fewest decisive (win or loss) pairs before a verdict other than inconclusive is possible |
| `--alpha A` | 0.05 | significance level of the sign test |
| `--max-tokens N` | 2048 | reply length limit; too small a value cuts JSON off and counts as invalid |
| `--scale-mode global` | request | use if the server ignores the per-request scale; the script resets the scale to 0.0 afterwards |
| `--heldout FILE` | | evaluate a bare `heldout_pairs.jsonl` instead of a zip |

## Read the result

For every held-out pair the script builds an answer key: the criteria whose
score the reviewer changed, with the reviewer's score. It sends the pair's
prompt with the adapter off and then on, and compares how far each reply's
scores are from the answer key.

- **win / loss / tie**: the adapter's reply was closer / further / equally far.
  An invalid reply counts as the worst possible error.
- **sign test p**: the chance of a split this lopsided if the adapter made no
  difference (ties are left out).
- **VERDICT**: `better` needs more wins than losses, p below `--alpha`, at least
  `--min-decisive` decisive pairs, and no more invalid JSON than the plain
  model. `worse` needs the mirror image. Anything else is `inconclusive`, and
  the reasons are printed.

Exit code: 0 better, 1 worse or inconclusive, 2 the run could not happen.

## What a verdict does and does not mean

- The held-out pairs are only cases a reviewer **changed**. A `better` verdict
  means the adapter fixes known mistakes; it says nothing about harm to cases
  reviewers approved.
- With few pairs a verdict is weak evidence. Twenty decisive pairs is the floor
  for saying anything; real confidence needs many more.
- Output is advisory. A person decides whether an adapter goes into use.

## Common problems

| Message | Cause and fix |
|---|---|
| `this adapter has no held-out set` | The zip has no `heldout` block: too few pairs, one evaluation, or trained with the older notebook. Retrain, or pass `--heldout`. |
| `no LoRA adapter is loaded on the server` | Ask the host to start llama-server with `--lora-scaled <file>.gguf:0.0`. |
| `WARNING: the adapter's replies are identical...` | The adapter is probably not being applied. Check `GET /lora-adapters` and retry with `--scale-mode global`. |
| adapter valid-JSON rate below the plain model's | The adapter damaged the output format; a `better` verdict is withheld. |
| HTTP 401/403 | Wrong or missing API key. |
````

- [ ] **Step 2: Append a pointer to `training/README.md`**

Append this to the end of `training/README.md`:

```markdown

## Serving and evaluating a trained adapter

The scripts above train an adapter. To use and judge one:

- `serving-lora-adapter.md`: how the host owner loads the adapter on llama.cpp.
- `smoke_test_lora_serving.py`: checks a served adapter still returns valid SME JSON.
- `evaluate_adapter.py`: compares the adapter with the plain model on held-out
  corrected cases and prints a verdict; see `evaluating-an-adapter.md`.
```

- [ ] **Step 3: Check the how-to matches the tool**

Run: `python training/evaluate_adapter.py --help`
Confirm every option named in the how-to's options table (`--limit`, `--min-decisive`, `--alpha`, `--max-tokens`, `--scale-mode`, `--heldout`, `--report-json`, `--adapter-zip`) appears in the help output, and that the defaults in the table (all, 20, 0.05, 2048, request) match.

- [ ] **Step 4: Commit**

```bash
git add training/evaluating-an-adapter.md training/README.md
git commit -m "docs(training): explain how to evaluate an adapter"
```

---

### Task 7: Manual verification (controller and user; not for a subagent)

Two checks that need the host's server, the shared dev database and Colab. Get the user's explicit go-ahead before each; the first sends real inference requests to the host's live server, the second creates a job and a stored adapter row in the shared Neon database.

**Files:** none in the repo. Record results in the SDD ledger (`.superpowers/sdd/2026-09-19-adapter-evaluation-tool/progress.md`).

- [ ] **Step 1: Dump the synthetic dataset as a held-out file (read-only)**

Write this to your scratchpad as `dump_heldout_from_job.py`:

```python
"""One-off: turn the frozen dataset of a training job into a heldout_pairs.jsonl.

Read-only. Run from the apps directory:
    cd apps && uv run --project server python <this file> <adapter_id> <out.jsonl>

The pairs are what the adapter was TRAINED on, so a run over this file proves the
tooling works but says nothing about quality.
"""

import json
import sys
import uuid

from server.core.database import get_session_factory
from server.modules.training_data.models import DpoTrainingJob, TrainedAdapter

adapter_id = uuid.UUID(sys.argv[1])
out_path = sys.argv[2]

with get_session_factory()() as session:
    adapter = session.get(TrainedAdapter, adapter_id)
    if adapter is None:
        raise SystemExit(f"no adapter {adapter_id}")
    job = session.get(DpoTrainingJob, adapter.job_id)
    pairs = [json.loads(l) for l in job.pairs_content.splitlines() if l.strip()]
    provenance = [json.loads(l) for l in job.provenance_content.splitlines() if l.strip()]
    assert len(pairs) == len(provenance), (len(pairs), len(provenance))
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        for pair, prov in zip(pairs, provenance, strict=True):
            row = {
                "pair_id": prov["pair_id"],
                "evaluation_id": prov["evaluation_id"],
                "prompt": pair["prompt"],
                "chosen": pair["chosen"],
                "rejected": pair["rejected"],
            }
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote {len(pairs)} pairs from job {job.job_id} to {out_path}")
```

Run from the repo root (it only reads the database):

```bash
cd apps && PYTHONPATH=. uv run --project server python <scratchpad>/dump_heldout_from_job.py 830d10de-c02f-49f7-9277-da0e165dad1e <scratchpad>/synthetic_heldout.jsonl
```

Expected: `wrote 25 pairs from job <uuid> to <path>`. (`830d10de-...` is the stored adapter from the earlier end-to-end run.)

- [ ] **Step 2: Offline check of the dump**

Run from the repo root, with the scratchpad path filled in:

```bash
python - <<'EOF'
import sys
sys.path.insert(0, "training")
import evaluate_adapter as ev
held = ev.load_heldout_file(r"<scratchpad>/synthetic_heldout.jsonl")
keys = [ev.answer_key(p.chosen, p.rejected) for p in held.pairs]
print(len(held.pairs), "pairs,", sum(k is not None for k in keys), "scoreable")
EOF
```

Expected: `25 pairs, 25 scoreable`. (Verified while writing this plan; if it differs, stop and investigate before touching the server.)

- [ ] **Step 3: Small run against the live server (needs the user's go-ahead)**

Ask the user to confirm the host may take about 8 requests. Load `LLM_API_BASE` and `LLM_API_KEY` from the repo's `.env` into the environment without printing them, then:

```bash
python training/evaluate_adapter.py --heldout <scratchpad>/synthetic_heldout.jsonl --limit 4 --min-decisive 4 --report-json <scratchpad>/report.json
```

Expected: exit code 0 or 1 (any verdict is fine, these pairs were trained on; only 2 means the run failed); a printed table with `4 held-out pair(s), 4 scoreable`; `report.json` exists, is valid JSON, has no `"prompt"` key and does not contain the API key. Then check the adapter is still off:

```bash
curl -s -H "Authorization: Bearer $LLM_API_KEY" -H "User-Agent: equiped-eval/1.0" "${LLM_API_BASE%/v1}/lora-adapters"
```

Expected: the adapter's `"scale": 0.0`. Record the verdict, valid-JSON rates and win/loss/tie counts in the ledger, labelled "trained-on pairs, plumbing check only".

- [ ] **Step 4: One real Colab run of the changed notebook (user does this)**

Follow the earlier procedure: admin panel, Training Data, SME, Start Training Job, open `docs/colab/dpo_training_template.ipynb` in Colab on a GPU runtime, paste the two URLs, Run all. Expected in the output of the split cell: `train_dataset: N pairs from M evaluation(s)` and `held-out: K pairs from J evaluation(s), saved with the adapter so it can be evaluated later`, and the last cell prints `Adapter uploaded:`.

- [ ] **Step 5: Verify the stored adapter carries a verifiable held-out set**

Find the new adapter zip under `adapters/sme/<adapter_id>/adapter.zip` (newest by modification time; `adapters/` is git-ignored), then:

```bash
python - <<'EOF'
import sys
sys.path.insert(0, "training")
import evaluate_adapter as ev
held = ev.load_heldout_zip(r"<path-to-new-adapter.zip>")
print(len(held.pairs), "held-out pairs; sha256 verified:", held.sha256_verified)
EOF
```

Expected: `K held-out pairs; sha256 verified: True` with K equal to the count Colab printed. Record it in the ledger. Evaluating that adapter on the server needs it converted and loaded by the host owner (see `training/serving-lora-adapter.md`); that is a separate, later step and not part of this plan.

---

## Notes

- **Spec coverage:** notebook grouped split, held-out file and manifest block, the `<20 pairs` guard, eval dataset reuse (Task 1); script inputs, answer key, per-pair scoring, off-then-on ordering, global-mode reset (Tasks 2, 4, 5); verdict rule and safety cap (Task 2); JSON and readable report, exit codes, limits note (Tasks 4, 5); how-to (Task 6); mechanics check with the 25 synthetic pairs (Task 7). The single-evaluation rule and the "invalid reply" wording were added to the spec while planning.
- **Not covered on purpose (spec non-goals):** anything under `apps/` other than the contract test, likelihood scoring, accepted-case regression checks, ITSO/GAD, auto-promotion, storing reports.
- **Known cosmetic bug left alone:** cell 9 sorts `target_modules`, which turns a regex string into single characters in the provenance manifest. Not in the spec; the real `adapter_config.json` is unaffected. Fix separately.


## Post-review changes (made during execution; the code blocks above are the original text)

Reviews during execution changed the code and docs in these ways. Where a block above disagrees with the files in the repo, the repo is right.

- **Task 3, `parse_heldout`:** `data.decode("utf-8").splitlines()` became `data.decode("utf-8").split("\n")`. `splitlines()` also splits on U+2028, U+2029 and U+0085, which the notebook writes raw (`ensure_ascii=False`), so a valid, hash-verified held-out file could fail with a bogus "not valid JSON". A regression test, `test_parse_heldout_handles_unicode_line_separators_in_text`, was added (the file then has 67 tests, and `python -m pytest training/tests -q` reports 126 passed, not the 125 stated in Task 5).
- **Task 6, how-to:** the `--heldout` option row and the "no held-out set" row now say the tool cannot check that a bare file is disjoint from the training data; the `worse` verdict wording no longer claims a validity condition; the exit-code line notes that 2 also covers a report that could not be written.
- **Task 1, notebook cell 8:** the "Skipped eval" message no longer says "too few pairs" (nothing may be held out for a single evaluation too). The contract test file was run through `ruff format`.
- **Deferred on purpose** (all judged harmless by the final review): non-ASCII text in interpolated error messages could raise `UnicodeEncodeError` on a cp1252 console; a report-write failure exits 2 even after a "better" verdict; no failure-path tests for the global-scale reset; the held-out share is by evaluation count, not pair count.
- **Task 7 was not run by the executor.** It needs the host's live server and a Colab run; it is left for the user to approve.
