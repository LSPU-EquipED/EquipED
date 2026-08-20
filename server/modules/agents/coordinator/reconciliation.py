"""Coordinator reconciliation and independent fallback execution."""

from __future__ import annotations

import dataclasses

from ...agents.contracts import AgentEvaluationResult
from ...agents.exceptions import AgentExecutionError
from ..sme.oracle.registry import REGISTERED_CODES
from .summary import _build_alignment_summary


def merge_with_sme(
    coordinator_result: AgentEvaluationResult,
    sme_result: AgentEvaluationResult,
) -> AgentEvaluationResult:
    """Splice SME's 9 non-A-05 scores with Coordinator's own A-05 score.

    No I/O beyond one optional LLM call: the summary is generated here
    (not in Coordinator's own ``run()``) specifically because this is
    the first point where the FULL 10-criterion context exists --
    letting the summary's positive line cite any strong criterion, not
    just A-05). Called from
    ``evaluations/orchestrator.py`` after both agents have already
    finished running. Coordinator's and SME's rubric text is
    intentionally identical (see module docstring), so the 9 reused
    scores' titles need no re-lookup. If ``llm_client`` is ``None`` or
    the call fails, falls back to the deterministic A-05-only summary.
    """
    coordinator_a05 = next(
        (c for c in coordinator_result.criterion_scores if c.criterion_id == "A-05"),
        None,
    )
    if coordinator_a05 is None:
        raise AgentExecutionError("Coordinator's own result has no A-05 score to merge")

    sme_codes = [c.criterion_id for c in sme_result.criterion_scores]
    if set(sme_codes) != set(REGISTERED_CODES) or len(sme_codes) != len(
        REGISTERED_CODES
    ):
        raise AgentExecutionError(
            "SME result must contain exactly the canonical ten criteria"
        )
    merged_scores = tuple(
        coordinator_a05 if c.criterion_id == "A-05" else c
        for c in sme_result.criterion_scores
    )
    subtotal = sum(c.score for c in merged_scores) / len(merged_scores)
    summary = _build_alignment_summary(merged_scores)
    provenance = dict(coordinator_result.provenance or {})

    return dataclasses.replace(
        sme_result,
        agent_name=coordinator_result.agent_name,
        criterion_scores=merged_scores,
        subtotal=subtotal,
        summary=summary,
        model_name=coordinator_result.model_name,
        processing_seconds=coordinator_result.processing_seconds,
        token_count=coordinator_result.token_count,
        prompt_version_id=None,
        provenance=provenance or None,
    )
