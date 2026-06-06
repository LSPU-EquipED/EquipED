"""Tests for base agent response parsing and concrete agent instantiation."""

from __future__ import annotations

import json
from uuid import uuid4

from server.modules.agents.contracts import CriterionScore
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.exceptions import AgentLLMError
from server.modules.agents.coordinator import Coordinator
from server.modules.agents.gad import GAD
from server.modules.agents.itso import ITSO
from server.modules.agents.sme import SME

from .conftest import _DummyAgent, _FakeLLM, _RawLLM, _RetrievedChunk, _mock_settings


def test_base_agent_parses_mock_llm_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "strong coverage",
                "criterion_scores": [
                    {
                        "criterion_id": "c1",
                        "criterion_title": "Criterion 1",
                        "score": 4,
                        "justification": "supported",
                        "chunk_ids": ["chunk-1"],
                        "evidence": ["evidence-1"],
                    }
                ],
            }
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert result.agent_name == "dummy"
    assert result.criterion_count == 1
    assert result.subtotal == 4
    assert result.summary == "strong coverage"


def test_base_agent_parses_fenced_json_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    raw_response = (
        "```json\n"
        "{\n"
        '  "summary": "wrapped",\n'
        '  "criterion_scores": [\n'
        '    {\n'
        '      "criterion_id": "c1",\n'
        '      "score": 2,\n'
        '      "justification": "ok"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "```"
    )
    agent = _DummyAgent(llm_client=_RawLLM(raw_response))

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert result.summary == "wrapped"
    assert result.criterion_count == 1


def test_base_agent_coerces_non_string_justification(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    raw_response = (
        '{"summary": "bad", "criterion_scores": '
        '[{"criterion_id": "c1", "score": 3, "justification": 123}]}'
    )
    agent = _DummyAgent(llm_client=_RawLLM(raw_response))

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
    )

    assert result.criterion_scores[0].justification == "123"


def test_base_agent_accepts_integer_like_float_scores(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "float score",
                "criterion_scores": [
                    {
                        "criterion_id": "c1",
                        "criterion_title": "Criterion 1",
                        "score": 3.0,
                        "justification": "rounded",
                    }
                ],
            }
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert result.criterion_scores[0].score == 3


def test_base_agent_rejects_non_integral_float_scores(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "float score",
                "criterion_scores": [
                    {
                        "criterion_id": "c1",
                        "score": 3.5,
                        "justification": "rounded",
                    }
                ],
            }
        )
    )

    try:
        agent.run(
            evaluation_id=uuid4(),
            document_id=uuid4(),
            chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
            context_text="Syllabus text",
            reference_document_ids={"syllabus": uuid4()},
        )
        raise AssertionError("expected AgentExecutionError")
    except AgentExecutionError:
        pass


def test_base_agent_accepts_numeric_string_scores(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "string score",
                "criterion_scores": [
                    {
                        "criterion_id": "c1",
                        "score": "3.0",
                        "justification": "parsed",
                    }
                ],
            }
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert result.criterion_scores[0].score == 3


def test_base_agent_rejects_boolean_and_non_numeric_string_scores(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    for bad_score in (True, "three"):
        agent = _DummyAgent(
            llm_client=_FakeLLM(
                {
                    "summary": "bad score",
                    "criterion_scores": [
                        {
                            "criterion_id": "c1",
                            "score": bad_score,
                            "justification": "invalid",
                        }
                    ],
                }
            )
        )

        try:
            agent.run(
                evaluation_id=uuid4(),
                document_id=uuid4(),
                chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
                context_text="Syllabus text",
                reference_document_ids={"syllabus": uuid4()},
            )
            raise AssertionError("expected AgentExecutionError")
        except AgentExecutionError:
            pass


def test_base_agent_preserves_llm_error_message(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    class _BoomLLM:
        def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
            raise RuntimeError("HTTP 500: prompt too long")

    agent = _DummyAgent(llm_client=_BoomLLM())

    try:
        agent.run(
            evaluation_id=uuid4(),
            document_id=uuid4(),
            chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
            context_text="Syllabus text",
            reference_document_ids={"syllabus": uuid4()},
        )
        raise AssertionError("expected AgentExecutionError")
    except AgentLLMError as exc:
        assert "HTTP 500: prompt too long" in str(exc)


def test_base_agent_extracts_json_from_prefixed_text(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    raw_response = (
        "Here is the result:\n"
        '{"summary":"ok","criterion_scores":[{"criterion_id":"c1","score":3,"justification":"good"}]}'
    )
    agent = _DummyAgent(llm_client=_RawLLM(raw_response))

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert result.summary == "ok"
    assert result.criterion_scores[0].score == 3


def test_base_agent_accepts_dict_criterion_scores(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "dict format",
                "criterion_scores": {
                    "Content accuracy": 4,
                    "Relevance": "3",
                },
            }
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert [score.criterion_id for score in result.criterion_scores] == [
        "Content accuracy",
        "Relevance",
    ]
    assert [score.score for score in result.criterion_scores] == [4, 3]


def test_base_agent_accepts_nested_dict_criterion_scores(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "nested dict format",
                "criterion_scores": {
                    "Content accuracy": {
                        "score": 4,
                        "justification": "accurate",
                        "evidence": "supported",
                        "chunk_ids": ["chunk-1"],
                    }
                },
            }
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert result.criterion_scores[0].criterion_id == "Content accuracy"
    assert result.criterion_scores[0].score == 4
    assert result.criterion_scores[0].justification == "accurate"
    assert result.criterion_scores[0].evidence == ("supported",)
    assert result.criterion_scores[0].chunk_ids == ("chunk-1",)


def test_base_agent_tolerates_string_evidence_and_missing_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "evidence tolerance",
                "criterion_scores": [
                    {
                        "criterion_id": "c1",
                        "score": 4,
                        "justification": 123,
                        "chunk_ids": "chunk-1",
                        "evidence": "evidence-1",
                    },
                    {
                        "criterion_id": "c2",
                        "score": 3,
                        "justification": None,
                    },
                ],
            }
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert result.criterion_scores[0].justification == "123"
    assert result.criterion_scores[0].chunk_ids == ("chunk-1",)
    assert result.criterion_scores[0].evidence == ("evidence-1",)
    assert result.criterion_scores[1].justification == "None"
    assert result.criterion_scores[1].chunk_ids == ()
    assert result.criterion_scores[1].evidence == ()


def test_concrete_agents_use_mocked_llm_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("context chunk")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    fake_llm = _FakeLLM(
        {
            "summary": "ok",
            "criterion_scores": [
                {
                    "criterion_id": "c1",
                    "criterion_title": "Criterion 1",
                    "score": 3,
                    "justification": "grounded",
                    "chunk_ids": ["chunk-1"],
                    "evidence": ["evidence-1"],
                }
            ],
        }
    )

    for agent in [
        SME(llm_client=fake_llm),
        Coordinator(llm_client=fake_llm),
        GAD(llm_client=fake_llm),
        ITSO(llm_client=fake_llm),
    ]:
        result = agent.run(
            evaluation_id=uuid4(),
            document_id=uuid4(),
            chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}],
            context_text="reference context",
            reference_document_ids={"syllabus": uuid4(), "curriculum": uuid4()},
        )
        assert result.agent_name == agent.agent_name
        assert result.criterion_count == 1
        assert result.summary == "ok"


# ------------------------------------------------------------------
# JSON parse retry / recovery (stability fix for truncated responses)
# ------------------------------------------------------------------


class _SequenceLLM:
    """LLM fake that returns different strings on each call.

    Records the prompts it receives so tests can assert that the repair
    call wraps the prior partial output in the concise repair template.
    """

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("LLM called more times than expected")
        return self.responses.pop(0)


def test_base_agent_retries_on_truncated_json(monkeypatch) -> None:
    """A truncated JSON response should trigger a single repair call,
    and the repaired response should be used downstream."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    truncated = (
        '{"summary": "partial", "criterion_scores": ['
        '{"criterion_id": "c1", "score": 3, "justification": "ok"'
    )  # No closing brackets → invalid JSON
    valid_json = json.dumps(
        {
            "summary": "recovered",
            "criterion_scores": [
                {
                    "criterion_id": "c1",
                    "criterion_title": "Criterion 1",
                    "score": 3,
                    "justification": "grounded",
                    "chunk_ids": ["chunk-1"],
                    "evidence": ["evidence-1"],
                }
            ],
        }
    )
    llm = _SequenceLLM([truncated, valid_json])
    agent = _DummyAgent(llm_client=llm)

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
        reference_document_ids={"syllabus": uuid4()},
    )

    # LLM was called twice: original + repair
    assert len(llm.prompts) == 2
    # Repair prompt wraps the partial output
    assert "Prior partial output" in llm.prompts[1]
    assert truncated in llm.prompts[1]
    # Parsed result comes from the repaired (second) response
    assert result.summary == "recovered"
    assert result.criterion_count == 1
    # The stored raw_response should be the repaired response, not the truncated one
    assert "recovered" in result.raw_response


def test_base_agent_does_not_retry_on_validation_error(monkeypatch) -> None:
    """If the response is valid JSON but fails schema validation, no
    repair call should be made — the existing fast-fail path is preserved."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    # Valid JSON, but a non-integral float score fails _normalize_score.
    invalid_score_response = json.dumps(
        {
            "summary": "bad",
            "criterion_scores": [
                {
                    "criterion_id": "c1",
                    "score": 3.5,  # non-integral → validation error
                    "justification": "ok",
                }
            ],
        }
    )
    llm = _SequenceLLM([invalid_score_response])
    agent = _DummyAgent(llm_client=llm)

    try:
        agent.run(
            evaluation_id=uuid4(),
            document_id=uuid4(),
            chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
            context_text="Syllabus text",
            reference_document_ids={"syllabus": uuid4()},
        )
        raise AssertionError("expected AgentExecutionError")
    except AgentExecutionError:
        pass

    # Only one LLM call should have been made — no repair on validation errors.
    assert len(llm.prompts) == 1


def test_base_agent_does_not_retry_on_top_level_non_dict(monkeypatch) -> None:
    """If the response is valid JSON but not an object, the existing
    validation error path should fire without a repair call."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    # Valid JSON, but top-level is a list → _validate_response raises.
    non_object_response = json.dumps([{"not": "an object"}])
    llm = _SequenceLLM([non_object_response])
    agent = _DummyAgent(llm_client=llm)

    try:
        agent.run(
            evaluation_id=uuid4(),
            document_id=uuid4(),
            chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
            context_text="Syllabus text",
            reference_document_ids={"syllabus": uuid4()},
        )
        raise AssertionError("expected AgentExecutionError")
    except AgentExecutionError:
        pass

    # Only one LLM call — no repair on structural validation errors.
    assert len(llm.prompts) == 1


def test_base_agent_raises_when_repair_also_fails(monkeypatch) -> None:
    """If both the original and the repair call return invalid JSON,
    the original error should be raised (preserving the raw_response
    in the message for debugging)."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    truncated = '{"summary": "partial", "criterion_scores": ['
    still_broken = "not even close to JSON"
    llm = _SequenceLLM([truncated, still_broken])
    agent = _DummyAgent(llm_client=llm)

    try:
        agent.run(
            evaluation_id=uuid4(),
            document_id=uuid4(),
            chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
            context_text="Syllabus text",
            reference_document_ids={"syllabus": uuid4()},
        )
        raise AssertionError("expected AgentExecutionError")
    except AgentExecutionError as exc:
        # Both calls were attempted, and the error message includes the
        # truncated original response for debugging.
        assert len(llm.prompts) == 2
        assert truncated[:50] in str(exc)


def test_base_agent_repair_prompt_caps_runaway_partial() -> None:
    """_build_repair_prompt should cap the embedded partial response
    so a runaway model output cannot blow the repair prompt budget."""
    agent = _DummyAgent()
    long_partial = "X" * 20_000
    prompt = agent._build_repair_prompt(long_partial)
    assert "Prior partial output" in prompt
    # The embedded partial must be capped well below the original length.
    assert len(prompt) < 6000
    assert "..." in prompt


def test_base_agent_repair_prompt_handles_empty_partial() -> None:
    """_build_repair_prompt should not crash on empty/None partial input."""
    agent = _DummyAgent()
    prompt = agent._build_repair_prompt("")
    assert "Prior partial output" in prompt
    prompt_none = agent._build_repair_prompt(None)  # type: ignore[arg-type]
    assert "Prior partial output" in prompt_none


# ------------------------------------------------------------------
# Rubric context (coordinator lookup + debug exposure)
# ------------------------------------------------------------------


def test_coordinator_rubric_lookup_maps_to_coordinator(monkeypatch) -> None:
    captured = {}

    def _capture(agent_id, db=None):
        captured["agent_id"] = agent_id
        return ["ctx"]

    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        _capture,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = Coordinator(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {
                        "criterion_id": "OP-01",
                        "criterion_title": "Topic Coherence",
                        "score": 3,
                        "justification": "ok",
                    }
                ],
            }
        )
    )

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}],
        context_text="reference context",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert captured["agent_id"] == "coordinator"


def test_base_agent_exposes_debug_rubric_context_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(agent_debug_rubric_context=True),
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda agent_id, db=None: [
            "[SME Rubric v1]",
            "Agent: sme",
            "Version: 1",
            "Domain: Organization & Presentation",
            "OP-01 | Title: Topic Coherence | Description: Topics are coherent from Unit to Chapter.",
        ],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = _DummyAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {
                        "criterion_id": "c1",
                        "score": 3,
                        "justification": "ok",
                    }
                ],
            }
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "Document chunk text"}],
        context_text="Syllabus text",
        reference_document_ids={"syllabus": uuid4()},
    )

    assert result.metadata["rubric_context"] is not None
    assert result.metadata["rubric_context"][0] == "[SME Rubric v1]"
