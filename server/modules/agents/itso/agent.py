"""ITSO domain agent."""

from __future__ import annotations

from typing import Any

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
        evaluation_id,
        document_id,
        chunk_infos,
        context_text=None,
        reference_text=None,
        prompt_version=None,
        prompt_version_id=None,
        reference_document_ids=None,
        precomputed_context=None,
        llm_client=None,
        llm_temperature=None,
        provenance=None,
        policy_evidence=None,
        **kwargs,
    ):
        del kwargs
        context = ITSOExecutionContext(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=tuple(chunk_infos),
            context_text=context_text,
            reference_text=reference_text,
            prompt_version=prompt_version,
            prompt_version_id=prompt_version_id,
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
