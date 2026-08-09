"""Shared fakes, helpers, and fixtures for agent tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

from server.modules.admin.models import PromptVersion
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.itso.agent import ITSO
from server.modules.agents.runtime.prompt_budget import pack_chunks


class SequencedFakeClient:
    """Return canned JSON payloads in call order for basket tests."""

    model: str

    def __init__(self, responses: list[dict[str, Any] | None]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, **_: object) -> str:
        if self.calls >= len(self.responses):
            raise AssertionError(
                f"LLM called more times than expected (call #{self.calls + 1})"
            )
        payload = self.responses[self.calls]
        self.calls += 1
        if payload is None:
            raise RuntimeError("configured to fail")
        return json.dumps(payload)


_BASKET_A1 = {
    "objectives": [{"id": 1}],
    "assessments": [{"id": 1, "assessment_type": "objective_test", "evidence": "Q1"}],
    "alignment": [{"objective_id": 1, "is_measured": True, "evidence": "Q1"}],
}
_BASKET_A2 = {
    "tasks": [{
        "text": "Task 1", "bloom_level": "apply", "directions": "Do X.",
        "has_clear_directions": True, "evidence": "Do X.",
    }]
}
_BASKET_A3 = {
    "monitoring_mechanisms": [{
        "text": "Check 1", "monitoring_type": "checkpoint", "evidence": "quiz",
    }]
}
_BASKET_A4 = {
    "enhancement_activities": [{"text": "Extra", "evidence": "Research more."}]
}
_BASKET_B1 = {
    "topics": [{"id": 1, "title": "T1"}, {"id": 2, "title": "T2"}],
    "transitions": [{"from_id": 1, "to_id": 2, "is_coherent": True, "reason": "ok"}],
    "feedback_mechanisms": [{
        "text": "Key", "feedback_type": "answer_key", "evidence": "p.1",
    }],
}
_BASKET_B2 = {
    "sections": [{"id": 1, "title": "S1", "is_clean": True, "issue": ""}]
}
_ALL_BASKETS_IN_ORDER = [
    _BASKET_A1, _BASKET_A2, _BASKET_A3, _BASKET_A4, _BASKET_B1, _BASKET_B2,
]


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


class _DummyAgent:
    """Minimal generic double for tests that only need agent metadata/run."""

    agent_name = "dummy"

    def __init__(self, *, llm_client=None, **kwargs):
        self.llm_client = llm_client

    def run(self, **kwargs):
        result = ITSO(llm_client=self.llm_client).run(**kwargs)
        return replace(result, agent_name=self.agent_name)


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
            "text": f"Page {i + 1} content about {keyword}"
            if keyword
            else f"Page {i + 1} generic content",  # noqa: E501
        }
        for i in range(n)
    ]


def _make_mixed_chunks() -> list[dict[str, object]]:
    """Generate chunks with mixed domain keywords for selection testing."""
    return [
        {
            "chunk_id": "c1",
            "page_number": 1,
            "text": "Gender equity and inclusion are important",
        },  # noqa: E501
        {
            "chunk_id": "c2",
            "page_number": 2,
            "text": "Data encryption and authentication protocols",
        },  # noqa: E501
        {
            "chunk_id": "c3",
            "page_number": 3,
            "text": "Course learning outcomes and program alignment",
        },  # noqa: E501
        {
            "chunk_id": "c4",
            "page_number": 4,
            "text": "Security threats and vulnerability assessment",
        },  # noqa: E501
        {
            "chunk_id": "c5",
            "page_number": 5,
            "text": "Content accuracy and factual knowledge",
        },  # noqa: E501
        {
            "chunk_id": "c6",
            "page_number": 6,
            "text": "Diversity representation and accessibility",
        },  # noqa: E501
        {
            "chunk_id": "c7",
            "page_number": 7,
            "text": "Curriculum standards and competencies",
        },  # noqa: E501
        {
            "chunk_id": "c8",
            "page_number": 8,
            "text": "Privacy protection and data integrity",
        },  # noqa: E501
        {
            "chunk_id": "c9",
            "page_number": 9,
            "text": "Theory principles and correct definitions",
        },  # noqa: E501
        {
            "chunk_id": "c10",
            "page_number": 10,
            "text": "Assessment goals and course objectives",
        },  # noqa: E501
    ]


class _PackingCaptureAgent:
    """Concrete adapter that captures the runtime chunk-packing result."""

    agent_name = "capture"
    rubric_source_type = "rubric_sme"
    domain_keywords = (
        "security",
        "data",
        "encryption",
    )

    def __init__(self, *args, **kwargs):
        self.captured_chunks: list[dict[str, object]] = []
        self.captured_chunks_dropped = False
        self.captured_text_excerpted = False

    def run(self, *, chunk_infos, **kwargs):
        del kwargs
        from server.modules.agents.itso.execution import get_settings

        settings = get_settings()
        packed, chunks_dropped, text_excerpted = pack_chunks(
            [dict(chunk) for chunk in chunk_infos],
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=settings.agent_prompt_budget_chars,
            small_doc_threshold=settings.agent_small_doc_threshold,
            domain_keywords=self.domain_keywords,
            agent_name="capture",
        )
        self.captured_chunks = packed
        self.captured_chunks_dropped = chunks_dropped
        self.captured_text_excerpted = text_excerpted
        return None


def _mock_settings(**overrides):
    """Build a minimal Settings-like object for tests."""
    defaults = {
        "llm_model_name": "test-model",
        "llm_temperature": 0.2,
        "llm_temperature_itso": 0.0,
        "llm_max_new_tokens": 2048,
        "agent_max_chunks": 12,
        "agent_max_excerpt_chars": 800,
        "agent_prompt_budget_chars": 5000,
        "agent_small_doc_threshold": 6,
        "agent_total_prompt_budget_chars": 8000,
        "itso_policy_delivery_enabled": False,
    }
    defaults.update(overrides)

    def get_agent_temperature(_self, agent_name):
        if agent_name == "itso":
            return defaults["llm_temperature_itso"]
        return defaults["llm_temperature"]

    defaults["get_agent_temperature"] = get_agent_temperature
    return type("Settings", (), defaults)()


def patch_settings(monkeypatch, **overrides) -> None:
    """Monkeypatch every ``get_settings`` import the agents touch.

    ``ITSO.run()`` calls both ``get_settings`` (in
    ``server.modules.agents.itso.execution``) and ``get_llm_model_name()`` (which
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
        "server.modules.agents.itso.execution.get_settings", lambda: mock
    )
    monkeypatch.setattr("server.modules.agents.itso.prompt.get_settings", lambda: mock)
    monkeypatch.setattr(
        "server.core.llm.get_settings",
        lambda: mock,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.dispatch.get_settings",
        lambda: mock,
    )
    monkeypatch.setattr(
        "server.core.database.get_settings",
        lambda: mock,
    )

