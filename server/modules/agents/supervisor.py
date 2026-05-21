"""Supervisor for sequential multi-agent evaluation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from server.modules.admin.service import get_active_prompt
from server.modules.documents.models import DocumentChunk

from .contracts import AgentEvaluationResult
from .coordinator import ProgramCoordinator
from .exceptions import SupervisorExecutionError
from .gad import GADAgent
from .itso import ITSOAgent
from .sme import SMEAgent


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

        query_text = query_text or "\n".join(info["text"] for info in chunk_infos)

        for agent in self.agents:
            agent_name = getattr(agent, "agent_name", agent.__class__.__name__)
            prompt_row = prompt_versions.get(agent_name)
            if prompt_row is None:
                raise SupervisorExecutionError(
                    f"No active prompt version found for agent {agent_name}"
                )

            try:
                agent_result = agent.run(
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    chunk_infos=chunk_infos,
                    context_text=query_text,
                    prompt_version=prompt_row.prompt_text,
                    prompt_version_id=prompt_row.version_id,
                    reference_document_ids=reference_document_ids,
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
                        success=False,
                        error_message=str(exc),
                    )
                )
                result.failures[agent_name] = str(exc)

        if not result.agent_results:
            raise SupervisorExecutionError("No usable agent outputs were produced")

        return result

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
