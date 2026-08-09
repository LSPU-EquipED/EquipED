"""ITSO execution and response handling tests."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.itso import execution
from server.modules.agents.itso.response import criterion_scores, parse_response
from server.modules.agents.runtime import llm as runtime_llm
from server.modules.agents.runtime.context import ITSOExecutionContext
from server.modules.agents.supervision.dispatch import AgentDispatcher


class _LLM:
    model = "primary"

    def __init__(self, responses):
        self.responses = iter(responses)

    def generate(self, prompt, *, temperature, max_new_tokens):
        return next(self.responses)


def _context(client, **kwargs):
    return ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "page_number": 1, "text": "security"},),
        llm_client=client,
        **kwargs,
    )


def test_itso_executes_and_preserves_provenance(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    result = execution.execute(
        _context(
            _LLM([_response("ok")]),
            provenance={"bibliography_found": True, "chunk_ids_ordered": ["c1"]},
        )
    )
    assert result.agent_name == "itso"
    assert result.summary == "ok"
    assert result.provenance["bibliography_found"] is True
    assert result.provenance["chunk_ids_ordered"] == ["c1"]
    assert result.provenance["actual_model"] == "primary"


def test_parse_response_supports_fenced_and_prefixed_json():
    payload = _response("parsed")
    assert parse_response(f"prefix {payload}")["summary"] == "parsed"
    assert parse_response(f"```json\n{payload}\n```")["summary"] == "parsed"


def test_malformed_response_is_safe_and_does_not_expose_raw_text():
    raw = "secret raw model output that must not leak"
    with pytest.raises(AgentExecutionError) as exc:
        parse_response(raw)
    message = str(exc.value)
    assert "ITSOInvalidJSON" in message
    assert raw not in message
    assert "reference:" in message


@pytest.mark.parametrize("score", [3, 3.0, "3", "3.0"])
def test_criterion_scores_accepts_integral_score_forms(score):
    result = criterion_scores(
        {"criterion_scores": [{"criterion_id": "c1", "score": score}]}
    )
    assert result[0].score == 3


@pytest.mark.parametrize(
    "score", [3.5, "3.5", float("nan"), float("inf"), True, False, 0, 5, "not-a-score"]
)
def test_criterion_scores_rejects_invalid_scores_safely(score):
    with pytest.raises((AgentExecutionError, ValueError)) as exc:
        criterion_scores({"criterion_scores": [{"criterion_id": "c1", "score": score}]})
    message = str(exc.value)
    if isinstance(exc.value, AgentExecutionError):
        assert "ITSOInvalidScore" in message
        assert "reference:" in message
    assert str(score) not in message


def test_criterion_scores_normalizes_evidence_and_chunk_ids_to_tuples():
    result = criterion_scores(
        {
            "criterion_scores": [
                {
                    "criterion_id": "c1",
                    "score": 3,
                    "chunk_ids": "chunk-1",
                    "evidence": "proof",
                },
                {
                    "criterion_id": "c2",
                    "score": 3,
                    "chunk_ids": [1, "chunk-2"],
                    "evidence": ("proof-2", 2),
                },
            ]
        }
    )
    assert result[0].chunk_ids == ("chunk-1",)
    assert result[0].evidence == ("proof",)
    assert result[1].chunk_ids == ("1", "chunk-2")
    assert result[1].evidence == ("proof-2", "2")


@pytest.mark.parametrize("title", [3, {"name": "title"}, None])
def test_criterion_scores_falls_back_for_non_string_titles(title):
    result = criterion_scores(
        {
            "criterion_scores": [
                {"criterion_id": "c1", "criterion_title": title, "score": 3}
            ]
        }
    )
    assert result[0].criterion_title == "c1"


def test_criterion_scores_preserves_string_title():
    result = criterion_scores(
        {
            "criterion_scores": [
                {"criterion_id": "c1", "criterion_title": "Title", "score": 3}
            ]
        }
    )
    assert result[0].criterion_title == "Title"


def test_repair_records_actual_model_and_fallback(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    client = _LLM(["{broken", _response("repaired")])
    calls = iter(
        (
            ("{broken", "initial-model"),
            (_response("repaired"), "repair-model"),
        )
    )
    monkeypatch.setattr(runtime_llm, "call_llm", lambda *args, **kwargs: next(calls))
    result = execution.execute(_context(client))
    assert result.model_name == "repair-model"
    assert result.provenance["repair_occurred"] is True
    assert result.provenance["fallback_occurred"] is True


@pytest.mark.parametrize(
    ("models", "expected"),
    [(("fallback", "assigned"), "assigned"), (("assigned", "fallback"), "fallback")],
)
def test_repair_keeps_final_model_and_accumulates_fallback(
    monkeypatch, models, expected
):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    responses = iter([("{broken", models[0]), (_response("repaired"), models[1])])
    monkeypatch.setattr(runtime_llm, "call_llm", lambda *a, **k: next(responses))
    result = execution.execute(_context(_LLM(["unused"])))
    assert result.model_name == expected
    assert result.provenance["fallback_occurred"] is True


def test_semantic_failure_does_not_repair(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    calls = []
    client = _LLM(
        [
            json.dumps(
                {
                    "summary": "ok",
                    "criterion_scores": [{"criterion_id": "c1", "score": 0}],
                }
            )
        ]
    )
    original = runtime_llm.call_llm
    monkeypatch.setattr(
        runtime_llm, "call_llm", lambda *a, **k: calls.append(1) or original(*a, **k)
    )
    with pytest.raises((AgentExecutionError, ValueError)):
        execution.execute(_context(client))
    assert len(calls) == 1


def test_invalid_repair_is_two_calls_and_dispatch_sanitizes_failure(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    calls = []
    monkeypatch.setattr(
        runtime_llm,
        "call_llm",
        lambda *a, **k: calls.append(1) or ("secret raw", "primary"),
    )
    with pytest.raises(AgentExecutionError) as exc:
        execution.execute(_context(_LLM(["unused"])))
    assert len(calls) == 2
    assert "secret raw" not in str(exc.value)
    failure = AgentDispatcher._sanitize_returned_failure(
        AgentEvaluationResult(
            agent_name="itso",
            evaluation_id=uuid4(),
            document_id=uuid4(),
            subtotal=1.0,
            criterion_scores=(),
            summary="secret narrative",
            model_name="primary",
            processing_seconds=0,
            token_count=1,
            success=True,
            error_message="secret error",
            raw_response="secret raw",
        )
    )
    assert failure.summary == ""
    assert failure.raw_response is None
    assert "secret" not in (failure.error_message or "")


def test_repair_prompt_caps_partial_output_at_4000(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    prompts = []
    monkeypatch.setattr(
        runtime_llm,
        "call_llm",
        lambda prompt, **k: prompts.append(prompt) or ("x" * 4001, "primary"),
    )
    with pytest.raises(AgentExecutionError):
        execution.execute(_context(_LLM(["unused"])))
    assert len(prompts[1].split("Prior partial output:\n\n", 1)[1]) == 4000


def _response(summary):
    return json.dumps(
        {
            "summary": summary,
            "criterion_scores": [
                {"criterion_id": "c1", "score": 3, "justification": "ok"}
            ],
        }
    )


def _settings():
    class Settings:
        agent_total_prompt_budget_chars = 8000
        agent_max_chunks = 12
        agent_max_excerpt_chars = 800
        agent_prompt_budget_chars = 5000
        agent_small_doc_threshold = 6
        llm_max_new_tokens = 2048

        def get_agent_temperature(self, name):
            return 0.0

    return Settings()
