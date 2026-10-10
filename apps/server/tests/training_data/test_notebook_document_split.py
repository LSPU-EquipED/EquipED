"""Execute notebook splitting/filtering/packaging without a GPU or network."""

from __future__ import annotations

import hashlib
import json

import pytest

from .test_dpo_colab_contract import (
    _get_notebook_cell_code,
    _pairs_and_provenance,
    _run_manifest_cell,
    _run_split_cell,
)
from .test_notebook_training_plan import _helpers


def _input(documents=8, evaluations=3):
    pairs, items = _pairs_and_provenance(documents * evaluations, 1)
    for n, (_, prov) in enumerate(items):
        prov["document_id"] = f"doc-{n // evaluations}"
    return pairs, items


def _documents(items):
    return {p["document_id"] for _, p in items}


def test_groups_repeated_evaluations_by_document(monkeypatch):
    pairs, items = _input()
    ns = _run_split_cell(monkeypatch, pairs, items)
    assert len(_documents(ns["heldout_items"])) == 2
    assert len(ns["heldout_items"]) == 6
    assert _documents(ns["train_items"]).isdisjoint(_documents(ns["heldout_items"]))
    assert ns["HELDOUT_METHOD"] == "group_by_document_id"
    assert all("document_id" in row for row in ns["heldout_rows"])


def test_assignment_is_independent_of_row_order_and_keeps_whole_unequal_groups(
    monkeypatch,
):
    pairs, items = _input()
    ns = _run_split_cell(monkeypatch, pairs, items)
    split = ns["split_by_document"]
    uneven = items + [items[0]] * 7
    train, held = split(uneven, 20, 42)
    reverse_train, reverse_held = split(list(reversed(uneven)), 20, 42)
    assert train == list(reversed(reverse_train))
    assert held == list(reversed(reverse_held))
    assert len(train) + len(held) == len(uneven)
    assert len(_documents(held)) == 2
    assert _documents(train).isdisjoint(_documents(held))


@pytest.mark.parametrize("identity", [None, "", "  ", 123])
def test_invalid_document_identity_fails_even_below_threshold(monkeypatch, identity):
    pairs, items = _input(documents=1, evaluations=2)
    items[0][1]["document_id"] = identity
    with pytest.raises(ValueError, match="document_id"):
        _run_split_cell(monkeypatch, pairs, items)


def test_missing_document_identity_fails(monkeypatch):
    pairs, items = _input()
    del items[0][1]["document_id"]
    with pytest.raises(ValueError, match="document_id"):
        _run_split_cell(monkeypatch, pairs, items)


@pytest.mark.parametrize(
    ("documents", "evaluations", "reason"),
    [(1, 25, "single_document"), (8, 1, "below_minimum_pairs")],
)
def test_training_only_runs_record_the_reason(
    monkeypatch, documents, evaluations, reason
):
    pairs, items = _input(documents, evaluations)
    ns = _run_split_cell(monkeypatch, pairs, items)
    assert ns["eval_dataset"] is None
    assert ns["heldout_rows"] == []
    assert ns["DATASET_SPLIT"]["no_heldout_reason"] == reason
    assert ns["DATASET_SPLIT"]["train"]["pair_count"] == len(pairs)


def test_empty_dataset_fails(monkeypatch):
    with pytest.raises(ValueError, match="training pairs"):
        _run_split_cell(monkeypatch, [], [])


def test_cross_document_exact_prompt_leakage_stops_without_source_text(monkeypatch):
    pairs, items = _input()
    ns = _run_split_cell(monkeypatch, pairs, items)
    ns["train_items"][0][0]["prompt"] = "PRIVATE SOURCE TEXT"
    ns["heldout_items"][0][0]["prompt"] = "PRIVATE SOURCE TEXT"
    with pytest.raises(ValueError, match="prompt overlap") as error:
        _run_split_cell(monkeypatch, pairs, items)
    assert "PRIVATE SOURCE TEXT" not in str(error.value)
    assert ns["train_items"][0][1]["pair_id"] in str(error.value)


def test_within_side_repeated_prompts_are_reported_not_removed(monkeypatch):
    pairs, items = _input()
    pairs[1]["prompt"] = pairs[0]["prompt"]
    ns = _run_split_cell(monkeypatch, pairs, items)
    meta = ns["DATASET_SPLIT"]
    assert meta["train"]["pair_count"] + meta["heldout"]["pair_count"] == 24
    assert sum(meta[s]["repeated_prompt_count"] for s in ("train", "heldout")) == 1
    assert meta["overlap"] == {"document_count": 0, "exact_prompt_count": 0}


class _Dataset(list):
    def select(self, indices):
        return _Dataset(self[i] for i in indices)


def _filter(ns, keep):
    """Execute real post-plan filtering with a controlled length-planner result."""
    ns["train_dataset"] = _Dataset(ns["train_dataset"])
    if ns["eval_dataset"] is not None:
        ns["eval_dataset"] = _Dataset(ns["eval_dataset"])
    ns["_train_rows"] = ns["train_items"]
    ns["_eval_rows"] = ns["heldout_items"]
    ns["LENGTH_PLAN"] = {"keep": keep}
    ns["split_keep"] = _helpers(6)["split_keep"]
    source = _get_notebook_cell_code(6)
    start = source.index("_n_train =")
    end = source.index("\nMAX_SEQ_LENGTH = LENGTH_PLAN[")
    exec(source[start:end], ns)  # noqa: S102


def test_filtered_records_saved_rows_and_manifest_agree(monkeypatch, tmp_path):
    pairs, items = _input()
    ns = _run_split_cell(monkeypatch, pairs, items)
    original_train = list(ns["train_items"])
    original_held = list(ns["heldout_items"])
    ntrain = len(original_train)
    keep = list(range(1, ntrain)) + list(range(ntrain + 1, len(items)))
    _filter(ns, keep)
    assert ns["train_items"] == original_train[1:]
    assert ns["heldout_items"] == original_held[1:]
    assert len(ns["heldout_rows"]) == len(ns["eval_dataset"]) == 5
    assert ns["DATASET_SPLIT"]["dropped"] == {
        "train_pair_ids": [original_train[0][1]["pair_id"]],
        "heldout_pair_ids": [original_held[0][1]["pair_id"]],
    }
    _run_manifest_cell(ns, tmp_path)
    manifest = json.loads((tmp_path / "training_manifest.json").read_text())
    raw = (tmp_path / "heldout_pairs.jsonl").read_bytes()
    assert manifest["dataset_split"] == ns["DATASET_SPLIT"]
    assert manifest["heldout"]["pair_count"] == 5
    assert manifest["heldout"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest["source_job_manifest"] == {
        "pairs_sha256": "a" * 64,
        "provenance_sha256": "b" * 64,
    }
    assert [json.loads(s) for s in raw.splitlines()] == ns["heldout_rows"]


def test_all_heldout_dropped_has_explicit_reason_and_removes_stale_file(
    monkeypatch, tmp_path
):
    pairs, items = _input()
    ns = _run_split_cell(monkeypatch, pairs, items)
    assigned = _documents(ns["heldout_items"])
    _filter(ns, list(range(len(ns["train_items"]))))
    assert ns["eval_dataset"] is None
    assert ns["heldout_items"] == ns["heldout_rows"] == []
    meta = ns["DATASET_SPLIT"]
    assert meta["no_heldout_reason"] == "all_heldout_dropped_for_length"
    assert meta["assigned"]["heldout_document_ids"] == sorted(assigned)
    stale = tmp_path / "heldout_pairs.jsonl"
    stale.write_text("previous run")
    _run_manifest_cell(ns, tmp_path)
    assert not stale.exists()
    manifest = json.loads((tmp_path / "training_manifest.json").read_text())
    assert manifest["heldout"] is None
    assert manifest["dataset_split"] == meta


def test_no_training_survivors_fails_before_training(monkeypatch):
    pairs, items = _input()
    ns = _run_split_cell(monkeypatch, pairs, items)
    with pytest.raises(ValueError, match="GPU length ceiling"):
        _filter(ns, list(range(len(ns["train_items"]), len(items))))


def test_rerun_keeps_cumulative_drop_count_in_artifact(monkeypatch, tmp_path):
    pairs, items = _input()
    ns = _run_split_cell(monkeypatch, pairs, items)
    _filter(ns, list(range(1, len(items))))
    _filter(ns, list(range(len(items) - 1)))
    ns.update(
        LENGTH_PLAN={"dropped": [], "max_prompt_length": 128, "max_seq_length": 2048},
        DOSE_PLAN={
            "steps_per_epoch": 5,
            "epochs": 4,
            "planned_updates": 20,
            "max_steps": None,
        },
        HARD_MAX_SEQ_LENGTH=6144,
        LEARNING_RATE=2e-5,
        GRAD_ACCUM=4,
        _gpu_gb=15,
    )
    _run_manifest_cell(ns, tmp_path)
    manifest = json.loads((tmp_path / "training_manifest.json").read_text())
    assert len(manifest["dataset_split"]["dropped"]["train_pair_ids"]) == 1
    assert manifest["training_plan"]["dropped_pairs"] == 1


@pytest.mark.parametrize(("documents", "should_fail"), [(8, True), (10, False)])
def test_all_heldout_length_drops_obey_the_twenty_percent_limit(
    monkeypatch, documents, should_fail
):
    pairs, items = _input(documents=documents)
    ns = _run_split_cell(monkeypatch, pairs, items)
    for pair, _ in ns["heldout_items"]:
        pair["prompt"] = "long " * 7000
    ns["train_dataset"] = _Dataset(ns["train_dataset"])
    ns["eval_dataset"] = _Dataset(ns["eval_dataset"])
    ns.update(_helpers(6))
    ns.update(
        _count_tokens=lambda value: len(value.split()),
        HARD_MAX_SEQ_LENGTH=6144,
        LONG_PAIR_POLICY="drop",
        MAX_DROP_FRACTION=0.2,
    )
    source = _get_notebook_cell_code(6)
    code = source[
        source.index("# Measure the plain text") : source.index(
            "\nMAX_SEQ_LENGTH = LENGTH_PLAN["
        )
    ]
    if should_fail:
        with pytest.raises(ValueError, match="ceiling"):
            exec(code, ns)  # noqa: S102
    else:
        exec(code, ns)  # noqa: S102
        assert ns["eval_dataset"] is None
        assert ns["heldout_rows"] == []
        assert (
            ns["DATASET_SPLIT"]["no_heldout_reason"] == "all_heldout_dropped_for_length"
        )


def test_training_introduction_names_document_grouping():
    from .test_dpo_colab_contract import NOTEBOOK_PATH

    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    intro = "".join(nb["cells"][3]["source"])
    assert "document_id" in intro
    assert "evaluation_id" not in intro
