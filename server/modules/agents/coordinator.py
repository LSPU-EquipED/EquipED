"""Program coordinator domain agent.

Coordinator's rubric is intentionally identical to SME's (see
``server/data/rubrics/rubrics.json``, agent_id="coordinator" -- same 10
codes/titles/descriptions as SME's). Coordinator runs its own full engine
scoring independently — it does NOT reuse SME's results, ensuring each agent
produces an independent evaluation for the synthesis layer.
"""

from __future__ import annotations

import uuid
from typing import Any

from .contracts import AgentEvaluationResult
from .engine_scoring import EngineScoredAgent
from .exceptions import AgentExecutionError


class Coordinator(EngineScoredAgent):
    agent_name = "coordinator"
    rubric_source_type = "rubric_coord"
    reference_source_types = ("syllabus",)
    domain_keywords = (
        "program", "outcomes", "objectives", "curriculum", "alignment",
        "competencies", "learning outcomes", "course", "standards",
        "assessment", "goals",
    )

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        db: Any | None = None,
        llm_client: Any | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Score every coordinator criterion independently via the engine."""
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        if llm_client is not None:
            self._llm_client = llm_client

        return self._run_full_engine_scoring(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=chunk_infos,
            context_text=context_text,
            prompt_version_id=prompt_version_id,
            db=db,
        )


ProgramCoordinator = Coordinator


__all__ = ["Coordinator", "ProgramCoordinator"]
