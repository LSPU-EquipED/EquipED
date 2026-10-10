"""Tests for the planning helpers inside the training notebook (no GPU, no unsloth)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
NOTEBOOK_PATH = REPO_ROOT / "docs" / "colab" / "dpo_training_template.ipynb"
START = "# --- planning helpers (tested) ---"
END = "# --- end planning helpers ---"


def _cell(index: int) -> str:
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return "".join(nb["cells"][index]["source"])


def _helpers(index: int) -> dict:
    source = _cell(index)
    assert START in source and END in source
    block = source[source.index(START) : source.index(END)]
    namespace: dict = {"math": __import__("math")}
    exec(block, namespace)  # noqa: S102
    return namespace


def _count(text: str) -> int:
    return len(text.split())  # one "token" per word keeps the numbers readable


def _row(prompt_words: int, chosen_words: int = 10, rejected_words: int = 10) -> dict:
    return {
        "prompt": " ".join(["p"] * prompt_words),
        "chosen": " ".join(["c"] * chosen_words),
        "rejected": " ".join(["r"] * rejected_words),
    }


# ---- Task 1: length plan -------------------------------------------------


def test_lengths_are_rounded_up_with_a_margin():
    plan = _helpers(6)["plan_lengths"]([_row(100), _row(130, 20, 30)], _count, 6144)
    assert plan["keep"] == [0, 1] and plan["dropped"] == []
    assert plan["max_prompt_length"] == 192  # 130 rounded up to a multiple of 64
    # longest pair = 130 + 30 = 160, plus a 64 margin = 224, rounded up to 256
    assert plan["max_seq_length"] == 256
    assert plan["stats"]["pairs"] == 2 and plan["stats"]["prompt_max"] == 130


def test_pairs_over_the_ceiling_are_dropped_and_reported():
    rows = [_row(100)] + [_row(7000)] * 1 + [_row(120)] * 8
    plan = _helpers(6)["plan_lengths"](rows, _count, 6144)
    assert plan["dropped"] == [1]
    assert 1 not in plan["keep"] and len(plan["keep"]) == 9
    assert plan["max_seq_length"] <= 6144


def test_too_many_dropped_pairs_stop_the_run():
    rows = [_row(100)] * 7 + [_row(7000)] * 3  # 30% over the ceiling
    with pytest.raises(ValueError, match="ceiling"):
        _helpers(6)["plan_lengths"](rows, _count, 6144)


def test_exactly_the_allowed_fraction_is_accepted():
    rows = [_row(100)] * 8 + [_row(7000)] * 2  # exactly 20%
    plan = _helpers(6)["plan_lengths"](rows, _count, 6144)
    assert plan["dropped"] == [8, 9]


def test_everything_over_the_ceiling_is_an_error():
    with pytest.raises(ValueError):
        _helpers(6)["plan_lengths"]([_row(7000)], _count, 6144)


def test_no_rows_is_an_error():
    with pytest.raises(ValueError):
        _helpers(6)["plan_lengths"]([], _count, 6144)


def test_truncate_policy_keeps_every_pair_at_the_ceiling():
    rows = [_row(100), _row(7000)]
    plan = _helpers(6)["plan_lengths"](rows, _count, 6144, policy="truncate")
    assert plan["dropped"] == [] and plan["keep"] == [0, 1]
    assert plan["max_seq_length"] == 6144
    assert plan["max_prompt_length"] < plan["max_seq_length"]


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        _helpers(6)["plan_lengths"]([_row(10)], _count, 6144, policy="shrug")


@pytest.mark.parametrize(
    ("gb", "ceiling"),
    [(0, 6144), (15.0, 6144), (22.5, 8192), (40.0, 12288), (80.0, 12288)],
)
def test_gpu_ceiling_by_memory(gb, ceiling):
    assert _helpers(6)["gpu_ceiling"](gb) == ceiling


def test_cell_6_sets_max_seq_length_from_the_plan_before_loading_the_model():
    source = _cell(6)
    assert "MAX_SEQ_LENGTH = LENGTH_PLAN[" in source
    assert source.index("LENGTH_PLAN =") < source.index(
        "FastLanguageModel.from_pretrained("
    )
    assert "MAX_SEQ_LENGTH = 2048" not in source


# ---- Task 2: dose plan ----------------------------------------------------


@pytest.mark.parametrize(
    ("pairs", "steps_per_epoch", "epochs", "planned", "max_steps"),
    [
        (25, 7, 3, 21, None),  # small dataset: three epochs reach about 20 updates
        (100, 25, 1, 25, None),  # one pass is already past the target
        (234, 59, 1, 59, None),  # one pass, below the cap
        (300, 75, 1, 75, 60),  # one pass would exceed the cap, so it is capped
        (3, 1, 4, 4, None),  # fewer pairs than one update: at least 1 step per epoch
    ],
)
def test_dose_follows_the_dataset_size(
    pairs, steps_per_epoch, epochs, planned, max_steps
):
    plan = _helpers(7)["plan_dose"](pairs, 1, 4)
    assert plan == {
        "steps_per_epoch": steps_per_epoch,
        "epochs": epochs,
        "planned_updates": planned,
        "max_steps": max_steps,
    }


def test_dose_accumulation_changes_the_steps():
    plan = _helpers(7)["plan_dose"](25, 1, 8)
    assert plan["steps_per_epoch"] == 4 and plan["epochs"] == 4  # capped at max epochs


def test_dose_needs_at_least_one_pair():
    with pytest.raises(ValueError):
        _helpers(7)["plan_dose"](0, 1, 4)


def test_cell_7_uses_the_plans_and_new_defaults():
    source = _cell(7)
    assert "DOSE_PLAN = plan_dose(" in source
    assert "num_train_epochs=DOSE_PLAN[" in source
    assert "max_prompt_length=LENGTH_PLAN[" in source
    assert "learning_rate=LEARNING_RATE" in source
    assert "LEARNING_RATE = 2e-5" in source
    assert "max_steps" in source
    # the old fixed values are gone
    assert "num_train_epochs=1," not in source
    assert "max_prompt_length=1536" not in source


# ---- Task 3: plan recorded in the manifest ---------------------------------


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
    learning_rate = 2e-5
    num_train_epochs = 3
    beta = 0.1
    per_device_train_batch_size = 1
    gradient_accumulation_steps = 4


def _run_manifest(tmp_path: Path, extra: dict) -> dict:
    adapter_dir = tmp_path / "trained_adapter"
    adapter_dir.mkdir()
    ctx = {
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
        "pairs": [],
        "heldout_rows": [{"pair_id": "x", "evaluation_id": "e"}],
        "HELDOUT_METHOD": "group_by_evaluation_id",
        "HELDOUT_SEED": 42,
        "HELDOUT_PERCENT": 20,
    }
    ctx.update(extra)
    exec(_cell(10), ctx)  # noqa: S102
    return json.loads((adapter_dir / "training_manifest.json").read_text())


def test_manifest_records_the_training_plan(tmp_path):
    length_plan = {
        "dropped": [4, 9],
        "max_prompt_length": 1024,
        "max_seq_length": 2048,
    }
    dose_plan = {
        "steps_per_epoch": 7,
        "epochs": 3,
        "planned_updates": 21,
        "max_steps": None,
    }
    manifest = _run_manifest(
        tmp_path,
        {
            "LENGTH_PLAN": length_plan,
            "DOSE_PLAN": dose_plan,
            "LEARNING_RATE": 2e-5,
            "GRAD_ACCUM": 4,
            "HARD_MAX_SEQ_LENGTH": 8192,
            "_gpu_gb": 22.46,
            "train_dataset": [1] * 25,
        },
    )
    assert manifest["training_plan"] == {
        "train_pairs": 25,
        "heldout_pairs": 1,
        "dropped_pairs": 2,
        "max_prompt_length": 1024,
        "max_seq_length": 2048,
        "hard_max_seq_length": 8192,
        "steps_per_epoch": 7,
        "epochs": 3,
        "planned_updates": 21,
        "max_steps": None,
        "learning_rate": 2e-5,
        "grad_accum": 4,
        "gpu_memory_gb": 22.5,
    }


def test_manifest_without_plan_variables_has_a_null_plan(tmp_path):
    assert _run_manifest(tmp_path, {})["training_plan"] is None


# ---- Review fixes ------------------------------------------------------------


@pytest.mark.parametrize("index", [6, 7, 9])
def test_edited_cells_compile(index):
    compile(_cell(index), f"cell{index}", "exec")


def test_all_eval_pairs_dropped_leaves_an_empty_eval_selection():
    keep_train, keep_eval = _helpers(6)["split_keep"]([0, 1, 2], 3, 5)
    assert keep_train == [0, 1, 2] and keep_eval == []
    source = _cell(6)
    assert "eval_dataset = None" in source and "heldout_rows = []" in source


def test_split_keep_offsets_eval_positions():
    keep_train, keep_eval = _helpers(6)["split_keep"]([0, 2, 3, 5], 3, 6)
    assert keep_train == [0, 2] and keep_eval == [0, 2]


def test_no_training_pairs_left_gives_a_clear_error():
    with pytest.raises(ValueError, match="GPU length ceiling"):
        _helpers(6)["split_keep"]([3, 4], 3, 5)


# ---- final fix wave: the split cell feeds the length-plan cell ------------------


class _FakeDataset:
    def __init__(self, rows):
        self.rows = list(rows)

    @classmethod
    def from_list(cls, rows):
        return cls(rows)

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)

    def select(self, indices):
        return _FakeDataset(self.rows[i] for i in indices)


def _strict_count(text):
    # Like AutoTokenizer.__call__: only text is accepted, chat rows are not.
    if not isinstance(text, str):
        raise ValueError(f"text input must be of type str, got {type(text)}")
    return len(text.split())


def _run_split_then_measure(monkeypatch, sizes):
    """Run the real split cell, then the measuring part of the length-plan cell."""
    import sys
    import types

    fake_datasets = types.ModuleType("datasets")
    fake_datasets.Dataset = _FakeDataset
    monkeypatch.setitem(sys.modules, "datasets", fake_datasets)
    pairs, records = [], []
    for n, words in enumerate(sizes):
        pairs.append(_row(words))
        records.append({"pair_id": f"p{n}", "evaluation_id": f"e{n % 10}"})
    namespace: dict = {
        "pairs": pairs,
        "pair_provenance_records": list(zip(pairs, records, strict=True)),
    }
    exec(_cell(5), namespace)  # noqa: S102
    assert isinstance(namespace["train_dataset"].rows[0]["prompt"], list)
    source = _cell(6)
    block = source[source.index(START) : source.index(END)]
    helpers: dict = {"math": __import__("math")}
    exec(block, helpers)  # noqa: S102
    namespace.update(
        {k: helpers[k] for k in ("plan_lengths", "split_keep", "gpu_ceiling")}
    )
    namespace.update(
        _count_tokens=_strict_count,
        HARD_MAX_SEQ_LENGTH=6144,
        LONG_PAIR_POLICY="drop",
        MAX_DROP_FRACTION=0.2,
    )
    start = source.index("# Measure the plain text")
    end = source.index("MAX_SEQ_LENGTH = LENGTH_PLAN[")
    exec(source[start:end], namespace)  # noqa: S102
    return namespace


def test_length_plan_measures_plain_text_not_chat_rows(monkeypatch):
    ns = _run_split_then_measure(monkeypatch, [100] * 30)
    assert ns["LENGTH_PLAN"]["stats"]["pairs"] == 30
    assert len(ns["train_dataset"]) + len(ns["eval_dataset"]) == 30
    assert ns["LENGTH_PLAN"]["stats"]["prompt_max"] == 100


def test_dropped_rows_stay_aligned_after_the_split(monkeypatch):
    sizes = [100] * 28 + [7000] * 2
    ns = _run_split_then_measure(monkeypatch, sizes)
    dropped = set(ns["LENGTH_PLAN"]["dropped"])
    assert len(dropped) == 2
    total = len(ns["train_dataset"]) + (
        len(ns["eval_dataset"]) if ns["eval_dataset"] is not None else 0
    )
    assert total == 28
    for dataset in (ns["train_dataset"], ns["eval_dataset"]):
        for row in dataset or []:
            assert len(row["prompt"][0]["content"].split()) == 100


def test_max_prompt_length_leaves_room_for_the_chat_template():
    # 64 words round up to 64 exactly; the 16 template tokens must push it to 128.
    plan = _helpers(6)["plan_lengths"]([_row(64)], _count, 6144)
    assert plan["max_prompt_length"] == 128
