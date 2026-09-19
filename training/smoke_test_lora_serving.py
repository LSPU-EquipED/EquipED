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
