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
    ITSO_CRITERIA,
    ITSO_CRITERIA_TITLES,
    collect_advisory_outputs,
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
    result = execution.execute(_context(_LLM([_response("ok")])))
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


@pytest.mark.parametrize("field,value", [("evidence", 123), ("chunk_ids", True)])
def test_criterion_scores_rejects_non_string_scalar_evidence_and_chunk_ids(
    field, value
):
    with pytest.raises(AgentExecutionError) as exc:
        parse_response(_response(**{field: value}), known_chunk_ids=("c1",))
    assert "ITSOInvalidEvidence" in str(exc.value)


def test_root_level_dict_format_parses_cleanly():
    payload = {
        cid: {
            "score": 4,
            "justification": f"Justification for {cid}",
            "chunk_ids": ["c1"],
            "evidence": ["evidence"],
        }
        for cid in ITSO_CRITERIA
    }
    parsed = parse_response(json.dumps(payload), known_chunk_ids=("c1",))
    scores = criterion_scores(parsed, known_chunk_ids=("c1",))
    assert len(scores) == 5
    assert [s.criterion_id for s in scores] == list(ITSO_CRITERIA)
    for s in scores:
        assert s.score == 4
        assert s.justification == f"Justification for {s.criterion_id}"
        assert s.chunk_ids == ("c1",)
        assert s.evidence == ("evidence",)


def test_scalar_string_evidence_and_chunk_ids_normalize_cleanly():
    payload = {
        "summary": "ITSO evaluated",
        "criterion_scores": [
            {
                "criterion_id": cid,
                "criterion_title": ITSO_CRITERIA_TITLES[cid],
                "score": 3,
                "justification": "justification",
                "chunk_ids": "c1",
                "evidence": "evidence text",
            }
            for cid in ITSO_CRITERIA
        ],
    }
    parsed = parse_response(json.dumps(payload), known_chunk_ids=("c1",))
    scores = criterion_scores(parsed, known_chunk_ids=("c1",))
    assert len(scores) == 5
    for s in scores:
        assert s.chunk_ids == ("c1",)
        assert s.evidence == ("evidence text",)


@pytest.mark.parametrize("title", [3, {"name": "title"}, None, "Wrong Title"])
def test_criterion_scores_derives_canonical_title_even_if_altered_or_non_string(title):
    parsed = parse_response(
        _response(**{"criterion_title": title}), known_chunk_ids=("c1",)
    )
    result = criterion_scores(parsed, known_chunk_ids=("c1",))
    assert result[0].criterion_title == ITSO_CRITERIA_TITLES["ITSO-01"]


def test_criterion_scores_preserves_string_title():
    result = criterion_scores(parse_response(_response(), known_chunk_ids=("c1",)))
    assert result[0].criterion_title == ITSO_CRITERIA_TITLES["ITSO-01"]


def test_dict_format_shorthand_scores_parses_cleanly():
    dict_payload = {
        "summary": "ITSO evaluated",
        "criterion_scores": {
            "ITSO-01": 4,
            "ITSO-02": 3,
            "ITSO-03": 4,
            "ITSO-04": 4,
            "ITSO-05": 4,
        },
    }
    parsed = parse_response(json.dumps(dict_payload))
    scores = criterion_scores(parsed)
    assert len(scores) == 5
    assert [s.criterion_id for s in scores] == list(ITSO_CRITERIA)
    for s in scores:
        assert s.criterion_title == ITSO_CRITERIA_TITLES[s.criterion_id]
        assert s.justification == ""
        assert s.chunk_ids == ()
        assert s.evidence == ()
    assert [s.score for s in scores] == [4, 3, 4, 4, 4]


def test_missing_justification_and_evidence_emits_advisory_output():
    dict_payload = {
        "summary": "ITSO evaluated",
        "criterion_scores": {
            "ITSO-01": 4,
            "ITSO-02": 3,
            "ITSO-03": 4,
            "ITSO-04": 4,
            "ITSO-05": 4,
        },
    }
    parsed = parse_response(json.dumps(dict_payload))
    advisory = collect_advisory_outputs(parsed)
    assert advisory is not None
    assert "ungrounded_criteria" in advisory
    assert len(advisory["ungrounded_criteria"]) == 5
    expected_reason = "model score provided without justification or evidence grounding"
    for item in advisory["ungrounded_criteria"]:
        assert item["reason"] == expected_reason
        assert item["advisory_only"] is True


def test_dict_format_with_grounding_does_not_emit_advisory():
    dict_payload = {
        "summary": "ITSO evaluated",
        "criterion_scores": {
            cid: {
                "score": 3,
                "justification": f"Grounded justification for {cid}",
                "chunk_ids": ["c1"],
                "evidence": [f"Evidence for {cid}"],
            }
            for cid in ITSO_CRITERIA
        },
    }
    parsed = parse_response(json.dumps(dict_payload), known_chunk_ids=("c1",))
    advisory = collect_advisory_outputs(parsed)
    assert advisory is None


def test_dict_format_rejects_invalid_score():
    for invalid_score in (5, "four", True, False, 0):
        dict_payload = {
            "summary": "ITSO evaluated",
            "criterion_scores": {
                "ITSO-01": invalid_score,
                "ITSO-02": 3,
                "ITSO-03": 4,
                "ITSO-04": 4,
                "ITSO-05": 4,
            },
        }
        with pytest.raises(AgentExecutionError):
            parse_response(json.dumps(dict_payload))


def test_dict_format_rejects_unknown_chunk_id():
    dict_payload = {
        "summary": "ITSO evaluated",
        "criterion_scores": {
            "ITSO-01": {
                "score": 4,
                "justification": "ok",
                "chunk_ids": ["unknown_chunk"],
            },
            "ITSO-02": {"score": 3},
            "ITSO-03": {"score": 4},
            "ITSO-04": {"score": 4},
            "ITSO-05": {"score": 4},
        },
    }
    with pytest.raises(AgentExecutionError) as exc:
        parse_response(json.dumps(dict_payload), known_chunk_ids=("c1",))
    assert "ITSOUnknownChunk" in str(exc.value)


def test_justification_without_evidence_or_chunks_is_flagged_ungrounded():
    # A score with a justification but no source grounding (empty evidence and
    # chunk_ids) must still be flagged for review, not treated as grounded.
    raw = _response(evidence=[])
    parsed = parse_response(raw, known_chunk_ids=("c1",))
    advisory = collect_advisory_outputs(parsed)
    assert advisory is not None
    assert len(advisory["ungrounded_criteria"]) == 5


def test_criterion_extra_field_rejected():
    raw = _response(unexpected="value")
    with pytest.raises(AgentExecutionError) as exc:
        parse_response(raw, known_chunk_ids=("c1",))
    assert "ITSOInvalidCriterion" in str(exc.value)


class _DowngradeLLM:
    model = "primary"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def generate_result(
        self, prompt, *, temperature, max_new_tokens, deadline, response_contract
    ):
        self.prompts.append(prompt)
        return CompletionResult(
            next(self.responses),
            "primary",
            10,
            20,
            30,
            "stop",
            attempts=1,
            response_format_downgraded=True,
        )


def test_execution_propagates_response_format_downgraded(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    result = execution.execute(_context(_DowngradeLLM([_response("ok")])))
    assert result.provenance["response_format_downgraded"] is True


def test_execution_succeeds_on_attempt_0_for_shorthand_dict(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    dict_response = json.dumps(
        {
            "summary": "shorthand response",
            "criterion_scores": {
                "ITSO-01": 4,
                "ITSO-02": 3,
                "ITSO-03": 4,
                "ITSO-04": 4,
                "ITSO-05": 4,
            },
        }
    )
    client = _LLM([dict_response])
    result = execution.execute(_context(client))
    assert result.success is True
    assert result.provenance["repair_occurred"] is False
    assert len(client.prompts) == 1
    assert result.advisory_outputs is not None
    assert len(result.advisory_outputs["ungrounded_criteria"]) == 5
    assert len(result.criterion_scores) == 5


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
