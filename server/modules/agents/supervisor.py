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
    CHUNK_BATCH_SIZE = 8

    def __init__(
        self,
        *,
        agents: list[Any] | None = None,
        db: Any | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.db = db
        self.batch_size = batch_size or self.CHUNK_BATCH_SIZE
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
        context: dict[str, Any] | None = None,
    ) -> SupervisorResult:
        context = context or {}
        result = SupervisorResult(evaluation_id=evaluation_id, document_id=document_id)

        chunk_texts = [chunk.text for chunk in chunks if getattr(chunk, "text", None)]
        if not chunk_texts:
            raise SupervisorExecutionError("document has no chunk text to evaluate")

        prompt_versions = self._load_active_prompt_versions()
        reference_document_ids = context.get("reference_document_ids")
        if reference_document_ids is not None and not isinstance(
            reference_document_ids, dict
        ):
            raise SupervisorExecutionError("reference_document_ids must be a mapping")

        for agent in self.agents:
            agent_name = getattr(agent, "agent_name", agent.__class__.__name__)
            prompt_row = prompt_versions.get(agent_name)
            if prompt_row is None:
                raise SupervisorExecutionError(
                    f"No active prompt version found for agent {agent_name}"
                )

            agent_failures: list[str] = []
            agent_succeeded = False
            for batch in self._chunk_batches(chunk_texts):
                try:
                    agent_result = agent.run(
                        evaluation_id=evaluation_id,
                        document_id=document_id,
                        chunk_texts=batch,
                        prompt_version=prompt_row.prompt_text,
                        prompt_version_id=prompt_row.version_id,
                        reference_document_ids=reference_document_ids,
                    )
                    result.agent_results.append(agent_result)
                    agent_succeeded = True
                except Exception as exc:
                    agent_failures.append(str(exc))

            if agent_failures:
                result.failures[agent_name] = "; ".join(agent_failures)
            if not agent_succeeded:
                result.failures.setdefault(
                    agent_name, f"Agent {agent_name} failed during evaluation"
                )

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

    def _chunk_batches(self, chunk_texts: list[str]) -> list[list[str]]:
        return [
            chunk_texts[index : index + self.batch_size]
            for index in range(0, len(chunk_texts), self.batch_size)
        ]


__all__ = ["Supervisor", "SupervisorResult"]
