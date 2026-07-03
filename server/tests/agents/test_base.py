"""Tests for base agent response parsing and concrete agent instantiation."""

from __future__ import annotations

import json
from uuid import uuid4

from server.modules.agents.contracts import CriterionScore
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.exceptions import AgentLLMError
from server.modules.agents.coordinator import Coordinator
from server.modules.agents.gad import (
    GAD,
    GAD_ROW_1_PROMPT,
    GAD_ROW_2_PROMPT,
    GAD_ROW_3_PROMPT,
    GAD_ROW_4_PROMPT,
    GAD_ROW_5_PROMPT,
)
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

    gad_llm = _SequenceLLM(
        [
            json.dumps(
                {
                    "criterion": "The material is free from gender stereotypes",
                    "instance_count": 0,
                    "instances": [],
                    "summary": "No gender stereotypes were identified.",
                }
            ),
            json.dumps(
                {
                    "criterion": (
                        "The material shows females and males an equal number "
                        "of times"
                    ),
                    "female_count": 1,
                    "male_count": 1,
                    "summary": "Representations are balanced.",
                }
            ),
            json.dumps(
                {
                    "criterion": (
                        "The material shows females and males with equal "
                        "respect and potential"
                    ),
                    "instance_count": 0,
                    "instances": [],
                    "summary": "Females and males are presented with equal respect.",
                }
            ),
            json.dumps(
                {
                    "criterion": (
                        "The material reflects the needs and life experiences "
                        "of both male and female students"
                    ),
                    "instance_count": 0,
                    "instances": [],
                    "summary": "The material remains gender-neutral.",
                }
            ),
            json.dumps(
                {
                    "criterion": (
                        "The material promotes peace and equality regardless "
                        "of gender, race, class, disability, religion, sexual "
                        "orientation, or ethnic background"
                    ),
                    "instance_count": 0,
                    "instances": [],
                    "summary": "No discriminatory content was identified.",
                }
            ),
        ]
    )
    gad_result = GAD(llm_client=gad_llm).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}
        ],
        context_text="reference context",
        reference_document_ids={"syllabus": uuid4(), "curriculum": uuid4()},
    )
    assert gad_result.agent_name == "gad"
    assert gad_result.criterion_count == 5
    assert gad_result.summary


def test_gad_builds_row_1_prompt(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda agent_id, db=None: [
            "GAD-01 | The material is free from gender stereotypes"
        ],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.gad.get_settings",
        lambda: _mock_settings(),
    )

    captured_prompt = []
    agent = GAD(
        llm_client=_SequenceLLM(
            [
                json.dumps(
                    {
                        "criterion": "The material is free from gender stereotypes",
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No gender stereotypes were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males an equal "
                            "number of times"
                        ),
                        "female_count": 2,
                        "male_count": 1,
                        "summary": "Representations are balanced.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males with equal "
                            "respect and potential"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": (
                            "Females and males are presented with equal respect."
                        ),
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material reflects the needs and life "
                            "experiences of both male and female students"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "The material remains gender-neutral.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material promotes peace and equality "
                            "regardless of gender, race, class, disability, "
                            "religion, sexual orientation, or ethnic background"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No discriminatory content was identified.",
                    }
                ),
            ]
        )
    )
    original_call_llm = agent._call_llm

    def capture_llm(prompt):
        captured_prompt.append(prompt)
        return original_call_llm(prompt)

    agent._call_llm = capture_llm

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}
        ],
        context_text="reference context",
    )

    assert len(captured_prompt) == 5
    row_1_payload = json.loads(captured_prompt[0])
    row_2_payload = json.loads(captured_prompt[1])
    row_3_payload = json.loads(captured_prompt[2])
    row_4_payload = json.loads(captured_prompt[3])
    row_5_payload = json.loads(captured_prompt[4])
    assert row_1_payload["criterion_id"] == "GAD-01"
    assert row_1_payload["criterion_prompt"] == GAD_ROW_1_PROMPT
    assert row_2_payload["criterion_id"] == "GAD-02"
    assert row_2_payload["criterion_prompt"] == GAD_ROW_2_PROMPT
    assert row_3_payload["criterion_id"] == "GAD-03"
    assert row_3_payload["criterion_prompt"] == GAD_ROW_3_PROMPT
    assert row_4_payload["criterion_id"] == "GAD-04"
    assert row_4_payload["criterion_prompt"] == GAD_ROW_4_PROMPT
    assert row_5_payload["criterion_id"] == "GAD-05"
    assert row_5_payload["criterion_prompt"] == GAD_ROW_5_PROMPT
    assert (
        "Return only the JSON object requested by criterion_prompt."
        in row_1_payload["instructions"]
    )
    assert result.criterion_scores[0].criterion_id == "GAD-01"
    assert result.criterion_scores[0].score == 4
    assert result.criterion_scores[1].criterion_id == "GAD-02"
    assert result.criterion_scores[1].score == 4
    assert result.criterion_scores[2].criterion_id == "GAD-03"
    assert result.criterion_scores[2].score == 4
    assert result.criterion_scores[3].criterion_id == "GAD-04"
    assert result.criterion_scores[3].score == 4
    assert result.criterion_scores[4].criterion_id == "GAD-05"
    assert result.criterion_scores[4].score == 4


def test_gad_converts_row_1_instances_to_score(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda agent_id, db=None: [
            "GAD-01 | The material is free from gender stereotypes"
        ],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.gad.get_settings",
        lambda: _mock_settings(),
    )

    agent = GAD(
        llm_client=_SequenceLLM(
            [
                json.dumps(
                    {
                        "criterion": "The material is free from gender stereotypes",
                        "instance_count": 2,
                        "instances": [
                            {
                                "excerpt": "Boys are naturally better at machines.",
                                "explanation": (
                                    "This assigns technical ability by gender."
                                ),
                            },
                            {
                                "excerpt": "Girls should choose caring roles.",
                                "explanation": (
                                    "This reinforces occupational stereotypes."
                                ),
                            },
                        ],
                        "summary": (
                            "Two gender-biased representations were identified."
                        ),
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males an equal "
                            "number of times"
                        ),
                        "female_count": 0,
                        "male_count": 0,
                        "summary": "No representations were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males with equal "
                            "respect and potential"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": (
                            "Females and males are presented with equal respect."
                        ),
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material reflects the needs and life "
                            "experiences of both male and female students"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "The material remains gender-neutral.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material promotes peace and equality "
                            "regardless of gender, race, class, disability, "
                            "religion, sexual orientation, or ethnic background"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No discriminatory content was identified.",
                    }
                ),
            ]
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}
        ],
        context_text="reference context",
    )

    score = result.criterion_scores[0]
    assert score.criterion_id == "GAD-01"
    assert score.criterion_title == "The material is free from gender stereotypes"
    assert score.score == 2
    assert score.evidence == (
        "Instance count: 2",
        "Boys are naturally better at machines.",
        "Girls should choose caring roles.",
        (
            "Findings: This assigns technical ability by gender.; "
            "This reinforces occupational stereotypes."
        ),
    )
    assert score.justification == "Two gender-biased representations were identified."


def test_gad_converts_row_2_representation_counts_to_score(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda agent_id, db=None: [
            "GAD-02 | The material shows females and males an equal number of times"
        ],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.gad.get_settings",
        lambda: _mock_settings(),
    )

    agent = GAD(
        llm_client=_SequenceLLM(
            [
                json.dumps(
                    {
                        "criterion": "The material is free from gender stereotypes",
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No gender stereotypes were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males an equal "
                            "number of times"
                        ),
                        "female_count": 2,
                        "male_count": 9,
                        "summary": "Male representations appear more often.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males with equal "
                            "respect and potential"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": (
                            "Females and males are presented with equal respect."
                        ),
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material reflects the needs and life "
                            "experiences of both male and female students"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "The material remains gender-neutral.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material promotes peace and equality "
                            "regardless of gender, race, class, disability, "
                            "religion, sexual orientation, or ethnic background"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No discriminatory content was identified.",
                    }
                ),
            ]
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}
        ],
        context_text="reference context",
    )

    score = result.criterion_scores[1]
    assert score.criterion_id == "GAD-02"
    assert score.criterion_title == (
        "The material shows females and males an equal number of times"
    )
    assert score.score == 2
    assert score.justification == "Male representations appear more often."
    assert score.evidence == (
        (
            "Representation counts: Female representations: 2. "
            "Male representations: 9. Difference: 7."
        ),
    )


def test_gad_corrects_row_2_zero_counts_from_gender_labeled_names(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda agent_id, db=None: [
            "GAD-02 | The material shows females and males an equal number of times"
        ],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.gad.get_settings",
        lambda: _mock_settings(),
    )

    agent = GAD(
        llm_client=_SequenceLLM(
            [
                json.dumps(
                    {
                        "criterion": "The material is free from gender stereotypes",
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No gender stereotypes were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males an equal "
                            "number of times"
                        ),
                        "female_count": 0,
                        "male_count": 0,
                        "summary": "",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males with equal "
                            "respect and potential"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": (
                            "Females and males are presented with equal respect."
                        ),
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material reflects the needs and life "
                            "experiences of both male and female students"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "The material remains gender-neutral.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material promotes peace and equality "
                            "regardless of gender, race, class, disability, "
                            "religion, sexual orientation, or ethnic background"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No discriminatory content was identified.",
                    }
                ),
            ]
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {
                "chunk_id": "chunk-1",
                "page_number": 1,
                "text": (
                    "Female: Ana Cruz, Maria Santos\n"
                    "Male: Juan Dela Cruz, Pedro Ramos"
                ),
            }
        ],
        context_text="reference context",
    )

    score = result.criterion_scores[1]
    assert score.criterion_id == "GAD-02"
    assert score.score == 4
    assert score.justification == (
        "Female and male representations were counted from explicit "
        "gender labels and references in the submitted material."
    )
    assert "Female representations: 2" in score.evidence[0]
    assert "Male representations: 2" in score.evidence[0]
    assert "Explicit gender-labeled names" in score.evidence[0]


def test_gad_corrects_row_2_zero_counts_from_inline_gender_labels(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda agent_id, db=None: [
            "GAD-02 | The material shows females and males an equal number of times"
        ],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.gad.get_settings",
        lambda: _mock_settings(),
    )

    agent = GAD(
        llm_client=_SequenceLLM(
            [
                json.dumps(
                    {
                        "criterion": "The material is free from gender stereotypes",
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No gender stereotypes were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males an equal "
                            "number of times"
                        ),
                        "female_count": 0,
                        "male_count": 0,
                        "summary": "",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males with equal "
                            "respect and potential"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": (
                            "Females and males are presented with equal respect."
                        ),
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material reflects the needs and life "
                            "experiences of both male and female students"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "The material remains gender-neutral.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material promotes peace and equality "
                            "regardless of gender, race, class, disability, "
                            "religion, sexual orientation, or ethnic background"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No discriminatory content was identified.",
                    }
                ),
            ]
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {
                "chunk_id": "chunk-1",
                "page_number": 1,
                "text": (
                    "Female representations: Ana Cruz, Maria Santos. "
                    "Male representations: Juan Dela Cruz, Pedro Ramos, "
                    "Jose Reyes, Mark Garcia, Carlo Mendoza, Luis Santos."
                ),
            }
        ],
        context_text="reference context",
    )

    score = result.criterion_scores[1]
    assert score.criterion_id == "GAD-02"
    assert score.score == 3
    assert "Female representations: 2" in score.evidence[0]
    assert "Male representations: 6" in score.evidence[0]
    assert "Difference: 4" in score.evidence[0]
    assert "Explicit gender-labeled names" in score.evidence[0]


def test_gad_corrects_row_2_zero_counts_from_gendered_prose(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda agent_id, db=None: [
            "GAD-02 | The material shows females and males an equal number of times"
        ],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.gad.get_settings",
        lambda: _mock_settings(),
    )

    agent = GAD(
        llm_client=_SequenceLLM(
            [
                json.dumps(
                    {
                        "criterion": "The material is free from gender stereotypes",
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No gender stereotypes were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males an equal "
                            "number of times"
                        ),
                        "female_count": 0,
                        "male_count": 0,
                        "summary": "No representations were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males with equal "
                            "respect and potential"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": (
                            "Females and males are presented with equal respect."
                        ),
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material reflects the needs and life "
                            "experiences of both male and female students"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "The material remains gender-neutral.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material promotes peace and equality "
                            "regardless of gender, race, class, disability, "
                            "religion, sexual orientation, or ethnic background"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No discriminatory content was identified.",
                    }
                ),
            ]
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {
                "chunk_id": "chunk-1",
                "page_number": 1,
                "text": (
                    "Ms. Ana explained the activity. Maria is a girl. "
                    "Mr. Juan and Mr. Pedro solved the exercise. "
                    "The father in the story thanked his son."
                ),
            }
        ],
        context_text="reference context",
    )

    score = result.criterion_scores[1]
    assert score.criterion_id == "GAD-02"
    assert "No representations were identified" not in score.justification
    assert "Female representations: 2" in score.evidence[0]
    assert "Male representations: 4" in score.evidence[0]
    assert "Explicit gender-labeled names" in score.evidence[0]


def test_gad_converts_row_3_respect_potential_instances_to_score(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda agent_id, db=None: [
            "GAD-03 | The material shows females and males with equal respect "
            "and potential"
        ],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.gad.get_settings",
        lambda: _mock_settings(),
    )

    agent = GAD(
        llm_client=_SequenceLLM(
            [
                json.dumps(
                    {
                        "criterion": "The material is free from gender stereotypes",
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No gender stereotypes were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males an equal "
                            "number of times"
                        ),
                        "female_count": 0,
                        "male_count": 0,
                        "summary": "No representations were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males with equal "
                            "respect and potential"
                        ),
                        "instance_count": 4,
                        "instances": [
                            {
                                "excerpt": "Only boys are encouraged to lead.",
                                "explanation": (
                                    "This limits leadership opportunity by gender."
                                ),
                            }
                        ],
                        "summary": (
                            "Unequal respect and opportunity appeared across "
                            "multiple sections."
                        ),
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material reflects the needs and life "
                            "experiences of both male and female students"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "The material remains gender-neutral.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material promotes peace and equality "
                            "regardless of gender, race, class, disability, "
                            "religion, sexual orientation, or ethnic background"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No discriminatory content was identified.",
                    }
                ),
            ]
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}
        ],
        context_text="reference context",
    )

    score = result.criterion_scores[2]
    assert score.criterion_id == "GAD-03"
    assert score.criterion_title == (
        "The material shows females and males with equal respect and potential"
    )
    assert score.score == 2
    assert score.evidence == (
        "Instance count: 4",
        "Only boys are encouraged to lead.",
        "Findings: This limits leadership opportunity by gender.",
    )
    assert score.justification == (
        "Unequal respect and opportunity appeared across multiple sections."
    )


def test_gad_converts_row_4_life_experience_instances_to_score(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda agent_id, db=None: [
            "GAD-04 | The material reflects the needs and life experiences of "
            "both male and female students"
        ],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.gad.get_settings",
        lambda: _mock_settings(),
    )

    agent = GAD(
        llm_client=_SequenceLLM(
            [
                json.dumps(
                    {
                        "criterion": "The material is free from gender stereotypes",
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No gender stereotypes were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males an equal "
                            "number of times"
                        ),
                        "female_count": 0,
                        "male_count": 0,
                        "summary": "No representations were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males with equal "
                            "respect and potential"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": (
                            "Females and males are presented with equal respect."
                        ),
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material reflects the needs and life "
                            "experiences of both male and female students"
                        ),
                        "instance_count": 6,
                        "instances": [
                            {
                                "excerpt": (
                                    "All career examples focus on male students."
                                ),
                                "explanation": (
                                    "This favors one gender's experiences."
                                ),
                            }
                        ],
                        "summary": "Experiences are repeatedly imbalanced.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material promotes peace and equality "
                            "regardless of gender, race, class, disability, "
                            "religion, sexual orientation, or ethnic background"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No discriminatory content was identified.",
                    }
                ),
            ]
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}
        ],
        context_text="reference context",
    )

    score = result.criterion_scores[3]
    assert score.criterion_id == "GAD-04"
    assert score.criterion_title == (
        "The material reflects the needs and life experiences of both male "
        "and female students"
    )
    assert score.score == 1
    assert score.evidence == (
        "Instance count: 6",
        "All career examples focus on male students.",
        "Findings: This favors one gender's experiences.",
    )
    assert score.justification == "Experiences are repeatedly imbalanced."


def test_gad_converts_row_5_peace_equality_instances_to_score(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.agents.base.get_active_rubric_context",
        lambda agent_id, db=None: [
            "GAD-05 | The material promotes peace and equality regardless of "
            "gender, race, class, disability, religion, sexual orientation, or "
            "ethnic background"
        ],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.gad.get_settings",
        lambda: _mock_settings(),
    )

    agent = GAD(
        llm_client=_SequenceLLM(
            [
                json.dumps(
                    {
                        "criterion": "The material is free from gender stereotypes",
                        "instance_count": 0,
                        "instances": [],
                        "summary": "No gender stereotypes were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males an equal "
                            "number of times"
                        ),
                        "female_count": 0,
                        "male_count": 0,
                        "summary": "No representations were identified.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material shows females and males with equal "
                            "respect and potential"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": (
                            "Females and males are presented with equal respect."
                        ),
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material reflects the needs and life "
                            "experiences of both male and female students"
                        ),
                        "instance_count": 0,
                        "instances": [],
                        "summary": "The material remains gender-neutral.",
                    }
                ),
                json.dumps(
                    {
                        "criterion": (
                            "The material promotes peace and equality "
                            "regardless of gender, race, class, disability, "
                            "religion, sexual orientation, or ethnic background"
                        ),
                        "instance_count": 3,
                        "instances": [
                            {
                                "excerpt": "Students from poor families cannot lead.",
                                "explanation": (
                                    "This promotes inequality based on class."
                                ),
                                "category": "Social class",
                            }
                        ],
                        "summary": "Biased content appears in multiple sections.",
                    }
                ),
            ]
        )
    )

    result = agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[
            {"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}
        ],
        context_text="reference context",
    )

    score = result.criterion_scores[4]
    assert score.criterion_id == "GAD-05"
    assert score.criterion_title == (
        "The material promotes peace and equality regardless of gender, race, "
        "class, disability, religion, sexual orientation, or ethnic background"
    )
    assert score.score == 2
    assert score.evidence == (
        "Instance count: 3",
        "Students from poor families cannot lead.",
        "Findings: Social class: This promotes inequality based on class.",
    )
    assert score.justification == "Biased content appears in multiple sections."


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
