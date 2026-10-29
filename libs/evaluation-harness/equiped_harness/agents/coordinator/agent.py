"""Public Program Coordinator agent."""

from __future__ import annotations

import uuid
from typing import Any

from equiped_harness.contracts.results import AgentEvaluationResult
from equiped_harness.contracts.snapshots import EvaluationFormSnapshotDTO


class Coordinator:
    agent_name = "coordinator"
    rubric_source_type = "rubric_coord"
    reference_source_types = ("syllabus",)
    domain_keywords = (
        "program",
        "outcomes",
        "objectives",
        "curriculum",
        "alignment",
        "competencies",
        "learning outcomes",
        "course",
        "standards",
        "assessment",
        "goals",
    )

    def __init__(self, *, llm_client: Any | None = None) -> None:
        self._default_llm_client = llm_client

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        form_snapshot: EvaluationFormSnapshotDTO,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        llm_client: Any | None = None,
        reference_document_ids: dict[str, Any] | None = None,
        roadmap_context: dict[str, Any] | None = None,
        canonical_source_text: str | None = None,
        curriculum_id: uuid.UUID | None = None,
        curriculum_context: str | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Dispatch the frozen adapter version without loading retired pipelines."""
        if form_snapshot.adapter_version != 4:
            from equiped_harness.exceptions import AgentExecutionError

            raise AgentExecutionError(
                "Coordinator execution supports adapter 4 only; create a new "
                "evaluation to use the current Coordinator harness"
            )
        from equiped_harness.agents.coordinator.pipeline import run

        return run(
            evaluation_id=evaluation_id,
            document_id=document_id,
            form_snapshot=form_snapshot,
            chunk_infos=chunk_infos,
            canonical_source_text=canonical_source_text,
            curriculum_id=curriculum_id,
            curriculum_context=curriculum_context,
            llm_client=llm_client or self._default_llm_client,
            prompt_version_id=prompt_version_id,
            **kwargs,
        )


__all__ = ["Coordinator"]
