"""ITSO domain agent."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from equiped_harness.agents.itso.contracts import ITSOExecutionContext
from equiped_harness.agents.itso.execution import execute
from equiped_harness.contracts.results import AgentEvaluationResult
from equiped_harness.contracts.snapshots import EvaluationFormSnapshotDTO
from equiped_harness.runtime.control import ExecutionControl
from equiped_harness.tools.config import ToolConfig


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

    def prepare_inputs(
        self,
        inputs: dict[str, Any],
        *,
        tools: ToolConfig | None,
        control: ExecutionControl,
    ) -> dict[str, Any]:
        """Perform required source checks before the prepared scoring pipeline."""
        version = inputs["form_snapshot"].adapter_version
        if version != 3:
            raise ValueError(f"Unsupported ITSO adapter version {version}")
        if tools is None or not tools.enabled:
            raise ValueError("ITSO adapter 3 requires enabled public-reference tools")
        from equiped_harness.agents.itso.tools.reference_search import (
            build_public_reference_report,
        )

        control.check()
        report = asyncio.run(
            build_public_reference_report(
                inputs.get("context_text") or inputs.get("canonical_source_text") or "",
                enabled=True,
                settings=tools,
                transport=tools.transport,
                control=control,
            )
        )
        control.check()
        precomputed = inputs.get("precomputed_context") or {}
        precomputed["public_reference_verification"] = [
            json.dumps(report, ensure_ascii=False, sort_keys=True)
        ]
        return {**inputs, "precomputed_context": precomputed}

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
