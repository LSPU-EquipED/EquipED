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


@dataclass(slots=True)
class SupervisorResult:
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    agent_results: list[AgentEvaluationResult] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)


class Supervisor:
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
    ) -> dict[str, list[str]]:
        """Pre-compute retrieval results per source-type (not merged).

        Each agent will look up only its own source types from this dict,
        preserving per-agent scope while avoiding repeated embedding + Chroma
        queries with the same query text.

        When ``query_embedding`` is provided it is reused across all retrieval
        calls, avoiding redundant model.encode() invocations.
        """
        from server.modules.embeddings.retrieval import (
            retrieve_context,
            retrieve_context_with_embedding,
        )
        from server.modules.embeddings.collections import resolve_collection_name

        # Compute embedding once if not supplied by caller.
        if query_embedding is None:
            query_embedding = self._compute_query_embedding(query_text)

        precomputed: dict[str, list[str]] = {}

        def _retrieve(
            source_type: str,
            *,
            document_id_filter: str | None = None,
            n_results: int = 5,
        ) -> list[str]:
            if source_type.startswith("rubric_"):
                return get_active_rubric_context(resolve_rubric_agent_id(source_type), db=self.db)
            collection_name = resolve_collection_name(source_type)
            if query_embedding is not None:
                chunks = retrieve_context_with_embedding(
                    query_embedding,
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
            for source_type in ("syllabus", "curriculum"):
                if source_type not in reference_document_ids:
                    continue
                try:
                    precomputed[source_type] = _retrieve(
                        source_type,
                        document_id_filter=str(
                            reference_document_ids[source_type],
                        ),
                    )
                except Exception:
                    precomputed[source_type] = []

        return precomputed

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
