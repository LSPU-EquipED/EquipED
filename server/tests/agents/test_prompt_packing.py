"""Tests for per-agent prompt packing, chunk selection, and truncation."""

from __future__ import annotations

import json
from uuid import uuid4

from server.modules.agents.sme import SME
from server.modules.agents.itso import ITSO
from server.modules.agents.gad import GAD

from .conftest import (
    _FakeLLM,
    _PackingCaptureAgent,
    _RetrievedChunk,
    _make_chunk_infos,
    _make_mixed_chunks,
    _mock_settings,
)


def test_per_agent_selection_differs_by_domain(monkeypatch) -> None:
    """Different agents should select different chunks based on domain keywords."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    # Use a small threshold so selection kicks in.
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: type(
            "Settings", (),
            {
                "agent_max_chunks": 4,
                "agent_max_excerpt_chars": 800,
                "agent_prompt_budget_chars": 12000,
                "agent_small_doc_threshold": 3,
            },
        )(),
    )

    chunks = _make_mixed_chunks()

    # SME should prefer content/accuracy/knowledge chunks.
    sme = SME()
    sme_selected = sme._select_chunks(
        chunks, max_chunks=4, small_doc_threshold=3,
    )
    sme_ids = {c["chunk_id"] for c in sme_selected}

    # ITSO should prefer security/data/encryption chunks.
    itso = ITSO()
    itso_selected = itso._select_chunks(
        chunks, max_chunks=4, small_doc_threshold=3,
    )
    itso_ids = {c["chunk_id"] for c in itso_selected}

    # GAD should prefer gender/inclusion/diversity chunks.
    gad = GAD()
    gad_selected = gad._select_chunks(
        chunks, max_chunks=4, small_doc_threshold=3,
    )
    gad_ids = {c["chunk_id"] for c in gad_selected}

    # At least one pair of agents should differ in selection.
    assert sme_ids != itso_ids or sme_ids != gad_ids or itso_ids != gad_ids

    # ITSO should include security-related chunks.
    assert "c2" in itso_ids or "c4" in itso_ids or "c8" in itso_ids
    # GAD should include gender-related chunks.
    assert "c1" in gad_ids or "c6" in gad_ids


def test_selection_is_capped(monkeypatch) -> None:
    """Chunk selection should never exceed max_chunks."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    agent = SME()
    chunks = _make_chunk_infos(20, keyword="accuracy content knowledge")

    for max_c in [1, 3, 5, 10]:
        selected = agent._select_chunks(
            chunks, max_chunks=max_c, small_doc_threshold=3,
        )
        assert len(selected) == max_c


def test_chunk_ids_and_page_numbers_preserved(monkeypatch) -> None:
    """Packed chunks must retain chunk_id and page_number from originals."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )

    chunks = _make_chunk_infos(5)
    agent = _PackingCaptureAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )
    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        context_text="query",
    )

    for packed in agent.captured_chunks:
        assert "chunk_id" in packed
        assert "page_number" in packed
        assert packed["chunk_id"].startswith("chunk-")
        assert isinstance(packed["page_number"], int)


def test_small_docs_not_over_truncated(monkeypatch) -> None:
    """Documents below the small-doc threshold should pass through unchanged."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )

    # 4 chunks — below threshold of 6.
    chunks = _make_chunk_infos(4)
    agent = _PackingCaptureAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )
    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        context_text="query",
    )

    # All chunks should be present.
    assert len(agent.captured_chunks) == 4
    # Text should not be truncated (no "..." suffix).
    for packed in agent.captured_chunks:
        assert not packed["text"].endswith("...")
    # No truncation flags.
    assert agent.captured_chunks_dropped is False
    assert agent.captured_text_excerpted is False


def test_excerpt_truncates_long_chunks(monkeypatch) -> None:
    """Long chunk text should be excerpted with ellipsis."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(
            agent_max_excerpt_chars=50,
            agent_small_doc_threshold=0,  # Force excerpting path
        ),
    )

    long_text = "A" * 200
    chunks = [{"chunk_id": "c1", "page_number": 1, "text": long_text}]
    agent = _PackingCaptureAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )
    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        context_text="query",
    )

    assert len(agent.captured_chunks) == 1
    assert agent.captured_chunks[0]["text"].endswith("...")
    assert len(agent.captured_chunks[0]["text"]) <= 50


def test_budget_guard_trims_when_exceeded(monkeypatch) -> None:
    """If packed prompt JSON exceeds budget, text should be further trimmed."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(
            agent_max_chunks=10,
            agent_max_excerpt_chars=500,
            agent_prompt_budget_chars=200,
            agent_small_doc_threshold=3,
        ),
    )

    chunks = _make_chunk_infos(8, keyword="security data encryption")
    agent = _PackingCaptureAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )
    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        context_text="query",
    )

    # Should have been truncated due to budget.
    assert agent.captured_chunks_dropped is True
    # The serialized chunks JSON must fit within the budget.
    packed_json = json.dumps(agent.captured_chunks, ensure_ascii=False)
    assert len(packed_json) <= 200


def test_budget_guard_enforces_after_serialization(monkeypatch) -> None:
    """Post-trim serialized JSON must actually fit within the budget."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(
            agent_max_chunks=10,
            agent_max_excerpt_chars=1000,
            agent_prompt_budget_chars=300,
            agent_small_doc_threshold=2,
        ),
    )

    # Generate chunks with long text to force budget trimming.
    chunks = [
        {"chunk_id": f"c{i}", "page_number": i + 1, "text": "X" * 500}
        for i in range(5)
    ]
    agent = _PackingCaptureAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )
    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        context_text="query",
    )

    # The serialized JSON of packed chunks must fit within budget.
    packed_json = json.dumps(agent.captured_chunks, ensure_ascii=False)
    assert len(packed_json) <= 300


def test_single_oversized_chunk_shrinks_to_fit(monkeypatch) -> None:
    """A single chunk that exceeds the budget must be shrunk to fit."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(
            agent_max_chunks=10,
            agent_max_excerpt_chars=5000,  # Large enough to not excerpt initially
            agent_prompt_budget_chars=150,  # Very tight budget
            agent_small_doc_threshold=0,    # Force selection path
        ),
    )

    # Single chunk with very long text.
    chunks = [{"chunk_id": "c1", "page_number": 1, "text": "A" * 2000}]
    agent = _PackingCaptureAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )
    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        context_text="query",
    )

    # Must still have exactly 1 chunk.
    assert len(agent.captured_chunks) == 1
    # Serialized JSON must fit within budget.
    packed_json = json.dumps(agent.captured_chunks, ensure_ascii=False)
    assert len(packed_json) <= 150
    # Text must have been excerpted.
    assert agent.captured_text_excerpted is True


def test_small_doc_long_chunk_passes_through_unchanged(monkeypatch) -> None:
    """Small docs with long individual chunks should NOT be excerpted."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(
            agent_max_chunks=12,
            agent_max_excerpt_chars=50,  # Would normally excerpt
            agent_prompt_budget_chars=12000,
            agent_small_doc_threshold=6,
        ),
    )

    # 3 chunks (below threshold of 6), each with long text.
    chunks = [
        {"chunk_id": f"c{i}", "page_number": i + 1, "text": "B" * 200}
        for i in range(3)
    ]
    agent = _PackingCaptureAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )
    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        context_text="query",
    )

    # All chunks present, none excerpted.
    assert len(agent.captured_chunks) == 3
    assert agent.captured_chunks_dropped is False
    assert agent.captured_text_excerpted is False
    for packed in agent.captured_chunks:
        assert len(packed["text"]) == 200
        assert not packed["text"].endswith("...")


def test_note_present_when_chunks_dropped(monkeypatch) -> None:
    """Prompt note should be present when chunks are dropped."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(
            agent_max_chunks=2,
            agent_max_excerpt_chars=800,
            agent_prompt_budget_chars=12000,
            agent_small_doc_threshold=1,
        ),
    )

    chunks = _make_chunk_infos(5, keyword="security data")
    agent = SME(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )

    # Capture the prompt by intercepting _call_llm.
    captured_prompt = []
    original_call_llm = agent._call_llm
    def capture_llm(prompt):
        captured_prompt.append(prompt)
        return original_call_llm(prompt)
    agent._call_llm = capture_llm

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        context_text="query",
    )

    assert len(captured_prompt) == 1
    payload = json.loads(captured_prompt[0])
    assert "note" in payload
    assert "subset of chunks" in payload["note"]


def test_note_present_when_text_excerpted(monkeypatch) -> None:
    """Prompt note should be present when text is excerpted."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(
            agent_max_chunks=12,
            agent_max_excerpt_chars=30,  # Very short, forces excerpting
            agent_prompt_budget_chars=12000,
            agent_small_doc_threshold=1,
        ),
    )

    chunks = _make_chunk_infos(3, keyword="security data")
    agent = SME(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )

    captured_prompt = []
    original_call_llm = agent._call_llm
    def capture_llm(prompt):
        captured_prompt.append(prompt)
        return original_call_llm(prompt)
    agent._call_llm = capture_llm

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        context_text="query",
    )

    assert len(captured_prompt) == 1
    payload = json.loads(captured_prompt[0])
    assert "note" in payload
    assert "excerpted" in payload["note"]


def test_note_absent_for_small_unchanged_docs(monkeypatch) -> None:
    """Prompt note should be absent when small docs pass through unchanged."""
    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.base.get_settings",
        lambda: _mock_settings(),
    )

    chunks = _make_chunk_infos(3)  # Below threshold of 6, short text.
    agent = SME(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        ),
    )

    captured_prompt = []
    original_call_llm = agent._call_llm
    def capture_llm(prompt):
        captured_prompt.append(prompt)
        return original_call_llm(prompt)
    agent._call_llm = capture_llm

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=chunks,
        context_text="query",
    )

    assert len(captured_prompt) == 1
    payload = json.loads(captured_prompt[0])
    assert "note" not in payload
