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


def test_edited_cells_compile():
    # Helper-only exec checks once let a cell that did not compile ship.
    cells = _cells()
    split_index, _ = _find("def _chat_row(pair):")
    trainer_index, _ = _find("trainer = DPOTrainer(")
    for index in (split_index, trainer_index, trainer_index + 1):
        compile(cells[index], f"cell-{index}", "exec")


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
    assert "StopIfChosenCollapses()" in source
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
