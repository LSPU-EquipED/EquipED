"""Shared fakes, helpers, and fixtures for agent tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

import pytest

from server.modules.admin.models import PromptVersion
from server.modules.agents.base import BaseAgent
from server.modules.agents.contracts import AgentEvaluationResult


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
        **kwargs,
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
        **kwargs,
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


def _make_chunk_infos(n: int, *, keyword: str = "") -> list[dict[str, object]]:
    """Generate n chunk infos, optionally embedding a keyword in every chunk."""
    return [
        {
            "chunk_id": f"chunk-{i}",
            "page_number": i + 1,
            "text": f"Page {i + 1} content about {keyword}" if keyword else f"Page {i + 1} generic content",
        }
        for i in range(n)
    ]


def _make_mixed_chunks() -> list[dict[str, object]]:
    """Generate chunks with mixed domain keywords for selection testing."""
    return [
        {"chunk_id": "c1", "page_number": 1, "text": "Gender equity and inclusion are important"},
        {"chunk_id": "c2", "page_number": 2, "text": "Data encryption and authentication protocols"},
        {"chunk_id": "c3", "page_number": 3, "text": "Course learning outcomes and program alignment"},
        {"chunk_id": "c4", "page_number": 4, "text": "Security threats and vulnerability assessment"},
        {"chunk_id": "c5", "page_number": 5, "text": "Content accuracy and factual knowledge"},
        {"chunk_id": "c6", "page_number": 6, "text": "Diversity representation and accessibility"},
        {"chunk_id": "c7", "page_number": 7, "text": "Curriculum standards and competencies"},
        {"chunk_id": "c8", "page_number": 8, "text": "Privacy protection and data integrity"},
        {"chunk_id": "c9", "page_number": 9, "text": "Theory principles and correct definitions"},
        {"chunk_id": "c10", "page_number": 10, "text": "Assessment goals and course objectives"},
    ]


class _PackingCaptureAgent(BaseAgent):
    """Agent that captures the packed chunks sent to _build_prompt."""
    agent_name = "capture"
    rubric_source_type = "rubric_sme"
    domain_keywords = ("security", "data", "encryption",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.captured_chunks: list[dict[str, object]] = []
        self.captured_chunks_dropped = False
        self.captured_text_excerpted = False

    def _build_prompt(self, *, chunk_infos, **kw):
        from server.modules.agents.base import get_settings as _get_settings
        settings = _get_settings()
        packed, chunks_dropped, text_excerpted = self._pack_chunks(
            chunk_infos,
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=settings.agent_prompt_budget_chars,
            small_doc_threshold=settings.agent_small_doc_threshold,
        )
        self.captured_chunks = packed
        self.captured_chunks_dropped = chunks_dropped
        self.captured_text_excerpted = text_excerpted
        return "{}"


def _mock_settings(**overrides):
    """Build a minimal Settings-like object for tests."""
    defaults = {
        "llm_model_name": "test-model",
        "llm_temperature": 0.2,
        "llm_max_new_tokens": 2048,
        "agent_max_chunks": 12,
        "agent_max_excerpt_chars": 800,
        "agent_prompt_budget_chars": 5000,
        "agent_small_doc_threshold": 6,
        "agent_total_prompt_budget_chars": 8000,
    }
    defaults.update(overrides)
    return type("Settings", (), defaults)()


def patch_settings(monkeypatch, **overrides) -> None:
    """Monkeypatch every ``get_settings`` import the agents touch.

    ``BaseAgent.run()`` calls both ``get_settings`` (in
    ``server.modules.agents.base``) and ``get_llm_model_name()`` (which
    transitively calls ``get_settings`` in ``server.core.llm``). The
    supervisor also imports ``get_settings`` directly. If the real one
    raises (because the new 8,000-char total budget default conflicts
    with the 5,000-char chunk budget default), the cached
    ``get_engine()`` / ``get_session_factory()`` would refuse to
    build, breaking ``get_active_rubric_context`` for any test that
    hits the real database.

    Patching all three ``get_settings`` references with a mock silences
    the cross-field validation everywhere it would fire inside the
    agent layer. The database module keeps its real ``get_settings``
    reference so the engine chain can still build against the
    ``DATABASE_URL`` from the project's ``.env``.
    """
    mock = _mock_settings(**overrides)
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings", lambda: mock,
    )
    monkeypatch.setattr(
        "server.core.llm.get_settings", lambda: mock,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_settings", lambda: mock,
    )
    monkeypatch.setattr(
        "server.core.database.get_settings", lambda: mock,
    )


@pytest.fixture(autouse=True)
def _isolate_agent_settings(monkeypatch) -> None:
    """Auto-applied fixture that pins every agent test to compatible
    prompt-budget env vars so the new cross-field validation in
    ``get_settings()`` (chunk budget must be less than total budget)
    does not fire mid-test.

    Strategy: set ``AGENT_PROMPT_BUDGET_CHARS=5000`` in the test
    environment. The new total-budget default (8,000) is strictly
    larger, so the cross-field check passes wherever ``get_settings()``
    is called — including the call chain
    ``agent.run() -> get_llm_model_name() -> get_settings()`` in
    ``server.core.llm`` that previously raised.

    We use env-var pinning rather than monkeypatching ``get_settings``
    because real-database tests (``db_session`` fixture) depend on
    ``get_settings()`` returning the real ``DATABASE_URL`` from the
    project's ``.env`` so the cached ``get_engine()`` /
    ``get_session_factory()`` chain can build a working engine.
    Patching ``get_settings`` in those tests would break the
    database lookup.
    """
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")


@pytest.fixture(autouse=True)
def _mock_llm_client_for_agent(monkeypatch) -> None:
    """Auto-applied fixture that mocks ``get_llm_client_for_agent`` for every
    agent test.

    The supervisor now calls ``get_llm_client_for_agent(agent_name)`` (from
    ``server.core.llm``) to obtain a per-agent LLM client.  Without this
    mock the real ``LocalLLMClient`` would be instantiated and attempt a
    real HTTP call to an LLM endpoint, causing the test to hang.

    We return a ``_FakeLLM`` that echoes a minimal valid JSON response so
    any agent (including real ``BaseAgent`` subclasses) can complete its
    LLM call in tests.
    """
    fake = _FakeLLM(
        {
            "summary": "test",
            "criterion_scores": [
                {"criterion_id": "c1", "score": 3, "justification": "ok"},
            ],
        }
    )
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_llm_client_for_agent",
        lambda _agent_name: fake,
    )


class _SleepCapture:
    """Context-like helper to capture time.sleep calls via monkeypatch.

    Usage:
        capture = _SleepCapture()
        capture.patch(monkeypatch, "server.modules.agents.supervisor.time.sleep")
        # ... run code that calls time.sleep ...
        assert capture.calls == [15, 30]
        assert capture.count == 2
    """

    def __init__(self) -> None:
        self.calls: list[float] = []

    def _fake_sleep(self, seconds: float) -> None:
        self.calls.append(seconds)

    def patch(self, monkeypatch, target: str) -> None:
        monkeypatch.setattr(target, self._fake_sleep)

    @property
    def count(self) -> int:
        return len(self.calls)
