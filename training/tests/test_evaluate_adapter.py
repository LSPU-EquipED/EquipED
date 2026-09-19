"""Offline tests for training/evaluate_adapter.py (no server, no GPU)."""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

TRAINING_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_DIR))

import evaluate_adapter as ev  # noqa: E402


def _reply(scores: dict[str, int], summary: str = "ok") -> str:
    return json.dumps(
        {
            "summary": summary,
            "criterion_measurements": [
                {"criterion_id": criterion_id, "score": score}
                for criterion_id, score in scores.items()
            ],
        }
    )


# --- answer_key ---------------------------------------------------------------


def test_answer_key_holds_only_criteria_the_reviewer_changed():
    rejected = _reply({"A-01": 1, "A-02": 3, "A-03": 2})
    chosen = _reply({"A-01": 3, "A-02": 3, "A-03": 4})
    assert ev.answer_key(chosen, rejected) == {"A-01": 3, "A-03": 4}


def test_answer_key_is_none_when_no_score_changed():
    same = _reply({"A-01": 2})
    assert ev.answer_key(same, same) is None


def test_answer_key_is_none_when_a_reply_is_unparsable():
    assert ev.answer_key("not json", _reply({"A-01": 1})) is None
    assert ev.answer_key(_reply({"A-01": 1}), "not json") is None


def test_answer_key_ignores_criteria_missing_from_the_other_reply():
    assert ev.answer_key(_reply({"A-01": 3, "A-02": 2}), _reply({"A-01": 1})) == {
        "A-01": 3
    }


# --- error_total and score_pair -------------------------------------------------


def test_error_total_sums_absolute_differences():
    assert ev.error_total({"A": 3, "B": 1}, {"A": 1, "B": 1, "C": 4}) == 2


def test_error_total_counts_a_missing_criterion_as_the_worst_error():
    assert ev.error_total({"A": 3, "B": 1}, {"A": 3}) == ev.WORST_ERROR


def test_error_total_counts_an_invalid_reply_as_the_worst_error():
    assert ev.error_total({"A": 3, "B": 1}, None) == 2 * ev.WORST_ERROR


def test_worst_error_is_the_score_range():
    assert ev.WORST_ERROR == 3


def test_score_pair_win_loss_and_tie():
    key = {"A": 3}
    win = ev.score_pair("p1", key, {"A": 1}, {"A": 3})
    loss = ev.score_pair("p2", key, {"A": 3}, {"A": 1})
    tie = ev.score_pair("p3", key, {"A": 2}, {"A": 4})
    assert (win.outcome, loss.outcome, tie.outcome) == ("win", "loss", "tie")
    assert (win.base_error, win.adapter_error) == (2.0, 0.0)
    assert win.gold == {"A": 3}
    assert win.pair_id == "p1"


def test_score_pair_a_valid_but_wrong_adapter_beats_an_invalid_base():
    result = ev.score_pair("p", {"A": 3}, None, {"A": 1})
    assert result.outcome == "win"
    assert result.base_scores is None


# --- sign test ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wins", "losses", "expected"),
    [
        (0, 0, 1.0),
        (5, 5, 1.0),
        (9, 1, 0.021484375),
        (1, 9, 0.021484375),
        (15, 5, 0.04138946533203125),
        (14, 6, 0.115318298339844),
        (20, 0, 2 / 2**20),
    ],
)
def test_sign_test_matches_exact_binomial_values(wins, losses, expected):
    assert ev.sign_test_p(wins, losses) == pytest.approx(expected, rel=1e-6)


# --- verdict --------------------------------------------------------------------


def _decide(wins, losses, base_rate=1.0, adapter_rate=1.0, **overrides):
    params = {"min_decisive": 20, "alpha": 0.05, **overrides}
    return ev.decide(wins, losses, base_rate, adapter_rate, **params)


def test_verdict_too_few_decisive_pairs_is_inconclusive_even_if_all_wins():
    result = _decide(19, 0)
    assert result.verdict == "inconclusive"
    assert "too few decisive pairs (19 < 20)" in result.reasons[0]


def test_verdict_better_when_wins_dominate():
    result = _decide(20, 4)
    assert result.verdict == "better"
    assert result.p_value < 0.05


def test_verdict_worse_when_losses_dominate():
    assert _decide(4, 20).verdict == "worse"


def test_verdict_inconclusive_when_not_significant():
    result = _decide(13, 9)
    assert result.verdict == "inconclusive"
    assert "not statistically significant" in result.reasons[0]


def test_verdict_better_is_capped_when_adapter_returns_more_invalid_json():
    result = _decide(24, 2, base_rate=1.0, adapter_rate=0.9)
    assert result.verdict == "inconclusive"
    assert "invalid JSON" in result.reasons[0]


def test_verdict_worse_is_not_capped_by_validity():
    assert _decide(2, 24, base_rate=1.0, adapter_rate=0.9).verdict == "worse"


def test_verdict_respects_custom_min_decisive_and_alpha():
    assert _decide(9, 1, min_decisive=10).verdict == "better"
    assert _decide(9, 1, min_decisive=10, alpha=0.01).verdict == "inconclusive"


# --- loading the held-out set ----------------------------------------------------


def _heldout_row(n: int, **overrides) -> dict:
    row = {
        "pair_id": f"pair-{n}",
        "evaluation_id": f"eval-{n // 2}",
        "prompt": f"PROMPT-{n}",
        "chosen": _reply({"A-01": 3}),
        "rejected": _reply({"A-01": 1}),
    }
    row.update(overrides)
    return row


def _jsonl(rows: list[dict]) -> bytes:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()


def _make_adapter_zip(
    tmp_path: Path,
    rows: list[dict] | None = None,
    *,
    heldout: dict | None | str = "auto",
    include_file: bool = True,
    file_bytes: bytes | None = None,
) -> Path:
    rows = rows if rows is not None else [_heldout_row(n) for n in range(4)]
    data = file_bytes if file_bytes is not None else _jsonl(rows)
    if heldout == "auto":
        heldout = {
            "method": "group_by_evaluation_id",
            "seed": 42,
            "fraction": 0.2,
            "pair_count": len(rows),
            "evaluation_count": len({row["evaluation_id"] for row in rows}),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    path = tmp_path / "adapter.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("adapter_config.json", "{}")
        archive.writestr("adapter_model.safetensors", b"weights")
        archive.writestr("training_manifest.json", json.dumps({"heldout": heldout}))
        if include_file:
            archive.writestr("heldout_pairs.jsonl", data)
    return path


def test_load_heldout_zip_reads_and_verifies_the_file(tmp_path):
    path = _make_adapter_zip(tmp_path)
    heldout = ev.load_heldout_zip(path)

    assert [pair.pair_id for pair in heldout.pairs] == [f"pair-{n}" for n in range(4)]
    assert heldout.pairs[0].prompt == "PROMPT-0"
    assert heldout.sha256_verified is True
    assert heldout.adapter_zip_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert str(path) in heldout.source


def test_load_heldout_zip_without_a_heldout_block_says_so(tmp_path):
    for heldout in (None, "missing"):
        path = _make_adapter_zip(tmp_path, heldout=heldout)
        with pytest.raises(ValueError, match="no held-out set"):
            ev.load_heldout_zip(path)


def test_load_heldout_zip_rejects_a_file_that_does_not_match_its_hash(tmp_path):
    path = _make_adapter_zip(tmp_path, heldout={"pair_count": 4, "sha256": "0" * 64})
    with pytest.raises(ValueError, match="sha256"):
        ev.load_heldout_zip(path)


def test_load_heldout_zip_rejects_a_pair_count_mismatch(tmp_path):
    rows = [_heldout_row(n) for n in range(4)]
    data = _jsonl(rows)
    path = _make_adapter_zip(
        tmp_path,
        rows,
        heldout={"pair_count": 9, "sha256": hashlib.sha256(data).hexdigest()},
    )
    with pytest.raises(ValueError, match="9 held-out pairs but"):
        ev.load_heldout_zip(path)


def test_load_heldout_zip_reports_a_missing_heldout_file(tmp_path):
    path = _make_adapter_zip(tmp_path, include_file=False)
    with pytest.raises(ValueError, match="heldout_pairs.jsonl is not in the adapter"):
        ev.load_heldout_zip(path)


def test_load_heldout_zip_rejects_a_file_that_is_not_a_zip(tmp_path):
    bogus = tmp_path / "bogus.zip"
    bogus.write_text("not a zip")
    with pytest.raises(zipfile.BadZipFile):
        ev.load_heldout_zip(bogus)


def test_load_heldout_file_reads_a_bare_jsonl_unverified(tmp_path):
    path = tmp_path / "heldout_pairs.jsonl"
    path.write_bytes(_jsonl([_heldout_row(0), _heldout_row(1)]))
    heldout = ev.load_heldout_file(path)

    assert len(heldout.pairs) == 2
    assert heldout.sha256_verified is False
    assert heldout.adapter_zip_sha256 is None


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        (b"", "no pairs"),
        (b"{not json}\n", "line 1: not valid JSON"),
        (b"[1]\n", "line 1: not a JSON object"),
        (_jsonl([{k: v for k, v in _heldout_row(0).items() if k != "prompt"}]), "'prompt'"),
        (_jsonl([_heldout_row(0, chosen="  ")]), "'chosen'"),
        (_jsonl([_heldout_row(0), _heldout_row(1, pair_id=5)]), "line 2"),
    ],
)
def test_parse_heldout_rejects_malformed_files(data, fragment):
    with pytest.raises(ValueError, match=fragment):
        ev.parse_heldout(data)


def test_parse_heldout_handles_unicode_line_separators_in_text(tmp_path):
    """Regression: splitlines() splits on U+2028/U+2029/U+0085, breaking JSON records."""
    prompt_with_separators = "PROMPT-with\u2028\u2029\u0085-separators"
    row = {
        "pair_id": "pair-0",
        "evaluation_id": "eval-0",
        "prompt": prompt_with_separators,
        "chosen": _reply({"A-01": 3}),
        "rejected": _reply({"A-01": 1}),
    }
    data = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")

    pairs = ev.parse_heldout(data)

    assert len(pairs) == 1
    assert pairs[0].prompt == prompt_with_separators


# --- running the evaluation and reporting ------------------------------------------


def _pairs(count: int) -> list[ev.HeldoutPair]:
    """Pairs whose reviewer score for A-01 is 3 (the plain model said 1)."""
    return [
        ev.HeldoutPair(
            pair_id=f"pair-{n}",
            evaluation_id=f"eval-{n}",
            prompt=f"P{n}",
            chosen=_reply({"A-01": 3}),
            rejected=_reply({"A-01": 1}),
        )
        for n in range(count)
    ]


def _complete(base_score: int, adapter_score: int, calls: list | None = None):
    """A stand-in for the server: every reply carries one fixed A-01 score."""

    def complete(prompt: str, scale: float) -> str:
        if calls is not None:
            calls.append((prompt, scale))
        return _reply({"A-01": adapter_score if scale > 0 else base_score})

    return complete


def test_run_evaluation_all_wins_is_better():
    evaluation = ev.run_evaluation(_pairs(25), _complete(base_score=1, adapter_score=3))

    assert (evaluation.wins, evaluation.losses, evaluation.ties) == (25, 0, 0)
    assert evaluation.total_pairs == 25 and evaluation.skipped == 0
    assert evaluation.verdict.verdict == "better"
    assert evaluation.mean_base_error == 2.0
    assert evaluation.mean_adapter_error == 0.0
    assert evaluation.base_valid_rate == evaluation.adapter_valid_rate == 1.0
    assert evaluation.warnings == []
    assert ev.exit_code(evaluation) == 0


def test_run_evaluation_all_losses_is_worse():
    evaluation = ev.run_evaluation(_pairs(25), _complete(base_score=3, adapter_score=1))
    assert evaluation.losses == 25
    assert evaluation.verdict.verdict == "worse"
    assert ev.exit_code(evaluation) == 1


def test_run_evaluation_sends_all_off_requests_before_any_on_request():
    calls: list = []
    ev.run_evaluation(_pairs(3), _complete(1, 3, calls))
    assert [scale for _, scale in calls] == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    assert [prompt for prompt, _ in calls[:3]] == ["P0", "P1", "P2"]


def test_run_evaluation_skips_unscoreable_pairs_without_sending_them():
    unscoreable = ev.HeldoutPair(
        "skip", "eval-x", "SKIPPED-PROMPT", _reply({"A-01": 2}), _reply({"A-01": 2})
    )
    calls: list = []
    evaluation = ev.run_evaluation(
        [*_pairs(2), unscoreable], _complete(1, 3, calls)
    )

    assert evaluation.total_pairs == 3
    assert evaluation.skipped == 1
    assert evaluation.scoreable == 2
    assert all(prompt != "SKIPPED-PROMPT" for prompt, _ in calls)


def test_run_evaluation_with_nothing_scoreable_raises():
    same = _reply({"A-01": 2})
    pair = ev.HeldoutPair("p", "e", "P", same, same)
    with pytest.raises(ValueError, match="nothing to evaluate"):
        ev.run_evaluation([pair], _complete(1, 3))


def test_run_evaluation_invalid_adapter_reply_is_a_loss_and_lowers_validity():
    def complete(prompt: str, scale: float) -> str:
        if scale > 0:
            return "not json"
        return _reply({"A-01": 3})

    evaluation = ev.run_evaluation(_pairs(25), complete)
    assert evaluation.losses == 25
    assert evaluation.adapter_valid_rate == 0.0
    assert evaluation.base_valid_rate == 1.0
    assert evaluation.verdict.verdict == "worse"


def test_run_evaluation_warns_when_adapter_replies_equal_base_replies():
    evaluation = ev.run_evaluation(_pairs(25), _complete(2, 2))

    assert evaluation.ties == 25
    assert evaluation.verdict.verdict == "inconclusive"
    assert "too few decisive pairs (0 < 20)" in evaluation.verdict.reasons[0]
    assert "may not be applied" in evaluation.warnings[0]


def test_run_evaluation_passes_thresholds_through():
    evaluation = ev.run_evaluation(
        _pairs(10), _complete(1, 3), min_decisive=10, alpha=0.05
    )
    assert evaluation.verdict.verdict == "better"
    assert (evaluation.min_decisive, evaluation.alpha) == (10, 0.05)


def test_build_report_is_json_serialisable_and_holds_no_prompts():
    evaluation = ev.run_evaluation(_pairs(25), _complete(1, 3))
    report = ev.build_report(
        evaluation,
        parameters={"min_decisive": 20, "alpha": 0.05},
        heldout={"source": "x", "pair_count": 25},
        adapter={"zip_sha256": "abc"},
    )
    text = json.dumps(report)

    assert report["verdict"] == "better"
    assert report["pairs"] == {
        "heldout_total": 25,
        "scoreable": 25,
        "skipped": 0,
        "wins": 25,
        "losses": 0,
        "ties": 0,
    }
    assert report["mean_abs_error"] == {"base": 2.0, "adapter": 0.0}
    assert report["valid_json_rate"] == {"base": 1.0, "adapter": 1.0}
    assert report["sign_test_p"] == pytest.approx(2 / 2**25)
    assert report["per_pair"][0] == {
        "pair_id": "pair-0",
        "gold": {"A-01": 3},
        "base_scores": {"A-01": 1},
        "adapter_scores": {"A-01": 3},
        "outcome": "win",
    }
    assert len(report["per_pair"]) == 25
    assert "P0" not in text  # prompts never appear in the report


def test_format_report_shows_counts_verdict_and_the_limits_note():
    evaluation = ev.run_evaluation(_pairs(25), _complete(1, 3))
    text = ev.format_report(evaluation)

    assert "25 held-out pair(s), 25 scoreable" in text
    assert "valid JSON       base 25/25   adapter 25/25" in text
    assert "adapter 25 win(s), 0 loss(es), 0 tie(s)" in text
    assert "VERDICT: BETTER" in text
    assert ev.LIMITS_NOTE in text


def test_format_report_mentions_skipped_pairs_and_warnings():
    same = _reply({"A-01": 2})
    skip = ev.HeldoutPair("skip", "e", "S", same, same)
    evaluation = ev.run_evaluation([*_pairs(2), skip], _complete(2, 2))
    text = ev.format_report(evaluation)

    assert "1 skipped" in text
    assert "WARNING:" in text


# --- command line, against a fake llama-server ------------------------------------


@pytest.fixture
def fake_server(monkeypatch):
    """A stand-in for llama-server whose replies depend on the prompt and scale."""
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL_NAME", raising=False)
    state = {
        "adapters": [{"id": 0, "path": "adapter.gguf", "scale": 0.0}],
        "requests": [],
        "global_scale": 0.0,
        "chat_400": False,
        # adapter improves every pair unless a test swaps this out
        "reply_for": lambda prompt, scale: _reply({"A-01": 3 if scale > 0 else 1}),
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
                    "user_agent": self.headers.get("User-Agent"),
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
                if state["chat_400"]:
                    self._send(400, {"error": {"message": "context too long"}})
                    return
                scale = state["global_scale"]
                if "lora" in payload:
                    scale = payload["lora"][0]["scale"]
                prompt = payload["messages"][0]["content"]
                content = state["reply_for"](prompt, scale)
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


def _zip_with_pairs(tmp_path: Path, count: int = 25) -> Path:
    rows = [_heldout_row(n) for n in range(count)]
    return _make_adapter_zip(tmp_path, rows)


def _chats(state) -> list[dict]:
    return [r for r in state["requests"] if r["path"] == "/v1/chat/completions"]


def _run_cli(argv, capsys):
    code = ev.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_cli_better_adapter_exits_0_and_writes_the_report(
    fake_server, tmp_path, capsys
):
    zip_path = _zip_with_pairs(tmp_path)
    report_path = tmp_path / "report.json"
    code, out, err = _run_cli(
        [
            "--adapter-zip",
            str(zip_path),
            "--base-url",
            fake_server["base_url"],
            "--report-json",
            str(report_path),
        ],
        capsys,
    )

    assert code == 0, err
    assert "VERDICT: BETTER" in out
    assert "sha256 verified" in out
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["verdict"] == "better"
    assert report["pairs"]["wins"] == 25
    assert report["heldout"]["sha256_verified"] is True
    assert report["adapter"]["zip_sha256"] == hashlib.sha256(
        zip_path.read_bytes()
    ).hexdigest()
    assert report["parameters"]["model"] == "gemma-3-4b-it"
    chats = _chats(fake_server)
    assert [c["body"]["lora"] for c in chats] == (
        [[{"id": 0, "scale": 0.0}]] * 25 + [[{"id": 0, "scale": 1.0}]] * 25
    )
    assert all(c["body"]["temperature"] == 0.0 for c in chats)
    assert all(c["body"]["max_tokens"] == ev.DEFAULT_MAX_TOKENS for c in chats)


def test_cli_worse_adapter_exits_1(fake_server, tmp_path, capsys):
    fake_server["reply_for"] = lambda prompt, scale: _reply(
        {"A-01": 1 if scale > 0 else 3}
    )
    code, out, _ = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            fake_server["base_url"],
        ],
        capsys,
    )
    assert code == 1
    assert "VERDICT: WORSE" in out


def test_cli_too_few_pairs_is_inconclusive_and_exits_1(fake_server, tmp_path, capsys):
    code, out, _ = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path, count=4)),
            "--base-url",
            fake_server["base_url"],
        ],
        capsys,
    )
    assert code == 1
    assert "VERDICT: INCONCLUSIVE" in out
    assert "too few decisive pairs (4 < 20)" in out


def test_cli_limit_and_thresholds_are_honoured(fake_server, tmp_path, capsys):
    code, out, _ = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            fake_server["base_url"],
            "--limit",
            "6",
            "--min-decisive",
            "6",
        ],
        capsys,
    )
    assert code == 0
    assert "(6 of 25 pair(s) used" in out
    assert len(_chats(fake_server)) == 12
    assert "VERDICT: BETTER" in out


def test_cli_accepts_a_bare_heldout_file(fake_server, tmp_path, capsys):
    path = tmp_path / "heldout_pairs.jsonl"
    path.write_bytes(_jsonl([_heldout_row(n) for n in range(25)]))
    code, out, err = _run_cli(
        ["--heldout", str(path), "--base-url", fake_server["base_url"]], capsys
    )
    assert code == 0, err
    assert "sha256 not checked" in out


def test_cli_global_mode_switches_scale_once_and_resets_it(
    fake_server, tmp_path, capsys
):
    code, out, err = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            fake_server["base_url"],
            "--scale-mode",
            "global",
        ],
        capsys,
    )

    assert code == 0, err
    assert "VERDICT: BETTER" in out
    assert all("lora" not in c["body"] for c in _chats(fake_server))
    scale_posts = [
        r["body"][0]["scale"]
        for r in fake_server["requests"]
        if r["method"] == "POST" and r["path"] == "/lora-adapters"
    ]
    assert scale_posts == [0.0, 1.0, 0.0]
    assert fake_server["global_scale"] == 0.0
    assert "adapter scale reset to 0.0" in out


def test_cli_sends_bearer_key_and_user_agent_and_never_prints_the_key(
    fake_server, tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("LLM_API_KEY", "secret-key-123")
    code, out, err = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path, count=2)),
            "--base-url",
            fake_server["base_url"],
        ],
        capsys,
    )

    assert code == 1, err  # only 2 pairs: inconclusive
    assert all(r["auth"] == "Bearer secret-key-123" for r in fake_server["requests"])
    assert {r["user_agent"] for r in fake_server["requests"]} == {ev.smoke.USER_AGENT}
    assert "secret-key-123" not in out + err


def test_cli_adapter_without_heldout_set_exits_2_before_touching_the_server(
    fake_server, tmp_path, capsys
):
    zip_path = _make_adapter_zip(tmp_path, heldout=None)
    code, _, err = _run_cli(
        ["--adapter-zip", str(zip_path), "--base-url", fake_server["base_url"]], capsys
    )
    assert code == 2
    assert "no held-out set" in err
    assert fake_server["requests"] == []


def test_cli_no_adapter_loaded_exits_2(fake_server, tmp_path, capsys):
    fake_server["adapters"] = []
    code, _, err = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            fake_server["base_url"],
        ],
        capsys,
    )
    assert code == 2
    assert "no LoRA adapter is loaded" in err


def test_cli_server_error_exits_2(fake_server, tmp_path, capsys):
    fake_server["chat_400"] = True
    code, _, err = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            fake_server["base_url"],
        ],
        capsys,
    )
    assert code == 2
    assert "context too long" in err


def test_cli_unreachable_server_exits_2(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    code, _, err = _run_cli(
        [
            "--adapter-zip",
            str(_zip_with_pairs(tmp_path)),
            "--base-url",
            "http://127.0.0.1:9/v1",
            "--timeout",
            "2",
        ],
        capsys,
    )
    assert code == 2
    assert err.startswith("error:")


def test_cli_without_a_base_url_exits_2(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    code, _, err = _run_cli(
        ["--adapter-zip", str(_zip_with_pairs(tmp_path))], capsys
    )
    assert code == 2
    assert "LLM_API_BASE" in err


@pytest.mark.parametrize(
    "bad_args",
    [
        ["--alpha", "1.5"],
        ["--alpha", "0"],
        ["--limit", "0"],
        ["--min-decisive", "0"],
        [],  # neither --adapter-zip nor --heldout
    ],
)
def test_cli_rejects_bad_arguments(bad_args, tmp_path):
    argv = list(bad_args)
    if bad_args:
        argv = ["--adapter-zip", str(tmp_path / "x.zip"), *bad_args]
    with pytest.raises(SystemExit) as excinfo:
        ev.parse_args(argv)
    assert excinfo.value.code == 2


def test_cli_adapter_and_heldout_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit):
        ev.parse_args(["--adapter-zip", "a.zip", "--heldout", "b.jsonl"])
