"""ITSO domain agent."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO

from ..contracts import AgentEvaluationResult
from ..runtime.context import ITSOExecutionContext
from .execution import execute


class ITSO:
    agent_name = "itso"
    rubric_source_type = "rubric_itso"
    domain_keywords = (
        "security",
        "privacy",
        "data",
        "protection",
        "encryption",
        "authentication",
        "threat",
        "vulnerability",
        "confidential",
        "integrity",
        "access control",
        "risk",
        "plagiarism",
        "citation",
        "reference",
        "bibliography",
        "source",
        "intellectual property",
        "copyright",
        "ownership",
        "student data",
        "rights",
    )

    def __init__(self, *, llm_client: Any | None = None) -> None:
        self._default_llm_client = llm_client

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        form_snapshot: EvaluationFormSnapshotDTO,
        context_text: str | None = None,
        reference_text: str | None = None,
        prompt_version: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        reference_document_ids: dict[str, Any] | None = None,
        precomputed_context: dict[str, Any] | None = None,
        llm_client: Any | None = None,
        llm_temperature: float | None = None,
        provenance: dict[str, Any] | None = None,
        policy_evidence: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        del kwargs
        context = ITSOExecutionContext(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=tuple(chunk_infos),
            context_text=context_text,
            reference_text=reference_text,
            prompt_version=prompt_version,
            prompt_version_id=prompt_version_id,
            form_snapshot=form_snapshot,
            provenance=provenance or {},
            policy_evidence=policy_evidence or {},
            reference_document_ids=reference_document_ids or {},
            precomputed_context=precomputed_context or {},
            domain_keywords=self.domain_keywords,
            llm_client=llm_client or self._default_llm_client,
            llm_temperature=llm_temperature,
        )
        return execute(
            context,
            llm_client=context.llm_client,
            llm_temperature=context.llm_temperature,
        )


__all__ = ["ITSO"]
