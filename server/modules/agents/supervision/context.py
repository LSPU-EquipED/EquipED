"""Sequential preparation of the immutable evaluation context."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from server.modules.admin.prompt_service import get_active_prompt
from server.modules.documents.ingestion.pipeline import prepare_canonical_source
from server.modules.documents.models import Document, DocumentChunk
from server.modules.documents.paths import resolve_document_pdf_path
from server.modules.rubrics.service import (
    get_active_rubric_context,
    resolve_rubric_agent_id,
)

from ..exceptions import SupervisorExecutionError

logger = logging.getLogger(__name__)


class _Unset:
    __slots__ = ()


_UNSET = _Unset()


@dataclass(frozen=True, slots=True)
class PreparedEvaluationContext:
    chunk_infos: tuple[Any, ...]
    query_text: str
    prompt_versions: MappingProxyType
    reference_document_ids: MappingProxyType
    precomputed_context: MappingProxyType
    canonical_source_text: str
    authoritative_curriculum_text: str | None


@dataclass(frozen=True, slots=True)
class PromptSnapshot:
    version_id: Any
    prompt_text: str


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


class EvaluationContextBuilder:
    _MAX_REFERENCE_ANCHORS = 3
    _REFERENCE_N_RESULTS_PER_ANCHOR = 2
    _REFERENCE_MAX_TOTAL = 5

    def __init__(self, db: Any | None, agents: list[Any]) -> None:
        self.db = db
        self.agents = agents

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
        from server.modules.embeddings.collections import resolve_collection_name
        from server.modules.embeddings.retrieval import (
            retrieve_context,
            retrieve_context_with_embedding,
        )

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
                    resolve_rubric_agent_id(source_type),
                    db=self.db,
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
                    query_text,
                    collection_name,
                    n_results=n_results,
                    document_id_filter=document_id_filter,
                )
            return [c.text for c in chunks]

        # Pre-compute rubric context for each agent's rubric source type.
        # Rubric behavior is preserved exactly as-is.
        rubric_sources = (
            "rubric_sme",
            "rubric_coord",
            "rubric_gad",
            "rubric_itso",
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

    def _load_active_prompt_versions(self) -> MappingProxyType:
        if self.db is None and any(
            getattr(agent, "agent_name", agent.__class__.__name__) != "coordinator"
            for agent in self.agents
        ):
            raise SupervisorExecutionError(
                "database session is required for evaluation"
            )

        prompt_versions: dict[str, PromptSnapshot] = {}
        for agent in self.agents:
            agent_name = getattr(agent, "agent_name", agent.__class__.__name__)
            if agent_name == "coordinator":
                prompt_versions[agent_name] = PromptSnapshot(None, "")
                continue
            prompt = get_active_prompt(agent_name, self.db)
            prompt_versions[agent_name] = PromptSnapshot(
                prompt.version_id, prompt.prompt_text
            )
        return _freeze(prompt_versions)

    def _load_authoritative_curriculum(self, refs: dict[str, Any]) -> str | None:
        curriculum_id = refs.get("curriculum")
        if self.db is None or curriculum_id is None:
            return None
        document = self.db.get(Document, curriculum_id)
        if document is None or document.source_type != "curriculum":
            return None
        chunks = (
            self.db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == curriculum_id)
            .order_by(DocumentChunk.chunk_index.asc(), DocumentChunk.page_number.asc())
            .all()
        )
        if not chunks or any(chunk.source_type != "curriculum" for chunk in chunks):
            return None
        text = "\n".join(
            chunk.text.strip() for chunk in chunks if chunk.text and chunk.text.strip()
        )
        return text or None

    def build(
        self, *, chunks: list[Any], query_text: str | None, context: dict[str, Any]
    ) -> PreparedEvaluationContext:
        infos = [
            {
                "chunk_id": str(chunk.chunk_id),
                "page_number": chunk.page_number,
                "text": chunk.text,
            }
            for chunk in chunks
            if getattr(chunk, "text", None)
        ]
        if not infos:
            raise SupervisorExecutionError("document has no chunk text to evaluate")
        refs = context.get("reference_document_ids")
        if refs is not None and not isinstance(refs, dict):
            raise SupervisorExecutionError("reference_document_ids must be a mapping")
        refs = refs or {}
        # Preserve legacy values and additional keys; retrieval consumes known keys.
        text = query_text or "\n".join(info["text"] for info in infos)
        document_id = context.get("document_id")
        document = self.db.get(Document, document_id) if self.db is not None else None
        file_path = getattr(document, "file_path", None) if document else None
        if not file_path:
            raise SupervisorExecutionError("owned document has no stored path")
        try:
            canonical_source_text = prepare_canonical_source(
                resolve_document_pdf_path(file_path)
            )
        except Exception as exc:
            raise SupervisorExecutionError(
                "canonical source preparation failed"
            ) from exc
        prompts = self._load_active_prompt_versions()
        precompute_started = time.perf_counter()
        precomputed_context = self._build_precomputed_context(
            text, reference_document_ids=refs, chunk_infos=infos
        )
        logger.info(
            "[EVAL_TIMING] phase=precompute_context | seconds=%.3f | sources=%d",
            time.perf_counter() - precompute_started,
            len(precomputed_context),
        )
        return PreparedEvaluationContext(
            chunk_infos=_freeze(infos),
            query_text=text,
            prompt_versions=prompts,
            reference_document_ids=_freeze(refs),
            precomputed_context=_freeze(precomputed_context),
            canonical_source_text=canonical_source_text,
            authoritative_curriculum_text=self._load_authoritative_curriculum(refs),
        )
