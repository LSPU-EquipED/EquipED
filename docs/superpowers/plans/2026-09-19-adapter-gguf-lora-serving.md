# Serving a Trained Adapter as a GGUF LoRA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a stored PEFT LoRA adapter into a GGUF LoRA file that the
existing llama.cpp server can load on top of the model file it already serves,
with a hand-off runbook and a smoke test that proves the server still returns
valid SME JSON with the adapter off and on.

**Architecture:** Three deliverables, all outside `apps/`. (1) A Colab notebook
converts the adapter with llama.cpp's own `convert_lora_to_gguf.py` and checks
the result is structurally a LoRA. (2) A short runbook tells the host owner how
to load it (`--lora`), toggle it, and roll back. (3) A stdlib-only client script
sends the same real SME prompts to the server with the adapter scaled 0 then 1
and validates every reply. Offline tests cover the script's logic (against a
fake local HTTP server) and the notebook's structure and helper functions.

**Tech Stack:** Python 3.12 stdlib only (`urllib`, `http.server` for the test
fake, `json`, `argparse`), pytest (run through the backend venv), Jupyter
notebook JSON (nbformat 4.5) built with stdlib `json`, llama.cpp's converter
(runs only in Colab), ruff.

**Spec:** `docs/superpowers/specs/2026-09-19-adapter-gguf-lora-serving-design.md`

## Global Constraints

- Nothing under `apps/` changes. No "active adapter" flag, database field,
  admin UI, adapter download endpoint, or automatic promotion. Activation stays
  a manual decision by the host owner.
- The served base model file is never modified or overwritten; rollback is
  removing the `--lora` flags and restarting.
- Served setup (verified 2026-09-19): llama.cpp `llama-server` build 10430
  (commit 4c1a0af40), plain `gemma-3-4b-it-q4_0.gguf`, alias `gemma-3-4b-it`,
  RTX 3060 Ti 8 GiB, started by `start-gemma.bat`.
- Conversion base override must be the regular `unsloth/gemma-3-4b-it`. The
  stored adapter's own `adapter_config.json` names
  `unsloth/gemma-3-4b-it-unsloth-bnb-4bit`, which the converter cannot use.
- Conversion output type is `f16`.
- The smoke test's validity rule: reply parses as JSON; has a string `summary`;
  has a non-empty `criterion_measurements` list; every entry has a non-empty
  string `criterion_id` and an integer `score` from 1 to 4 (booleans rejected).
- The smoke test is Python stdlib only. The API key is never printed.
  Exit codes: 0 all replies valid, 1 some reply invalid, 2 could not run.
- Tests run offline, with no GPU, no server, and no network beyond
  `127.0.0.1`. Run them with:
  `cd apps && uv run --project server pytest ../training/tests -q`
- Lint and format the new Python files with (from `apps/`):
  `uv run --project server ruff check --select E,F,I,UP --line-length 88 <files>`
  and `uv run --project server ruff format --line-length 88 <files>`
  (the files live outside the backend project, so its ruff config does not
  apply; these flags match it: rules E, F, I, UP, line length 88).
- The Colab notebook cannot be executed here (no GPU, limited disk). It is
  verified by offline structure/helper tests plus one manual Colab run (Task 6).
- Work happens on branch `docs/adapter-gguf-lora-serving-spec` (already
  checked out, off `main`). Before Task 1 the controller commits the spec and
  this plan as the branch's first commit. Commit after each task.

---

## File Structure

```
training/
  smoke_test_lora_serving.py            [new] client script (Tasks 1-3)
  sample_pairs.jsonl                    [new] 2 real-shaped synthetic pairs (Task 1)
  serving-lora-adapter.md               [new] host-owner runbook (Task 5)
  tests/
    test_smoke_test_lora_serving.py     [new] offline tests (Tasks 1-3)
    test_adapter_to_gguf_notebook.py    [new] notebook structure/helper tests (Task 4)
docs/colab/
  adapter_to_gguf_template.ipynb        [new] conversion notebook (Task 4)
```

No other files are created or modified.

---

### Task 1: Smoke test input loading and reply validation

**Files:**
- Create: `training/smoke_test_lora_serving.py`
- Create: `training/sample_pairs.jsonl`
- Create: `training/tests/test_smoke_test_lora_serving.py`

**Interfaces:**
- Produces (used by Tasks 2 and 3):
  - `MIN_SCORE: int = 1`, `MAX_SCORE: int = 4`
  - `ValidationResult` frozen dataclass: `valid: bool`, `reason: str | None = None`, `scores: dict[str, int]` (default empty)
  - `validate_sme_reply(text: str) -> ValidationResult`
  - `load_prompts(path: Path, limit: int) -> list[str]`

- [ ] **Step 1: Create the bundled sample input**

A file of two real SME prompts already exists from the earlier synthetic-data
smoke test. Copy it and verify its shape:

```bash
SRC="C:/Users/Admin/AppData/Local/Temp/claude/C--Users-Admin-Desktop-PROJECTS-EquipED/3ef2f285-249d-41d7-9966-9f5fd0a32b6c/scratchpad/pairs.jsonl"
cp "$SRC" training/sample_pairs.jsonl
python -c "import json; rows=[json.loads(l) for l in open('training/sample_pairs.jsonl', encoding='utf-8') if l.strip()]; assert len(rows)==2 and all({'prompt','chosen','rejected'}<=set(r) for r in rows); assert all('REQUIRED JSON OUTPUT STRUCTURE' in r['prompt'] for r in rows); print('ok', len(rows))"
```

Expected: `ok 2`. If the source file is missing, stop and report BLOCKED. Do not
invent replacement prompts.

- [ ] **Step 2: Write the failing tests**

Create `training/tests/test_smoke_test_lora_serving.py`:

````python
"""Offline tests for training/smoke_test_lora_serving.py (no server, no GPU)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TRAINING_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_DIR))

import smoke_test_lora_serving as smoke  # noqa: E402


def _reply(*scores: int, summary: str = "ok") -> str:
    return json.dumps(
        {
            "summary": summary,
            "criterion_measurements": [
                {
                    "criterion_id": f"OP-0{index}",
                    "criterion_title": f"Title {index}",
                    "score": score,
                    "evidence": "quote",
                    "reasoning": "because",
                }
                for index, score in enumerate(scores, start=1)
            ],
        }
    )


_OK_ENTRY = {"criterion_id": "A", "score": 2}


def _measurements(*entries: dict) -> str:
    return json.dumps({"summary": "s", "criterion_measurements": list(entries)})


def test_valid_reply_returns_scores_and_ignores_extra_fields():
    result = smoke.validate_sme_reply(_reply(3, 4))
    assert result.valid is True
    assert result.reason is None
    assert result.scores == {"OP-01": 3, "OP-02": 4}


def test_code_fenced_reply_is_accepted():
    fenced = "```json\n" + _reply(2) + "\n```"
    result = smoke.validate_sme_reply(fenced)
    assert result.valid is True
    assert result.scores == {"OP-01": 2}


@pytest.mark.parametrize(
    ("text", "reason_fragment"),
    [
        ("", "empty"),
        ("   \n", "empty"),
        ("not json at all", "not valid JSON"),
        ("[1, 2, 3]", "not an object"),
        (json.dumps({"criterion_measurements": [_OK_ENTRY]}), "summary"),
        (json.dumps({"summary": "s"}), "criterion_measurements"),
        (_measurements(), "criterion_measurements"),
        (_measurements("x"), "not an object"),
        (_measurements({"score": 2}), "criterion_id"),
        (_measurements({"criterion_id": " ", "score": 2}), "criterion_id"),
        (_measurements({"criterion_id": "A", "score": True}), "integer"),
        (_measurements({"criterion_id": "A", "score": 2.5}), "integer"),
        (_measurements({"criterion_id": "A", "score": "3"}), "integer"),
        (_measurements({"criterion_id": "A"}), "integer"),
        (_measurements({"criterion_id": "A", "score": 0}), "out of range"),
        (_measurements({"criterion_id": "A", "score": 5}), "out of range"),
    ],
)
def test_invalid_replies_are_rejected_with_a_reason(text, reason_fragment):
    result = smoke.validate_sme_reply(text)
    assert result.valid is False
    assert reason_fragment in (result.reason or "")
    assert result.scores == {}


def test_load_prompts_reads_prompt_field_and_respects_limit(tmp_path):
    path = tmp_path / "pairs.jsonl"
    rows = [{"prompt": f"p{i}", "chosen": "c", "rejected": "r"} for i in range(4)]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n\n", encoding="utf-8")
    assert smoke.load_prompts(path, 2) == ["p0", "p1"]
    assert smoke.load_prompts(path, 10) == ["p0", "p1", "p2", "p3"]


def test_load_prompts_rejects_missing_prompt_and_bad_limit(tmp_path):
    path = tmp_path / "pairs.jsonl"
    path.write_text(json.dumps({"chosen": "c"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="prompt"):
        smoke.load_prompts(path, 1)
    with pytest.raises(ValueError, match="limit"):
        smoke.load_prompts(path, 0)


def test_load_prompts_rejects_empty_file(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no prompts"):
        smoke.load_prompts(path, 1)


def test_bundled_sample_pairs_hold_real_sme_prompts():
    prompts = smoke.load_prompts(TRAINING_DIR / "sample_pairs.jsonl", 10)
    assert len(prompts) == 2
    for prompt in prompts:
        assert "REQUIRED JSON OUTPUT STRUCTURE" in prompt
        assert "criterion_measurements" in prompt
````

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest ../training/tests -q`
Expected: collection error `ModuleNotFoundError: No module named 'smoke_test_lora_serving'`.

- [ ] **Step 4: Write the implementation**

Create `training/smoke_test_lora_serving.py`:

````python
"""Smoke test a llama-server that has a GGUF LoRA adapter loaded.

Sends the same real SME prompts to the server with the adapter switched off
and then on, and checks that every reply is JSON in the shape the SME agent
expects. Full usage notes are added with the command-line entry point.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MIN_SCORE = 1
MAX_SCORE = 4


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str | None = None
    scores: dict[str, int] = field(default_factory=dict)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def validate_sme_reply(text: str) -> ValidationResult:
    """Check one model reply against the SME response shape.

    Only checks what the smoke test needs: JSON object, string summary, and a
    non-empty criterion_measurements list whose entries each carry a
    criterion_id and an integer score from MIN_SCORE to MAX_SCORE. Extra
    fields (evidence, reasoning, titles) are ignored.
    """
    if not isinstance(text, str) or not text.strip():
        return ValidationResult(False, "empty reply")
    try:
        payload = json.loads(_strip_code_fence(text))
    except json.JSONDecodeError as exc:
        return ValidationResult(False, f"not valid JSON: {exc.msg}")
    if not isinstance(payload, dict):
        return ValidationResult(False, "top-level JSON is not an object")
    if not isinstance(payload.get("summary"), str):
        return ValidationResult(False, "missing string 'summary'")
    measurements = payload.get("criterion_measurements")
    if not isinstance(measurements, list) or not measurements:
        return ValidationResult(False, "missing or empty 'criterion_measurements'")
    scores: dict[str, int] = {}
    for index, entry in enumerate(measurements):
        if not isinstance(entry, dict):
            return ValidationResult(False, f"measurement {index} is not an object")
        criterion_id = entry.get("criterion_id")
        if not isinstance(criterion_id, str) or not criterion_id.strip():
            return ValidationResult(False, f"measurement {index} has no criterion_id")
        score = entry.get("score")
        if isinstance(score, bool) or not isinstance(score, int):
            return ValidationResult(
                False, f"measurement {index} score is not an integer"
            )
        if not MIN_SCORE <= score <= MAX_SCORE:
            return ValidationResult(
                False, f"measurement {index} score {score} out of range"
            )
        scores[criterion_id] = score
    return ValidationResult(True, None, scores)


def load_prompts(path: Path, limit: int) -> list[str]:
    """Read up to `limit` prompts from a pairs.jsonl file."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    prompts: list[str] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            prompt = row.get("prompt") if isinstance(row, dict) else None
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError(f"line {line_number} has no 'prompt' string")
            prompts.append(prompt)
            if len(prompts) == limit:
                break
    if not prompts:
        raise ValueError(f"no prompts found in {path}")
    return prompts
````

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd apps && uv run --project server pytest ../training/tests -q`
Expected: all tests pass (about 22).

- [ ] **Step 6: Lint and format**

```bash
cd apps && uv run --project server ruff format --line-length 88 ../training/smoke_test_lora_serving.py ../training/tests/test_smoke_test_lora_serving.py && uv run --project server ruff check --select E,F,I,UP --line-length 88 ../training/smoke_test_lora_serving.py ../training/tests/test_smoke_test_lora_serving.py && uv run --project server pytest ../training/tests -q
```

Expected: `All checks passed!` and the tests still pass. Fix any finding, then
re-run.

- [ ] **Step 7: Commit**

```bash
git add training/smoke_test_lora_serving.py training/sample_pairs.jsonl training/tests/test_smoke_test_lora_serving.py
git commit -m "feat(training): add smoke-test reply validation and prompt loading"
```

---

### Task 2: Smoke test comparison, orchestration, and report

**Files:**
- Modify: `training/smoke_test_lora_serving.py`
- Modify: `training/tests/test_smoke_test_lora_serving.py`

**Interfaces:**
- Consumes (Task 1): `ValidationResult`, `validate_sme_reply`.
- Produces (used by Task 3):
  - `PromptResult(index: int, off: ValidationResult, on: ValidationResult)` frozen dataclass with property `score_changed -> bool | None` (`None` unless both replies are valid; otherwise whether any shared `criterion_id` has a different score)
  - `Report(results: tuple[PromptResult, ...])` frozen dataclass with properties `total`, `valid_off`, `valid_on`, `comparable`, `changed`, `all_valid`
  - `run_smoke_test(prompts: Sequence[str], complete: Callable[[str, float], str]) -> Report` (calls `complete(prompt, 0.0)` for every prompt, then `complete(prompt, 1.0)` for every prompt)
  - `format_report(report: Report) -> str`
  - `exit_code(report: Report) -> int` (0 if `all_valid` else 1)

- [ ] **Step 1: Write the failing tests**

Append to `training/tests/test_smoke_test_lora_serving.py`:

````python
def test_run_smoke_test_calls_off_then_on_and_compares_scores():
    calls: list[tuple[str, float]] = []

    def complete(prompt: str, scale: float) -> str:
        calls.append((prompt, scale))
        return _reply(2 if scale == 0.0 else 3)

    report = smoke.run_smoke_test(["p1", "p2"], complete)

    assert calls == [("p1", 0.0), ("p2", 0.0), ("p1", 1.0), ("p2", 1.0)]
    assert report.total == 2
    assert report.valid_off == 2
    assert report.valid_on == 2
    assert report.comparable == 2
    assert report.changed == 2
    assert report.all_valid is True
    assert smoke.exit_code(report) == 0


def test_run_smoke_test_reports_unchanged_scores():
    report = smoke.run_smoke_test(["p1"], lambda prompt, scale: _reply(2))
    assert report.comparable == 1
    assert report.changed == 0
    assert report.results[0].score_changed is False


def test_invalid_on_reply_fails_the_run_and_is_not_comparable():
    def complete(prompt: str, scale: float) -> str:
        return "garbage" if scale == 1.0 else _reply(2)

    report = smoke.run_smoke_test(["p1"], complete)

    assert report.valid_off == 1
    assert report.valid_on == 0
    assert report.comparable == 0
    assert report.results[0].score_changed is None
    assert report.all_valid is False
    assert smoke.exit_code(report) == 1


def test_scores_are_only_compared_on_shared_criteria():
    def complete(prompt: str, scale: float) -> str:
        criterion = "A" if scale == 0.0 else "B"
        return _measurements({"criterion_id": criterion, "score": 2})

    report = smoke.run_smoke_test(["p1"], complete)
    assert report.results[0].score_changed is False


def test_format_report_summarises_counts_and_lists_each_prompt():
    def complete(prompt: str, scale: float) -> str:
        if prompt == "bad" and scale == 1.0:
            return _measurements({"criterion_id": "OP-01", "score": 9})
        return _reply(2 if scale == 0.0 else 3)

    text = smoke.format_report(smoke.run_smoke_test(["good", "bad"], complete))

    assert "Adapter smoke test: 2 prompt(s)" in text
    assert "adapter OFF: 2/2 valid JSON" in text
    assert "adapter ON : 1/2 valid JSON" in text
    assert "score changed with adapter ON: 1/1 comparable prompt(s)" in text
    assert "RESULT: FAIL - 1 invalid reply(ies)" in text
    first = next(line for line in text.splitlines() if line.startswith("  #1"))
    assert "off=ok" in first and "on=ok" in first
    assert first.rstrip().endswith("scores changed")
    second = next(line for line in text.splitlines() if line.startswith("  #2"))
    assert "off=ok" in second and "on=INVALID" in second
    assert "on: measurement 0 score 9 out of range" in second


def test_format_report_passes_and_warns_when_no_score_changed():
    text = smoke.format_report(
        smoke.run_smoke_test(["p1"], lambda prompt, scale: _reply(2))
    )
    assert "RESULT: PASS - every reply was valid JSON" in text
    assert "NOTE: no score changed between OFF and ON" in text
    assert "--scale-mode global" in text


def test_format_report_has_no_note_when_scores_changed():
    text = smoke.format_report(
        smoke.run_smoke_test(["p1"], lambda prompt, scale: _reply(2 + int(scale)))
    )
    assert "NOTE:" not in text
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest ../training/tests -q`
Expected: the new tests fail with `AttributeError: module 'smoke_test_lora_serving' has no attribute 'run_smoke_test'`.

- [ ] **Step 3: Write the implementation**

In `training/smoke_test_lora_serving.py`, replace the import block with:

```python
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
```

Then append below `load_prompts`:

```python
@dataclass(frozen=True)
class PromptResult:
    index: int
    off: ValidationResult
    on: ValidationResult

    @property
    def score_changed(self) -> bool | None:
        if not (self.off.valid and self.on.valid):
            return None
        shared = self.off.scores.keys() & self.on.scores.keys()
        return any(self.off.scores[key] != self.on.scores[key] for key in shared)


@dataclass(frozen=True)
class Report:
    results: tuple[PromptResult, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def valid_off(self) -> int:
        return sum(1 for result in self.results if result.off.valid)

    @property
    def valid_on(self) -> int:
        return sum(1 for result in self.results if result.on.valid)

    @property
    def comparable(self) -> int:
        return sum(1 for result in self.results if result.score_changed is not None)

    @property
    def changed(self) -> int:
        return sum(1 for result in self.results if result.score_changed is True)

    @property
    def all_valid(self) -> bool:
        return self.valid_off == self.total and self.valid_on == self.total


def run_smoke_test(
    prompts: Sequence[str], complete: Callable[[str, float], str]
) -> Report:
    """Run every prompt with the adapter off (scale 0), then every prompt on.

    All "off" replies come first so a server that needs a global scale change
    between the two passes only has to switch once.
    """
    off_replies = [complete(prompt, 0.0) for prompt in prompts]
    on_replies = [complete(prompt, 1.0) for prompt in prompts]
    results = tuple(
        PromptResult(
            index=index,
            off=validate_sme_reply(off_text),
            on=validate_sme_reply(on_text),
        )
        for index, (off_text, on_text) in enumerate(
            zip(off_replies, on_replies, strict=True), start=1
        )
    )
    return Report(results)


def _status(result: ValidationResult) -> str:
    return "ok" if result.valid else "INVALID"


def _detail(result: PromptResult) -> str:
    if result.off.valid and result.on.valid:
        return "scores changed" if result.score_changed else "scores unchanged"
    parts = []
    if not result.off.valid:
        parts.append(f"off: {result.off.reason}")
    if not result.on.valid:
        parts.append(f"on: {result.on.reason}")
    return "; ".join(parts)


def format_report(report: Report) -> str:
    lines = [
        f"Adapter smoke test: {report.total} prompt(s)",
        f"  adapter OFF: {report.valid_off}/{report.total} valid JSON",
        f"  adapter ON : {report.valid_on}/{report.total} valid JSON",
        f"  score changed with adapter ON: {report.changed}/{report.comparable}"
        " comparable prompt(s)",
        "",
        "Per prompt:",
    ]
    for result in report.results:
        lines.append(
            f"  #{result.index}  off={_status(result.off):<7}  "
            f"on={_status(result.on):<7}  {_detail(result)}"
        )
    lines.append("")
    invalid = (report.total - report.valid_off) + (report.total - report.valid_on)
    if invalid:
        lines.append(f"RESULT: FAIL - {invalid} invalid reply(ies)")
    else:
        lines.append("RESULT: PASS - every reply was valid JSON")
    if report.comparable and report.changed == 0:
        lines.append(
            "NOTE: no score changed between OFF and ON. Either the adapter's "
            "effect is small or the per-request scale was ignored; check "
            "GET /lora-adapters and try --scale-mode global."
        )
    return "\n".join(lines)


def exit_code(report: Report) -> int:
    return 0 if report.all_valid else 1
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps && uv run --project server pytest ../training/tests -q`
Expected: all tests pass.

- [ ] **Step 5: Lint and format**

```bash
cd apps && uv run --project server ruff format --line-length 88 ../training/smoke_test_lora_serving.py ../training/tests/test_smoke_test_lora_serving.py && uv run --project server ruff check --select E,F,I,UP --line-length 88 ../training/smoke_test_lora_serving.py ../training/tests/test_smoke_test_lora_serving.py && uv run --project server pytest ../training/tests -q
```

Expected: `All checks passed!` and the tests still pass.

- [ ] **Step 6: Commit**

```bash
git add training/smoke_test_lora_serving.py training/tests/test_smoke_test_lora_serving.py
git commit -m "feat(training): add smoke-test off/on comparison and report"
```

---

### Task 3: Smoke test HTTP layer and command-line entry point

**Files:**
- Modify: `training/smoke_test_lora_serving.py`
- Modify: `training/tests/test_smoke_test_lora_serving.py`

**Interfaces:**
- Consumes (Tasks 1-2): `load_prompts`, `run_smoke_test`, `format_report`, `exit_code`.
- Produces:
  - `DEFAULT_MODEL: str = "gemma-3-4b-it"`
  - `server_root(base_url: str) -> str` (strips a trailing `/` and a trailing `/v1`)
  - `build_chat_payload(model: str, prompt: str, *, adapter_id: int, scale: float, scale_mode: str, max_tokens: int) -> dict` (`"lora": [{"id": adapter_id, "scale": scale}]` only when `scale_mode == "request"`; always `temperature` 0.0)
  - `extract_reply_text(response: object) -> str` (raises `ValueError` starting `unexpected chat completion` on a bad shape)
  - `list_adapters(base_url, api_key, timeout) -> list[dict]` (GET `{server_root}/lora-adapters`)
  - `choose_adapter_id(adapters: list[dict], requested: int | None) -> int`
  - `set_global_scale(base_url, api_key, adapter_id, scale, timeout) -> None` (POST `{server_root}/lora-adapters`)
  - `make_complete(...) -> Callable[[str, float], str]`
  - `parse_args(argv)` and `main(argv: Sequence[str] | None = None) -> int`

- [ ] **Step 1: Write the failing tests**

Add these imports at the top of `training/tests/test_smoke_test_lora_serving.py`
(merge into the existing import block so it stays sorted):

```python
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
```

Append to the file:

````python
def test_server_root_strips_v1_and_trailing_slash():
    assert smoke.server_root("http://h:8080/v1") == "http://h:8080"
    assert smoke.server_root("http://h:8080/v1/") == "http://h:8080"
    assert smoke.server_root("http://h:8080") == "http://h:8080"


def test_build_chat_payload_puts_lora_only_in_request_mode():
    payload = smoke.build_chat_payload(
        "m", "hi", adapter_id=1, scale=0.5, scale_mode="request", max_tokens=64
    )
    assert payload == {
        "model": "m",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.0,
        "max_tokens": 64,
        "lora": [{"id": 1, "scale": 0.5}],
    }
    global_payload = smoke.build_chat_payload(
        "m", "hi", adapter_id=1, scale=0.5, scale_mode="global", max_tokens=64
    )
    assert "lora" not in global_payload


def test_extract_reply_text_reads_first_choice_and_rejects_bad_shapes():
    good = {"choices": [{"message": {"content": "hello"}}]}
    assert smoke.extract_reply_text(good) == "hello"
    for bad in ({}, {"choices": []}, {"choices": [{"message": {"content": None}}]}):
        with pytest.raises(ValueError, match="unexpected chat completion"):
            smoke.extract_reply_text(bad)


def test_choose_adapter_id_defaults_to_first_and_validates_request():
    adapters = [{"id": 3, "path": "a.gguf", "scale": 0.0}]
    assert smoke.choose_adapter_id(adapters, None) == 3
    assert smoke.choose_adapter_id(adapters, 3) == 3
    with pytest.raises(ValueError, match="not loaded"):
        smoke.choose_adapter_id(adapters, 5)
    with pytest.raises(ValueError, match="no LoRA adapter"):
        smoke.choose_adapter_id([], None)


@pytest.fixture
def fake_server(monkeypatch):
    """A tiny stand-in for llama-server: /lora-adapters and chat completions."""
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL_NAME", raising=False)
    state = {
        "adapters": [{"id": 0, "path": "adapter.gguf", "scale": 0.0}],
        "requests": [],
        "global_scale": 0.0,
        "bad_on": False,
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
                scale = state["global_scale"]
                if "lora" in payload:
                    scale = payload["lora"][0]["scale"]
                if scale > 0 and state["bad_on"]:
                    content = "definitely not json"
                else:
                    content = _reply(3 if scale > 0 else 2)
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


SAMPLE_PAIRS = str(TRAINING_DIR / "sample_pairs.jsonl")


def _run_cli(argv, capsys):
    code = smoke.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_cli_request_mode_passes_and_sends_lora_field(fake_server, capsys):
    code, out, err = _run_cli(
        [SAMPLE_PAIRS, "--base-url", fake_server["base_url"], "--limit", "2"], capsys
    )

    assert code == 0, err
    assert "adapter OFF: 2/2 valid JSON" in out
    assert "score changed with adapter ON: 2/2 comparable prompt(s)" in out
    assert "RESULT: PASS" in out
    chats = [r for r in fake_server["requests"] if r["path"] == "/v1/chat/completions"]
    assert [c["body"]["lora"] for c in chats] == (
        [[{"id": 0, "scale": 0.0}]] * 2 + [[{"id": 0, "scale": 1.0}]] * 2
    )
    assert all(c["body"]["model"] == "gemma-3-4b-it" for c in chats)
    assert all(c["body"]["temperature"] == 0.0 for c in chats)


def test_cli_sends_bearer_key_and_never_prints_it(fake_server, capsys, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret-key-123")
    code, out, err = _run_cli(
        [SAMPLE_PAIRS, "--base-url", fake_server["base_url"], "--limit", "1"], capsys
    )

    assert code == 0, err
    assert all(r["auth"] == "Bearer secret-key-123" for r in fake_server["requests"])
    assert "secret-key-123" not in out + err


def test_cli_global_mode_sets_scale_through_the_adapter_endpoint(fake_server, capsys):
    code, out, err = _run_cli(
        [
            SAMPLE_PAIRS,
            "--base-url",
            fake_server["base_url"],
            "--limit",
            "2",
            "--scale-mode",
            "global",
        ],
        capsys,
    )

    assert code == 0, err
    posts = [
        r
        for r in fake_server["requests"]
        if r["method"] == "POST" and r["path"] == "/lora-adapters"
    ]
    assert [p["body"] for p in posts] == [
        [{"id": 0, "scale": 0.0}],
        [{"id": 0, "scale": 1.0}],
    ]
    chats = [r for r in fake_server["requests"] if r["path"] == "/v1/chat/completions"]
    assert len(chats) == 4
    assert all("lora" not in c["body"] for c in chats)
    assert "score changed with adapter ON: 2/2 comparable prompt(s)" in out


def test_cli_exits_1_when_an_adapter_on_reply_is_invalid(fake_server, capsys):
    fake_server["bad_on"] = True
    code, out, _ = _run_cli(
        [SAMPLE_PAIRS, "--base-url", fake_server["base_url"], "--limit", "1"], capsys
    )
    assert code == 1
    assert "RESULT: FAIL" in out


def test_cli_exits_2_when_no_adapter_is_loaded(fake_server, capsys):
    fake_server["adapters"] = []
    code, _, err = _run_cli(
        [SAMPLE_PAIRS, "--base-url", fake_server["base_url"], "--limit", "1"], capsys
    )
    assert code == 2
    assert "no LoRA adapter" in err


def test_cli_exits_2_when_requested_adapter_id_is_not_loaded(fake_server, capsys):
    code, _, err = _run_cli(
        [
            SAMPLE_PAIRS,
            "--base-url",
            fake_server["base_url"],
            "--adapter-id",
            "5",
            "--limit",
            "1",
        ],
        capsys,
    )
    assert code == 2
    assert "not loaded" in err


def test_cli_exits_2_when_the_server_is_unreachable(fake_server, capsys):
    code, _, err = _run_cli(
        [
            SAMPLE_PAIRS,
            "--base-url",
            "http://127.0.0.1:9/v1",
            "--limit",
            "1",
            "--timeout",
            "2",
        ],
        capsys,
    )
    assert code == 2
    assert err.startswith("error:")


def test_cli_exits_2_when_no_base_url_is_given(fake_server, capsys):
    code, _, err = _run_cli([SAMPLE_PAIRS, "--limit", "1"], capsys)
    assert code == 2
    assert "base URL" in err
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest ../training/tests -q`
Expected: the new tests fail with `AttributeError: ... has no attribute 'server_root'` (or `main`).

- [ ] **Step 3: Write the implementation**

In `training/smoke_test_lora_serving.py`, replace the import block with:

```python
from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
```

Replace the module docstring (the whole triple-quoted block at the top) with:

````python
"""Smoke test a llama-server that has a GGUF LoRA adapter loaded.

Sends the same real SME prompts to the server twice -- once with the adapter
switched off (scale 0) and once on (scale 1) -- and checks that every reply is
JSON in the shape the SME agent expects. It proves the adapter loads and the
server still behaves; it does NOT judge whether the adapter is any good.

Usage:
    python training/smoke_test_lora_serving.py training/sample_pairs.jsonl \
        --base-url http://127.0.0.1:8080/v1 --limit 2

The base URL falls back to LLM_API_BASE, the API key to LLM_API_KEY (prefer the
environment: command-line arguments end up in shell history), and the model to
LLM_MODEL_NAME. The key is never printed.

Scale modes: "request" (default) sends the scale in each chat request; "global"
sets it once through POST /lora-adapters, for servers that ignore the
per-request field.

Exit code: 0 all replies valid, 1 some reply invalid, 2 could not run (server
unreachable, no adapter loaded, bad input).

Prompts are sent as a single user message: pairs.jsonl stores each prompt
already flattened (system + user text), and Gemma's chat template folds system
text into the user turn anyway.
"""
````

Add below the score constants (after `MAX_SCORE = 4`):

```python
DEFAULT_MODEL = "gemma-3-4b-it"
```

Append below `exit_code`:

```python
def server_root(base_url: str) -> str:
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    return root


def _headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _get_json(url: str, api_key: str | None, timeout: float) -> object:
    request = urllib.request.Request(url, headers=_headers(api_key), method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(
    url: str, payload: object, api_key: str | None, timeout: float
) -> object:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(api_key),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_chat_payload(
    model: str,
    prompt: str,
    *,
    adapter_id: int,
    scale: float,
    scale_mode: str,
    max_tokens: int,
) -> dict:
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    if scale_mode == "request":
        payload["lora"] = [{"id": adapter_id, "scale": scale}]
    return payload


def extract_reply_text(response: object) -> str:
    try:
        content = response["choices"][0]["message"]["content"]  # type: ignore[index]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected chat completion response shape") from exc
    if not isinstance(content, str):
        raise ValueError("unexpected chat completion response: no text content")
    return content


def list_adapters(base_url: str, api_key: str | None, timeout: float) -> list[dict]:
    data = _get_json(f"{server_root(base_url)}/lora-adapters", api_key, timeout)
    if not isinstance(data, list):
        raise ValueError("unexpected response from GET /lora-adapters")
    return data


def choose_adapter_id(adapters: list[dict], requested: int | None) -> int:
    ids = [adapter.get("id") for adapter in adapters if isinstance(adapter, dict)]
    ids = [adapter_id for adapter_id in ids if isinstance(adapter_id, int)]
    if not ids:
        raise ValueError(
            "no LoRA adapter is loaded on the server; start llama-server with "
            "--lora <file.gguf> --lora-init-without-apply"
        )
    if requested is None:
        return ids[0]
    if requested not in ids:
        raise ValueError(f"adapter id {requested} is not loaded (loaded ids: {ids})")
    return requested


def set_global_scale(
    base_url: str,
    api_key: str | None,
    adapter_id: int,
    scale: float,
    timeout: float,
) -> None:
    _post_json(
        f"{server_root(base_url)}/lora-adapters",
        [{"id": adapter_id, "scale": scale}],
        api_key,
        timeout,
    )


def make_complete(
    *,
    base_url: str,
    api_key: str | None,
    model: str,
    adapter_id: int,
    scale_mode: str,
    max_tokens: int,
    timeout: float,
) -> Callable[[str, float], str]:
    current: dict[str, float | None] = {"scale": None}

    def complete(prompt: str, scale: float) -> str:
        if scale_mode == "global" and current["scale"] != scale:
            set_global_scale(base_url, api_key, adapter_id, scale, timeout)
            current["scale"] = scale
        payload = build_chat_payload(
            model,
            prompt,
            adapter_id=adapter_id,
            scale=scale,
            scale_mode=scale_mode,
            max_tokens=max_tokens,
        )
        response = _post_json(
            f"{base_url.rstrip('/')}/chat/completions", payload, api_key, timeout
        )
        return extract_reply_text(response)

    return complete


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test a llama-server with a GGUF LoRA adapter loaded."
    )
    parser.add_argument("pairs", type=Path, help="pairs.jsonl to take prompts from")
    parser.add_argument("--limit", type=int, default=2, help="prompts to send")
    parser.add_argument("--base-url", default=None, help="default: $LLM_API_BASE")
    parser.add_argument("--api-key", default=None, help="default: $LLM_API_KEY")
    parser.add_argument("--model", default=None, help="default: $LLM_MODEL_NAME")
    parser.add_argument("--adapter-id", type=int, default=None)
    parser.add_argument(
        "--scale-mode", choices=("request", "global"), default="request"
    )
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout", type=float, default=300.0)
    return parser.parse_args(argv)


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
    model = args.model or os.environ.get("LLM_MODEL_NAME") or DEFAULT_MODEL
    try:
        prompts = load_prompts(args.pairs, args.limit)
        adapters = list_adapters(base_url, api_key, args.timeout)
        adapter_id = choose_adapter_id(adapters, args.adapter_id)
        complete = make_complete(
            base_url=base_url,
            api_key=api_key,
            model=model,
            adapter_id=adapter_id,
            scale_mode=args.scale_mode,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
        )
        report = run_smoke_test(prompts, complete)
    except (OSError, ValueError, http.client.HTTPException) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(format_report(report))
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps && uv run --project server pytest ../training/tests -q`
Expected: all tests pass. The fake-server tests use `127.0.0.1` only. If one
hangs, the fake server thread failed to start; check the fixture, do not
raise timeouts.

- [ ] **Step 5: Lint and format**

```bash
cd apps && uv run --project server ruff format --line-length 88 ../training/smoke_test_lora_serving.py ../training/tests/test_smoke_test_lora_serving.py && uv run --project server ruff check --select E,F,I,UP --line-length 88 ../training/smoke_test_lora_serving.py ../training/tests/test_smoke_test_lora_serving.py && uv run --project server pytest ../training/tests -q
```

Expected: `All checks passed!` and the tests still pass.

- [ ] **Step 6: Verify the script runs as a command**

```bash
python training/smoke_test_lora_serving.py --help
```

Expected: usage text listing `pairs`, `--limit`, `--base-url`, `--scale-mode`, and the other options; exit code 0.

- [ ] **Step 7: Commit**

```bash
git add training/smoke_test_lora_serving.py training/tests/test_smoke_test_lora_serving.py
git commit -m "feat(training): add smoke-test HTTP client and command-line entry point"
```

---

### Task 4: Colab conversion notebook

**Files:**
- Create: `docs/colab/adapter_to_gguf_template.ipynb`
- Create: `training/tests/test_adapter_to_gguf_notebook.py`

**Interfaces:**
- Produces a notebook of 8 cells (ids `cell-0` … `cell-7`): 0 markdown intro;
  1 config (`ADAPTER_ZIP`, `BASE_MODEL_ID`, `OUTPUT_GGUF`, `LLAMA_CPP_REPO`,
  `LLAMA_CPP_REF`); 2 helpers (`run`, `safe_extract`, `sha256_of`,
  `check_lora_fields`, `verify_gguf_lora`); 3 unpack and inspect the adapter;
  4 clone llama.cpp and install converter requirements; 5 run the conversion;
  6 verify the GGUF; 7 checksum and download.
- Helper contracts (tested offline by exec-ing cell 2):
  - `safe_extract(zip_path, target_dir) -> None`, raises `ValueError` for any
    member path that escapes `target_dir`
  - `sha256_of(path) -> str`
  - `check_lora_fields(general_type, adapter_type, alpha, tensors, expected_rank, expected_alpha) -> dict`
    where `tensors` is a list of `(name, shape_tuple)`; raises `ValueError`
    listing every problem; returns `{"tensor_pairs": int, "rank": int, "alpha": float}`
  - `verify_gguf_lora(path, expected_rank, expected_alpha) -> dict` (reads the
    GGUF with llama.cpp's `gguf` package, then calls `check_lora_fields`)

- [ ] **Step 1: Write the failing tests**

Create `training/tests/test_adapter_to_gguf_notebook.py`:

````python
"""Offline checks for docs/colab/adapter_to_gguf_template.ipynb.

The notebook needs Colab (and the llama.cpp converter) to run for real; these
tests cover what can be checked offline: structure, that every code cell
parses, that the converter call has the agreed arguments, and the pure helper
functions in the helpers cell.
"""

from __future__ import annotations

import ast
import json
import zipfile
from pathlib import Path

import pytest

NOTEBOOK = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "colab"
    / "adapter_to_gguf_template.ipynb"
)


def _load() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def _code_sources() -> list[str]:
    return [
        "".join(cell["source"])
        for cell in _load()["cells"]
        if cell["cell_type"] == "code"
    ]


def _helpers() -> dict:
    source = next(src for src in _code_sources() if "def safe_extract" in src)
    namespace: dict = {}
    exec(compile(source, "<helpers-cell>", "exec"), namespace)
    return namespace


def test_notebook_is_nbformat4_with_unique_cell_ids_and_intro():
    notebook = _load()
    assert notebook["nbformat"] == 4
    ids = [cell["id"] for cell in notebook["cells"]]
    assert len(ids) == len(set(ids)) == 8
    assert notebook["cells"][0]["cell_type"] == "markdown"


def test_every_code_cell_parses_as_python():
    for source in _code_sources():
        ast.parse(source)


def test_converter_call_overrides_base_and_writes_f16():
    joined = "\n".join(_code_sources())
    assert 'BASE_MODEL_ID = "unsloth/gemma-3-4b-it"' in joined
    assert "convert_lora_to_gguf.py" in joined
    assert '"--base-model-id", BASE_MODEL_ID' in joined
    assert '"--outtype", "f16"' in joined
    assert '"--outfile", OUTPUT_GGUF' in joined


def test_safe_extract_unpacks_a_normal_zip(tmp_path):
    archive = tmp_path / "ok.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("adapter_config.json", "{}")
        handle.writestr("sub/file.txt", "hi")
    _helpers()["safe_extract"](archive, tmp_path / "out")
    assert (tmp_path / "out" / "adapter_config.json").read_text() == "{}"
    assert (tmp_path / "out" / "sub" / "file.txt").read_text() == "hi"


@pytest.mark.parametrize("bad_name", ["../evil.txt", "sub/../../evil.txt", "/abs.txt"])
def test_safe_extract_rejects_paths_that_escape(tmp_path, bad_name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(bad_name, "x")
    with pytest.raises(ValueError, match="unsafe path"):
        _helpers()["safe_extract"](archive, tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_sha256_of_matches_hashlib(tmp_path):
    import hashlib

    path = tmp_path / "blob.bin"
    path.write_bytes(b"abc" * 1000)
    assert _helpers()["sha256_of"](path) == hashlib.sha256(b"abc" * 1000).hexdigest()


GOOD_TENSORS = [
    ("blk.0.attn_q.weight.lora_a", (2560, 16)),
    ("blk.0.attn_q.weight.lora_b", (16, 2048)),
    ("blk.0.ffn_up.weight.lora_a", (2560, 16)),
    ("blk.0.ffn_up.weight.lora_b", (16, 10240)),
]


def test_check_lora_fields_accepts_a_valid_adapter():
    summary = _helpers()["check_lora_fields"](
        "adapter", "lora", 32.0, GOOD_TENSORS, 16, 32.0
    )
    assert summary == {"tensor_pairs": 2, "rank": 16, "alpha": 32.0}


def test_check_lora_fields_reports_every_problem():
    check = _helpers()["check_lora_fields"]
    with pytest.raises(ValueError) as caught:
        check("model", "other", 8.0, [("blk.0.x.weight.lora_a", (2560, 8))], 16, 32.0)
    message = str(caught.value)
    assert "general.type" in message
    assert "adapter.type" in message
    assert "alpha" in message
    assert "lora_b" in message
    assert "rank" in message


def test_check_lora_fields_rejects_an_adapter_with_no_tensors():
    with pytest.raises(ValueError, match="no lora_a"):
        _helpers()["check_lora_fields"]("adapter", "lora", 32.0, [], 16, 32.0)
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest ../training/tests/test_adapter_to_gguf_notebook.py -q`
Expected: failures with `FileNotFoundError` for `adapter_to_gguf_template.ipynb`.

- [ ] **Step 3: Generate the notebook**

Run this once from the repo root (it writes the notebook; the cell sources are
raw strings so `\n` stays a backslash-n inside the notebook's code):

```bash
python - <<'PYEOF'
import json

def lines(text):
    parts = text.strip("\n").split("\n")
    return [part + "\n" for part in parts[:-1]] + [parts[-1]]

def markdown(cell_id, text):
    return {"cell_type": "markdown", "id": cell_id, "metadata": {}, "source": lines(text)}

def code(cell_id, text):
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cell_id,
        "metadata": {},
        "outputs": [],
        "source": lines(text),
    }

INTRO = r'''
# EquipED adapter -> GGUF LoRA conversion

Converts a trained PEFT LoRA adapter (from the DPO Colab training run) into a
GGUF LoRA file that llama.cpp's `llama-server` can load with `--lora`, on top
of the model file it already serves. The served model file is never modified.

Before running:

1. Any runtime works; no GPU is needed.
2. Upload the adapter zip to the **Files** panel (left sidebar) as
   `adapter.zip`. It is the zip stored on the backend under
   `adapters/<agent>/<adapter id>/adapter.zip`. There is no download button yet.
3. Runtime -> Run all.

Output: `adapter-f16.gguf` plus `adapter-f16.gguf.sha256`, downloaded at the
end. Give both to the host owner with `training/serving-lora-adapter.md`.

This only proves the file converts and is structurally a LoRA. Whether the
adapter actually helps is a separate evaluation.
'''

CONFIG = r'''
ADAPTER_ZIP = "adapter.zip"
# The adapter's own adapter_config.json names a 4-bit variant as its base
# (unsloth/gemma-3-4b-it-unsloth-bnb-4bit), which the converter cannot use.
# Point it at the regular instruct model, which is what the served Q4_0 file
# was quantized from.
BASE_MODEL_ID = "unsloth/gemma-3-4b-it"
OUTPUT_GGUF = "adapter-f16.gguf"
LLAMA_CPP_REPO = "https://github.com/ggml-org/llama.cpp"
# None = llama.cpp's default branch. To match the host's llama-server build,
# set a FULL commit hash from that build's source tree.
LLAMA_CPP_REF = None
'''

HELPERS = r'''
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


def run(command):
    command = [str(part) for part in command]
    print("$", " ".join(command))
    subprocess.run(command, check=True)


def safe_extract(zip_path, target_dir):
    target = Path(target_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if destination != target and target not in destination.parents:
                raise ValueError(f"unsafe path in zip: {member.filename!r}")
        archive.extractall(target)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_lora_fields(
    general_type, adapter_type, alpha, tensors, expected_rank, expected_alpha
):
    problems = []
    if general_type != "adapter":
        problems.append(f"general.type is {general_type!r}, expected 'adapter'")
    if adapter_type != "lora":
        problems.append(f"adapter.type is {adapter_type!r}, expected 'lora'")
    if alpha is None or abs(float(alpha) - expected_alpha) > 1e-6:
        problems.append(f"alpha is {alpha!r}, expected {expected_alpha}")
    lora_a = [item for item in tensors if item[0].endswith(".lora_a")]
    lora_b = [item for item in tensors if item[0].endswith(".lora_b")]
    if not lora_a:
        problems.append("no lora_a tensors found")
    if len(lora_a) != len(lora_b):
        problems.append(f"{len(lora_a)} lora_a tensors but {len(lora_b)} lora_b tensors")
    for name, shape in lora_a + lora_b:
        if min(shape) != expected_rank:
            problems.append(
                f"{name}: smallest dimension {min(shape)} is not rank {expected_rank}"
            )
            break
    if problems:
        raise ValueError("; ".join(problems))
    return {"tensor_pairs": len(lora_a), "rank": expected_rank, "alpha": float(alpha)}


def verify_gguf_lora(path, expected_rank, expected_alpha):
    sys.path.insert(0, "llama.cpp/gguf-py")
    from gguf import GGUFReader

    reader = GGUFReader(path)

    def field_value(name):
        field = reader.fields.get(name)
        return None if field is None else field.contents()

    tensors = [
        (tensor.name, tuple(int(dim) for dim in tensor.shape))
        for tensor in reader.tensors
    ]
    return check_lora_fields(
        field_value("general.type"),
        field_value("adapter.type"),
        field_value("adapter.lora.alpha"),
        tensors,
        expected_rank,
        expected_alpha,
    )
'''

UNPACK = r'''
ADAPTER_DIR = Path("adapter_src")

if not os.path.exists(ADAPTER_ZIP):
    raise FileNotFoundError(
        f"Upload the adapter zip to the Files panel as {ADAPTER_ZIP!r} first."
    )
safe_extract(ADAPTER_ZIP, ADAPTER_DIR)

adapter_config = json.loads(
    (ADAPTER_DIR / "adapter_config.json").read_text(encoding="utf-8")
)
if adapter_config.get("peft_type") != "LORA":
    raise ValueError(f"not a LoRA adapter: peft_type={adapter_config.get('peft_type')!r}")
if not (ADAPTER_DIR / "adapter_model.safetensors").exists():
    raise FileNotFoundError("adapter_model.safetensors is missing from the zip")

LORA_RANK = int(adapter_config["r"])
LORA_ALPHA = float(adapter_config["lora_alpha"])
print("adapter base (as trained):", adapter_config.get("base_model_name_or_path"))
print("converter will use base config from:", BASE_MODEL_ID)
print("rank:", LORA_RANK, "alpha:", LORA_ALPHA)
'''

INSTALL = r'''
if not os.path.isdir("llama.cpp"):
    run(["git", "clone", "--depth", "1", LLAMA_CPP_REPO, "llama.cpp"])
    if LLAMA_CPP_REF:
        fetched = subprocess.run(
            ["git", "-C", "llama.cpp", "fetch", "--depth", "1", "origin", LLAMA_CPP_REF]
        )
        if fetched.returncode == 0:
            run(["git", "-C", "llama.cpp", "checkout", "FETCH_HEAD"])
        else:
            print(f"WARNING: could not fetch {LLAMA_CPP_REF}; using the default branch.")

requirements_dir = Path("llama.cpp/requirements")
candidates = [
    requirements_dir / "requirements-convert_lora_to_gguf.txt",
    requirements_dir / "requirements-convert_hf_to_gguf.txt",
]
requirements_file = next((path for path in candidates if path.exists()), None)
if requirements_file is None:
    raise FileNotFoundError(
        "no converter requirements file under llama.cpp/requirements; "
        "the llama.cpp layout may have changed, check that directory"
    )
run([sys.executable, "-m", "pip", "install", "-q", "-r", requirements_file])
'''

CONVERT = r'''
# Print the converter's own flags first, so the log records what this
# llama.cpp version actually accepts.
run([sys.executable, "llama.cpp/convert_lora_to_gguf.py", "--help"])

run(
    [
        sys.executable,
        "llama.cpp/convert_lora_to_gguf.py",
        "--base-model-id", BASE_MODEL_ID,
        "--outfile", OUTPUT_GGUF,
        "--outtype", "f16",
        ADAPTER_DIR,
    ]
)
if not os.path.exists(OUTPUT_GGUF):
    raise FileNotFoundError(f"converter finished but {OUTPUT_GGUF!r} was not created")
'''

VERIFY = r'''
summary = verify_gguf_lora(OUTPUT_GGUF, LORA_RANK, LORA_ALPHA)
print("GGUF LoRA verified:", summary)
'''

FINISH = r'''
size_mb = os.path.getsize(OUTPUT_GGUF) / (1024 * 1024)
digest = sha256_of(OUTPUT_GGUF)
Path(OUTPUT_GGUF + ".sha256").write_text(f"{digest}  {OUTPUT_GGUF}\n", encoding="utf-8")
print(f"{OUTPUT_GGUF}: {size_mb:.1f} MB")
print("sha256:", digest)

try:
    from google.colab import files
except ImportError:
    print("Not running in Colab: the files are in the working directory.")
else:
    files.download(OUTPUT_GGUF)
    files.download(OUTPUT_GGUF + ".sha256")
'''

notebook = {
    "cells": [
        markdown("cell-0", INTRO),
        code("cell-1", CONFIG),
        code("cell-2", HELPERS),
        code("cell-3", UNPACK),
        code("cell-4", INSTALL),
        code("cell-5", CONVERT),
        code("cell-6", VERIFY),
        code("cell-7", FINISH),
    ],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open("docs/colab/adapter_to_gguf_template.ipynb", "w", encoding="utf-8") as handle:
    json.dump(notebook, handle, indent=1, ensure_ascii=False)
    handle.write("\n")
print("wrote notebook with", len(notebook["cells"]), "cells")
PYEOF
```

Expected: `wrote notebook with 8 cells`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps && uv run --project server pytest ../training/tests -q`
Expected: all tests pass (the earlier smoke-test suite plus the 11 notebook tests).

- [ ] **Step 5: Lint and format the test file**

```bash
cd apps && uv run --project server ruff format --line-length 88 ../training/tests/test_adapter_to_gguf_notebook.py && uv run --project server ruff check --select E,F,I,UP --line-length 88 ../training/tests/test_adapter_to_gguf_notebook.py && uv run --project server pytest ../training/tests -q
```

Expected: `All checks passed!` and the tests still pass. (The notebook's own cell
code is not linted; it is checked by the `ast.parse` test.)

- [ ] **Step 6: Commit**

```bash
git add docs/colab/adapter_to_gguf_template.ipynb training/tests/test_adapter_to_gguf_notebook.py
git commit -m "feat(colab): add adapter-to-GGUF-LoRA conversion notebook"
```

---

### Task 5: Host-owner runbook

**Files:**
- Create: `training/serving-lora-adapter.md`

**Interfaces:**
- Consumes: the GGUF file and `.sha256` from Task 4, and the smoke test
  command line from Task 3 (`python training/smoke_test_lora_serving.py
  training/sample_pairs.jsonl --base-url ... --limit 2`, options `--scale-mode`,
  `--adapter-id`).
- Produces: a runbook the host owner follows; no code depends on it.

- [ ] **Step 1: Write the runbook**

Create `training/serving-lora-adapter.md` with exactly this content:

````markdown
# Serving a trained adapter on llama-server (GGUF LoRA)

For the person who runs the model server (Windows, llama.cpp CUDA build,
started by `start-gemma.bat`). This adds a trained adapter **on top of** the
model file you already serve. It never changes that file, and you can remove it
again at any time.

You will receive two files from the training side:

- `adapter-f16.gguf` (about 100-150 MB), the adapter converted for llama.cpp
- `adapter-f16.gguf.sha256`, its checksum

## 1. Put the file somewhere with space

Copy `adapter-f16.gguf` next to your models on the F: drive, for example
`F:\Dev\Models\gemma\adapters\sme-adapter-f16.gguf`. Do not put it on the full
C: drive, and never over the base model file.

Check the file arrived intact (compare with the value in the `.sha256` file):

```
certutil -hashfile F:\Dev\Models\gemma\adapters\sme-adapter-f16.gguf SHA256
```

## 2. Check your llama-server supports the flags

```
F:\Dev\Servers\llama.cpp\build-cuda\bin\Release\llama-server.exe --help | findstr /i lora
```

You should see `--lora` and `--lora-init-without-apply`. If
`--lora-init-without-apply` is missing, use
`--lora-scaled <file> 0.0` instead of the two flags in step 3.

## 3. Add two arguments to the launch command

In `start-gemma.bat`, add these to the `llama-server.exe` arguments (keep every
existing flag as is):

```
--lora F:\Dev\Models\gemma\adapters\sme-adapter-f16.gguf --lora-init-without-apply
```

`--lora-init-without-apply` loads the adapter but starts with it switched
**off**, so the server behaves exactly as it does today until a request asks
for the adapter.

Restart the server. Restarting is your call and briefly interrupts anything
using it.

## 4. Confirm it loaded

```powershell
Invoke-RestMethod http://127.0.0.1:8080/lora-adapters
```

Expected: one entry with `id` 0, the path to your file, and `scale` 0.

## 5. Turn it on for a request

Per request (no restart, other requests are unaffected):

```powershell
$body = @{
  model = "gemma-3-4b-it"
  messages = @(@{ role = "user"; content = "Say hello in one sentence." })
  max_tokens = 40
  lora = @(@{ id = 0; scale = 1.0 })
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri http://127.0.0.1:8080/v1/chat/completions -Method Post -ContentType "application/json" -Body $body
```

Use `scale = 0.0` (or leave `lora` out) for the plain model.

If the per-request field seems to be ignored, set the scale for the whole
server instead (this affects every request until you set it back):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8080/lora-adapters -Method Post -ContentType "application/json" -Body '[{"id":0,"scale":1.0}]'
```

## 6. Run the smoke test

From any machine that has this repo and Python:

```
python training/smoke_test_lora_serving.py training/sample_pairs.jsonl --base-url http://127.0.0.1:8080/v1 --limit 2
```

Through the tunnel, set `LLM_API_BASE` (and `LLM_API_KEY` if your endpoint
needs one) in the environment instead of passing them on the command line. Add
`--scale-mode global` if step 5's per-request field was ignored.

It sends the same real SME prompts with the adapter off and then on, and
checks every reply is valid SME JSON. `RESULT: PASS` means the adapter loads
and the server still behaves. It does **not** say the adapter is good: the
stored adapter was trained on only 25 synthetic pairs.

## 7. Roll back

Remove the two arguments from `start-gemma.bat` and restart. The base model
file was never touched.

## Notes

- **GPU memory:** the current settings (`--ctx-size 24576 --parallel 3`, q8 KV
  cache) are estimated at about 5 of the 8 GiB. The adapter adds roughly
  0.1-0.2 GiB. Check with `nvidia-smi` before and after, and tell us the
  numbers. A second server running at the same time is not expected to fit.
- **Speed:** requests using different adapter settings may not be batched
  together across the 3 parallel slots. If throughput drops, that is why.
- **What this does not tell you:** whether the adapter improves answers. That
  needs a separate comparison on held-out reviewer data.
````

- [ ] **Step 2: Verify the runbook mentions every flag and command it must**

```bash
for needle in "--lora-init-without-apply" "--lora-scaled" "/lora-adapters" "certutil" "nvidia-smi" "--scale-mode global" "smoke_test_lora_serving.py" "start-gemma.bat" "Roll back"; do grep -q -- "$needle" training/serving-lora-adapter.md && echo "ok  $needle" || echo "MISSING  $needle"; done
```

Expected: nine `ok` lines and no `MISSING`.

- [ ] **Step 3: Commit**

```bash
git add training/serving-lora-adapter.md
git commit -m "docs(training): add host-owner runbook for serving a GGUF LoRA adapter"
```

---

### Task 6: Manual end-to-end validation (needs you and the host owner)

**Files:** none (validation only; a fix would touch the notebook or script).

**Interfaces:** none.

This cannot be run by an automated worker: it needs Colab, the stored adapter,
and the host owner's server. Per the spec's Testing section, do it once before
considering this done.

- [ ] **Step 1: Convert the stored adapter in Colab**

1. Open `docs/colab/adapter_to_gguf_template.ipynb` in Colab (upload the file).
2. Upload the stored adapter as `adapter.zip`. On this machine it is
   `adapters/sme/830d10de-c02f-49f7-9277-da0e165dad1e/adapter.zip` (114 MB).
3. Runtime -> Run all.
4. Confirm: the converter's `--help` prints; conversion finishes; the
   "GGUF LoRA verified" line shows `rank` 16 and `alpha` 32.0; the two files
   download.

If the converter rejects a flag, adapt cell 5 using the `--help` output in the
log, fix the notebook, re-run the offline tests, and commit the fix. If it
fails on Gemma 3 tensor names or produces zero tensors, stop and report: the
spec's fallback is a converter patch or the merge approach.

- [ ] **Step 2: Hand off to the host owner**

Send `adapter-f16.gguf`, `adapter-f16.gguf.sha256` and
`training/serving-lora-adapter.md`. They follow steps 1-4 of the runbook,
including checking the hash and that `GET /lora-adapters` lists the adapter.

- [ ] **Step 3: Smoke test against their server**

```bash
python training/smoke_test_lora_serving.py training/sample_pairs.jsonl --base-url http://127.0.0.1:8080/v1 --limit 2
```

(run on their machine, or from here with `LLM_API_BASE` pointed at the tunnel).
Expected: `RESULT: PASS`. If the report says the score did not change and
`GET /lora-adapters` shows the adapter, re-run with `--scale-mode global`.

- [ ] **Step 4: Record measurements and the outcome**

Ask the owner for `nvidia-smi` memory use with the server running before and
after adding the adapter. Add a "Completed <date>" note under this task
recording: the llama.cpp commit used for conversion, whether per-request scale
worked, the VRAM numbers, and the smoke test result, then commit it.

No commit for this task unless a fix or the outcome note was needed.
