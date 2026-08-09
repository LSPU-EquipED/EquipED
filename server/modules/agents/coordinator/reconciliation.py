"""Coordinator reconciliation and independent fallback execution."""

from __future__ import annotations

import dataclasses
import logging
import uuid
from typing import TYPE_CHECKING, Any

from server.core.llm import get_llm_client, get_llm_model_name

from ...agents.contracts import AgentEvaluationResult
from ...agents.exceptions import AgentExecutionError
from ..runtime.llm import FallbackAwareClient, error_reference
from . import curriculum
from .summary import _build_llm_alignment_summary

if TYPE_CHECKING:
    from .agent import Coordinator

logger = logging.getLogger(__name__)


def merge_with_sme(
    coordinator_result: AgentEvaluationResult,
    sme_result: AgentEvaluationResult,
    *,
    llm_client: Any | None = None,
) -> AgentEvaluationResult:
    """Splice SME's 9 non-A-05 scores with Coordinator's own A-05 score.

    No I/O beyond one optional LLM call: the summary is generated here
    (not in Coordinator's own ``run()``) specifically because this is
    the first point where the FULL 10-criterion context exists --
    letting the summary's positive line cite any strong criterion, not
    just A-05 (see ``_build_llm_alignment_summary``). Called from
    ``evaluations/orchestrator.py`` after both agents have already
    finished running. Coordinator's and SME's rubric text is
    intentionally identical (see module docstring), so the 9 reused
    scores' titles need no re-lookup. If ``llm_client`` is ``None`` or
    the call fails, falls back to the deterministic A-05-only summary.
    """
    coordinator_a05 = next(
        (
            c
            for c in coordinator_result.criterion_scores
            if c.criterion_id == "A-05"
        ),
        None,
    )
    if coordinator_a05 is None:
        raise AgentExecutionError(
            "Coordinator's own result has no A-05 score to merge"
        )

    merged_scores = tuple(
        coordinator_a05 if c.criterion_id == "A-05" else c
        for c in sme_result.criterion_scores
    )
    subtotal = sum(c.score for c in merged_scores) / len(merged_scores)
    client = llm_client
    if client is not None and not isinstance(client, FallbackAwareClient):
        client = FallbackAwareClient(
            client,
            "coordinator",
            requested_model=(
                getattr(client, "model", None) or get_llm_model_name()
            ),
        )
    summary = _build_llm_alignment_summary(merged_scores, client)
    provenance = dict(coordinator_result.provenance or {})
    if isinstance(client, FallbackAwareClient):
        provenance.update(
            summary_requested_model=client.requested_model,
            summary_actual_model=client.actual_model,
            summary_fallback_occurred=client.fallback_occurred,
            fallback_occurred=(
                bool(provenance.get("fallback_occurred"))
                or client.fallback_occurred
            ),
        )

    return dataclasses.replace(
        sme_result,
        agent_name=coordinator_result.agent_name,
        criterion_scores=merged_scores,
        subtotal=subtotal,
        summary=summary,
        model_name=coordinator_result.model_name,
        processing_seconds=coordinator_result.processing_seconds,
        token_count=coordinator_result.token_count,
        prompt_version_id=coordinator_result.prompt_version_id,
        provenance=provenance or None,
    )

def run_full_independent(
    agent: Coordinator,
    *,
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
    chunk_infos: list[dict[str, Any]],
    context_text: str | None = None,
    prompt_version_id: uuid.UUID | None = None,
    db: Any | None = None,
    llm_client: Any | None = None,
    reference_document_ids: dict[str, Any] | None = None,
    roadmap_context: dict[str, Any] | None = None,
    **kwargs: Any,
) -> AgentEvaluationResult:
    """Run Coordinator's complete engine pass when SME reuse is unavailable."""
    if not chunk_infos:
        raise AgentExecutionError("document chunks are required for evaluation")
    client = llm_client or agent._default_llm_client or get_llm_client()
    adapter = (
        client
        if isinstance(client, FallbackAwareClient)
        else FallbackAwareClient(
            client,
            agent.agent_name,
            requested_model=(
                getattr(client, "model", None) or get_llm_model_name()
            ),
        )
    )
    curriculum_text = ""
    curriculum_id = (reference_document_ids or {}).get("curriculum")
    if curriculum_id is not None:
        try:
            curriculum_text = curriculum.prepare_curriculum_text(
                agent, document_id, curriculum_id, db
            )
        except Exception as exc:
            logger.warning(
                "Coordinator curriculum retrieval failed, scoring SLM-only "
                "(category=%s, reference=%s)",
                type(exc).__name__, error_reference(exc),
            )
            curriculum_text = ""
    raw_baskets: dict[str, dict[str, Any]] = {}
    roadmap_note = (
        curriculum.format_roadmap_note(roadmap_context) if roadmap_context else None
    )
    basket_extract_kwargs = (
        {
            "A1": {
                "curriculum_text": curriculum_text or None,
                "roadmap_context": roadmap_note or None,
            }
        }
        if curriculum_text or roadmap_note
        else None
    )
    result = agent._run_full_engine_scoring(
        evaluation_id=evaluation_id,
        document_id=document_id,
        chunk_infos=chunk_infos,
        context_text=context_text,
        prompt_version_id=prompt_version_id,
        db=db,
        raw_baskets_out=raw_baskets,
        basket_extract_kwargs=basket_extract_kwargs,
        llm_client=adapter,
    )
    if curriculum_text:
        try:
            result = curriculum.apply_curriculum_alignment(
                result, raw_baskets, curriculum_text
            )
        except Exception as exc:
            logger.warning(
                "Coordinator curriculum postprocess failed, preserving engine "
                "result (category=%s, reference=%s)",
                type(exc).__name__, error_reference(exc),
            )
    return dataclasses.replace(
        result,
        summary=_build_llm_alignment_summary(result.criterion_scores, adapter),
        model_name=(
            adapter.actual_model
            if adapter.actual_model != "unknown"
            else adapter.requested_model
        ),
        provenance={
            **(result.provenance or {}),
            "requested_model": adapter.requested_model,
            "actual_model": (
                adapter.actual_model
                if adapter.actual_model != "unknown"
                else adapter.requested_model
            ),
            "fallback_occurred": adapter.fallback_occurred,
        },
    )
