"""Public Program Coordinator agent.

The current adapter-v3 engine runs independent criterion tasks, official A-05
objective gauging and advisory-only C-01 curriculum alignment. Historical
snapshot and envelope compatibility is implemented in ``legacy.py``.
"""

from __future__ import annotations

import uuid
from typing import Any

from equiped_harness.coordinator.engine import run_current
from equiped_harness.result_contracts import AgentEvaluationResult
from equiped_harness.snapshot_contracts import EvaluationFormSnapshotDTO


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
        """Dispatch current adapter-3 execution; retain the legacy runner."""
        return run_current(
            self,
            evaluation_id=evaluation_id,
            document_id=document_id,
            form_snapshot=form_snapshot,
            chunk_infos=chunk_infos,
            context_text=context_text,
            prompt_version_id=prompt_version_id,
            llm_client=llm_client,
            reference_document_ids=reference_document_ids,
            roadmap_context=roadmap_context,
            canonical_source_text=canonical_source_text,
            curriculum_id=curriculum_id,
            curriculum_context=curriculum_context,
            **kwargs,
        )


__all__ = ["Coordinator"]
