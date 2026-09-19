"""Offline tests for training/smoke_test_lora_serving.py (no server, no GPU)."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
        "chat_500_when_on": False,
        "chat_400": False,
        "fail_reset": False,
        "scale_on_seen": False,
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
                new_scale = payload[0]["scale"]
                if new_scale > 0:
                    state["scale_on_seen"] = True
                if new_scale == 0 and state["fail_reset"] and state["scale_on_seen"]:
                    self._send(500, {"error": "cannot reset"})
                    return
                state["global_scale"] = new_scale
                self._send(200, {"success": True})
            elif self.path == "/v1/chat/completions":
                if state["chat_400"]:
                    self._send(400, {"error": {"message": "context too long"}})
                    return
                scale = state["global_scale"]
                if "lora" in payload:
                    scale = payload["lora"][0]["scale"]
                if scale > 0 and state["chat_500_when_on"]:
                    self._send(500, {"error": "boom"})
                    return
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
        [{"id": 0, "scale": 0.0}],
    ]
    chats = [r for r in fake_server["requests"] if r["path"] == "/v1/chat/completions"]
    assert len(chats) == 4
    assert all("lora" not in c["body"] for c in chats)
    assert "score changed with adapter ON: 2/2 comparable prompt(s)" in out
    assert "adapter scale reset to 0.0" in out
    assert fake_server["global_scale"] == 0.0


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


def _global_argv(fake_server):
    return [
        SAMPLE_PAIRS,
        "--base-url",
        fake_server["base_url"],
        "--limit",
        "1",
        "--scale-mode",
        "global",
    ]


def _lora_posts(fake_server):
    return [
        r["body"]
        for r in fake_server["requests"]
        if r["method"] == "POST" and r["path"] == "/lora-adapters"
    ]


def test_cli_global_mode_resets_scale_when_a_chat_request_fails(fake_server, capsys):
    fake_server["chat_500_when_on"] = True
    code, out, err = _run_cli(_global_argv(fake_server), capsys)

    assert code == 2
    assert err.startswith("error:")
    assert _lora_posts(fake_server)[-1] == [{"id": 0, "scale": 0.0}]
    assert _lora_posts(fake_server)[-2] == [{"id": 0, "scale": 1.0}]
    assert fake_server["global_scale"] == 0.0
    assert "adapter scale reset to 0.0" in out


def test_cli_global_mode_resets_scale_when_replies_are_invalid(fake_server, capsys):
    fake_server["bad_on"] = True
    code, _, _ = _run_cli(_global_argv(fake_server), capsys)

    assert code == 1
    assert _lora_posts(fake_server)[-1] == [{"id": 0, "scale": 0.0}]


def test_cli_global_reset_failure_warns_loudly_and_keeps_exit_code(
    fake_server, capsys, monkeypatch
):
    monkeypatch.setenv("LLM_API_KEY", "secret-key-123")
    fake_server["fail_reset"] = True
    code, out, err = _run_cli(_global_argv(fake_server), capsys)

    assert code == 0
    assert "RESULT: PASS" in out
    assert "may still be ON" in err
    assert "/lora-adapters" in err
    assert '"scale":0.0' in err
    assert "secret-key-123" not in out + err


def test_cli_request_mode_never_posts_to_the_adapter_endpoint(fake_server, capsys):
    code, out, _ = _run_cli(
        [SAMPLE_PAIRS, "--base-url", fake_server["base_url"], "--limit", "1"], capsys
    )
    assert code == 0
    assert _lora_posts(fake_server) == []
    assert "reset" not in out


def test_cli_global_mode_does_not_reset_when_the_server_was_never_touched(
    fake_server, capsys
):
    fake_server["adapters"] = []
    code, out, err = _run_cli(_global_argv(fake_server), capsys)

    assert code == 2
    assert _lora_posts(fake_server) == []
    assert "may still be ON" not in err
    assert "reset" not in out


def test_cli_reports_the_http_error_body(fake_server, capsys):
    fake_server["chat_400"] = True
    code, _, err = _run_cli(
        [SAMPLE_PAIRS, "--base-url", fake_server["base_url"], "--limit", "1"], capsys
    )

    assert code == 2
    assert "HTTP Error 400" in err
    assert "context too long" in err
