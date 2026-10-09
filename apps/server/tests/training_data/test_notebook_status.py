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
    sending = cell.index('report("sending_model")')
    assert sending < cell.index("upload_response = requests")


def test_conversion_failures_are_reported_without_masking_the_error():
    cell = _find("def conversion_step(name):")
    assert 'globals().get("report")' in cell
    assert '"failed"' in cell


def test_gguf_upload_cell_reports_sending_file_first():
    cell = _find('with conversion_step("upload the GGUF to EquipED"):')
    assert cell.startswith('report("sending_file")')


def test_every_edited_cell_compiles():
    markers = [
        'UPLOAD_URL = "PASTE_UPLOAD_URL_HERE"',
        "trainer = DPOTrainer(",
        "upload_response = requests.post(",
        "def conversion_step(name):",
        'with conversion_step("upload the GGUF to EquipED"):',
    ]
    for marker in markers:
        compile(_find(marker), marker, "exec")
