"""Smoke test a llama-server that has a GGUF LoRA adapter loaded.

Sends the same real SME prompts to the server with the adapter switched off
and then on, and checks that every reply is JSON in the shape the SME agent
expects. Full usage notes are added with the command-line entry point.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
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
