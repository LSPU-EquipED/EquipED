"""SME domain evaluation agent."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO

from ..contracts import AgentEvaluationResult
from .pipeline import EngineScoredAgent


class SME(EngineScoredAgent):
    agent_name = "sme"
    rubric_source_type = "rubric_sme"
    domain_keywords = (
        "accuracy",
        "content",
        "knowledge",
        "concepts",
        "theory",
        "definitions",
        "principles",
        "facts",
        "understanding",
        "correct",
    )

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        form_snapshot: EvaluationFormSnapshotDTO,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        prompt_version: str | None = None,
        llm_client: Any | None = None,
        canonical_source_text: str | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Evaluate SME criteria from an immutable EvaluationFormSnapshotDTO.

        - Snapshot is the sole rubric and criteria authority.
        - Packs domains into at most 3 primary envelopes.
        - Emits strategy-shaped measurements evaluated by deterministic pure
          calculators.
        """
        del kwargs
        return self._run_snapshot_scoring(
            evaluation_id=evaluation_id,
            document_id=document_id,
            form_snapshot=form_snapshot,
            chunk_infos=chunk_infos,
            context_text=context_text,
            prompt_version_id=prompt_version_id,
            canonical_source_text=canonical_source_text,
            llm_client=llm_client,
            prompt_preamble=prompt_version,
        )


__all__ = ["SME"]
