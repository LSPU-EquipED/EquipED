"""Supervisor for sequential multi-agent evaluation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

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
    def __init__(self, *, agents: list[Any] | None = None) -> None:
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
        context: dict[str, str] | None = None,
    ) -> SupervisorResult:
        context = context or {}
        result = SupervisorResult(evaluation_id=evaluation_id, document_id=document_id)

        chunk_texts = [chunk.text for chunk in chunks if getattr(chunk, "text", None)]
        if not chunk_texts:
            raise SupervisorExecutionError("document has no chunk text to evaluate")

        for agent in self.agents:
            try:
                agent_result = agent.run(
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    chunk_texts=chunk_texts,
                    context_text=context.get("syllabus"),
                    reference_text=context.get("curriculum"),
                    prompt_version=context.get("prompt_version"),
                )
                result.agent_results.append(agent_result)
            except Exception as exc:
                agent_name = getattr(agent, "agent_name", agent.__class__.__name__)
                result.failures[agent_name] = str(exc)

        return result


__all__ = ["Supervisor", "SupervisorResult"]
