"""Master synthesis scorecard assembly with evaluator and document details."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.auth.models import User
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.synthesis.exceptions import MonitoringMatrixNotFoundError
from server.modules.synthesis.matrix import (
    AGENT_WEIGHTS,
    PROGRESSIVE_AGENT_IDS,
    _composite_from_domains,
)
from server.modules.synthesis.models import (
    AgentResult,
    CriterionScore,
    EvaluationFlag,
    MonitoringMatrix,
)
from server.modules.synthesis.schemas import (
    CriterionScoreItem,
    EvaluationFlagItem,
    EvaluatorAttribution,
    MasterSynthesisDetailResponse,
    MasterSynthesisPillar,
    score_to_adjectival,
)
from sqlalchemy import func


def get_master_synthesis_detail(
    db: Any,
    document_id: uuid.UUID,
) -> MasterSynthesisDetailResponse:
    """Return master synthesis scorecard with author & evaluator attribution."""
    matrix = (
        db.query(MonitoringMatrix).filter_by(document_id=document_id).first()
        if db is not None
        else None
    )
    if matrix is None:
        raise MonitoringMatrixNotFoundError(
            f"Monitoring matrix for document {document_id} not found."
        )

    doc_row = (
        db.query(Document, User)
        .outerjoin(User, Document.uploaded_by == User.user_id)
        .filter(Document.document_id == document_id)
        .first()
        if db is not None
        else None
    )

    document = None
    if doc_row is not None:
        document, author_user = doc_row
        if author_user is not None:
            author = EvaluatorAttribution(
                user_id=author_user.user_id,
                name=author_user.name,
                email=author_user.email,
                department=author_user.department,
            )
        else:
            author = EvaluatorAttribution(
                user_id=document.uploaded_by if document else None,
                name="Unknown Author",
                email=None,
                department=None,
            )
    else:
        author = EvaluatorAttribution(
            user_id=None,
            name="Unknown Author",
            email=None,
            department=None,
        )

    same_module_doc_ids = [document_id]
    if document is not None and getattr(document, "source_type", None) == "slm":
        same_module_doc_ids = [
            d.document_id
            for d in db.query(Document.document_id)
            .filter(
                Document.source_type == "slm",
                func.lower(Document.title) == document.title.strip().lower(),
                func.lower(Document.program)
                == (document.program or "").strip().lower(),
            )
            .all()
        ]

    job_rows = (
        db.query(EvaluationJob, User)
        .outerjoin(User, EvaluationJob.submitted_by == User.user_id)
        .filter(
            EvaluationJob.document_id.in_(same_module_doc_ids),
            EvaluationJob.status == EvaluationStatus.COMPLETED.value,
        )
        .order_by(EvaluationJob.submitted_at.desc())
        .all()
        if db is not None
        else []
    )

    evaluator_by_agent: dict[str, EvaluatorAttribution] = {}
    fallback_bundle_evaluator: EvaluatorAttribution | None = None
    for job, user in job_rows:
        attr = None
        if user is not None:
            attr = EvaluatorAttribution(
                user_id=user.user_id,
                name=user.name,
                email=user.email,
                department=user.department,
            )
        elif job.submitted_by is not None:
            attr = EvaluatorAttribution(
                user_id=job.submitted_by,
                name="Unknown Evaluator",
                email=None,
                department=None,
            )

        if attr is not None:
            if job.target_agent in PROGRESSIVE_AGENT_IDS:
                if job.target_agent not in evaluator_by_agent:
                    evaluator_by_agent[job.target_agent] = attr
            elif job.target_agent == "all" and fallback_bundle_evaluator is None:
                fallback_bundle_evaluator = attr

    domain_scores_json = (
        matrix.domain_scores_json if isinstance(matrix.domain_scores_json, dict) else {}
    )
    pillars: dict[str, MasterSynthesisPillar] = {}
    for agent in PROGRESSIVE_AGENT_IDS:
        weight = AGENT_WEIGHTS.get(agent, 0.0)
        domain_data = (
            domain_scores_json.get(agent)
            if isinstance(domain_scores_json, dict)
            else None
        )

        if domain_data is not None and isinstance(domain_data, dict):
            subtotal_raw = domain_data.get("subtotal")
            subtotal = float(subtotal_raw) if subtotal_raw is not None else None
            status_val = domain_data.get("status") or "COMPLETED"
            if str(status_val).upper() == "OK":
                status_str = "COMPLETED"
            else:
                status_str = str(status_val).upper()
            summary = str(domain_data.get("summary") or "")

            raw_criteria = domain_data.get("criteria") or []
            criteria_items: list[CriterionScoreItem] = []
            for c in raw_criteria:
                if isinstance(c, dict):
                    criteria_items.append(CriterionScoreItem(**c))
                elif isinstance(c, CriterionScoreItem):
                    criteria_items.append(c)
        else:
            subtotal = None
            status_str = "PENDING"
            summary = ""
            criteria_items = []

        if not criteria_items and db is not None:
            agent_crit_scores = (
                db.query(CriterionScore)
                .join(
                    AgentResult,
                    CriterionScore.agent_result_id == AgentResult.agent_result_id,
                )
                .filter(
                    CriterionScore.document_id.in_(same_module_doc_ids),
                    AgentResult.agent_name == agent,
                )
                .all()
            )
            if agent_crit_scores:
                criteria_items = [
                    CriterionScoreItem(
                        criterion_id=cs.criterion_id,
                        criterion_text=cs.criterion_title,
                        score=cs.score,
                        justification=cs.justification,
                        evidence=cs.evidence,
                    )
                    for cs in agent_crit_scores
                ]

        evaluator = evaluator_by_agent.get(agent) or fallback_bundle_evaluator
        pillars[agent] = MasterSynthesisPillar(
            weight=weight,
            subtotal=subtotal,
            status=status_str,
            criteria=criteria_items,
            summary=summary,
            evaluator=evaluator,
        )

    flag_rows = (
        db.query(
            EvaluationFlag,
            AgentResult.agent_name,
            CriterionScore.criterion_title,
        )
        .outerjoin(
            AgentResult,
            EvaluationFlag.agent_result_id == AgentResult.agent_result_id,
        )
        .outerjoin(
            CriterionScore,
            EvaluationFlag.criterion_score_id == CriterionScore.criterion_score_id,
        )
        .filter(EvaluationFlag.document_id.in_(same_module_doc_ids))
        .all()
        if db is not None
        else []
    )
    flags = [
        EvaluationFlagItem(
            flag_id=flag.evaluation_flag_id,
            evaluation_id=flag.evaluation_id,
            agent_id=agent_name or "",
            criterion_id=flag.criterion_id,
            criterion_text=criterion_title or flag.criterion_id,
            score=flag.score,
            justification=flag.reason,
            chunk_id=flag.chunk_id,
        )
        for flag, agent_name, criterion_title in flag_rows
    ]

    synth_raw = matrix.synthesized_score
    synthesized_score = float(synth_raw) if synth_raw is not None else None
    adjectival_rating = None
    if synthesized_score is not None:
        if len(domain_scores_json) >= 4:
            _, _, rating = _composite_from_domains(domain_scores_json)
            adjectival_rating = rating
        else:
            adjectival_rating = score_to_adjectival(synthesized_score)

    completed_pillars_count = sum(
        1
        for p in pillars.values()
        if p.subtotal is not None and p.status in ("COMPLETED", "OK")
    )
    can_certify = completed_pillars_count >= 4

    return MasterSynthesisDetailResponse(
        document_id=matrix.document_id,
        document_title=document.title if document else None,
        course_code=document.course_code if document else None,
        program=matrix.program or (document.program if document else None),
        author=author,
        synthesized_score=synthesized_score,
        adjectival_rating=adjectival_rating,
        evaluation_status=matrix.evaluation_status,
        last_updated=matrix.last_updated,
        pillars=pillars,
        flags=flags,
        can_certify=can_certify,
    )


__all__ = ["get_master_synthesis_detail"]
