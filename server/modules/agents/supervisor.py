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
        precomputed_context = self._build_precomputed_context(
            query_text, reference_document_ids=reference_document_ids,
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
            if idx > 0 and settings.llm_agent_delay_seconds > 0:
                time.sleep(settings.llm_agent_delay_seconds)

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

        if not result.agent_results:
            raise SupervisorExecutionError("No usable agent outputs were produced")

        return result

    def _build_precomputed_context(
        self,
        query_text: str,
        *,
        reference_document_ids: dict[str, uuid.UUID] | None = None,
    ) -> dict[str, list[str]]:
        """Pre-compute retrieval results per source-type (not merged).

        Each agent will look up only its own source types from this dict,
        preserving per-agent scope while avoiding repeated embedding + Chroma
        queries with the same query text.
        """
        from server.modules.embeddings.collections import resolve_collection_name
        from server.modules.embeddings.retrieval import retrieve_context

        precomputed: dict[str, list[str]] = {}

        # Pre-compute rubric context for each agent's rubric source type.
        rubric_sources = (
            "rubric_sme", "rubric_coord", "rubric_gad", "rubric_itso",
        )
        for source_type in rubric_sources:
            try:
                collection_name = resolve_collection_name(source_type)
                chunks = retrieve_context(
                    query_text, collection_name, n_results=5,
                )
                precomputed[source_type] = [c.text for c in chunks]
            except Exception:
                precomputed[source_type] = []

        # Pre-compute reference context per source type.
        if reference_document_ids:
            for source_type in ("syllabus", "curriculum"):
                if source_type not in reference_document_ids:
                    continue
                try:
                    collection_name = resolve_collection_name(source_type)
                    chunks = retrieve_context(
                        query_text,
                        collection_name,
                        n_results=5,
                        document_id_filter=str(
                            reference_document_ids[source_type],
                        ),
                    )
                    precomputed[source_type] = [c.text for c in chunks]
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
