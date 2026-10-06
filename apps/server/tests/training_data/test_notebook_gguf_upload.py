"""Runs the notebook's last cell (GGUF upload + download) without Colab."""

from __future__ import annotations

import contextlib
import json
import sys
import time
import types
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
NOTEBOOK_PATH = REPO_ROOT / "docs" / "colab" / "dpo_training_template.ipynb"
UPLOAD_URL = "https://x/upload?token=t"


def _cells() -> list[dict]:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))["cells"]


def _last_cell() -> str:
    return "".join(_cells()[17]["source"])


class _Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeRequests(types.ModuleType):
    def __init__(self, outcomes):
        super().__init__("requests")
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    def post(self, url, files=None, timeout=None):
        _, handle, _ = files["file"][0], files["file"][1], files["file"][2]
        self.calls.append(
            {
                "url": url,
                "name": files["file"][0],
                "head": handle.read(4),
                "timeout": timeout,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def run_cell(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sme-v8.gguf").write_bytes(b"GGUF" + b"\x00" * 16)
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    def run(outcomes, *, upload_response: Any = "default"):
        fake = _FakeRequests(outcomes)
        monkeypatch.setitem(sys.modules, "requests", fake)

        @contextlib.contextmanager
        def conversion_step(name):
            try:
                yield
            except Exception:
                print(f"step '{name}' failed")
                raise

        # `google.colab` is absent here, so the download step takes its
        # local branch and prints the file list.
        ctx: dict[str, Any] = {
            "conversion_step": conversion_step,
            "OUTPUT_GGUF": "sme-v8.gguf",
            "GGUF_OUTPUT_FILES": ["sme-v8.gguf"],
        }
        if upload_response == "default":
            upload_response = _Response(body={"gguf_upload_url": UPLOAD_URL})
        if upload_response is not None:
            ctx["upload_response"] = upload_response
        exec(_last_cell(), ctx)  # noqa: S102
        return fake

    return run


def test_notebook_still_has_18_cells():
    assert len(_cells()) == 18


def test_upload_succeeds_once(run_cell, capsys):
    fake = run_cell([_Response(200)])
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["url"] == UPLOAD_URL
    assert call["name"] == "sme-v8.gguf"
    assert call["head"] == b"GGUF"
    assert isinstance(call["timeout"], (int, float)) and call["timeout"] > 0
    assert "Uploaded sme-v8.gguf to EquipED" in capsys.readouterr().out


def test_retries_then_succeeds(run_cell, capsys):
    fake = run_cell(
        [ConnectionError("a"), ConnectionError("b"), _Response(200)],
    )
    assert len(fake.calls) == 3
    assert "Uploaded sme-v8.gguf" in capsys.readouterr().out


def test_three_failures_do_not_raise_and_download_still_runs(run_cell, capsys):
    fake = run_cell([ConnectionError("a")] * 3)
    out = capsys.readouterr().out
    assert len(fake.calls) == 3
    assert "Upload GGUF" in out
    assert "files are in the working directory" in out  # download step ran


def test_4xx_is_not_retried(run_cell, capsys):
    fake = run_cell([_Response(403)])
    out = capsys.readouterr().out
    assert len(fake.calls) == 1
    assert "refused" in out
    assert "Upload GGUF" in out
    assert "files are in the working directory" in out


def test_missing_upload_url_is_skipped(run_cell, capsys):
    fake = run_cell([], upload_response=_Response(body={"adapter_id": "x"}))
    assert fake.calls == []
    out = capsys.readouterr().out
    assert "Skipping the upload" in out
    assert "files are in the working directory" in out


def test_missing_upload_response_is_skipped(run_cell, capsys):
    fake = run_cell([], upload_response=None)
    assert fake.calls == []
    assert "Skipping the upload" in capsys.readouterr().out
