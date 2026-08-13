"""ITSO execution and response handling tests."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.itso import execution
from server.modules.agents.itso.response import (
    ITSO_CRITERIA_TITLES,
    criterion_scores,
    parse_response,
)
from server.modules.agents.runtime.context import ITSOExecutionContext
from server.modules.agents.supervision.dispatch import AgentDispatcher


class _LLM:
    model = "primary"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def generate_result(
        self, prompt, *, temperature, max_new_tokens, deadline, response_contract
    ):
        self.prompts.append(prompt)
        return CompletionResult(
            next(self.responses), "primary", 10, 20, 30, "stop", attempts=1
        )


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


def test_itso_executes_and_snapshots_prompt_text(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    result = execution.execute(
        _context(_LLM([_response("ok")]))
    )
    assert result.prompt_text is not None
    assert '"agent": "itso"' in result.prompt_text
    assert '"criterion_scores"' not in result.prompt_text


def test_parse_response_supports_fenced_and_prefixed_json():
    payload = _response("parsed")
    assert parse_response(f"```json\n{payload}\n```")["summary"] == "parsed"


def test_malformed_response_is_safe_and_does_not_expose_raw_text():
    raw = "secret raw model output that must not leak"
    with pytest.raises(AgentExecutionError) as exc:
        parse_response(raw)
    message = str(exc.value)
    assert "ITSOInvalidJSON" in message
    assert raw not in message
    assert "reference:" in message


def _response(summary="ok", *, score=3, **overrides):
    entries = []
    for criterion_id in ("ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05"):
        entries.append(
            {
                "criterion_id": criterion_id,
                "criterion_title": ITSO_CRITERIA_TITLES[criterion_id],
                "score": score,
                "justification": "justification",
                "chunk_ids": [],
                "evidence": ["evidence"],
                **overrides,
            }
        )
    return json.dumps({"summary": summary, "criterion_scores": entries})


def test_criterion_scores_accepts_plain_integer_score():
    result = criterion_scores(parse_response(_response(), known_chunk_ids=("c1",)))
    assert result[0].score == 3


@pytest.mark.parametrize(
    "score", [3.0, "3", "3.5", float("nan"), float("inf"), True, False, 0, 5]
)
def test_criterion_scores_rejects_invalid_scores_safely(score):
    with pytest.raises((AgentExecutionError, ValueError)) as exc:
        parse_response(_response(score=score), known_chunk_ids=("c1",))
    message = str(exc.value)
    if isinstance(exc.value, AgentExecutionError):
        assert "ITSOInvalidScore" in message
        assert "reference:" in message


@pytest.mark.parametrize(
    "field,value", [("evidence", "proof"), ("chunk_ids", "chunk-1")]
)
def test_criterion_scores_rejects_scalar_evidence_and_chunk_ids(field, value):
    with pytest.raises(AgentExecutionError) as exc:
        parse_response(_response(**{field: value}), known_chunk_ids=("c1",))
    assert "ITSOInvalidEvidence" in str(exc.value)


@pytest.mark.parametrize("title", [3, {"name": "title"}, None])
def test_criterion_scores_rejects_non_string_titles(title):
    with pytest.raises(AgentExecutionError) as exc:
        parse_response(_response(**{"criterion_title": title}), known_chunk_ids=("c1",))
    assert "ITSOInvalidCriterion" in str(exc.value)


def test_criterion_scores_preserves_string_title():
    result = criterion_scores(parse_response(_response(), known_chunk_ids=("c1",)))
    assert result[0].criterion_title == ITSO_CRITERIA_TITLES["ITSO-01"]


def test_repair_records_actual_model_without_fallback(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    client = _LLM(["{broken", _response("repaired")])
    result = execution.execute(_context(client))
    assert result.model_name == "primary"
    assert result.provenance["repair_occurred"] is True
    assert result.provenance["fallback_occurred"] is False
    assert len(client.prompts) == 2


def test_semantic_failure_repairs_once(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    client = _LLM(
        [
            json.dumps(
                {
                    "summary": "ok",
                    "criterion_scores": [{"criterion_id": "c1", "score": 0}],
                }
            ),
            _response("repaired"),
        ]
    )
    execution.execute(_context(client))
    assert len(client.prompts) == 2


def test_invalid_repair_is_two_calls_and_dispatch_sanitizes_failure(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    client = _LLM(["{bad", "secret raw"])
    with pytest.raises(AgentExecutionError) as exc:
        execution.execute(_context(client))
    assert len(client.prompts) == 2
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
    client = _LLM(["x" * 4001, "still invalid"])
    with pytest.raises(AgentExecutionError):
        execution.execute(_context(client))
    assert len(client.prompts) == 2
    assert "Prior partial output" not in client.prompts[1]
    assert "x" * 4001 not in client.prompts[1]


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
