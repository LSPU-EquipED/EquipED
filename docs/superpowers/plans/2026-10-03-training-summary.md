# Training Summary (Preference Margin) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every newly trained adapter version carries a small training summary (preference margin, accuracy, loss, held-out numbers) that the admin Training Data page shows.

**Architecture:** The Colab notebook builds a `training_summary` from the trainer log right after training and writes it into the `training_manifest.json` it already uploads. The backend validates it on upload (never rejecting the upload because of it), stores it in a new nullable JSON column on `trained_adapters`, and returns it in the adapter list API. The admin adapter row shows it above a collapsed "Technical details" section.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pytest; React 18 + TypeScript + Vitest; Jupyter notebook JSON (Colab, TRL 0.24).

**Spec:** `docs/superpowers/specs/2026-10-03-training-summary-design.md`

## Global Constraints

- Backend: ruff (E, F, I, UP), line length 88, Python 3.12. Absolute `server.*` imports. Run commands from `apps/` with `uv run --project server ...`.
- Frontend: custom components only (no shadcn/ui), features must not import from sibling features, Tailwind v4 tokens already used by `AdapterRow`.
- A missing or invalid `training_summary` must NEVER make an upload fail (the upload link is single-use and the training run is long). It is logged and stored as `NULL`.
- Summary JSON shape (version 1): `{"version": 1, "steps": int, "epochs": number, "first": {"step","loss","margin","accuracy","chosen","rejected"}, "last": {same keys}, "heldout": {"pair_count","loss","margin","accuracy"}}`. Every key except `version` is optional. All numbers finite; unknown keys are dropped; booleans are not numbers.
- Do NOT insert or remove cells in `docs/colab/dpo_training_template.ipynb`: existing tests address cells by index (1, 2, 4, 5, 6, 7, 9, 10). Edit cell contents only.
- The notebook file uses CRLF line endings and has no trailing newline. Rewrite it only with the snippet given in Task 4 (it round-trips byte-for-byte).
- Only the safe memory fixes come from the user's `latest_dpo_training_template.ipynb`: `expandable_segments` env var, `use_logits_to_keep=True`, `per_device_eval_batch_size=1`. Do not change `MAX_SEQ_LENGTH`, `max_prompt_length` or `num_train_epochs` in the tracked template. Do not touch `latest_dpo_training_template.ipynb`.
- Out of scope: charts, comparison across versions, backfilling existing adapters.
- No `Co-Authored-By` or `Claude-Session` trailers in commit messages (CLAUDE.md). Commit per task only if the user authorized commits for this execution.
- Work on a new branch `feat/training-summary` created from `main`.

## Review Focus

1. A `training_summary` containing `NaN`, `Infinity`, booleans, strings or absurdly large numbers: ignored, upload still succeeds (Tasks 1, 2, 3).
2. A `training_summary` of the wrong type (list, string, number) or an unknown `version`: ignored, upload succeeds (Tasks 1, 2).
3. An empty trainer log, no held-out split, or `trainer.evaluate()` failing: notebook still writes the manifest, with `training_summary` null or without `heldout` (Task 4).
4. Existing adapter rows (`NULL` column) and the existing manifest-cell tests that never define `TRAINING_SUMMARY`: API returns `null`, the cell still runs, the UI says "Not recorded" (Tasks 3, 4, 5).
5. Partial summaries (only `last.margin`, or only `heldout`): the panel shows just what exists and never prints `undefined`/`NaN` (Task 5).

---

### Task 1: Training summary validation module

**Files:**
- Create: `apps/server/modules/training_data/training_summary.py`
- Test: `apps/server/tests/training_data/test_training_summary.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `TrainingSnapshot`, `HeldoutSummary`, `TrainingSummary` (Pydantic models) and `extract_training_summary(raw: Any) -> dict[str, Any] | None` in `server.modules.training_data.training_summary`. The returned dict contains only known keys with `None` values removed and always has `"version": 1`; `None` is returned for anything invalid or empty.

- [ ] **Step 1: Create the branch**

Run: `git switch -c feat/training-summary` (from `main`).

- [ ] **Step 2: Write the failing tests**

Create `apps/server/tests/training_data/test_training_summary.py`:

```python
"""apps/server/tests/training_data/test_training_summary.py"""

from __future__ import annotations

import logging

import pytest
from server.modules.training_data.training_summary import (
    TrainingSummary,
    extract_training_summary,
)

FULL = {
    "version": 1,
    "steps": 12,
    "epochs": 3.0,
    "first": {
        "step": 1,
        "loss": 0.69,
        "margin": 0.0,
        "accuracy": 0.5,
        "chosen": 0.0,
        "rejected": 0.0,
    },
    "last": {
        "step": 12,
        "loss": 0.21,
        "margin": 1.4,
        "accuracy": 1.0,
        "chosen": 0.3,
        "rejected": -1.1,
    },
    "heldout": {"pair_count": 7, "loss": 0.4, "margin": 0.9, "accuracy": 0.86},
}


def test_full_summary_round_trips():
    assert extract_training_summary(FULL) == FULL


def test_partial_summary_keeps_only_present_values():
    result = extract_training_summary({"version": 1, "last": {"margin": 1.4}})
    assert result == {"version": 1, "last": {"margin": 1.4}}


def test_integers_are_accepted_as_metric_values():
    result = extract_training_summary({"last": {"margin": 1, "accuracy": 1}})
    assert result == {"version": 1, "last": {"margin": 1.0, "accuracy": 1.0}}


@pytest.mark.parametrize("raw", [None, {}, {"version": 1}, [], "text", 5, True])
def test_nothing_useful_returns_none(raw):
    assert extract_training_summary(raw) is None


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf"), True, "1.4", 1e12, -1e12],
)
def test_invalid_metric_value_makes_the_summary_none(bad_value):
    raw = {"version": 1, "last": {"margin": bad_value}}
    assert extract_training_summary(raw) is None


def test_explicit_null_counts_as_missing():
    assert extract_training_summary({"version": 1, "last": {"margin": None}}) is None


def test_empty_nested_objects_are_not_a_summary():
    assert extract_training_summary({"version": 1, "last": {}}) is None


def test_unknown_keys_are_dropped():
    raw = {"version": 1, "junk": 1, "last": {"margin": 1.4, "extra": "x"}}
    assert extract_training_summary(raw) == {"version": 1, "last": {"margin": 1.4}}


def test_unknown_version_is_ignored():
    assert extract_training_summary({"version": 2, "last": {"margin": 1.0}}) is None


def test_negative_or_fractional_counts_are_invalid():
    assert extract_training_summary({"steps": -1, "last": {"margin": 1.0}}) is None
    assert extract_training_summary({"steps": 1.5, "last": {"margin": 1.0}}) is None


def test_invalid_summary_logs_a_warning(caplog):
    with caplog.at_level(logging.WARNING):
        extract_training_summary({"last": {"margin": float("nan")}})
    assert "training_summary" in caplog.text


def test_model_is_usable_for_api_responses():
    parsed = TrainingSummary.model_validate(FULL)
    assert parsed.last is not None and parsed.last.margin == 1.4
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_training_summary.py -v`
Expected: FAIL / collection error (`ModuleNotFoundError: server.modules.training_data.training_summary`).

- [ ] **Step 4: Write the implementation**

Create `apps/server/modules/training_data/training_summary.py`:

```python
"""Validation of the optional training summary an adapter archive carries."""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

logger = logging.getLogger(__name__)

_BOUND = 1_000_000.0

Metric = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-_BOUND, le=_BOUND)]
Count = Annotated[int, Field(strict=True, ge=0, le=10_000_000)]


class _Summary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @field_validator("*", mode="before")
    @classmethod
    def _reject_bool(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("booleans are not numbers")
        return value


class TrainingSnapshot(_Summary):
    step: Count | None = None
    loss: Metric | None = None
    margin: Metric | None = None
    accuracy: Metric | None = None
    chosen: Metric | None = None
    rejected: Metric | None = None


class HeldoutSummary(_Summary):
    pair_count: Count | None = None
    loss: Metric | None = None
    margin: Metric | None = None
    accuracy: Metric | None = None


class TrainingSummary(_Summary):
    version: Literal[1] = 1
    steps: Count | None = None
    epochs: Metric | None = None
    first: TrainingSnapshot | None = None
    last: TrainingSnapshot | None = None
    heldout: HeldoutSummary | None = None


def extract_training_summary(raw: Any) -> dict[str, Any] | None:
    """Return a clean summary dict, or None when it is absent or invalid.

    Never raises: a bad summary must not cost anyone a finished training run.
    """
    if raw is None:
        return None
    try:
        summary = TrainingSummary.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "Ignoring invalid training_summary in adapter archive "
            "(%d validation error(s))",
            exc.error_count(),
        )
        return None
    cleaned = summary.model_dump(mode="json", exclude_none=True)
    for key in ("first", "last", "heldout"):
        if cleaned.get(key) == {}:
            del cleaned[key]
    # Only {"version": 1} (or nothing else of value) means there is nothing to show.
    if not any(key in cleaned for key in ("steps", "first", "last", "heldout")):
        return None
    return cleaned


__all__ = [
    "HeldoutSummary",
    "TrainingSnapshot",
    "TrainingSummary",
    "extract_training_summary",
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_training_summary.py -v`
Expected: PASS. If a `strict=True` metric rejects a plain JSON integer, re-check the `test_integers_are_accepted_as_metric_values` case and use `Annotated[float, Strict(False)]` semantics (accept `int`, reject `str`/`bool`) instead.

- [ ] **Step 6: Lint and commit**

Run: `cd apps && uv run --project server ruff check --fix server/modules/training_data/training_summary.py server/tests/training_data/test_training_summary.py && uv run --project server ruff format server/modules/training_data/training_summary.py server/tests/training_data/test_training_summary.py`

```bash
git add apps/server/modules/training_data/training_summary.py apps/server/tests/training_data/test_training_summary.py
git commit -m "feat(training-data): validate the optional training summary"
```

---

### Task 2: Archive staging returns the validated summary

**Files:**
- Modify: `apps/server/modules/training_data/adapter_artifacts.py` (`StagedAdapterArtifact`, `_validate_archive`, `stage_adapter_artifact`)
- Test: `apps/server/tests/training_data/test_adapter_artifacts.py`

**Interfaces:**
- Consumes: `extract_training_summary` (Task 1).
- Produces: `StagedAdapterArtifact.training_summary: dict | None = None`; `stage_adapter_artifact(...)` fills it. `_validate_archive` now returns `dict | None`.

- [ ] **Step 1: Write the failing tests**

In `apps/server/tests/training_data/test_adapter_artifacts.py`, add a sentinel and a parameter to `_make_adapter_zip_bytes`:

```python
_NO_SUMMARY = object()
```
(place it above `_make_adapter_zip_bytes`), add the keyword `training_summary: object = _NO_SUMMARY,` to its signature, and replace the manifest block with:

```python
        if include_training_manifest:
            manifest_data = {"source_job_manifest": source_manifest}
            if training_summary is not _NO_SUMMARY:
                manifest_data["training_summary"] = training_summary
            zf.writestr("training_manifest.json", json.dumps(manifest_data))
```

Append these tests at the end of the file:

```python
def _stage(monkeypatch, tmp_path, zip_bytes, manifest):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    return stage_adapter_artifact(
        "sme",
        uuid.uuid4(),
        filename="adapter.zip",
        source=io.BytesIO(zip_bytes),
        expected_source_manifest=manifest,
    )


def test_stage_returns_valid_training_summary(monkeypatch, tmp_path):
    manifest = {"agent_id": "sme", "pair_count": 1}
    summary = {"version": 1, "steps": 12, "last": {"step": 12, "margin": 1.4}}
    staged = _stage(
        monkeypatch,
        tmp_path,
        _make_adapter_zip_bytes(manifest, training_summary=summary),
        manifest,
    )
    assert staged.training_summary == summary


def test_stage_without_training_summary_is_none(monkeypatch, tmp_path):
    manifest = {"agent_id": "sme", "pair_count": 1}
    staged = _stage(monkeypatch, tmp_path, _make_adapter_zip_bytes(manifest), manifest)
    assert staged.training_summary is None


@pytest.mark.parametrize(
    "bad_summary",
    [
        "not a summary",
        [1, 2, 3],
        {"version": 1, "last": {"margin": "high"}},
        {"version": 2, "last": {"margin": 1.0}},
        {"version": 1, "last": {"margin": True}},
    ],
)
def test_stage_ignores_invalid_training_summary(monkeypatch, tmp_path, bad_summary):
    manifest = {"agent_id": "sme", "pair_count": 1}
    staged = _stage(
        monkeypatch,
        tmp_path,
        _make_adapter_zip_bytes(manifest, training_summary=bad_summary),
        manifest,
    )
    assert staged.training_summary is None
    assert staged.staging_path.exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_adapter_artifacts.py -v -k training_summary`
Expected: FAIL (`AttributeError: ... has no attribute 'training_summary'` or `TypeError` on the dataclass).

- [ ] **Step 3: Implement**

In `adapter_artifacts.py`:

1. Import: `from server.modules.training_data.training_summary import extract_training_summary` (merge into the existing import block; ruff will order it).
2. Dataclass: add as the LAST field of `StagedAdapterArtifact`: `training_summary: dict | None = None`.
3. `_validate_archive`: change the signature to `-> dict | None`. Right after the `source_job_manifest` comparison add:

```python
            training_summary = extract_training_summary(
                training_manifest.get("training_summary")
            )
```
   and after the `testzip()` check (still inside the `with` block) add `return training_summary`.
4. `stage_adapter_artifact`: replace `_validate_archive(staging_path, expected_source_manifest)` with `training_summary = _validate_archive(staging_path, expected_source_manifest)` and pass `training_summary=training_summary` into the `StagedAdapterArtifact(...)` call.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_adapter_artifacts.py -v`
Expected: all PASS (existing tests included).

- [ ] **Step 5: Lint and commit**

Run ruff check --fix and ruff format on the two files (as in Task 1), then:

```bash
git add apps/server/modules/training_data/adapter_artifacts.py apps/server/tests/training_data/test_adapter_artifacts.py
git commit -m "feat(training-data): read the training summary while staging an adapter"
```

---

### Task 3: Store it, migrate the table, return it from the API

**Files:**
- Modify: `apps/server/modules/training_data/models.py` (`TrainedAdapter`)
- Create: `apps/server/alembic/versions/20261003_0001_add_training_summary_to_trained_adapters.py`
- Modify: `apps/server/modules/training_data/adapters.py` (`store_adapter_upload`)
- Modify: `apps/server/modules/training_data/schemas.py` (`TrainedAdapterResponse`)
- Test: `apps/server/tests/training_data/test_adapters.py`, `apps/server/tests/training_data/test_router.py`

**Interfaces:**
- Consumes: `StagedAdapterArtifact.training_summary` (Task 2), `TrainingSummary` (Task 1).
- Produces: column `trained_adapters.training_summary` (JSON, nullable, `TrainedAdapter.training_summary: dict | None`); `TrainedAdapterResponse.training_summary: TrainingSummary | None = None`, which flows into `TrainedAdapterListItem` and the list endpoint.

- [ ] **Step 1: Write the failing tests**

In `apps/server/tests/training_data/test_adapters.py`, add a sentinel and a parameter to `_make_adapter_zip` (same pattern as Task 2):

```python
_NO_SUMMARY = object()
```
add `training_summary: object = _NO_SUMMARY,` to its signature and build the manifest as:

```python
        manifest = {"source_job_manifest": source_manifest}
        if training_summary is not _NO_SUMMARY:
            manifest["training_summary"] = training_summary
        zf.writestr("training_manifest.json", json.dumps(manifest))
```
Append:

```python
def _upload(db_session, admin_user, tmp_path, monkeypatch, **zip_kwargs):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    result = create_training_job(db_session, "gad", admin_user.user_id)
    zip_bytes = _make_adapter_zip(result.job.manifest_json, **zip_kwargs)
    return store_adapter_upload(
        db_session,
        result.job.job_id,
        result.raw_upload_token,
        filename="adapter.zip",
        source=io.BytesIO(zip_bytes),
    )


def test_store_adapter_upload_persists_training_summary(
    db_session, admin_user, tmp_path, monkeypatch
):
    summary = {
        "version": 1,
        "steps": 12,
        "last": {"step": 12, "margin": 1.4, "accuracy": 1.0},
    }
    adapter = _upload(
        db_session, admin_user, tmp_path, monkeypatch, training_summary=summary
    )
    db_session.refresh(adapter)
    assert adapter.training_summary == summary


def test_store_adapter_upload_without_summary_stores_null(
    db_session, admin_user, tmp_path, monkeypatch
):
    adapter = _upload(db_session, admin_user, tmp_path, monkeypatch)
    db_session.refresh(adapter)
    assert adapter.training_summary is None


def test_store_adapter_upload_with_invalid_summary_still_succeeds(
    db_session, admin_user, tmp_path, monkeypatch
):
    adapter = _upload(
        db_session,
        admin_user,
        tmp_path,
        monkeypatch,
        training_summary={"version": 1, "last": {"margin": "huge"}},
    )
    db_session.refresh(adapter)
    assert adapter.version == 1
    assert adapter.training_summary is None
```

In `apps/server/tests/training_data/test_router.py`, after `test_list_adapters_includes_loaded_and_published`, add:

```python
def test_list_adapters_returns_training_summary(
    client: TestClient, db_session, admin_user, auth_cookies_admin, monkeypatch
):
    from server.tests.training_data.conftest import make_adapter

    v1 = make_adapter(db_session, "sme", 1)
    make_adapter(db_session, "sme", 2)
    v1.training_summary = {
        "version": 1,
        "steps": 12,
        "last": {"step": 12, "margin": 1.4, "accuracy": 1.0},
    }
    db_session.commit()
    _fake_state(monkeypatch, loaded=[])
    _auth(client, auth_cookies_admin)

    body = client.get("/api/v1/admin/training-data/sme/adapters").json()
    by_version = {a["version"]: a for a in body["adapters"]}
    assert by_version[1]["training_summary"]["last"]["margin"] == 1.4
    assert by_version[1]["training_summary"]["steps"] == 12
    assert by_version[2]["training_summary"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_adapters.py server/tests/training_data/test_router.py -v -k training_summary`
Expected: FAIL (`AttributeError`/`TypeError`: `training_summary` is not a column or attribute).

- [ ] **Step 3: Implement the model column and migration**

In `models.py`, in `TrainedAdapter`, after `size_bytes` add:

```python
    training_summary: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
```
(`sa` is already imported in this module; `manifest_json` uses `sa.JSON`.)

Create `apps/server/alembic/versions/20261003_0001_add_training_summary_to_trained_adapters.py`:

```python
"""Add training_summary to trained_adapters.

Revision ID: 20261003_0001
Revises: 20260929_0001
Create Date: 2026-10-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261003_0001"
down_revision: str | None = "20260929_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trained_adapters",
        sa.Column("training_summary", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trained_adapters", "training_summary")
```

- [ ] **Step 4: Implement the store and the API schema**

In `adapters.py` (`store_adapter_upload`), add one keyword to the `TrainedAdapter(...)` construction:

```python
                size_bytes=artifact.size_bytes,
                training_summary=staged.training_summary,
```

In `schemas.py`, import `TrainingSummary` (`from server.modules.training_data.training_summary import TrainingSummary`) and add to `TrainedAdapterResponse` after `created_at`:

```python
    training_summary: TrainingSummary | None = None
```
(`TrainedAdapterListItem` inherits it; `router.py` already builds list items from `TrainedAdapterResponse.model_validate(adapter).model_dump()`, so no router change is needed.) Add `"TrainingSummary"` re-export is NOT needed.

- [ ] **Step 5: Run the tests and check the migration chain**

Run: `cd apps && uv run --project server pytest server/tests/training_data -q`
Expected: all PASS.

Run: `cd apps/server && uv run alembic heads`
Expected: exactly one line, `20261003_0001 (head)`.

Run: `cd apps/server && uv run alembic upgrade 20260929_0001:20261003_0001 --sql`
Expected: output contains `ALTER TABLE trained_adapters ADD COLUMN training_summary JSON`. (If this environment's `env.py` does not support offline mode, skip this one command; the heads check is the required gate.)

- [ ] **Step 6: Lint and commit**

Run ruff check --fix and ruff format on the changed `.py` files (models, adapters, schemas, the migration, the two test files), then:

```bash
git add apps/server/modules/training_data/models.py apps/server/modules/training_data/adapters.py apps/server/modules/training_data/schemas.py apps/server/alembic/versions/20261003_0001_add_training_summary_to_trained_adapters.py apps/server/tests/training_data/test_adapters.py apps/server/tests/training_data/test_router.py
git commit -m "feat(training-data): store and return the adapter training summary"
```

---

### Task 4: Notebook builds and uploads the summary

**Files:**
- Modify (cell contents only, no new cells): `docs/colab/dpo_training_template.ipynb` cells 1, 7, 8, 9
- Create: `apps/server/tests/training_data/test_notebook_training_summary.py`

**Interfaces:**
- Consumes: the manifest shape from Task 2 (`training_manifest.json` -> `training_summary`).
- Produces: after cell 8 runs, the global `TRAINING_SUMMARY` (dict or `None`); cell 9 writes it to `training_manifest.json` under `"training_summary"`.

- [ ] **Step 1: Write the failing tests**

Create `apps/server/tests/training_data/test_notebook_training_summary.py`:

```python
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


def _run_cell_8(trainer, *, eval_dataset="ds", heldout_rows=(1, 2, 3)) -> dict[str, Any]:
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
    assert 'PYTORCH_CUDA_ALLOC_CONF' in _cell(1)
    assert "expandable_segments:True" in _cell(1)


def test_manifest_cell_includes_the_summary(tmp_path):
    code = _cell(9)
    assert '"training_summary"' in code
    assert 'globals().get("TRAINING_SUMMARY")' in code
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_notebook_training_summary.py -v`
Expected: FAIL (cell 8 has no `TRAINING_SUMMARY`; cell 7/1/9 lack the new text).

- [ ] **Step 3: Edit the notebook cells with a round-trip-safe script**

The notebook is CRLF with no trailing newline; this snippet round-trips it byte-for-byte. Save it as a temporary file in the scratchpad (not in the repo) and run it from the repo root: `python <path-to-snippet>`.

```python
import json
from pathlib import Path

path = Path("docs/colab/dpo_training_template.ipynb")
raw = path.read_bytes().decode("utf-8")
nb = json.loads(raw)
assert json.dumps(nb, indent=1).replace("\n", "\r\n") == raw, "round-trip changed"


def set_source(index: int, text: str) -> None:
    lines = text.split("\n")
    nb["cells"][index]["source"] = [line + "\n" for line in lines[:-1]] + [lines[-1]]


def source(index: int) -> str:
    return "".join(nb["cells"][index]["source"])


# cell 1: expandable segments before anything touches CUDA
c1 = source(1)
assert "expandable_segments" not in c1
anchor = 'UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"\n'
assert anchor in c1
c1 = c1.replace(
    anchor,
    anchor + '\nimport os\n\nos.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"\n',
    1,
)
set_source(1, c1)

# cell 7: log every step; keep evaluation memory small; compute logits only for answers
c7 = source(7)
for old, new in (
    ("    logging_steps=5,\n", "    logging_steps=1,\n    per_device_eval_batch_size=1,\n    use_logits_to_keep=True,\n"),
):
    assert old in c7
    c7 = c7.replace(old, new, 1)
set_source(7, c7)

# cell 8: keep the existing evaluation block, add the summary builder after it
c8 = source(8)
assert "TRAINING_SUMMARY" not in c8
HELPERS = '''import math


def _finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _snapshot(row):
    snapshot = {}
    if _finite(row.get("step")):
        snapshot["step"] = int(row["step"])
    for name, key in (
        ("loss", "loss"),
        ("margin", "rewards/margins"),
        ("accuracy", "rewards/accuracies"),
        ("chosen", "rewards/chosen"),
        ("rejected", "rewards/rejected"),
    ):
        if _finite(row.get(key)):
            snapshot[name] = float(row[key])
    return snapshot


def build_training_summary(
    log_history, num_train_epochs, heldout_metrics=None, heldout_pair_count=None
):
    """Condense the trainer log into the small summary the admin page shows.

    Never raises: returns None when nothing usable was logged.
    """
    try:
        rows = [
            row
            for row in (log_history or [])
            if isinstance(row, dict) and "loss" in row and "rewards/margins" in row
        ]
        summary = {"version": 1}
        if _finite(num_train_epochs):
            summary["epochs"] = float(num_train_epochs)
        if rows:
            summary["first"] = _snapshot(rows[0])
            summary["last"] = _snapshot(rows[-1])
            if "step" in summary["last"]:
                summary["steps"] = summary["last"]["step"]
        if isinstance(heldout_metrics, dict):
            heldout = {}
            for name, key in (
                ("loss", "eval_loss"),
                ("margin", "eval_rewards/margins"),
                ("accuracy", "eval_rewards/accuracies"),
            ):
                if _finite(heldout_metrics.get(key)):
                    heldout[name] = float(heldout_metrics[key])
            if heldout:
                if isinstance(heldout_pair_count, int) and heldout_pair_count > 0:
                    heldout["pair_count"] = heldout_pair_count
                summary["heldout"] = heldout
        if "last" not in summary and "heldout" not in summary:
            return None
        return summary
    except Exception:
        return None


def _fmt(row, key, spec):
    value = row.get(key)
    return format(value, spec) if value is not None else "n/a"


def print_training_summary(summary):
    if not summary:
        print("No training summary could be built (nothing was logged).")
        return
    print("Training summary (measured on the training pairs):")
    for label in ("first", "last"):
        row = summary.get(label)
        if row:
            print(
                f"  {label:<5} step {_fmt(row, 'step', 'd')}  "
                f"loss {_fmt(row, 'loss', '.4f')}  "
                f"margin {_fmt(row, 'margin', '.4f')}  "
                f"accuracy {_fmt(row, 'accuracy', '.2f')}"
            )
    if summary.get("heldout"):
        print("  held-out:", summary["heldout"])


'''
TAIL = '''

TRAINING_SUMMARY = None
try:
    TRAINING_SUMMARY = build_training_summary(
        trainer.state.log_history,
        training_args.num_train_epochs,
        metrics,
        len(heldout_rows) if heldout_rows else None,
    )
except Exception as exc:
    print(f"Could not build the training summary ({exc!r}); continuing.")
print_training_summary(TRAINING_SUMMARY)
'''
set_source(8, HELPERS + c8.rstrip("\n") + TAIL)

# cell 9: add the summary to the manifest the notebook uploads
c9 = source(9)
old = '    "eval_metrics": metrics,\n'
assert old in c9
c9 = c9.replace(
    old,
    old + '    "training_summary": globals().get("TRAINING_SUMMARY"),\n',
    1,
)
set_source(9, c9)

out = json.dumps(nb, indent=1).replace("\n", "\r\n")
path.write_bytes(out.encode("utf-8"))
print("notebook updated")
```

Notes: the snippet keeps the existing evaluation block exactly as it is (it sits between the helpers and the tail), so cell 8 still defines `metrics` in every branch before the tail uses it. The `metrics` name is referenced by cell 9 already.

- [ ] **Step 4: Run the notebook tests and the existing contract tests**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_notebook_training_summary.py server/tests/training_data/test_dpo_colab_contract.py -v`
Expected: all PASS. If an existing contract test fails because it asserts exact text of cells 1 or 7, adjust only that assertion to the new text and mention it in the commit message body.

Run: `git diff --stat docs/colab/dpo_training_template.ipynb`
Expected: a small diff (about 100 lines added, 2 changed). If the whole file shows as changed, the round trip went wrong: restore the file with `git checkout docs/colab/dpo_training_template.ipynb` and rerun the snippet unchanged.

- [ ] **Step 5: Lint and commit**

Run: `cd apps && uv run --project server ruff check --fix server/tests/training_data/test_notebook_training_summary.py && uv run --project server ruff format server/tests/training_data/test_notebook_training_summary.py`

```bash
git add docs/colab/dpo_training_template.ipynb apps/server/tests/training_data/test_notebook_training_summary.py
git commit -m "feat(colab): save a training summary with the adapter and log every step"
```

---

### Task 5: Admin UI shows the summary

**Files:**
- Modify: `apps/admin/src/features/training-data/types.ts`
- Modify: `apps/admin/src/features/training-data/utils/trainingData.utils.ts`
- Create: `apps/admin/src/features/training-data/components/TrainingSummaryPanel.tsx`
- Modify: `apps/admin/src/features/training-data/components/AdapterRow.tsx`
- Test: `apps/admin/src/features/training-data/components/__tests__/TrainingSummaryPanel.test.tsx`, `apps/admin/src/features/training-data/components/__tests__/AdapterRow.test.tsx`

**Interfaces:**
- Consumes: API field `training_summary` on each adapter item (Task 3).
- Produces: `TrainingSummary`, `TrainingSnapshot`, `HeldoutSummary` types; `buildTrainingSummaryEntries(summary): [string, string][]` in `trainingData.utils.ts`; `<TrainingSummaryPanel summary={...} />`.

- [ ] **Step 1: Write the failing tests**

Create `apps/admin/src/features/training-data/components/__tests__/TrainingSummaryPanel.test.tsx`:

```tsx
// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { TrainingSummaryPanel } from '../TrainingSummaryPanel';

afterEach(cleanup);

it('shows margin, accuracy, loss, steps and the held-out numbers', () => {
  render(
    <TrainingSummaryPanel
      summary={{
        version: 1,
        steps: 12,
        epochs: 3,
        first: { step: 1, margin: 0, loss: 0.69, accuracy: 0.5 },
        last: { step: 12, margin: 1.4, loss: 0.21, accuracy: 1 },
        heldout: { pair_count: 7, margin: 0.9, accuracy: 0.86, loss: 0.4 },
      }}
    />,
  );
  expect(screen.getByText('Training summary')).toBeDefined();
  expect(screen.getByText('0.00 → 1.40')).toBeDefined();
  expect(screen.getByText('100%')).toBeDefined();
  expect(screen.getByText('0.210')).toBeDefined();
  expect(screen.getByText('12 (3 epochs)')).toBeDefined();
  expect(screen.getByText('0.90')).toBeDefined();
  expect(screen.getByText('86%')).toBeDefined();
  expect(screen.getByText(/measured on the training pairs/i)).toBeDefined();
});

it('says "Not recorded" when there is no summary', () => {
  render(<TrainingSummaryPanel summary={null} />);
  expect(screen.getByText('Not recorded')).toBeDefined();
  expect(screen.queryByText(/measured on the training pairs/i)).toBeNull();
});

it('renders only what exists for a partial summary and never prints NaN', () => {
  const { container } = render(
    <TrainingSummaryPanel summary={{ version: 1, last: { margin: 1.25 } }} />,
  );
  expect(screen.getByText('1.25')).toBeDefined();
  expect(container.textContent).not.toMatch(/NaN|undefined|null/);
  expect(screen.queryByText('Preference accuracy')).toBeNull();
});

it('treats an empty summary object as not recorded', () => {
  render(<TrainingSummaryPanel summary={{ version: 1 }} />);
  expect(screen.getByText('Not recorded')).toBeDefined();
});
```

In `AdapterRow.test.tsx`, extend the existing test file with:

```tsx
const base = {
  gguf_filename: 'sme-v7.gguf',
  loaded: true,
  published: false,
  adapter_id: 'adapter-7',
  agent_id: 'sme',
  job_id: 'source-job-7',
  version: 7,
  file_sha256: 'hash-7',
  size_bytes: 1048576,
  created_at: '2026-10-03T00:00:00Z',
};

function renderRow(adapter: typeof base & { training_summary?: unknown }) {
  return render(
    <table>
      <tbody>
        <AdapterRow
          onPublish={vi.fn()}
          onUnpublish={vi.fn()}
          adapter={adapter as never}
        />
      </tbody>
    </table>,
  );
}

it('shows the training summary above a collapsed technical-details section', () => {
  renderRow({
    ...base,
    training_summary: { version: 1, steps: 12, last: { step: 12, margin: 1.4 } },
  });
  fireEvent.click(screen.getByRole('button', { name: /show details for adapter v7/i }));
  expect(screen.getByText('1.40')).toBeDefined();
  const technical = screen.getByText('Technical details');
  expect(technical.closest('details')?.hasAttribute('open')).toBe(false);
  expect(screen.getByText('sme-v7.gguf')).toBeDefined();
  expect(screen.getByText('source-job-7')).toBeDefined();
});

it('shows "Not recorded" for adapters without a training summary', () => {
  renderRow(base);
  fireEvent.click(screen.getByRole('button', { name: /show details for adapter v7/i }));
  expect(screen.getByText('Not recorded')).toBeDefined();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps/admin && pnpm exec vitest run src/features/training-data/components/__tests__/TrainingSummaryPanel.test.tsx src/features/training-data/components/__tests__/AdapterRow.test.tsx`
Expected: FAIL (`TrainingSummaryPanel` does not exist; "Technical details" missing).

- [ ] **Step 3: Add the types**

In `types.ts`, above `TrainedAdapterItem`, add:

```ts
export interface TrainingSnapshot {
  step?: number | null;
  loss?: number | null;
  margin?: number | null;
  accuracy?: number | null;
  chosen?: number | null;
  rejected?: number | null;
}

export interface HeldoutSummary {
  pair_count?: number | null;
  loss?: number | null;
  margin?: number | null;
  accuracy?: number | null;
}

export interface TrainingSummary {
  version: number;
  steps?: number | null;
  epochs?: number | null;
  first?: TrainingSnapshot | null;
  last?: TrainingSnapshot | null;
  heldout?: HeldoutSummary | null;
}
```
and add to `TrainedAdapterItem` (after `published: boolean;`): `training_summary?: TrainingSummary | null;`.

- [ ] **Step 4: Add the entries builder**

In `utils/trainingData.utils.ts` add (merge the type import with existing imports):

```ts
import type { TrainingSummary } from '../types';

function isNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

const fixed = (value: number, digits = 2) => value.toFixed(digits);
const percent = (value: number) => `${Math.round(value * 100)}%`;

export function buildTrainingSummaryEntries(
  summary: TrainingSummary | null | undefined,
): [string, string][] {
  if (!summary) return [];
  const entries: [string, string][] = [];
  const first = summary.first;
  const last = summary.last;
  const heldout = summary.heldout;

  const lastMargin = last?.margin;
  const firstMargin = first?.margin;
  if (isNumber(lastMargin)) {
    const showStart = isNumber(firstMargin) && first?.step !== last?.step;
    entries.push([
      'Preference margin',
      showStart ? `${fixed(firstMargin)} → ${fixed(lastMargin)}` : fixed(lastMargin),
    ]);
  }
  if (isNumber(last?.accuracy)) entries.push(['Preference accuracy', percent(last.accuracy)]);
  if (isNumber(last?.loss)) entries.push(['Training loss', fixed(last.loss, 3)]);
  if (isNumber(summary.steps)) {
    entries.push([
      'Steps',
      isNumber(summary.epochs) ? `${summary.steps} (${summary.epochs} epochs)` : `${summary.steps}`,
    ]);
  }
  if (isNumber(heldout?.margin)) entries.push(['Held-out margin', fixed(heldout.margin)]);
  if (isNumber(heldout?.accuracy)) entries.push(['Held-out accuracy', percent(heldout.accuracy)]);
  if (isNumber(heldout?.pair_count)) entries.push(['Held-out pairs', `${heldout.pair_count}`]);
  return entries;
}
```
If TypeScript cannot narrow `last?.accuracy` through the `isNumber(...)` guard, copy each value into a `const` first (as done for the margin) and test that. The test file expects: `'0.00 → 1.40'`, `'100%'`, `'0.210'`, `'12 (3 epochs)'`, `'0.90'`, `'86%'`.

- [ ] **Step 5: Add the panel and use it in the row**

Create `components/TrainingSummaryPanel.tsx`:

```tsx
import type { TrainingSummary } from '../types';
import { buildTrainingSummaryEntries } from '../utils/trainingData.utils';
import { TrainingRecordMetadata } from './TrainingRecordMetadata';

export function TrainingSummaryPanel({ summary }: { summary?: TrainingSummary | null }) {
  const entries = buildTrainingSummaryEntries(summary);
  return (
    <section aria-label="Training summary" className="space-y-2">
      <p className="text-[13px] font-medium leading-5 text-text">Training summary</p>
      {entries.length === 0 ? (
        <p className="text-[13px] leading-5 text-text-muted">Not recorded</p>
      ) : (
        <>
          <TrainingRecordMetadata entries={entries} tabularValues />
          <p className="text-xs leading-5 text-text-muted">
            Measured on the training pairs. It shows the model learned the preference, not how
            it scores new documents.
          </p>
        </>
      )}
    </section>
  );
}
```

In `AdapterRow.tsx` import `TrainingSummaryPanel` and replace the single `<TrainingRecordMetadata entries={[...]} />` block with:

```tsx
        <TrainingSummaryPanel summary={adapter.training_summary} />
        <div className="mt-3">
          <TrainingRecordMetadata
            entries={[
              ['Filename', adapter.gguf_filename],
              ['Uploaded', uploaded.toLocaleString()],
            ]}
          />
        </div>
        <details className="mt-3 border-t border-border pt-3 text-sm text-text-muted">
          <summary className="cursor-pointer text-[13px] font-medium text-text">
            Technical details
          </summary>
          <div className="mt-3">
            <TrainingRecordMetadata
              entries={[
                ['Source run', adapter.job_id],
                ['File SHA-256', adapter.file_sha256],
                ['Adapter ID', adapter.adapter_id],
              ]}
            />
          </div>
        </details>
```
Leave the existing `adapter.loaded === false` load-hint block below it unchanged.

- [ ] **Step 6: Run the tests, typecheck, lint**

Run: `cd apps/admin && pnpm exec vitest run src/features/training-data`
Expected: all PASS (including the original `keeps adapter provenance accessible from the version row` test: jsdom keeps text inside a closed `<details>` in the DOM).

Run (repo root): `pnpm typecheck` and `pnpm lint`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add apps/admin/src/features/training-data
git commit -m "feat(admin): show the training summary on adapter versions"
```

---

### Final verification (after Task 5)

- [ ] Backend: `cd apps && uv run --project server pytest server/tests/training_data -q` then `uv run --project server ruff check server && uv run --project server ruff format --check server` (limit to the touched files if the repo has unrelated pre-existing lint failures).
- [ ] Notebook round trip: `git diff --stat docs/colab/dpo_training_template.ipynb` shows only a small diff; `python -c "import json;json.load(open('docs/colab/dpo_training_template.ipynb',encoding='utf-8'))"` succeeds.
- [ ] Frontend: `pnpm test` for the admin workspace passes, `pnpm typecheck` and `pnpm lint` clean.
- [ ] Manual end-to-end (next Colab run, after merge): train, confirm the printed "Training summary" table appears under the training cell, upload, open Admin > Training Data > v<n> details and see the summary; older versions show "Not recorded".

---

## Self-Review Notes

- **Spec coverage:** summary shape (Task 1 models, Task 4 builder), notebook `logging_steps=1`/`per_device_eval_batch_size=1`/summary cell content/manifest key/before-cleanup ordering (Task 4: cells 7, 8, 9; cell 8 runs before the cleanup cell), `expandable_segments` and `use_logits_to_keep` carry-over (Task 4, Global Constraints), lenient backend validation + never-reject (Tasks 1, 2, 3), column + migration (Task 3), API field (Task 3), UI summary + collapsed technical details + "Not recorded" (Task 5), tests for all three layers.
- **Deviation from the spec text:** the spec says "a new code cell directly after the training cell". Existing tests address cells by index, so the summary builder lives inside the existing evaluation cell (cell 8), which runs right after training and before the manifest and cleanup cells. Same behavior, no index shift.
- **Consistency:** `extract_training_summary`, `TrainingSummary`, `StagedAdapterArtifact.training_summary`, `TrainedAdapter.training_summary`, API field `training_summary`, notebook global `TRAINING_SUMMARY`, manifest key `training_summary`, and the TS names are used identically across tasks.
