"""Synthesis matrix — weighted score aggregation and monitoring matrix logic."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.documents.models import Document
from server.modules.synthesis.models import (
    AgentResult,
    MonitoringMatrix,
)
from server.modules.synthesis.schemas import score_to_adjectival
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

AGENT_WEIGHTS: dict[str, float] = {
    "sme": 0.35,
    "coordinator": 0.30,
    "gad": 0.20,
    "itso": 0.15,
}


def compute_synthesized_score(
    agent_results: list[AgentResult],
    *,
    force_partial: bool = False,
    partial_reason: str | None = None,
) -> dict[str, Any]:
    active = [r for r in agent_results if r.success]
    failed = [r for r in agent_results if not r.success]

    domain_scores: dict[str, dict[str, Any]] = {}
    for result in agent_results:
        subtotal = float(result.subtotal or 0)
        domain_scores[result.agent_name] = {
            "criteria": [],
            "subtotal": subtotal,
            "max_score": 4,
            "status": "OK" if result.success else "ERROR",
        }

    if active:
        active_weight_sum = sum(AGENT_WEIGHTS.get(a.agent_name, 0.0) for a in active)
        normalized = {
            a.agent_name: AGENT_WEIGHTS.get(a.agent_name, 0.0) / active_weight_sum
            for a in active
        }

        synthesized = sum(
            normalized[a.agent_name] * _domain_pct(a.subtotal) for a in active
        )
        synthesized_score = round(synthesized, 2)

        overall = sum(normalized[a.agent_name] * float(a.subtotal) for a in active)
        overall_score = round(overall, 2)
    else:
        synthesized_score = 0.0
        overall_score = None

    # Add adjectival ratings to each domain
    for agent_name, domain in domain_scores.items():
        if domain["status"] == "OK":
            domain["adjectival_rating"] = score_to_adjectival(domain["subtotal"])
        else:
            domain["adjectival_rating"] = None

    # is_partial is True only when explicit partial intent is set (force_partial)
    is_partial = force_partial

    return {
        "synthesized_score": synthesized_score,
        "overall_score": overall_score,
        "adjectival_rating": score_to_adjectival(overall_score)
        if overall_score is not None
        else None,
        "domain_scores": domain_scores,
        "active_agents": [a.agent_name for a in active],
        "failed_agents": [a.agent_name for a in failed],
        "is_partial": is_partial,
        "partial_reason": partial_reason if is_partial else None,
    }


def _domain_pct(subtotal: float | None) -> float:
    if subtotal is None:
        return 0.0
    return (float(subtotal) / 4) * 100


def upsert_monitoring_matrix(
    db: Session,
    document_id: uuid.UUID,
    evaluation_id: uuid.UUID | None,
    evaluation_status: str,
    synthesized_score: float | None = None,
    domain_scores: dict[str, dict[str, Any]] | None = None,
    flag_count: int = 0,
    feedback_status: str = "NO_FEEDBACK",
) -> MonitoringMatrix:
    doc = db.get(Document, document_id)
    row = MonitoringMatrix(
        document_id=document_id,
        evaluation_id=evaluation_id,
        faculty_name=None,
        program=doc.program if doc else None,
        evaluation_status=evaluation_status,
        synthesized_score=synthesized_score,
        domain_scores_json=domain_scores,
        flag_count=flag_count,
        feedback_status=feedback_status,
    )

    try:
        db.add(row)
        db.flush()
        return row
    except IntegrityError:
        db.rollback()
        existing = db.query(MonitoringMatrix).filter_by(document_id=document_id).one()
        existing.evaluation_id = evaluation_id
        existing.evaluation_status = evaluation_status
        if synthesized_score is not None:
            existing.synthesized_score = synthesized_score
        if domain_scores is not None:
            existing.domain_scores_json = domain_scores
        if flag_count is not None:
            existing.flag_count = flag_count
        if feedback_status is not None:
            existing.feedback_status = feedback_status
        db.flush()
        return existing
