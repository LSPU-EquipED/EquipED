"""Concurrency and safe-diagnostics tests for the SME engine path."""

from __future__ import annotations

import concurrent.futures
import inspect
import threading
import uuid

from server.modules.agents.contracts import CriterionScore
from server.modules.agents.runtime.llm import error_reference
from server.modules.agents.sme import pipeline
from server.modules.agents.sme.agent import SME
from server.modules.agents.sme.rubric import REGISTERED_CODES


class _Client:
    def __init__(self, model: str) -> None:
        self.model = model


class _BarrierSME(SME):
    barrier = threading.Barrier(2)

    def _rubric_titles(self, db):
        return {code: code for code in REGISTERED_CODES}

    def _rubric_descriptions(self, db):
        return {code: code for code in REGISTERED_CODES}

    def _rubric_scoring_rules(self, db):
        return {}


def _barrier_execute_group(
    group, codes, titles, descriptions, scoring_rules, client, full_text, **kwargs
):
    """Stand-in for ``grouped_execution.execute_group`` that blocks both
    threads inside the scoring lane before either can return."""
    _BarrierSME.barrier.wait(timeout=5)
    scores = tuple(
        CriterionScore(
            criterion_id=code,
            criterion_title=titles[code],
            score=4,
            justification=f"result from {client.model}",
        )
        for code in codes
    )
    return (
        scores,
        f"prompt for {group}",
        {
            "summary": "ok",
            "criterion_scores": [
                {
                    "criterion_id": s.criterion_id,
                    "criterion_title": s.criterion_title,
                    "score": s.score,
                    "justification": s.justification,
                    "evidence": [],
                }
                for s in scores
            ],
        },
    )


def test_same_sme_instance_keeps_injected_clients_isolated(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "execute_group", _barrier_execute_group)
    default = _Client("default")
    clients = [_Client("model-a"), _Client("model-b")]
    agent = _BarrierSME(llm_client=default)

    def run(client):
        return agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=[{"text": "text"}],
            context_text="text",
            canonical_source_text="canonical source",
            llm_client=client,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, clients))

    assert {result.model_name for result in results} == {"model-a", "model-b"}
    for result in results:
        assert {score.justification for score in result.criterion_scores} in (
            {"result from model-a"},
            {"result from model-b"},
        )
    assert agent._default_llm_client is default
    assert not hasattr(agent, "_llm_client")


def test_error_reference_is_deterministic_and_bounded() -> None:
    error = RuntimeError("secret diagnostic")
    reference = error_reference(error)
    assert reference == error_reference(RuntimeError("secret diagnostic"))
    assert len(reference) == 16
    assert reference == reference.lower()
    assert all(character in "0123456789abcdef" for character in reference)


def test_sme_uses_canonical_text_without_pdf_reopening(monkeypatch) -> None:
    source = inspect.getsource(SME)
    assert "fitz" not in source.lower()
    assert "pymupdf" not in source.lower()
    assert "_load_document_text" not in source

    captured: list[str] = []

    def capture_execute_group(
        group, codes, titles, descriptions, scoring_rules, client, full_text, **kwargs
    ):
        captured.append(full_text)
        scores = tuple(
            CriterionScore(
                criterion_id=code,
                criterion_title=titles[code],
                score=4,
                justification="ok",
            )
            for code in codes
        )
        return (
            scores,
            "prompt",
            {
                "summary": "ok",
                "criterion_scores": [
                    {
                        "criterion_id": s.criterion_id,
                        "criterion_title": s.criterion_title,
                        "score": s.score,
                        "justification": s.justification,
                        "evidence": [],
                    }
                    for s in scores
                ],
            },
        )

    monkeypatch.setattr(pipeline, "execute_group", capture_execute_group)
    monkeypatch.setattr(
        pipeline.EngineScoredAgent,
        "_rubric_titles",
        lambda self, db: {code: code for code in REGISTERED_CODES},
    )
    monkeypatch.setattr(
        pipeline.EngineScoredAgent,
        "_rubric_descriptions",
        lambda self, db: {code: code for code in REGISTERED_CODES},
    )
    monkeypatch.setattr(
        pipeline.EngineScoredAgent,
        "_rubric_scoring_rules",
        lambda self, db: {},
    )
    agent = SME(llm_client=_Client("model"))
    result = agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=[{"text": "chunk fallback must not be used"}],
        context_text="context fallback must not be used",
        canonical_source_text="EXACT CANONICAL SOURCE",
    )
    assert result.success is True
    # One entry per group, every one the canonical text (never the PDF/chunks).
    assert set(captured) == {"EXACT CANONICAL SOURCE"}
    assert len(captured) == 3
