"""Shared test-only rubric and snapshot fixtures and helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from server.modules.agents.contracts import (
    AdvisoryOutput,
    AgentEvaluationResult,
    CriterionScore,
)
from server.modules.evaluations.agent_schedule import scheduled_agent_ids
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.tests.rubrics.helpers import seed_all_rubrics

SEEDED_FIXTURE_CRITERION_CODES: dict[str, tuple[str, ...]] = {
    "sme": (
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
    ),
    "coordinator": (
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
    ),
    "gad": ("GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"),
    "itso": ("ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05"),
}
AGENT_CRITERION_CODES = SEEDED_FIXTURE_CRITERION_CODES


def prepare_test_snapshots(
    session,
    evaluation_id: UUID,
    *,
    partial_without_curriculum: bool = False,
):
    """Seed rubrics and resolve/reuse snapshots for the specified evaluation.

    Asserts that active snapshots match canonical seeded fixture criterion codes.
    """
    seed_all_rubrics(session)
    scheduled_ids = scheduled_agent_ids(
        partial_without_curriculum=partial_without_curriculum
    )
    snapshots = resolve_or_reuse_evaluation_snapshots(
        session, evaluation_id, scheduled_ids
    )
    for dto in snapshots:
        assert set(dto.criterion_codes) == set(
            SEEDED_FIXTURE_CRITERION_CODES[dto.agent_id]
        ), f"Snapshot criterion drift detected for {dto.agent_id}"
    return snapshots


def make_agent_result(
    agent_id: str,
    evaluation_id: UUID,
    document_id: UUID,
    *,
    success: bool = True,
    scores_by_criterion: dict[str, int] | None = None,
    chunk_ids_by_criterion: dict[str, tuple[str, ...]] | None = None,
    evidence_by_criterion: dict[str, tuple[str, ...]] | None = None,
    default_score: int = 3,
    error_message: str | None = None,
    advisory_outputs: AdvisoryOutput | None = None,
    metadata: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    prompt_version_id: UUID | None = None,
    summary: str = "Evaluation complete",
    model_name: str = "test-model",
    processing_seconds: float = 1.0,
    token_count: int = 100,
) -> AgentEvaluationResult:
    """Construct an AgentEvaluationResult with exact criterion codes for the agent."""
    if not success:
        safe_msg = (
            error_message or f"AgentReportedFailure (reference: {uuid4().hex[:16]})"
        )
        return AgentEvaluationResult(
            agent_name=agent_id,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=0.0,
            criterion_scores=(),
            summary="",
            model_name=model_name,
            processing_seconds=processing_seconds,
            token_count=0,
            prompt_version_id=prompt_version_id,
            success=False,
            error_message=safe_msg,
            metadata=metadata or {},
            provenance=provenance,
            advisory_outputs=None,
        )

    codes = SEEDED_FIXTURE_CRITERION_CODES.get(agent_id, ())
    scores: list[CriterionScore] = []
    total_score = 0
    for code in codes:
        sc = (
            scores_by_criterion.get(code, default_score)
            if scores_by_criterion
            else default_score
        )
        c_chunks = (
            chunk_ids_by_criterion.get(code, ()) if chunk_ids_by_criterion else ()
        )
        c_evidence = (
            evidence_by_criterion.get(code, ()) if evidence_by_criterion else ()
        )
        scores.append(
            CriterionScore(
                criterion_id=code,
                criterion_title=f"{code} Title",
                score=sc,
                justification=f"Justification for {code}",
                chunk_ids=c_chunks,
                evidence=c_evidence,
            )
        )
        total_score += sc

    subtotal = float(total_score) / len(codes) if codes else 0.0

    if agent_id == "itso" and advisory_outputs is None:
        un_cids = [
            s.criterion_id
            for s in scores
            if not s.chunk_ids or not s.evidence or not s.justification.strip()
        ]
        if un_cids:
            from server.modules.agents.contracts import UngroundedCriterionAdvisory

            advisory_outputs = AdvisoryOutput(
                ungrounded_criteria=tuple(
                    UngroundedCriterionAdvisory(
                        criterion_id=cid,
                        reason=f"Model score for {cid} ungrounded",
                    )
                    for cid in un_cids
                )
            )

    return AgentEvaluationResult(
        agent_name=agent_id,
        evaluation_id=evaluation_id,
        document_id=document_id,
        subtotal=subtotal,
        criterion_scores=tuple(scores),
        summary=summary,
        model_name=model_name,
        processing_seconds=processing_seconds,
        token_count=token_count,
        prompt_version_id=prompt_version_id,
        success=True,
        error_message=None,
        metadata=metadata or {},
        provenance=provenance,
        advisory_outputs=advisory_outputs,
    )


def make_scheduled_agent_results(
    evaluation_id: UUID,
    document_id: UUID,
    *,
    partial_without_curriculum: bool = False,
    **kwargs: Any,
) -> list[AgentEvaluationResult]:
    """Create results for all scheduled agents in canonical order."""
    scheduled = scheduled_agent_ids(
        partial_without_curriculum=partial_without_curriculum
    )
    return [
        make_agent_result(agent_id, evaluation_id, document_id, **kwargs)
        for agent_id in scheduled
    ]
