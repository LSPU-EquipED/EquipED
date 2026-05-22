"""Tests for agents and synthesis persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

from server.modules.admin.models import PromptVersion
from server.modules.agents.base import BaseAgent
from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.coordinator import Coordinator
from server.modules.agents.exceptions import AgentLLMError
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.gad import GAD
from server.modules.agents.itso import ITSO
from server.modules.agents.sme import SME
from server.modules.agents.supervisor import Supervisor
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.synthesis.models import AgentResult, EvaluationFlag
from server.modules.synthesis.service import persist_agent_outputs


@dataclass
class _RetrievedChunk:
    text: str


class _FakeLLM:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        return json.dumps(self.response)


class _RawLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, prompt: str, *, temperature: float, max_new_tokens: int) -> str:
        return self.response


class _DummyAgent(BaseAgent):
    agent_name = "dummy"
    rubric_source_type = "rubric_sme"
    reference_source_types = ("syllabus",)


class _BatchAgent:
    agent_name = "sme"

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def run(
        self,
        *,
        evaluation_id,
        document_id,
        chunk_infos,
        context_text=None,
        reference_text=None,
        prompt_version=None,
        prompt_version_id=None,
        reference_document_ids=None,
    ):
        self.batches.append([chunk["text"] for chunk in chunk_infos])
        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=float(len(chunk_infos)),
            criterion_scores=(),
            summary="batch",
            model_name="local-model",
            processing_seconds=0.0,
            token_count=len(chunk_infos),
            prompt_version_id=prompt_version_id,
        )


class _FailingAgent:
    agent_name = "coordinator"

    def __init__(self) -> None:
        self.calls = 0

    def run(
        self,
        *,
        evaluation_id,
        document_id,
        chunk_infos,
        context_text=None,
        reference_text=None,
        prompt_version=None,
        prompt_version_id=None,
        reference_document_ids=None,
    ):
        self.calls += 1
        raise RuntimeError("agent failed")


class _PromptRow:
    def __init__(self, version_id, prompt_text: str) -> None:
        self.version_id = version_id
        self.prompt_text = prompt_text


def _seed_active_prompts(db_session) -> None:
    for agent_id in ["sme", "coordinator", "gad", "itso"]:
        db_session.add(
            PromptVersion(
                agent_id=agent_id,
                version_number=1,
                prompt_text=f"{agent_id} prompt",
                is_active=True,
            )
        )
    db_session.commit()


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


def test_persist_agent_outputs_creates_flags_for_low_scores(db_session) -> None:
    owner_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    evaluation_id = uuid4()
    prompt_version_id = uuid4()

    db_session.add(
        Document(
            document_id=document_id,
            title="SLM",
            program="bsit",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=owner_id,
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.add(
        DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="chunk text",
            token_count=2,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    _seed_active_prompts(db_session)
    prompt_version_id = (
        db_session.query(PromptVersion).filter_by(agent_id="sme").one().version_id
    )
    db_session.add(
        EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            syllabus_id=uuid4(),
            curriculum_id=uuid4(),
            status=EvaluationStatus.EVALUATING.value,
            submitted_by=owner_id,
        )
    )
    db_session.commit()

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        [
            AgentEvaluationResult(
                agent_name="sme",
                evaluation_id=evaluation_id,
                document_id=document_id,
                subtotal=1,
                criterion_scores=(
                    CriterionScore(
                        criterion_id="c1",
                        criterion_title="Criterion 1",
                        score=1,
                        justification="needs work",
                        chunk_ids=(str(chunk_id),),
                        evidence=("evidence",),
                    ),
                    CriterionScore(
                        criterion_id="c2",
                        criterion_title="Criterion 2",
                        score=3,
                        justification="fine",
                    ),
                ),
                summary="summary",
                model_name="local-model",
                processing_seconds=0.1,
                token_count=10,
                raw_response="{}",
                prompt_version_id=prompt_version_id,
            )
        ],
    )

    result_row = db_session.query(AgentResult).one()
    assert result_row.prompt_version_id == prompt_version_id
    assert db_session.query(EvaluationFlag).count() == 1
    flag = db_session.query(EvaluationFlag).one()
    assert flag.chunk_id == chunk_id
    assert flag.score == 1
    assert flag.criterion_id == "c1"


def test_persist_agent_outputs_ignores_invalid_and_missing_chunk_ids(
    db_session,
) -> None:
    owner_id = uuid4()
    document_id = uuid4()
    valid_chunk_id = uuid4()
    evaluation_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="SLM",
            program="bsit",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=owner_id,
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.add(
        DocumentChunk(
            chunk_id=valid_chunk_id,
            document_id=document_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="chunk text",
            token_count=2,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    _seed_active_prompts(db_session)
    prompt_version_id = (
        db_session.query(PromptVersion).filter_by(agent_id="sme").one().version_id
    )
    db_session.commit()

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        [
            AgentEvaluationResult(
                agent_name="sme",
                evaluation_id=evaluation_id,
                document_id=document_id,
                subtotal=1,
                criterion_scores=(
                    CriterionScore(
                        criterion_id="c1",
                        criterion_title="Criterion 1",
                        score=1,
                        justification="needs work",
                        chunk_ids=("not-a-uuid", str(uuid4()), str(valid_chunk_id)),
                        evidence=("evidence",),
                    ),
                ),
                summary="summary",
                model_name="local-model",
                processing_seconds=0.1,
                token_count=10,
                raw_response="{}",
                prompt_version_id=prompt_version_id,
            )
        ],
    )

    result_row = db_session.query(AgentResult).one()
    assert result_row.prompt_version_id == prompt_version_id
    assert db_session.query(EvaluationFlag).count() == 1
    flag = db_session.query(EvaluationFlag).one()
    assert flag.chunk_id == valid_chunk_id


def test_supervisor_passes_all_chunks_and_loads_active_prompts(
    monkeypatch, db_session
) -> None:
    _seed_active_prompts(db_session)
    prompt_row = db_session.query(PromptVersion).filter_by(agent_id="sme").one()
    agent = _BatchAgent()
    supervisor = Supervisor(agents=[agent], db=db_session)

    chunks = [
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="one",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        ),
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_type="slm",
            agent_domain="all",
            page_number=2,
            text="two",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        ),
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_type="slm",
            agent_domain="all",
            page_number=3,
            text="three",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        ),
    ]

    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_active_prompt",
        lambda agent_id, db: prompt_row,
    )

    result = supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
        context={
            "reference_document_ids": {
                "syllabus": uuid4(),
                "curriculum": uuid4(),
            }
        },
    )

    assert agent.batches == [["one", "two", "three"]]
    assert len(result.agent_results) == 1


def test_supervisor_continues_after_one_agent_failure(monkeypatch, db_session) -> None:
    _seed_active_prompts(db_session)
    failing_agent = _FailingAgent()
    success_agent = _BatchAgent()
    supervisor = Supervisor(agents=[failing_agent, success_agent], db=db_session)

    prompt_rows = {
        agent_id: db_session.query(PromptVersion).filter_by(agent_id=agent_id).one()
        for agent_id in ["coordinator", "sme"]
    }

    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_active_prompt",
        lambda agent_id, db: prompt_rows[agent_id],
    )

    chunks = [
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="one",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        ),
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_type="slm",
            agent_domain="all",
            page_number=2,
            text="two",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        ),
    ]

    result = supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
        context={
            "reference_document_ids": {
                "syllabus": uuid4(),
                "curriculum": uuid4(),
            }
        },
    )

    assert failing_agent.calls == 1
    assert success_agent.batches == [["one", "two"]]
    assert len(result.agent_results) == 2
    assert result.failures == {"coordinator": "agent failed"}
