"""Runs the notebook's training-summary cell without a GPU."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from server.modules.training_data.training_summary import extract_training_summary

REPO_ROOT = Path(__file__).resolve().parents[4]
NOTEBOOK_PATH = REPO_ROOT / "docs" / "colab" / "dpo_training_template.ipynb"

LOG_HISTORY = [
    {
        "step": 1,
        "loss": 0.69,
        "rewards/margins": 0.0,
        "rewards/accuracies": 0.5,
        "rewards/chosen": 0.0,
        "rewards/rejected": 0.0,
    },
    {
        "step": 12,
        "loss": 0.21,
        "rewards/margins": 1.4,
        "rewards/accuracies": 1.0,
        "rewards/chosen": 0.3,
        "rewards/rejected": -1.1,
    },
    {"step": 12, "train_runtime": 120.0},
]


def _cell(index: int) -> str:
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cell = nb["cells"][index]
    assert cell["cell_type"] == "code"
    return "".join(cell["source"])


class _State:
    def __init__(self, log_history):
        self.log_history = log_history


class _Trainer:
    def __init__(self, log_history, eval_result=None, eval_error=None):
        self.state = _State(log_history)
        self._eval_result = eval_result
        self._eval_error = eval_error

    def evaluate(self):
        if self._eval_error is not None:
            raise self._eval_error
        return self._eval_result


class _Args:
    num_train_epochs = 3


def _run_cell_8(
    trainer, *, eval_dataset="ds", heldout_rows=(1, 2, 3)
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "trainer": trainer,
        "training_args": _Args(),
        "eval_dataset": eval_dataset,
        "heldout_rows": list(heldout_rows),
    }
    exec(_cell(8), ctx)  # noqa: S102
    return ctx


def test_summary_is_built_from_the_trainer_log(capsys):
    trainer = _Trainer(
        LOG_HISTORY,
        eval_result={
            "eval_loss": 0.4,
            "eval_rewards/margins": 0.9,
            "eval_rewards/accuracies": 0.86,
        },
    )
    ctx = _run_cell_8(trainer)

    summary = ctx["TRAINING_SUMMARY"]
    assert summary["version"] == 1
    assert summary["epochs"] == 3.0
    assert summary["steps"] == 12
    assert summary["first"]["margin"] == 0.0
    assert summary["last"]["margin"] == 1.4
    assert summary["last"]["accuracy"] == 1.0
    assert summary["heldout"] == {
        "loss": 0.4,
        "margin": 0.9,
        "accuracy": 0.86,
        "pair_count": 3,
    }
    # the backend accepts exactly what the notebook produces
    assert extract_training_summary(summary) is not None
    assert "margin" in capsys.readouterr().out


def test_summary_without_heldout_split():
    ctx = _run_cell_8(_Trainer(LOG_HISTORY), eval_dataset=None, heldout_rows=())
    assert "heldout" not in ctx["TRAINING_SUMMARY"]
    assert ctx["metrics"] is None
    assert ctx["TRAINING_SUMMARY"]["last"]["margin"] == 1.4


def test_summary_survives_a_failing_evaluation():
    ctx = _run_cell_8(_Trainer(LOG_HISTORY, eval_error=RuntimeError("oom")))
    assert ctx["metrics"] is None
    assert "heldout" not in ctx["TRAINING_SUMMARY"]
    assert ctx["TRAINING_SUMMARY"]["last"]["margin"] == 1.4


def test_empty_log_history_gives_no_summary(capsys):
    ctx = _run_cell_8(_Trainer([]), eval_dataset=None)
    assert ctx["TRAINING_SUMMARY"] is None
    assert "No training summary" in capsys.readouterr().out


def test_log_rows_without_reward_keys_are_ignored():
    ctx = _run_cell_8(_Trainer([{"step": 5, "loss": 0.5}]), eval_dataset=None)
    assert ctx["TRAINING_SUMMARY"] is None


def test_non_finite_values_are_left_out():
    log = [
        {"step": 1, "loss": float("nan"), "rewards/margins": float("inf")},
        {
            "step": 2,
            "loss": 0.2,
            "rewards/margins": 1.0,
            "rewards/accuracies": 1.0,
        },
    ]
    ctx = _run_cell_8(_Trainer(log), eval_dataset=None)
    summary = ctx["TRAINING_SUMMARY"]
    assert "margin" not in summary["first"]
    assert all(math.isfinite(v) for v in summary["last"].values())


def test_training_cell_uses_the_safe_memory_settings():
    code = _cell(7)
    assert "use_logits_to_keep=True" in code
    assert "per_device_eval_batch_size=1" in code
    assert "logging_steps=1" in code
    assert "max_prompt_length=1536" in code  # experiment values stay out
    assert "num_train_epochs=1" in code


def test_first_cell_sets_expandable_segments():
    assert "PYTORCH_CUDA_ALLOC_CONF" in _cell(1)
    assert "expandable_segments:True" in _cell(1)


def test_manifest_cell_includes_the_summary(tmp_path):
    code = _cell(9)
    assert '"training_summary"' in code
    assert 'globals().get("TRAINING_SUMMARY")' in code
