"""Concurrency and safe-diagnostics tests for the SME engine path."""

from __future__ import annotations

import concurrent.futures
import inspect
import threading
import uuid

import pytest
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.runtime.llm import error_reference
from server.modules.agents.sme import registry
from server.modules.agents.sme.agent import SME
from server.modules.agents.sme.pipeline import EngineScoredAgent


class _Client:
    def __init__(self, model: str) -> None:
        self.model = model


class _BarrierSME(SME):
    barrier = threading.Barrier(2)

    def _rubric_titles(self, db):
        return {code: code for code in registry.REGISTERED_CODES}

    def _score_via_engine(self, client, full_text, **kwargs):
        self.barrier.wait(timeout=5)
        return {
            code: (4, f"result from {client.model}", ())
            for code in registry.REGISTERED_CODES
        }, 0


def test_same_sme_instance_keeps_injected_clients_isolated() -> None:
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


def test_grouped_and_criterion_failures_log_safe_references(
    caplog, monkeypatch
) -> None:
    secret = "SECRET-SME-CONTENT"

    def fail_extract(*args, **kwargs):
        raise RuntimeError(secret)

    first_basket = registry._BASKETS[0]
    monkeypatch.setattr(
        registry,
        "_BASKETS",
        ((first_basket[0], first_basket[1], fail_extract, first_basket[3]),)
        + registry._BASKETS[1:],
    )
    with caplog.at_level("WARNING"):
        registry.run_grouped(_Client("model"), "text")
    assert secret not in caplog.text
    assert "category=RuntimeError" in caplog.text
    assert error_reference(RuntimeError(secret)) in caplog.text

    engine = EngineScoredAgent()
    monkeypatch.setattr(
        registry,
        "run_grouped",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    monkeypatch.setattr(
        registry,
        "run_criterion",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    with pytest.raises(AgentExecutionError) as raised:
        engine._score_via_engine(_Client("model"), "text")
    message = str(raised.value)
    assert secret not in message
    assert "category=RuntimeError" in message
    assert error_reference(RuntimeError(secret)) in message


def test_sme_uses_canonical_text_without_pdf_reopening(monkeypatch) -> None:
    source = inspect.getsource(SME)
    assert "fitz" not in source.lower()
    assert "pymupdf" not in source.lower()
    assert "_load_document_text" not in source

    captured: list[str] = []
    monkeypatch.setattr(
        registry,
        "run_grouped",
        lambda client, text, **kwargs: (
            captured.append(text)
            or {code: (4, "ok", ()) for code in registry.REGISTERED_CODES}
        ),
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
    assert captured == ["EXACT CANONICAL SOURCE"]
