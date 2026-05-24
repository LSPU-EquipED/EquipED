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

from .conftest import _DummyAgent, _FakeLLM, _RawLLM, _RetrievedChunk


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
