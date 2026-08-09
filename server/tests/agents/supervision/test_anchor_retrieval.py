"""Tests for bounded chunk-aware (multi-anchor) reference retrieval in the
builder's precomputed-context builder.

These tests focus on the design contract:
- Short / single-chunk documents keep the historical single-query path.
- Long documents (more than one non-empty chunk) split reference retrieval
  across at most 3 deterministic anchor queries (early / middle / late),
  dedupe the merged text, and cap the final context.
- Rubric precompute, the ``precomputed_context`` shape, and the Phase 1
  empty-list fallback on retrieval failure are all preserved.
"""

from __future__ import annotations

from uuid import uuid4

from server.modules.agents.supervision.context import EvaluationContextBuilder
from server.modules.embeddings.retrieval import RetrievedChunk
from server.tests.agents.helpers import _RetrievedChunk

# ------------------------------------------------------------------
# Anchor selection
# ------------------------------------------------------------------


def _chunks(texts: list[str]) -> list[dict[str, object]]:
    """Helper: build chunk_infos with sequential page numbers."""
    return [
        {"chunk_id": f"c{i}", "page_number": i + 1, "text": t}
        for i, t in enumerate(texts)
    ]


def test_select_reference_query_texts_empty_returns_empty() -> None:
    builder = EvaluationContextBuilder(db=None, agents=[])
    assert builder._select_reference_query_texts([], max_anchors=3) == []


def test_select_reference_query_texts_handles_none_chunk_infos() -> None:
    """Legacy callers passing ``None`` should not crash and should return []."""
    builder = EvaluationContextBuilder(db=None, agents=[])
    assert (
        builder._select_reference_query_texts(None, max_anchors=3) == []  # type: ignore[arg-type]  # noqa: E501
    )


def test_select_reference_query_texts_max_anchors_zero_returns_empty() -> None:
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks(["a", "b", "c"])
    assert builder._select_reference_query_texts(chunks, max_anchors=0) == []


def test_select_reference_query_texts_single_non_empty_chunk() -> None:
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks(["only chunk"])
    assert (
        builder._select_reference_query_texts(chunks, max_anchors=3)
        == ["only chunk"]
    )


def test_select_reference_query_texts_two_non_empty_chunks_returns_both() -> None:
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks(["early", "late"])
    assert (
        builder._select_reference_query_texts(chunks, max_anchors=3)
        == ["early", "late"]
    )


def test_select_reference_query_texts_filters_whitespace_chunks() -> None:
    """Empty / whitespace-only chunks must be filtered out before selection."""
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks(["alpha", "", "   ", "\n\t", "beta", "gamma"])
    # 3 non-empty after filtering; below or equal to max_anchors=3, so all kept.
    assert (
        builder._select_reference_query_texts(chunks, max_anchors=3)
        == ["alpha", "beta", "gamma"]
    )


def test_select_reference_query_texts_uses_early_middle_late_for_long_docs() -> None:
    """For >max_anchors non-empty chunks, picks indices [0, mid, last]."""
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(7)])
    selected = builder._select_reference_query_texts(chunks, max_anchors=3)
    assert selected == ["chunk-0", "chunk-3", "chunk-6"]


def test_select_reference_query_texts_early_middle_late_for_four_chunks() -> None:
    """For 4 non-empty chunks, indices are [0, 1, 3] (middle_index = (n-1)//2)."""
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(4)])
    selected = builder._select_reference_query_texts(chunks, max_anchors=3)
    assert selected == ["chunk-0", "chunk-1", "chunk-3"]


def test_select_reference_query_texts_early_middle_late_for_ten_chunks() -> None:
    """For 10 chunks, indices are [0, 4, 9]."""
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(10)])
    selected = builder._select_reference_query_texts(chunks, max_anchors=3)
    assert selected == ["chunk-0", "chunk-4", "chunk-9"]


def test_select_reference_query_texts_dedupes_overlapping_indices() -> None:
    """For 2 chunks, [0, 0, 1] should dedupe to [0, 1] preserving order."""
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks(["a", "b"])
    selected = builder._select_reference_query_texts(chunks, max_anchors=3)
    assert selected == ["a", "b"]


def test_select_reference_query_texts_all_empty_returns_empty() -> None:
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks(["", "   ", "\n"])
    assert (
        builder._select_reference_query_texts(chunks, max_anchors=3) == []
    )


# ------------------------------------------------------------------
# Dedupe helper
# ------------------------------------------------------------------


def test_dedupe_context_chunks_preserves_first_seen_order() -> None:
    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._dedupe_context_chunks(["a", "b", "a", "c", "b"])
    assert out == ["a", "b", "c"]


def test_dedupe_context_chunks_empty_input() -> None:
    builder = EvaluationContextBuilder(db=None, agents=[])
    assert builder._dedupe_context_chunks([]) == []


def test_dedupe_context_chunks_all_unique() -> None:
    builder = EvaluationContextBuilder(db=None, agents=[])
    assert builder._dedupe_context_chunks(["x", "y", "z"]) == ["x", "y", "z"]


def test_dedupe_context_chunks_all_duplicates() -> None:
    builder = EvaluationContextBuilder(db=None, agents=[])
    assert builder._dedupe_context_chunks(["a", "a", "a"]) == ["a"]


def test_dedupe_context_chunks_treats_distinct_strings_as_distinct() -> None:
    """Whitespace differences should NOT be silently collapsed."""
    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._dedupe_context_chunks(["a", "a ", " a"])
    assert out == ["a", "a ", " a"]


# ------------------------------------------------------------------
# Multi-anchor retrieval: dedupe + cap
# ------------------------------------------------------------------


def test_retrieve_reference_context_for_queries_calls_retrieve_per_anchor(
    monkeypatch,
) -> None:
    """One Chroma call per anchor (sequential), preserves per-anchor order."""
    captured_calls: list[tuple[str, int, str | None]] = []

    def fake_retrieve(query_text, collection, n_results=5, document_id_filter=None):
        captured_calls.append((query_text, n_results, document_id_filter))
        return [_RetrievedChunk(f"hit-for:{query_text}")]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        fake_retrieve,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._retrieve_reference_context_for_queries(
        ["anchor-0", "anchor-1", "anchor-2"],
        collection_name="col_reference_all",
        document_id_filter="ref-id-1",
        n_results_per_query=2,
        max_total_results=5,
    )

    assert len(captured_calls) == 3
    assert captured_calls[0][0] == "anchor-0"
    assert captured_calls[1][0] == "anchor-1"
    assert captured_calls[2][0] == "anchor-2"
    assert all(n == 2 for _, n, _ in captured_calls)
    assert all(f == "ref-id-1" for _, _, f in captured_calls)
    assert out == ["hit-for:anchor-0", "hit-for:anchor-1", "hit-for:anchor-2"]


def test_retrieve_reference_context_for_queries_dedupes_across_anchors(
    monkeypatch,
) -> None:
    """Duplicate text from different anchors must collapse to a single entry."""
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        lambda *a, **k: [_RetrievedChunk("shared"), _RetrievedChunk(f"unique-{a[0]}")],
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._retrieve_reference_context_for_queries(
        ["a0", "a1", "a2"],
        collection_name="col_reference_all",
        document_id_filter=None,
        n_results_per_query=2,
        max_total_results=10,
    )

    # 3 anchors * 2 hits = 6 raw, but "shared" repeats 3 times -> 4 unique.
    assert out == ["shared", "unique-a0", "unique-a1", "unique-a2"]


def test_retrieve_reference_context_for_queries_caps_total_results(
    monkeypatch,
) -> None:
    """Final result list must not exceed max_total_results."""
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        lambda *a, **k: [
            _RetrievedChunk(f"{a[0]}-hit-{i}") for i in range(3)
        ],
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._retrieve_reference_context_for_queries(
        ["a0", "a1", "a2"],
        collection_name="col_reference_all",
        document_id_filter=None,
        n_results_per_query=3,
        max_total_results=4,
    )

    assert len(out) == 4
    # Order preserved: first 4 unique hits from the first anchors.
    assert out == ["a0-hit-0", "a0-hit-1", "a0-hit-2", "a1-hit-0"]


def test_retrieve_reference_context_for_queries_stops_when_cap_reached(
    monkeypatch,
) -> None:
    """Once cap is hit, no further anchor queries are issued."""
    call_count = {"n": 0}

    def fake_retrieve(query_text, collection, n_results=5, document_id_filter=None):
        call_count["n"] += 1
        return [_RetrievedChunk(f"{query_text}-hit-{i}") for i in range(2)]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        fake_retrieve,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._retrieve_reference_context_for_queries(
        ["a0", "a1", "a2"],
        collection_name="col_reference_all",
        document_id_filter=None,
        n_results_per_query=2,
        max_total_results=2,
    )

    # Cap is 2; after the first anchor (2 unique hits) we must stop.
    assert call_count["n"] == 1
    assert out == ["a0-hit-0", "a0-hit-1"]


def test_retrieve_reference_context_for_queries_continues_on_per_anchor_failure(
    monkeypatch,
) -> None:
    """A failed anchor must not block subsequent anchors."""
    def flaky_retrieve(query_text, collection, n_results=5, document_id_filter=None):
        if query_text == "bad":
            raise RuntimeError("chroma temporarily unavailable")
        return [_RetrievedChunk(f"ok-for:{query_text}")]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        flaky_retrieve,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._retrieve_reference_context_for_queries(
        ["good-0", "bad", "good-1"],
        collection_name="col_reference_all",
        document_id_filter=None,
        n_results_per_query=2,
        max_total_results=5,
    )

    assert out == ["ok-for:good-0", "ok-for:good-1"]


def test_retrieve_reference_context_for_queries_empty_input_returns_empty(
    monkeypatch,
) -> None:
    """No anchors -> no calls, no results."""
    called = {"n": 0}

    def fake_retrieve(*a, **k):
        called["n"] += 1
        return []

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        fake_retrieve,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._retrieve_reference_context_for_queries(
        [],
        collection_name="col_reference_all",
        document_id_filter=None,
        n_results_per_query=2,
        max_total_results=5,
    )
    assert out == []
    assert called["n"] == 0


def test_retrieve_reference_context_for_queries_handles_empty_anchor_result(
    monkeypatch,
) -> None:
    """An anchor returning no chunks must not break the pipeline."""
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        lambda *a, **k: [],
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._retrieve_reference_context_for_queries(
        ["a0", "a1"],
        collection_name="col_reference_all",
        document_id_filter=None,
        n_results_per_query=2,
        max_total_results=5,
    )
    assert out == []


# ------------------------------------------------------------------
# Single-query fallback (short / single-chunk / legacy callers)
# ------------------------------------------------------------------


def test_build_precomputed_context_uses_single_query_for_single_chunk(
    monkeypatch,
) -> None:
    """1 non-empty chunk -> single-query path (no sequential per-anchor calls)."""
    multi_anchor_calls = {"n": 0}

    def trap_multi_anchor(self, query_texts, **kwargs):
        multi_anchor_calls["n"] += 1
        return []

    monkeypatch.setattr(
        "server.modules.agents.supervision.context.EvaluationContextBuilder._retrieve_reference_context_for_queries",  # noqa: E501
        trap_multi_anchor,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        lambda *a, **k: [_RetrievedChunk("single-query-result")],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = [{"chunk_id": "c1", "page_number": 1, "text": "only one"}]
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=[0.1, 0.2],
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    assert multi_anchor_calls["n"] == 0
    assert result["syllabus"] == ["single-query-result"]


def test_build_precomputed_context_uses_single_query_for_legacy_caller(
    monkeypatch,
) -> None:
    """chunk_infos=None (legacy) -> single-query path is preserved."""
    multi_anchor_calls = {"n": 0}

    def trap_multi_anchor(self, query_texts, **kwargs):
        multi_anchor_calls["n"] += 1
        return []

    monkeypatch.setattr(
        "server.modules.agents.supervision.context.EvaluationContextBuilder._retrieve_reference_context_for_queries",  # noqa: E501
        trap_multi_anchor,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        lambda *a, **k: [_RetrievedChunk("legacy-result")],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=[0.1, 0.2],
        chunk_infos=None,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    assert multi_anchor_calls["n"] == 0
    assert result["syllabus"] == ["legacy-result"]


def test_build_precomputed_context_uses_multi_anchor_for_long_doc(
    monkeypatch,
) -> None:
    """>1 non-empty chunk -> multi-anchor path is engaged."""
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        lambda query_text, collection, n_results=5, document_id_filter=None: [
            _RetrievedChunk(f"hit:{query_text}")
        ],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    # 5 non-empty chunks, max_anchors=3 -> 3 anchor queries: [0, 2, 4]
    assert result["syllabus"] == [
        "hit:chunk-0",
        "hit:chunk-2",
        "hit:chunk-4",
    ]


def test_build_precomputed_context_multi_anchor_respects_caps(
    monkeypatch,
) -> None:
    """Long doc path must apply _REFERENCE_N_RESULTS_PER_ANCHOR and _REFERENCE_MAX_TOTAL."""  # noqa: E501
    captured: list[int] = []

    def fake_retrieve(query_text, collection, n_results=5, document_id_filter=None):
        captured.append(n_results)
        # Return distinct hits per anchor to exercise the cap cleanly.
        return [
            _RetrievedChunk(f"{query_text}-hit-{i}")
            for i in range(n_results)
        ]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        fake_retrieve,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(10)])
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    # 3 anchors * n_results_per_query=2 = 6 raw, capped at 5.
    assert all(n == EvaluationContextBuilder._REFERENCE_N_RESULTS_PER_ANCHOR for n in captured)  # noqa: E501
    assert len(result["syllabus"]) == EvaluationContextBuilder._REFERENCE_MAX_TOTAL


def test_build_precomputed_context_multi_anchor_dedupes_results(
    monkeypatch,
) -> None:
    """Multi-anchor path must dedupe across anchors via _dedupe_context_chunks."""
    # Both anchor queries return the same text plus a unique marker.
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        lambda *a, **k: [
            _RetrievedChunk("shared"),
            _RetrievedChunk(f"unique-{a[0]}"),
        ],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    # 3 anchors, each returning ["shared", "unique-..."]. After dedupe:
    # ["shared", "unique-chunk-0", "unique-chunk-2", "unique-chunk-4"]
    assert result["syllabus"] == [
        "shared",
        "unique-chunk-0",
        "unique-chunk-2",
        "unique-chunk-4",
    ]


def test_build_precomputed_context_preserves_precomputed_shape(monkeypatch) -> None:
    """The precomputed_context dict shape (rubric + reference keys) must be stable."""
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        lambda *a, **k: [_RetrievedChunk("ref-hit")],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.get_active_rubric_context",
        lambda agent_id, db: [f"rubric-for:{agent_id}"],
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
            "curriculum": "00000000-0000-0000-0000-000000000002",
        },
    )

    # Shape: every rubric_ + both reference keys.
    expected_keys = {
        "rubric_sme", "rubric_coord", "rubric_gad", "rubric_itso",
        "syllabus", "curriculum",
    }
    assert expected_keys.issubset(set(result.keys()))

    # All values must be list[str] (precomputed contract).
    for key, value in result.items():
        assert isinstance(value, list), f"{key} should be a list"
        for item in value:
            assert isinstance(item, str), f"{key} items should be str"

    # Rubric precompute is preserved exactly (no anchor interference).
    assert result["rubric_sme"] == ["rubric-for:sme"]
    assert result["rubric_coord"] == ["rubric-for:coordinator"]
    assert result["rubric_gad"] == ["rubric-for:gad"]
    assert result["rubric_itso"] == ["rubric-for:itso"]


def test_build_precomputed_context_rubric_precompute_unaffected_by_anchors(
    monkeypatch,
) -> None:
    """Rubric precompute must use get_active_rubric_context, not retrieval."""
    retrieval_calls = {"n": 0}
    rubric_calls = {"agent_ids": []}

    def fake_retrieve(*a, **k):
        retrieval_calls["n"] += 1
        return [_RetrievedChunk("should-not-be-used-for-rubric")]

    def fake_rubric(agent_id, db):
        rubric_calls["agent_ids"].append(agent_id)
        return [f"real-rubric-for:{agent_id}"]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        fake_retrieve,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.get_active_rubric_context",
        fake_rubric,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    # Rubric precompute is still via get_active_rubric_context, exactly 4 agents.
    assert sorted(rubric_calls["agent_ids"]) == sorted(
        ["sme", "coordinator", "gad", "itso"]
    )


# ------------------------------------------------------------------
# Phase 1 fallback (retrieval failure -> empty list)
# ------------------------------------------------------------------


def test_build_precomputed_context_falls_back_to_empty_on_retrieval_failure(
    monkeypatch,
) -> None:
    """A reference retrieval exception must collapse to [] (Phase 1 contract)."""
    def boom(*a, **k):
        raise RuntimeError("chroma unavailable")

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        boom,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.rubrics.service.get_active_rubric_context",
        lambda agent_id, db: [],
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    # Even though retrieval exploded, syllabus key is present and empty,
    # and the surrounding pipeline is not interrupted.
    assert result["syllabus"] == []
    # Rubric keys are also present (preserved shape).
    for key in ("rubric_sme", "rubric_coord", "rubric_gad", "rubric_itso"):
        assert key in result


def test_build_precomputed_context_multi_anchor_continues_on_partial_failure(
    monkeypatch,
) -> None:
    """Multi-anchor path: per-anchor failures should not lose the other anchors."""
    def selective_boom(query_text, *a, **k):
        if query_text == "chunk-2":
            raise RuntimeError("intermittent chroma error")
        return [_RetrievedChunk(f"hit:{query_text}")]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        selective_boom,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    # Anchors: [chunk-0, chunk-2, chunk-4]. Middle one fails; the other two
    # still contribute.
    assert result["syllabus"] == ["hit:chunk-0", "hit:chunk-4"]


def test_build_precomputed_context_short_doc_does_not_use_anchor_text_filtering(
    monkeypatch,
) -> None:
    """Whitespace-only chunks should not push a single non-empty doc into multi-anchor."""  # noqa: E501
    multi_anchor_calls = {"n": 0}

    def trap_multi_anchor(self, query_texts, **kwargs):
        multi_anchor_calls["n"] += 1
        return []

    monkeypatch.setattr(
        "server.modules.agents.supervision.context.EvaluationContextBuilder._retrieve_reference_context_for_queries",  # noqa: E501
        trap_multi_anchor,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        lambda *a, **k: [_RetrievedChunk("ok")],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    # 1 non-empty + 2 whitespace -> 1 effective chunk -> single-query path.
    chunks = _chunks(["real-text", "   ", "\n"])
    builder._build_precomputed_context(
        "query text",
        query_embedding=[0.1, 0.2],
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    assert multi_anchor_calls["n"] == 0


def test_build_precomputed_context_uses_real_retrieved_chunk_dataclass(
    monkeypatch,
) -> None:
    """Merge real retrieval dataclasses in anchor and result order."""
    def retrieve(query_text, collection_name, *, n_results, document_id_filter):
        assert query_text in {"a0", "a1"}
        assert collection_name == "col_reference_all"
        assert n_results == 2
        assert document_id_filter == "d1"
        return [
            RetrievedChunk("shared", 0.1, "d1", "reference", 1, False, 1),
            RetrievedChunk(f"unique-{query_text}", 0.2, "d1", "reference", 1, False, 1),
        ]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context", retrieve
    )
    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._retrieve_reference_context_for_queries(
        ["a0", "a1"],
        collection_name="col_reference_all",
        document_id_filter="d1",
        n_results_per_query=2,
        max_total_results=3,
    )
    assert out == ["shared", "unique-a0", "unique-a1"]


def test_uuid_smoke_for_reference_doc_ids() -> None:
    """Sanity: precompute still accepts UUID-shaped reference doc ids."""
    from uuid import UUID
    assert isinstance(uuid4(), UUID)


# ------------------------------------------------------------------
# Additional edge-case coverage for the bounded retrieval patch
# ------------------------------------------------------------------


def test_select_reference_query_texts_exactly_max_anchors_returns_all() -> None:
    """Boundary: exactly max_anchors non-empty chunks -> all returned (no anchor selection)."""  # noqa: E501
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks(["first", "second", "third"])
    selected = builder._select_reference_query_texts(chunks, max_anchors=3)
    # len(non_empty) == max_anchors -> short-doc path, all chunks returned.
    assert selected == ["first", "second", "third"]


def test_select_reference_query_texts_max_anchors_one_returns_first() -> None:
    """max_anchors=1 with many chunks -> only the first non-empty chunk."""
    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    selected = builder._select_reference_query_texts(chunks, max_anchors=1)
    assert selected == ["chunk-0"]


def test_retrieve_reference_context_for_queries_all_anchors_fail(
    monkeypatch,
) -> None:
    """When every anchor raises, the result is an empty list (not an exception)."""
    def always_boom(query_text, collection, n_results=5, document_id_filter=None):
        raise RuntimeError("chroma completely down")

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        always_boom,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    out = builder._retrieve_reference_context_for_queries(
        ["a0", "a1", "a2"],
        collection_name="col_reference_all",
        document_id_filter=None,
        n_results_per_query=2,
        max_total_results=5,
    )
    assert out == []


def test_build_precomputed_context_empty_reference_document_ids(
    monkeypatch,
) -> None:
    """Empty reference_document_ids dict -> no reference retrieval at all."""
    retrieval_calls = {"n": 0}

    def fake_retrieve(*a, **k):
        retrieval_calls["n"] += 1
        return [_RetrievedChunk("should-not-appear")]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        fake_retrieve,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        fake_retrieve,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.get_active_rubric_context",
        lambda agent_id, db: [f"rubric-for:{agent_id}"],
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=[0.1, 0.2],
        chunk_infos=chunks,
        reference_document_ids={},
    )

    # No reference retrieval should have occurred.
    assert retrieval_calls["n"] == 0
    # No reference keys in the result.
    assert "syllabus" not in result
    assert "curriculum" not in result
    # Rubric keys are still present.
    assert "rubric_sme" in result


def test_build_precomputed_context_empty_chunk_infos_list_uses_single_query(
    monkeypatch,
) -> None:
    """chunk_infos=[] (empty list, not None) -> single-query path (no anchors)."""
    multi_anchor_calls = {"n": 0}

    def trap_multi_anchor(self, query_texts, **kwargs):
        multi_anchor_calls["n"] += 1
        return []

    monkeypatch.setattr(
        "server.modules.agents.supervision.context.EvaluationContextBuilder._retrieve_reference_context_for_queries",  # noqa: E501
        trap_multi_anchor,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        lambda *a, **k: [_RetrievedChunk("single-query-result")],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=[0.1, 0.2],
        chunk_infos=[],
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    assert multi_anchor_calls["n"] == 0
    assert result["syllabus"] == ["single-query-result"]


def test_build_precomputed_context_both_sources_use_multi_anchor(
    monkeypatch,
) -> None:
    """When both syllabus and curriculum are present, both use multi-anchor path."""
    captured_sources: list[str] = []

    def fake_retrieve(query_text, collection, n_results=5, document_id_filter=None):
        captured_sources.append(collection)
        return [_RetrievedChunk(f"hit:{collection}:{query_text}")]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        fake_retrieve,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    result = builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
            "curriculum": "00000000-0000-0000-0000-000000000002",
        },
    )

    # Both sources should have been retrieved via multi-anchor.
    # 3 anchors per source = 6 total retrieve_context calls.
    assert captured_sources.count("syllabus") == 3
    assert captured_sources.count("curriculum") == 3
    # Both keys present with results.
    assert len(result["syllabus"]) == 3
    assert len(result["curriculum"]) == 3
    # Verify anchor texts are correct (indices 0, 2, 4 for 5 chunks).
    assert result["syllabus"] == [
        "hit:syllabus:chunk-0",
        "hit:syllabus:chunk-2",
        "hit:syllabus:chunk-4",
    ]
    assert result["curriculum"] == [
        "hit:curriculum:chunk-0",
        "hit:curriculum:chunk-2",
        "hit:curriculum:chunk-4",
    ]


# ------------------------------------------------------------------
# Lazy query embedding optimization
# ------------------------------------------------------------------


def test_build_precomputed_context_long_doc_does_not_compute_full_embedding(
    monkeypatch,
) -> None:
    """Long-doc multi-anchor path must NOT call _compute_query_embedding."""
    compute_calls = {"n": 0}

    def trap_compute(self, query_text):
        compute_calls["n"] += 1
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(
        "server.modules.agents.supervision.context.EvaluationContextBuilder._compute_query_embedding",  # noqa: E501
        trap_compute,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        lambda query_text, collection, n_results=5, document_id_filter=None: [
            _RetrievedChunk(f"hit:{query_text}")
        ],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    # Multi-anchor path should NOT compute full-document embedding.
    assert compute_calls["n"] == 0


def test_build_precomputed_context_no_reference_ids_does_not_compute_embedding(
    monkeypatch,
) -> None:
    """Empty reference_document_ids must NOT call _compute_query_embedding."""
    compute_calls = {"n": 0}

    def trap_compute(self, query_text):
        compute_calls["n"] += 1
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(
        "server.modules.agents.supervision.context.EvaluationContextBuilder._compute_query_embedding",  # noqa: E501
        trap_compute,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        lambda *a, **k: [_RetrievedChunk("should-not-appear")],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        lambda *a, **k: [_RetrievedChunk("should-not-appear")],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.get_active_rubric_context",
        lambda agent_id, db: [f"rubric-for:{agent_id}"],
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks([f"chunk-{i}" for i in range(5)])
    builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={},
    )

    # No reference IDs -> no embedding computation at all.
    assert compute_calls["n"] == 0


def test_build_precomputed_context_short_doc_still_computes_embedding(
    monkeypatch,
) -> None:
    """Short-doc single-query path must still compute/use the embedding."""
    compute_calls = {"n": 0}

    def trap_compute(self, query_text):
        compute_calls["n"] += 1
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(
        "server.modules.agents.supervision.context.EvaluationContextBuilder._compute_query_embedding",  # noqa: E501
        trap_compute,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        lambda embedding, collection, n_results=5, document_id_filter=None: [
            _RetrievedChunk("single-query-result")
        ],
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    builder = EvaluationContextBuilder(db=None, agents=[])
    chunks = _chunks(["only one chunk"])
    builder._build_precomputed_context(
        "query text",
        query_embedding=None,
        chunk_infos=chunks,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    # Short-doc path should compute embedding exactly once.
    assert compute_calls["n"] == 1
