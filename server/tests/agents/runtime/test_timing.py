"""Tests for timing instrumentation (_PhaseTimer and EVAL_TIMING logs)."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from server.modules.admin.models import PromptVersion
from server.modules.agents.runtime.timing import PhaseTimer
from server.tests.agents.helpers import _DummyAgent, _FakeLLM, _RetrievedChunk
from server.tests.agents.runtime.response_helpers import itso_response


def test_phase_timer_accumulates_and_logs(monkeypatch, caplog) -> None:
    """_PhaseTimer should accumulate durations and emit a structured log."""
    caplog.set_level(logging.INFO, logger="server.modules.agents.runtime.timing")

    timer = PhaseTimer("test_agent")

    with timer.measure("retrieval"):
        time.sleep(0.01)

    with timer.measure("llm_call"):
        time.sleep(0.02)

    # Second measure of same phase should accumulate.
    with timer.measure("retrieval"):
        time.sleep(0.01)

    timer.log_summary(prompt_chars=1234)

    # Should have logged a single EVAL_TIMING line.
    timing_records = [
        r
        for r in caplog.records
        if "EVAL_TIMING" in r.message and "agent=test_agent" in r.message
    ]
    assert len(timing_records) == 1
    msg = timing_records[0].message
    assert "retrieval=" in msg
    assert "llm_call=" in msg
    assert "prompt_chars=1234" in msg

    # Retrieval should be ~0.02s (two 0.01 sleeps).
    assert timer.phases["retrieval"] >= 0.015
    assert timer.phases["llm_call"] >= 0.015


def test_phase_timer_reports_parse_error(monkeypatch, caplog) -> None:
    """_PhaseTimer should include parse_error in log when present."""
    caplog.set_level(logging.INFO, logger="server.modules.agents.runtime.timing")

    timer = PhaseTimer("fail_agent")
    with timer.measure("parse"):
        time.sleep(0.001)

    timer.log_summary(prompt_chars=500, parse_error="invalid JSON")

    timing_records = [
        r
        for r in caplog.records
        if "EVAL_TIMING" in r.message and "parse_error=invalid JSON" in r.message
    ]
    assert len(timing_records) == 1


def test_agent_run_emits_timing_log(monkeypatch, caplog) -> None:
    """A successful agent.run() should emit an EVAL_TIMING log line."""
    caplog.set_level(logging.INFO, logger="server.modules.agents.runtime.timing")
    monkeypatch.setattr(
        "server.modules.agents.itso.execution.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.itso.execution.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = _DummyAgent(llm_client=_FakeLLM(itso_response()))

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "doc text"}],
        context_text="query",
    )

    timing_records = [
        r
        for r in caplog.records
        if "EVAL_TIMING" in r.message and "agent=itso" in r.message
    ]
    assert len(timing_records) == 1
    msg = timing_records[0].message
    assert "retrieval=" in msg
    assert "prompt_build=" in msg
    assert "llm_call=" in msg
    assert "parse=" in msg
    assert "prompt_chars=" in msg


def test_supervisor_emits_timing_logs(monkeypatch, caplog, db_session) -> None:
    """Supervisor run_evaluation should emit precompute and per-agent timing logs."""
    from server.modules.agents.supervision.supervisor import Supervisor
    from server.tests.agents.helpers import _BatchAgent, _seed_active_prompts

    for logger_name in (
        "server.modules.agents.supervision.context",
        "server.modules.agents.supervision.dispatch",
        "server.modules.agents.supervision.supervisor",
    ):
        caplog.set_level(logging.INFO, logger=logger_name)

    _seed_active_prompts(db_session)
    monkeypatch.setattr(
        db_session,
        "get",
        lambda _model, _id: type("Document", (), {"file_path": "source.pdf"})(),
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.prepare_canonical_source",
        lambda _path: "canonical source",
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.resolve_document_pdf_path",
        lambda _path: _path,
    )
    prompt_row = db_session.query(PromptVersion).filter_by(agent_id="sme").one()

    monkeypatch.setattr(
        "server.modules.agents.supervision.context.get_active_prompt",
        lambda agent_id, db: prompt_row,
    )
    agent = _BatchAgent()
    supervisor = Supervisor(agents=[agent], db=db_session)

    from server.modules.documents.models import DocumentChunk

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
    ]

    supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
    )

    # Should have precompute timing log.
    precompute_logs = [
        r
        for r in caplog.records
        if "EVAL_TIMING" in r.message and "phase=precompute_context" in r.message
    ]
    assert len(precompute_logs) == 1

    # Should have per-agent timing log.
    agent_logs = [
        r
        for r in caplog.records
        if "EVAL_TIMING" in r.message and "agent=sme" in r.message
    ]
    assert len(agent_logs) == 1

    # Should have total evaluation timing log.
    total_logs = [
        r
        for r in caplog.records
        if "EVAL_TIMING" in r.message and "phase=evaluation_total" in r.message
    ]
    assert len(total_logs) == 1
