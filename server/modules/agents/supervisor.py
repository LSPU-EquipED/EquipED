"""Supervisor for sequential multi-agent evaluation."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from server.core.config import get_settings
from server.modules.admin.service import get_active_prompt
from server.modules.documents.models import DocumentChunk
from server.modules.rubrics.service import get_active_rubric_context, resolve_rubric_agent_id

from .contracts import AgentEvaluationResult
from .coordinator import ProgramCoordinator
from .exceptions import SupervisorExecutionError
from .gad import GADAgent
from .itso import ITSOAgent
from .sme import SMEAgent

logger = logging.getLogger(__name__)


class _Unset:
    """Sentinel distinguishing 'not yet computed' from 'computed as None'."""

    __slots__ = ()


_UNSET = _Unset()


@dataclass(slots=True)
class SupervisorResult:
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    agent_results: list[AgentEvaluationResult] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)


class Supervisor:
    # Bounded multi-anchor reference retrieval (Phase 1) reduces full-document
    # query dilution for long SLMs. Short documents (≤1 non-empty chunk) still
    # use the historical single-query path; this is preserved to keep
    # small-doc behavior stable.
    _MAX_REFERENCE_ANCHORS: int = 3
    _REFERENCE_N_RESULTS_PER_ANCHOR: int = 2
    # Final cap per source matches the historical per-source n_results=5.
    _REFERENCE_MAX_TOTAL: int = 5

    def __init__(
        self,
        *,
        agents: list[Any] | None = None,
        db: Any | None = None,
    ) -> None:
        self.db = db
        self.agents = agents or [
            SMEAgent(),
            ProgramCoordinator(),
            GADAgent(),
            ITSOAgent(),
        ]

    def run_evaluation(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunks: list[DocumentChunk],
        query_text: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> SupervisorResult:
        eval_start = time.perf_counter()
        context = context or {}
        result = SupervisorResult(evaluation_id=evaluation_id, document_id=document_id)
        settings = get_settings()

        chunk_infos = [
            {
                "chunk_id": str(chunk.chunk_id),
                "page_number": chunk.page_number,
                "text": chunk.text,
            }
            for chunk in chunks
            if getattr(chunk, "text", None)
        ]
        if not chunk_infos:
            raise SupervisorExecutionError("document has no chunk text to evaluate")

        prompt_versions = self._load_active_prompt_versions()
        reference_document_ids = context.get("reference_document_ids")
        if reference_document_ids is not None and not isinstance(
            reference_document_ids, dict
        ):
            raise SupervisorExecutionError("reference_document_ids must be a mapping")
        if reference_document_ids is None:
            reference_document_ids = {}

        query_text = query_text or "\n".join(info["text"] for info in chunk_infos)

        # Pre-compute retrieval context per source-type (not merged).
        # Each agent receives only the context for its own rubric/reference
        # source types, preserving per-agent scope while avoiding repeated
        # embedding + Chroma queries with the same query text.
        precompute_start = time.perf_counter()
        precomputed_context = self._build_precomputed_context(
            query_text,
            reference_document_ids=reference_document_ids,
            chunk_infos=chunk_infos,
        )
        precompute_seconds = time.perf_counter() - precompute_start
        logger.info(
            "[EVAL_TIMING] phase=precompute_context | seconds=%.3f | sources=%d",
            precompute_seconds,
            len(precomputed_context),
        )

        for idx, agent in enumerate(self.agents):
            agent_name = getattr(agent, "agent_name", agent.__class__.__name__)
            prompt_row = prompt_versions.get(agent_name)
            if prompt_row is None:
                raise SupervisorExecutionError(
                    f"No active prompt version found for agent {agent_name}"
                )

            # Smart pacing: sleep BEFORE the LLM call (not after), and skip
            # the sleep before the very first agent. This eliminates the
            # wasted post-final-agent sleep while preserving rate-limit safety.
            # Per-agent delays take precedence over the global fallback.
            sleep_seconds = 0.0
            if idx > 0:
                sleep_seconds = self._get_agent_delay(
                    agent_name, settings,
                )
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

            agent_start = time.perf_counter()
            try:
                agent_result = agent.run(
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    chunk_infos=chunk_infos,
                    context_text=query_text,
                    prompt_version=prompt_row.prompt_text,
                    prompt_version_id=prompt_row.version_id,
                    reference_document_ids=reference_document_ids,
                    precomputed_context=precomputed_context,
                )
                result.agent_results.append(agent_result)
            except Exception as exc:
                agent_seconds = time.perf_counter() - agent_start
                logger.warning(
                    "[EVAL_TIMING] agent=%s | status=failed | seconds=%.3f | sleep_before=%.3f | error=%s",
                    agent_name,
                    agent_seconds,
                    sleep_seconds,
                    str(exc)[:200],
                )
                result.agent_results.append(
                    AgentEvaluationResult(
                        agent_name=agent_name,
                        evaluation_id=evaluation_id,
                        document_id=document_id,
                        subtotal=0.0,
                        criterion_scores=(),
                        summary="",
                        model_name="",
                        processing_seconds=0,
                        token_count=0,
                        prompt_version_id=prompt_row.version_id,
                        success=False,
                        error_message=str(exc),
                    )
                )
                result.failures[agent_name] = str(exc)
            else:
                agent_seconds = time.perf_counter() - agent_start
                logger.info(
                    "[EVAL_TIMING] agent=%s | status=ok | seconds=%.3f | sleep_before=%.3f",
                    agent_name,
                    agent_seconds,
                    sleep_seconds,
                )

        total_seconds = time.perf_counter() - eval_start
        logger.info(
            "[EVAL_TIMING] phase=evaluation_total | seconds=%.3f | agents=%d | failures=%d",
            total_seconds,
            len(result.agent_results),
            len(result.failures),
        )

        if not result.agent_results:
            raise SupervisorExecutionError("No usable agent outputs were produced")

        return result

    def _compute_query_embedding(self, query_text: str) -> list[float] | None:
        """Encode query text once for reuse across retrieval calls."""
        if not query_text or not query_text.strip():
            return None
        try:
            from server.core.embedding import get_embedding_model
            model = get_embedding_model()
            return model.encode([query_text], show_progress_bar=False).tolist()[0]
        except Exception:
            return None

    def _get_agent_delay(
        self, agent_name: str, settings: Any,
    ) -> int:
        """Return per-agent delay if configured, else global fallback."""
        per_agent = getattr(settings, "llm_agent_delay_per_agent", None)
        if per_agent and agent_name in per_agent:
            return int(per_agent[agent_name])
        return getattr(settings, "llm_agent_delay_seconds", 0)

    def _build_precomputed_context(
        self,
        query_text: str,
        *,
        reference_document_ids: dict[str, uuid.UUID] | None = None,
        query_embedding: list[float] | None = None,
        chunk_infos: list[dict[str, Any]] | None = None,
    ) -> dict[str, list[str]]:
        """Pre-compute retrieval results per source-type (not merged).

        Each agent will look up only its own source types from this dict,
        preserving per-agent scope while avoiding repeated embedding + Chroma
        queries with the same query text.

        When ``query_embedding`` is provided it is reused across all retrieval
        calls, avoiding redundant model.encode() invocations.

        When ``chunk_infos`` is provided and the document has more than one
        non-empty chunk, reference retrieval is split across at most
        ``_MAX_REFERENCE_ANCHORS`` anchor queries (early / middle / late) to
        avoid full-document query dilution for long SLMs. Rubric precompute
        is unaffected. When ``chunk_infos`` is absent (legacy callers /
        tests), the historical single-query path is preserved.
        """
        from server.modules.embeddings.retrieval import (
            retrieve_context,
            retrieve_context_with_embedding,
        )
        from server.modules.embeddings.collections import resolve_collection_name

        # Lazy query embedding: only computed when the short/single-query
        # reference path actually needs it. The multi-anchor path encodes
        # each anchor independently inside ``retrieve_context``, so computing
        # a full-document embedding up-front would waste work (and partially
        # defeat the purpose of avoiding full-document embedding for long
        # SLMs). When there are no reference IDs, no embedding is computed
        # at all.
        _cached_query_embedding: list[float] | None | _Unset = _UNSET

        def get_query_embedding() -> list[float] | None:
            nonlocal _cached_query_embedding
            if isinstance(_cached_query_embedding, _Unset):
                _cached_query_embedding = (
                    query_embedding
                    if query_embedding is not None
                    else self._compute_query_embedding(query_text)
                )
            return _cached_query_embedding

        precomputed: dict[str, list[str]] = {}

        def _retrieve(
            source_type: str,
            *,
            document_id_filter: str | None = None,
            n_results: int = 5,
        ) -> list[str]:
            if source_type.startswith("rubric_"):
                return get_active_rubric_context(
                    resolve_rubric_agent_id(source_type), db=self.db,
                )
            collection_name = resolve_collection_name(source_type)
            embedding = get_query_embedding()
            if embedding is not None:
                chunks = retrieve_context_with_embedding(
                    embedding,
                    collection_name,
                    n_results=n_results,
                    document_id_filter=document_id_filter,
                )
            else:
                chunks = retrieve_context(
                    query_text, collection_name,
                    n_results=n_results,
                    document_id_filter=document_id_filter,
                )
            return [c.text for c in chunks]

        # Pre-compute rubric context for each agent's rubric source type.
        # Rubric behavior is preserved exactly as-is.
        rubric_sources = (
            "rubric_sme", "rubric_coord", "rubric_gad", "rubric_itso",
        )
        for source_type in rubric_sources:
            try:
                precomputed[source_type] = get_active_rubric_context(
                    resolve_rubric_agent_id(source_type), db=self.db
                )
            except Exception:
                precomputed[source_type] = []

        # Pre-compute reference context per source type.
        if reference_document_ids:
            anchor_texts = self._select_reference_query_texts(
                chunk_infos or [],
                max_anchors=self._MAX_REFERENCE_ANCHORS,
            )
            use_multi_anchor = len(anchor_texts) > 1

            for source_type in ("syllabus", "curriculum"):
                if source_type not in reference_document_ids:
                    continue
                document_id_filter = str(reference_document_ids[source_type])
                try:
                    if use_multi_anchor:
                        # Long-doc path: bounded anchor queries to avoid
                        # full-document query dilution.
                        collection_name = resolve_collection_name(source_type)
                        precomputed[source_type] = (
                            self._retrieve_reference_context_for_queries(
                                anchor_texts,
                                collection_name=collection_name,
                                document_id_filter=document_id_filter,
                                n_results_per_query=(
                                    self._REFERENCE_N_RESULTS_PER_ANCHOR
                                ),
                                max_total_results=self._REFERENCE_MAX_TOTAL,
                            )
                        )
                    else:
                        # Short-doc / legacy path: single-query retrieval,
                        # preserving the historical query_text / query_embedding
                        # optimization.
                        precomputed[source_type] = _retrieve(
                            source_type,
                            document_id_filter=document_id_filter,
                            n_results=self._REFERENCE_MAX_TOTAL,
                        )
                except Exception:
                    precomputed[source_type] = []

        return precomputed

    def _select_reference_query_texts(
        self,
        chunk_infos: list[dict[str, Any]],
        *,
        max_anchors: int,
    ) -> list[str]:
        """Pick at most ``max_anchors`` non-empty chunk texts to use as queries.

        For documents with at most ``max_anchors`` non-empty chunks, all chunks
        are returned in original order. For longer documents, deterministic
        early / middle / late anchors are selected (preserving original order
        and deduping indices). Empty / whitespace-only texts are filtered out.
        """
        if not chunk_infos or max_anchors < 1:
            return []
        non_empty = [
            str(info.get("text", "")).strip()
            for info in chunk_infos
            if str(info.get("text", "")).strip()
        ]
        if not non_empty:
            return []
        if len(non_empty) <= max_anchors:
            return non_empty
        last_index = len(non_empty) - 1
        middle_index = last_index // 2
        candidate_indices = [0, middle_index, last_index]
        # Dedupe while preserving order (e.g. when len <= 2, indices may collide).
        seen: set[int] = set()
        selected: list[str] = []
        for idx in candidate_indices:
            if idx in seen:
                continue
            seen.add(idx)
            selected.append(non_empty[idx])
        return selected[:max_anchors]

    def _retrieve_reference_context_for_queries(
        self,
        query_texts: list[str],
        *,
        collection_name: str,
        document_id_filter: str | None,
        n_results_per_query: int,
        max_total_results: int,
    ) -> list[str]:
        """Run retrieval sequentially per anchor, merge / dedupe, cap total.

        Falls back gracefully per anchor (and overall) so a single failed
        anchor does not lose the others. The merged order preserves
        retrieval order (anchor-by-anchor, in-list order).

        ``retrieve_context`` already logs a warning and returns ``[]`` on
        internal errors, so the per-anchor try/except is a defensive net
        that keeps the sequential pipeline moving on unexpected exceptions.
        """
        from server.modules.embeddings.retrieval import retrieve_context

        merged: list[str] = []
        for query_text in query_texts:
            if len(merged) >= max_total_results:
                break
            try:
                chunks = retrieve_context(
                    query_text,
                    collection_name,
                    n_results=n_results_per_query,
                    document_id_filter=document_id_filter,
                )
            except Exception:
                continue
            for chunk in chunks:
                text = chunk.text if hasattr(chunk, "text") else str(chunk)
                merged.append(text)
        return self._dedupe_context_chunks(merged)[:max_total_results]

    def _dedupe_context_chunks(self, chunks: list[str]) -> list[str]:
        """Dedupe retrieved text while preserving first-seen order."""
        seen: set[str] = set()
        out: list[str] = []
        for chunk in chunks:
            if chunk in seen:
                continue
            seen.add(chunk)
            out.append(chunk)
        return out

    def _load_active_prompt_versions(self) -> dict[str, Any]:
        if self.db is None:
            raise SupervisorExecutionError(
                "database session is required for evaluation"
            )

        prompt_versions: dict[str, Any] = {}
        for agent in self.agents:
            agent_name = getattr(agent, "agent_name", agent.__class__.__name__)
            prompt_versions[agent_name] = get_active_prompt(agent_name, self.db)
        return prompt_versions

__all__ = ["Supervisor", "SupervisorResult"]
