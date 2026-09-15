"""ITSO execution and response handling tests."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.contracts import (
    AdvisoryOutput,
    AgentEvaluationResult,
    UngroundedCriterionAdvisory,
)
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
from server.tests.agents.itso.conftest_helper import make_itso_test_snapshot


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


def _context(client, form_snapshot=None, evaluation_id=None, **kwargs):
    eval_id = evaluation_id or uuid4()
    snapshot = (
        form_snapshot
        if form_snapshot is not None
        else make_itso_test_snapshot(evaluation_id=eval_id)
    )
    return ITSOExecutionContext(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "page_number": 1, "text": "security"},),
        form_snapshot=snapshot,
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
    client = _LLM([_response("ok")])
    result = execution.execute(_context(client))
    assert result.prompt_text is None
    assert result.raw_response is None
    assert '"agent": "itso"' in client.prompts[0]
    assert '"criterion_scores"' not in client.prompts[0]


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
        entry = {
            "criterion_id": criterion_id,
            "criterion_title": ITSO_CRITERIA_TITLES[criterion_id],
            "score": score,
            "justification": "justification",
            "chunk_ids": ["c1"],
            "evidence": ["security"],
        }
        entry.update(overrides)
        entries.append(entry)
    return json.dumps({"summary": summary, "criterion_scores": entries})


def test_criterion_scores_accepts_plain_integer_score():
    result = criterion_scores(
        parse_response(
            _response(), known_chunk_ids=("c1",), packed_chunk_map={"c1": "security"}
        ),
        known_chunk_ids=("c1",),
        packed_chunk_map={"c1": "security"},
    )
    assert result[0].score == 3


@pytest.mark.parametrize(
    "score", [3.0, "3", "3.5", float("nan"), float("inf"), True, False, 0, 5]
)
def test_criterion_scores_rejects_invalid_scores_safely(score):
    with pytest.raises((AgentExecutionError, ValueError)) as exc:
        parse_response(
            _response(score=score),
            known_chunk_ids=("c1",),
            packed_chunk_map={"c1": "security"},
        )
    message = str(exc.value)
    if isinstance(exc.value, AgentExecutionError):
        assert "ITSOInvalidScore" in message
        assert "reference:" in message


@pytest.mark.parametrize("field,value", [("evidence", 123), ("chunk_ids", True)])
def test_criterion_scores_rejects_non_string_scalar_evidence_and_chunk_ids(
    field, value
):
    with pytest.raises(AgentExecutionError) as exc:
        parse_response(
            _response(**{field: value}),
            known_chunk_ids=("c1",),
            packed_chunk_map={"c1": "security"},
        )
    assert "ITSOInvalidEvidence" in str(exc.value)


def test_root_level_dict_format_parses_cleanly():
    payload = {
        cid: {
            "score": 4,
            "justification": f"Justification for {cid}",
            "chunk_ids": ["c1"],
            "evidence": ["security"],
        }
        for cid in ITSO_CRITERIA
    }
    parsed = parse_response(
        json.dumps(payload),
        known_chunk_ids=("c1",),
        packed_chunk_map={"c1": "security"},
    )
    scores = criterion_scores(
        parsed,
        known_chunk_ids=("c1",),
        packed_chunk_map={"c1": "security"},
    )
    assert len(scores) == 5
    assert [s.criterion_id for s in scores] == list(ITSO_CRITERIA)
    for s in scores:
        assert s.score == 4
        assert s.justification == f"Justification for {s.criterion_id}"
        assert s.chunk_ids == ("c1",)
        assert s.evidence == ("security",)


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
                "evidence": "security",
            }
            for cid in ITSO_CRITERIA
        ],
    }
    parsed = parse_response(
        json.dumps(payload),
        known_chunk_ids=("c1",),
        packed_chunk_map={"c1": "security"},
    )
    scores = criterion_scores(
        parsed,
        known_chunk_ids=("c1",),
        packed_chunk_map={"c1": "security"},
    )
    assert len(scores) == 5
    for s in scores:
        assert s.chunk_ids == ("c1",)
        assert s.evidence == ("security",)


@pytest.mark.parametrize("title", [3, {"name": "title"}, None, "Wrong Title"])
def test_criterion_scores_derives_canonical_title_even_if_altered_or_non_string(title):
    parsed = parse_response(
        _response(**{"criterion_title": title}),
        known_chunk_ids=("c1",),
        packed_chunk_map={"c1": "security"},
    )
    result = criterion_scores(
        parsed,
        known_chunk_ids=("c1",),
        packed_chunk_map={"c1": "security"},
    )
    assert result[0].criterion_title == ITSO_CRITERIA_TITLES["ITSO-01"]


def test_criterion_scores_preserves_string_title():
    result = criterion_scores(
        parse_response(
            _response(),
            known_chunk_ids=("c1",),
            packed_chunk_map={"c1": "security"},
        ),
        known_chunk_ids=("c1",),
        packed_chunk_map={"c1": "security"},
    )
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
    assert isinstance(advisory, AdvisoryOutput)
    assert len(advisory.ungrounded_criteria) == 5
    expected_reason = "model score provided without justification or evidence grounding"
    for item in advisory.ungrounded_criteria:
        assert isinstance(item, UngroundedCriterionAdvisory)
        assert item.reason == expected_reason
        assert item.advisory_only is True
    # Verify to_dict output
    as_dict = advisory.to_dict()
    assert "ungrounded_criteria" in as_dict
    assert len(as_dict["ungrounded_criteria"]) == 5
    assert as_dict["ungrounded_criteria"][0] == {
        "criterion_id": "ITSO-01",
        "reason": expected_reason,
        "advisory_only": True,
    }


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
    assert isinstance(advisory, AdvisoryOutput)
    assert len(advisory.ungrounded_criteria) == 5


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
    assert isinstance(result.advisory_outputs, AdvisoryOutput)
    assert len(result.advisory_outputs.ungrounded_criteria) == 5
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


def test_advisory_contract_validation_and_immutability():
    item = UngroundedCriterionAdvisory(
        criterion_id="ITSO-01",
        reason="Reason text",
        advisory_only=True,
    )
    with pytest.raises(AttributeError):
        item.criterion_id = "ITSO-02"  # type: ignore[misc]

    advisory = AdvisoryOutput(ungrounded_criteria=(item,))
    with pytest.raises(AttributeError):
        advisory.ungrounded_criteria = ()  # type: ignore[misc]

    # Serialization and round trip
    dumped = advisory.to_dict()
    assert dumped == {
        "ungrounded_criteria": [
            {
                "criterion_id": "ITSO-01",
                "reason": "Reason text",
                "advisory_only": True,
            }
        ]
    }
    loaded = AdvisoryOutput.from_dict(dumped)
    assert loaded == advisory

    # Rejection of whitespace / untrimmed fields
    with pytest.raises(ValueError, match="whitespace"):
        UngroundedCriterionAdvisory(
            criterion_id="  ITSO-01  ",
            reason="Reason text",
            advisory_only=True,
        )
    with pytest.raises(ValueError, match="whitespace"):
        UngroundedCriterionAdvisory(
            criterion_id="ITSO-01",
            reason="  Reason text  ",
            advisory_only=True,
        )

    # Validation: blank or oversized criterion_id
    with pytest.raises(ValueError, match="criterion_id"):
        UngroundedCriterionAdvisory(criterion_id="", reason="Valid")
    with pytest.raises(ValueError, match="criterion_id"):
        UngroundedCriterionAdvisory(criterion_id="   ", reason="Valid")
    with pytest.raises(ValueError, match="criterion_id"):
        UngroundedCriterionAdvisory(criterion_id="a" * 51, reason="Valid")

    # Validation: blank or oversized reason
    with pytest.raises(ValueError, match="reason"):
        UngroundedCriterionAdvisory(criterion_id="ITSO-01", reason="")
    with pytest.raises(ValueError, match="reason"):
        UngroundedCriterionAdvisory(criterion_id="ITSO-01", reason="   ")
    with pytest.raises(ValueError, match="reason"):
        UngroundedCriterionAdvisory(criterion_id="ITSO-01", reason="a" * 2001)

    # Validation: advisory_only must be literal True
    with pytest.raises(ValueError, match="advisory_only"):
        UngroundedCriterionAdvisory(
            criterion_id="ITSO-01",
            reason="Valid",
            advisory_only=False,  # type: ignore[arg-type]
        )

    # Validation: AdvisoryOutput constructor requires tuple, rejects mutable list
    with pytest.raises(ValueError, match="must be a tuple"):
        AdvisoryOutput(ungrounded_criteria=[item])  # type: ignore[arg-type]

    # Validation: item count 1..100
    with pytest.raises(ValueError, match="between 1 and 100"):
        AdvisoryOutput(ungrounded_criteria=())
    many_items = tuple(
        UngroundedCriterionAdvisory(criterion_id=f"C-{i}", reason="r")
        for i in range(101)
    )
    with pytest.raises(ValueError, match="between 1 and 100"):
        AdvisoryOutput(ungrounded_criteria=many_items)

    # Validation: duplicate criterion IDs rejected
    dup_items = (
        UngroundedCriterionAdvisory(criterion_id="ITSO-01", reason="r1"),
        UngroundedCriterionAdvisory(criterion_id="ITSO-01", reason="r2"),
    )
    with pytest.raises(ValueError, match="duplicate criterion IDs"):
        AdvisoryOutput(ungrounded_criteria=dup_items)

    # Validation: unknown keys / missing keys in from_dict rejected without leak
    secret_key = "SECRET_LEAK_KEY"
    with pytest.raises(ValueError) as exc:
        AdvisoryOutput.from_dict({"ungrounded_criteria": [], secret_key: 1})
    assert secret_key not in str(exc.value)
    assert "exact key required" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        UngroundedCriterionAdvisory.from_dict(
            {
                "criterion_id": "ITSO-01",
                "reason": "r",
                "advisory_only": True,
                secret_key: 3,
            }
        )
    assert secret_key not in str(exc.value)
    assert "exact keys required" in str(exc.value)

    # Validation: from_dict requires missing advisory_only or other required keys
    with pytest.raises(ValueError, match="exact keys required"):
        UngroundedCriterionAdvisory.from_dict(
            {"criterion_id": "ITSO-01", "reason": "r"}
        )
    with pytest.raises(ValueError, match="exact key required"):
        AdvisoryOutput.from_dict({})

    # Validation: AdvisoryOutput.from_dict rejects tuple and requires list
    with pytest.raises(ValueError, match="must be a list"):
        AdvisoryOutput.from_dict({"ungrounded_criteria": (item.to_dict(),)})


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


def test_itso_fails_boundedly_on_missing_or_invalid_snapshot():
    eval_id = uuid4()
    context_no_snap = ITSOExecutionContext(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "text": "sec"},),
        form_snapshot=None,
    )
    with pytest.raises(AgentExecutionError, match="EvaluationFormSnapshotDTO"):
        execution.execute(context_no_snap)

    # Snapshot with wrong agent_id
    wrong_agent_snap = make_itso_test_snapshot(
        eval_id, agent_id="sme", adapter_key="sme"
    )
    context_wrong_agent = ITSOExecutionContext(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "text": "sec"},),
        form_snapshot=wrong_agent_snap,
    )
    with pytest.raises(AgentExecutionError, match="agent_id"):
        execution.execute(context_wrong_agent)

    # Snapshot with adapter mismatch
    wrong_adapter_snap = make_itso_test_snapshot(eval_id, adapter_key="other_adapter")
    context_wrong_adapter = ITSOExecutionContext(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "text": "sec"},),
        form_snapshot=wrong_adapter_snap,
    )
    with pytest.raises(AgentExecutionError, match="adapter_key"):
        execution.execute(context_wrong_adapter)

    # Snapshot with evaluation_id mismatch
    itso_snap_other_eval = make_itso_test_snapshot(evaluation_id=uuid4())
    context_wrong_eval = ITSOExecutionContext(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "text": "sec"},),
        form_snapshot=itso_snap_other_eval,
    )
    with pytest.raises(AgentExecutionError, match="evaluation_id"):
        execution.execute(context_wrong_eval)


def test_itso_novel_subset_reorder_and_title_edits(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    eval_id = uuid4()

    # Novel criteria, reordered, custom titles
    specs = (
        ("ITSO-CUSTOM-02", "Custom Title Two"),
        ("ITSO-CUSTOM-01", "Custom Title One"),
    )
    snapshot = make_itso_test_snapshot(evaluation_id=eval_id, criteria_specs=specs)

    resp_json = json.dumps(
        {
            "summary": "Custom evaluation summary",
            "criterion_scores": [
                {
                    "criterion_id": "ITSO-CUSTOM-02",
                    "criterion_title": "Custom Title Two",
                    "score": 4,
                    "justification": "Justification for 2",
                    "chunk_ids": ["c1"],
                    "evidence": ["security"],
                },
                {
                    "criterion_id": "ITSO-CUSTOM-01",
                    "criterion_title": "Custom Title One",
                    "score": 2,
                    "justification": "Justification for 1",
                    "chunk_ids": ["c1"],
                    "evidence": ["security"],
                },
            ],
        }
    )

    client = _LLM([resp_json])
    context = _context(client, form_snapshot=snapshot, evaluation_id=eval_id)
    result = execution.execute(context)

    assert result.success
    assert len(result.criterion_scores) == 2
    assert result.criterion_scores[0].criterion_id == "ITSO-CUSTOM-02"
    assert result.criterion_scores[0].criterion_title == "Custom Title Two"
    assert result.criterion_scores[0].score == 4
    assert result.criterion_scores[1].criterion_id == "ITSO-CUSTOM-01"
    assert result.criterion_scores[1].criterion_title == "Custom Title One"
    assert result.criterion_scores[1].score == 2
    assert result.subtotal == 3.0
    assert result.prompt_text is None
    assert result.raw_response is None
    assert "ITSO-CUSTOM-02 = Custom Title Two" in client.prompts[0]
    assert "ITSO-CUSTOM-01 = Custom Title One" in client.prompts[0]


def test_itso_no_worker_db_or_chroma_fallback(monkeypatch):
    """Ensure worker execution does not call rubric DB or Chroma retrieval fallback."""
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    eval_id = uuid4()
    client = _LLM([_response("ok")])

    # No precomputed rubric_itso, no syllabus or curriculum
    context = _context(
        client,
        evaluation_id=eval_id,
        precomputed_context={},
        reference_document_ids={"syllabus": uuid4()},
    )
    result = execution.execute(context)
    assert result.success
    assert result.metadata["rubric_context_size"] == 0
    assert result.metadata["reference_context_size"] == 0
    assert result.prompt_text is None
    assert result.raw_response is None
    assert "rubric_context" not in json.loads(client.prompts[0])


def test_parse_response_rejects_duplicate_json_keys():
    raw_dup = (
        '{"summary": "ok", "summary": "duplicate", '
        '"criterion_scores": {"ITSO-01": 4, "ITSO-02": 4, "ITSO-03": 4}}'
    )
    with pytest.raises(AgentExecutionError, match="ITSODuplicateKey"):
        parse_response(raw_dup)


def test_list_form_criterion_scores_rejects_out_of_order_elements():
    """List-form scores must strictly adhere to expected criterion position index."""
    reordered_list = [
        {
            "criterion_id": "ITSO-02",
            "criterion_title": ITSO_CRITERIA_TITLES["ITSO-02"],
            "score": 3,
            "justification": "just",
            "chunk_ids": [],
            "evidence": ["ev"],
        },
        {
            "criterion_id": "ITSO-01",
            "criterion_title": ITSO_CRITERIA_TITLES["ITSO-01"],
            "score": 3,
            "justification": "just",
            "chunk_ids": [],
            "evidence": ["ev"],
        },
        {
            "criterion_id": "ITSO-03",
            "criterion_title": ITSO_CRITERIA_TITLES["ITSO-03"],
            "score": 3,
            "justification": "just",
            "chunk_ids": [],
            "evidence": ["ev"],
        },
        {
            "criterion_id": "ITSO-04",
            "criterion_title": ITSO_CRITERIA_TITLES["ITSO-04"],
            "score": 3,
            "justification": "just",
            "chunk_ids": [],
            "evidence": ["ev"],
        },
        {
            "criterion_id": "ITSO-05",
            "criterion_title": ITSO_CRITERIA_TITLES["ITSO-05"],
            "score": 3,
            "justification": "just",
            "chunk_ids": [],
            "evidence": ["ev"],
        },
    ]
    raw = json.dumps({"summary": "reordered", "criterion_scores": reordered_list})
    with pytest.raises(AgentExecutionError, match="ITSOInvalidCriterion"):
        parse_response(raw)


def test_evidence_rejects_whitespace_only_or_untrimmed():
    """Whitespace-only and untrimmed evidence items must be rejected."""
    with pytest.raises(AgentExecutionError, match="ITSOInvalidEvidence"):
        parse_response(_response(evidence=["   "]))
    with pytest.raises(AgentExecutionError, match="ITSOInvalidEvidence"):
        parse_response(_response(evidence=["  untrimmed  "]))
    with pytest.raises(AgentExecutionError, match="ITSOInvalidEvidence"):
        parse_response(_response(chunk_ids=["  c1  "]))


def test_agent_llm_error_non_truncation_raises_without_repair(monkeypatch):
    """Only AgentLLMError truncation triggers repair; other errors raise."""
    from server.modules.agents.exceptions import AgentLLMError

    class _ErrorLLM:
        def generate_result(self, *args, **kwargs):
            raise AgentLLMError("API connection failed")

    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    context = _context(_ErrorLLM())
    with pytest.raises(AgentLLMError, match="API connection failed"):
        execution.execute(context)


def test_duplicate_chunk_ids_fail_before_llm(monkeypatch):
    """Duplicate chunk IDs in chunk_infos must be rejected before packing."""
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    client = _LLM([_response("ok")])
    eval_id = uuid4()
    context = ITSOExecutionContext(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=(
            {"chunk_id": "c1", "text": "security one"},
            {"chunk_id": "c1", "text": "security two"},
        ),
        form_snapshot=make_itso_test_snapshot(evaluation_id=eval_id),
        llm_client=client,
    )
    with pytest.raises(AgentExecutionError, match="Duplicate chunk ID"):
        execution.execute(context)
    assert len(client.prompts) == 0


def test_omitted_chunk_citation_fails(monkeypatch):
    """Citing a chunk that was omitted during packing must fail."""
    settings_obj = _settings()
    settings_obj.agent_max_chunks = 2
    settings_obj.agent_small_doc_threshold = 1

    monkeypatch.setattr(execution, "get_settings", lambda: settings_obj)
    eval_id = uuid4()
    # c3 will be dropped because max_chunks=2 and c1/c2 match domain keywords
    chunk_infos = (
        {"chunk_id": "c1", "text": "security data protection 1"},
        {"chunk_id": "c2", "text": "security data protection 2"},
        {"chunk_id": "c3", "text": "irrelevant text without keywords"},
    )
    # Model attempts to cite omitted chunk c3
    resp = json.dumps(
        {
            "summary": "evaluation",
            "criterion_scores": [
                {
                    "criterion_id": cid,
                    "criterion_title": ITSO_CRITERIA_TITLES[cid],
                    "score": 3,
                    "justification": "justification",
                    "chunk_ids": ["c3"],
                    "evidence": ["irrelevant"],
                }
                for cid in ITSO_CRITERIA
            ],
        }
    )
    client = _LLM([resp, resp])
    context = ITSOExecutionContext(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=chunk_infos,
        form_snapshot=make_itso_test_snapshot(evaluation_id=eval_id),
        llm_client=client,
    )
    with pytest.raises(AgentExecutionError, match="ITSOUnknownChunk"):
        execution.execute(context)


def test_foreign_chunk_id_fails(monkeypatch):
    """Citing a foreign chunk ID unknown to the packed prompt must fail."""
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    resp = json.dumps(
        {
            "summary": "evaluation",
            "criterion_scores": [
                {
                    "criterion_id": cid,
                    "criterion_title": ITSO_CRITERIA_TITLES[cid],
                    "score": 3,
                    "justification": "justification",
                    "chunk_ids": ["foreign_chunk_999"],
                    "evidence": ["security"],
                }
                for cid in ITSO_CRITERIA
            ],
        }
    )
    client = _LLM([resp, resp])
    context = _context(client)
    with pytest.raises(AgentExecutionError, match="ITSOUnknownChunk"):
        execution.execute(context)


def test_arbitrary_evidence_not_contained_in_cited_packed_chunk_fails(monkeypatch):
    """Evidence excerpt not in cited packed chunk must fail."""
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    resp = json.dumps(
        {
            "summary": "evaluation",
            "criterion_scores": [
                {
                    "criterion_id": cid,
                    "criterion_title": ITSO_CRITERIA_TITLES[cid],
                    "score": 3,
                    "justification": "justification",
                    "chunk_ids": ["c1"],
                    "evidence": ["fabricated quote not in chunk text"],
                }
                for cid in ITSO_CRITERIA
            ],
        }
    )
    client = _LLM([resp, resp])
    context = _context(client)
    with pytest.raises(AgentExecutionError, match="ITSOInvalidEvidence"):
        execution.execute(context)


def test_valid_exact_quote_passes(monkeypatch):
    """Exact substring quote from cited packed chunk must succeed."""
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    exact_quote = "security credentials must be encrypted"
    eval_id = uuid4()
    context = ITSOExecutionContext(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=(
            {
                "chunk_id": "c1",
                "text": f"Document header. {exact_quote}. Footer.",
            },
        ),
        form_snapshot=make_itso_test_snapshot(evaluation_id=eval_id),
    )
    resp = json.dumps(
        {
            "summary": "grounded evaluation",
            "criterion_scores": [
                {
                    "criterion_id": cid,
                    "criterion_title": ITSO_CRITERIA_TITLES[cid],
                    "score": 4,
                    "justification": f"Verified in chunk: {exact_quote}",
                    "chunk_ids": ["c1"],
                    "evidence": [exact_quote],
                }
                for cid in ITSO_CRITERIA
            ],
        }
    )
    client = _LLM([resp])
    context = ITSOExecutionContext(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=(
            {
                "chunk_id": "c1",
                "text": f"Document header. {exact_quote}. Footer.",
            },
        ),
        form_snapshot=make_itso_test_snapshot(evaluation_id=eval_id),
        llm_client=client,
    )
    result = execution.execute(context)
    assert result.success is True
    assert len(result.criterion_scores) == 5
    assert result.criterion_scores[0].evidence == (exact_quote,)
    assert result.criterion_scores[0].chunk_ids == ("c1",)
    assert result.advisory_outputs is None


@pytest.mark.parametrize(
    "marker",
    [
        "...",
        "[...]",
        "…",
        "[omitted]",
        "[ellipsis]",
        "<omitted>",
        "(omitted)",
        "[deleted]",
        "[text omitted]",
    ],
)
def test_marker_evidence_fails(marker):
    """Synthetic omission markers in evidence must be rejected."""
    with pytest.raises(AgentExecutionError, match="ITSOInvalidEvidence"):
        parse_response(
            _response(evidence=[marker]),
            known_chunk_ids=("c1",),
            packed_chunk_map={"c1": "security"},
        )


def test_evidence_without_cited_chunk_fails():
    """Nonblank evidence with empty chunk_ids must be rejected."""
    with pytest.raises(AgentExecutionError, match="ITSOInvalidEvidence"):
        parse_response(
            _response(chunk_ids=[], evidence=["security"]),
            known_chunk_ids=("c1",),
            packed_chunk_map={"c1": "security"},
        )


def test_advisory_output_remains_correct_for_ungrounded_and_grounded_mix(monkeypatch):
    """ITSO advisory output correctly records only ungrounded criteria."""
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    resp = json.dumps(
        {
            "summary": "mixed evaluation",
            "criterion_scores": [
                {
                    "criterion_id": "ITSO-01",
                    "criterion_title": ITSO_CRITERIA_TITLES["ITSO-01"],
                    "score": 4,
                    "justification": "Grounded justification",
                    "chunk_ids": ["c1"],
                    "evidence": ["security"],
                },
                {
                    "criterion_id": "ITSO-02",
                    "criterion_title": ITSO_CRITERIA_TITLES["ITSO-02"],
                    "score": 4,
                    "justification": "Grounded justification",
                    "chunk_ids": ["c1"],
                    "evidence": ["security"],
                },
                {
                    "criterion_id": "ITSO-03",
                    "criterion_title": ITSO_CRITERIA_TITLES["ITSO-03"],
                    "score": 2,
                    "justification": "",
                    "chunk_ids": [],
                    "evidence": [],
                },
                {
                    "criterion_id": "ITSO-04",
                    "criterion_title": ITSO_CRITERIA_TITLES["ITSO-04"],
                    "score": 2,
                    "justification": "",
                    "chunk_ids": [],
                    "evidence": [],
                },
                {
                    "criterion_id": "ITSO-05",
                    "criterion_title": ITSO_CRITERIA_TITLES["ITSO-05"],
                    "score": 2,
                    "justification": "",
                    "chunk_ids": [],
                    "evidence": [],
                },
            ],
        }
    )
    client = _LLM([resp])
    context = _context(client)
    result = execution.execute(context)
    assert result.success is True
    assert result.advisory_outputs is not None
    ungrounded_ids = {
        u.criterion_id for u in result.advisory_outputs.ungrounded_criteria
    }
    assert ungrounded_ids == {"ITSO-03", "ITSO-04", "ITSO-05"}


def test_itso_prompt_and_raw_response_are_none_and_persistence_invariant(monkeypatch):
    """ITSO live result must emit None prompt/raw response and builder enforces it."""
    from server.modules.synthesis.exceptions import EvaluationResultIntegrityError
    from server.modules.synthesis.result_integrity import build_persistable_agent_result

    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    client = _LLM([_response("ok")])
    eval_id = uuid4()
    snapshot = make_itso_test_snapshot(evaluation_id=eval_id)
    context = _context(client, form_snapshot=snapshot, evaluation_id=eval_id)
    result = execution.execute(context)

    # Live execution result has None for prompt_text and raw_response
    assert result.prompt_text is None
    assert result.raw_response is None

    # Valid build_persistable_agent_result
    persistable = build_persistable_agent_result(result, snapshot)
    assert persistable.prompt_text is None
    assert persistable.raw_response is None

    # ITSO success with prompt_text is rejected
    tampered_prompt = AgentEvaluationResult(
        agent_name=result.agent_name,
        evaluation_id=result.evaluation_id,
        document_id=result.document_id,
        subtotal=result.subtotal,
        criterion_scores=result.criterion_scores,
        prompt_version_id=result.prompt_version_id,
        summary=result.summary,
        model_name=result.model_name,
        processing_seconds=result.processing_seconds,
        token_count=result.token_count,
        success=True,
        error_message=None,
        raw_response=None,
        prompt_text="leaked prompt text",
        provenance=result.provenance,
        advisory_outputs=result.advisory_outputs,
        metadata=result.metadata,
    )
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="must not contain raw_response or prompt_text",
    ):
        build_persistable_agent_result(tampered_prompt, snapshot)

    # ITSO success with raw_response is rejected
    tampered_raw = AgentEvaluationResult(
        agent_name=result.agent_name,
        evaluation_id=result.evaluation_id,
        document_id=result.document_id,
        subtotal=result.subtotal,
        criterion_scores=result.criterion_scores,
        prompt_version_id=result.prompt_version_id,
        summary=result.summary,
        model_name=result.model_name,
        processing_seconds=result.processing_seconds,
        token_count=result.token_count,
        success=True,
        error_message=None,
        raw_response="leaked raw response",
        prompt_text=None,
        provenance=result.provenance,
        advisory_outputs=result.advisory_outputs,
        metadata=result.metadata,
    )
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="must not contain raw_response or prompt_text",
    ):
        build_persistable_agent_result(tampered_raw, snapshot)
