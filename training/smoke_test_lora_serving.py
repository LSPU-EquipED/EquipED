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
sets it through POST /lora-adapters, for servers that ignore the per-request
field. Global mode changes the server-wide scale, so the script resets it to 0.0
when it finishes or fails and prints a note (or a warning on stderr if that
reset itself fails).

Exit code: 0 all replies valid, 1 some reply invalid, 2 could not run (server
unreachable, no adapter loaded, bad input).

Prompts are sent as a single user message: pairs.jsonl stores each prompt
already flattened (system + user text), and Gemma's chat template folds system
text into the user turn anyway.
"""

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

MIN_SCORE = 1
MAX_SCORE = 4
DEFAULT_MODEL = "gemma-3-4b-it"


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
    scale_touched: list[bool] | None = None,
) -> Callable[[str, float], str]:
    current: dict[str, float | None] = {"scale": None}

    def complete(prompt: str, scale: float) -> str:
        if scale_mode == "global" and current["scale"] != scale:
            if scale_touched is not None:
                scale_touched.append(True)
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
    parser.add_argument(
        "--adapter-id",
        type=int,
        default=None,
        help="adapter id to test (default: the first loaded adapter)",
    )
    parser.add_argument(
        "--scale-mode",
        choices=("request", "global"),
        default="request",
        help="request: send the scale in each chat request (default). global: "
        "set it through POST /lora-adapters; this changes the server-wide "
        "scale, and the script resets it to 0.0 afterwards",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="max tokens per reply (default: 1024)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="seconds to wait for each HTTP request (default: 300)",
    )
    return parser.parse_args(argv)


def describe_error(exc: BaseException) -> str:
    """One-line description of a failure; adds the server's body for HTTP errors."""
    text = str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read(500).decode("utf-8", errors="replace").strip()
        except (OSError, http.client.HTTPException):
            body = ""
        if body:
            text = f"{text} - {body}"
    return text


def reset_global_scale(
    base_url: str, api_key: str | None, adapter_id: int, timeout: float
) -> None:
    """Put the server-wide adapter scale back to 0.0 and say how it went."""
    try:
        set_global_scale(base_url, api_key, adapter_id, 0.0, timeout)
    except (OSError, ValueError, http.client.HTTPException) as exc:
        print(
            f"WARNING: could not reset the adapter scale ({describe_error(exc)}). "
            "The adapter may still be ON for every request. Reset it yourself: "
            f"POST {server_root(base_url)}/lora-adapters "
            f'[{{"id":{adapter_id},"scale":0.0}}]',
            file=sys.stderr,
        )
    else:
        print(
            "note: adapter scale reset to 0.0 "
            "(global mode changes the server-wide scale)"
        )


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
    adapter_id: int | None = None
    scale_touched: list[bool] = []
    try:
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
                scale_touched=scale_touched,
            )
            report = run_smoke_test(prompts, complete)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            print(f"error: {describe_error(exc)}", file=sys.stderr)
            return 2
        print(format_report(report))
        return exit_code(report)
    finally:
        if args.scale_mode == "global" and scale_touched and adapter_id is not None:
            reset_global_scale(base_url, api_key, adapter_id, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
