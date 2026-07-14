"""Gender and Development domain agent."""

from __future__ import annotations

import uuid
from typing import Any

from .contracts import AgentEvaluationResult
from .exceptions import AgentExecutionError
from .gad_scoring.gad_engine_scoring import GADScoredAgent


class GAD(GADScoredAgent):
    agent_name = "gad"
    rubric_source_type = "rubric_gad"
    domain_keywords = (
        "gender",
        "inclusion",
        "diversity",
        "equity",
        "accessibility",
        "representation",
        "inclusive",
        "fair",
        "bias",
        "equal",
        "marginalized",
        "sensitivity",
    )

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        prompt_version: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        llm_client: Any | None = None,
        provenance: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Score all five GAD criteria through the code-side GAD engine."""
        del kwargs
        has_text = any(str(chunk.get("text", "")).strip() for chunk in chunk_infos)
        if not chunk_infos or not has_text:
            raise AgentExecutionError("document chunks are required for evaluation")
        if llm_client is not None:
            self._llm_client = llm_client

        return self._run_gad_scoring(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=chunk_infos,
            prompt_version=prompt_version,
            prompt_version_id=prompt_version_id,
            provenance=provenance,
        )


GADAgent = GAD


__all__ = ["GAD", "GADAgent"]
