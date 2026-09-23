"""Synthesis matrix — weighted score aggregation and monitoring matrix logic."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from server.modules.documents.metadata import canonicalize_supported_program
from server.modules.documents.models import Document
from server.modules.synthesis.exceptions import UnsupportedProgramFilterError
from server.modules.synthesis.models import (
    AgentResult,
    MonitoringMatrix,
)
from server.modules.synthesis.schemas import (
    MatrixListResponse,
    MatrixMetrics,
    MatrixRowItem,
    score_to_adjectival,
)
from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

AGENT_WEIGHTS: dict[str, float] = {
    "sme": 0.35,
    "coordinator": 0.30,
    "gad": 0.20,
    "itso": 0.15,
}

PROGRESSIVE_AGENT_IDS: tuple[str, ...] = ("sme", "coordinator", "gad", "itso")


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


def _composite_from_domains(
    domain_scores: dict[str, dict[str, Any]],
) -> tuple[float, float, str | None]:
    """Compute final composite (pct), overall (1-4), and adjectival rating."""
    weighted_pct = sum(
        AGENT_WEIGHTS[agent] * _domain_pct(domain.get("subtotal"))
        for agent, domain in domain_scores.items()
        if agent in AGENT_WEIGHTS
    )
    weighted_overall = sum(
        AGENT_WEIGHTS[agent] * float(domain.get("subtotal") or 0)
        for agent, domain in domain_scores.items()
        if agent in AGENT_WEIGHTS
    )
    synthesized = round(weighted_pct, 2)
    overall = round(weighted_overall, 2)
    return synthesized, overall, score_to_adjectival(overall)


def _completed_domain_count(domain_scores: dict[str, Any] | None) -> int:
    if not isinstance(domain_scores, dict):
        return 0
    return sum(1 for agent in PROGRESSIVE_AGENT_IDS if agent in domain_scores)


def upsert_monitoring_matrix(
    db: Session,
    document_id: uuid.UUID,
    evaluation_id: uuid.UUID | None,
    evaluation_status: str,
    synthesized_score: float | None = None,
    domain_scores: dict[str, dict[str, Any]] | None = None,
    flag_count: int = 0,
    feedback_status: str = "NO_FEEDBACK",
    target_agent: str | None = None,
) -> MonitoringMatrix:
    doc = db.get(Document, document_id)
    program = doc.program if doc and doc.program else None
    if not program and evaluation_id:
        from server.modules.evaluations.models import EvaluationJob

        job = db.get(EvaluationJob, evaluation_id)
        if job and job.confirmed_program:
            program = job.confirmed_program

    # Resolve the effective target agent for progressive merging.
    effective_target = target_agent
    if effective_target is None and evaluation_id is not None:
        try:
            from server.modules.evaluations.models import EvaluationJob

            _job = db.get(EvaluationJob, evaluation_id)
            candidate = getattr(_job, "target_agent", None) if _job else None
            if candidate in PROGRESSIVE_AGENT_IDS:
                effective_target = candidate
        except Exception:
            effective_target = None
    if effective_target is None and isinstance(domain_scores, dict):
        single_keys = [k for k in domain_scores if k in PROGRESSIVE_AGENT_IDS]
        if len(single_keys) == 1:
            effective_target = single_keys[0]

    if evaluation_status == "FAILED":
        return _upsert_failure(
            db,
            document_id=document_id,
            evaluation_id=evaluation_id,
            program=program,
            domain_scores=domain_scores,
            flag_count=flag_count,
            feedback_status=feedback_status,
            effective_target=effective_target,
        )

    if effective_target in PROGRESSIVE_AGENT_IDS and isinstance(domain_scores, dict):
        return _upsert_progressive_domain(
            db,
            document_id=document_id,
            evaluation_id=evaluation_id,
            program=program,
            domain_scores=domain_scores,
            flag_count=flag_count,
            feedback_status=feedback_status,
            effective_target=effective_target,
        )

    # Legacy full-bundle path (historical "all" jobs or explicit multi-domain
    # payloads): preserve the previous overwrite semantics.
    row = MonitoringMatrix(
        document_id=document_id,
        evaluation_id=evaluation_id,
        faculty_name=None,
        program=program,
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
        if program is not None and (existing.program is None or existing.program == ""):
            existing.program = program
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


def _upsert_progressive_domain(
    db: Session,
    *,
    document_id: uuid.UUID,
    evaluation_id: uuid.UUID | None,
    program: str | None,
    domain_scores: dict[str, dict[str, Any]],
    flag_count: int,
    feedback_status: str,
    effective_target: str,
) -> MonitoringMatrix:
    """Deep-merge one agent's domain score into the per-document matrix row."""
    incoming = domain_scores.get(effective_target)
    if incoming is None:
        # Fall back to merging whatever progressive keys are present.
        incoming_map = {
            k: v for k, v in domain_scores.items() if k in PROGRESSIVE_AGENT_IDS
        }
    else:
        incoming_map = {effective_target: incoming}

    try:
        existing = (
            db.query(MonitoringMatrix).filter_by(document_id=document_id).one_or_none()
        )
    except Exception:
        existing = None

    if existing is None:
        doc = db.get(Document, document_id)
        if doc is not None and getattr(doc, "source_type", None) == "slm":
            existing = (
                db.query(MonitoringMatrix)
                .join(Document, MonitoringMatrix.document_id == Document.document_id)
                .filter(
                    Document.source_type == "slm",
                    func.lower(Document.title) == doc.title.strip().lower(),
                    func.lower(Document.program) == (doc.program or "").strip().lower(),
                )
                .order_by(MonitoringMatrix.last_updated.desc())
                .first()
            )

    if existing is None:
        merged: dict[str, Any] = {}
        for agent, payload in incoming_map.items():
            merged[agent] = copy.deepcopy(payload)
        completed = _completed_domain_count(merged)
        if completed >= 4:
            synthesized, _overall, _rating = _composite_from_domains(merged)
            status = "COMPLETED"
        elif completed >= 1:
            synthesized = None
            status = "IN_PROGRESS"
        else:
            synthesized = None
            status = "SUBMITTED"
        row = MonitoringMatrix(
            document_id=document_id,
            evaluation_id=evaluation_id,
            faculty_name=None,
            program=program,
            evaluation_status=status,
            synthesized_score=synthesized,
            domain_scores_json=merged if merged else None,
            flag_count=flag_count or 0,
            feedback_status=feedback_status,
        )
        try:
            db.add(row)
            db.flush()
            return row
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(MonitoringMatrix).filter_by(document_id=document_id).one()
            )
        else:
            return row

    current = (
        copy.deepcopy(existing.domain_scores_json)
        if isinstance(existing.domain_scores_json, dict)
        else {}
    )
    for agent, payload in incoming_map.items():
        current[agent] = copy.deepcopy(payload)

    completed = _completed_domain_count(current)
    existing.evaluation_id = evaluation_id
    if program is not None and (existing.program is None or existing.program == ""):
        existing.program = program
    # Flag accumulation: add this domain's flags when it is newly completed;
    # re-evaluations of the same domain keep the prior total to avoid
    # double-counting without per-domain flag bookkeeping.
    try:
        prior_total = int(existing.flag_count or 0)
    except (TypeError, ValueError):
        prior_total = 0
    try:
        incoming_flags = int(flag_count or 0)
    except (TypeError, ValueError):
        incoming_flags = 0
    pre_merge_count = _completed_domain_count(
        existing.domain_scores_json
        if isinstance(existing.domain_scores_json, dict)
        else {}
    )
    is_new_domain = effective_target not in (
        existing.domain_scores_json
        if isinstance(existing.domain_scores_json, dict)
        else {}
    )
    if is_new_domain or pre_merge_count == 0:
        existing.flag_count = prior_total + incoming_flags
    # else: re-evaluation of an existing domain — retain prior total.
    existing.domain_scores_json = current
    if completed >= 4:
        synthesized, _overall, _rating = _composite_from_domains(current)
        existing.synthesized_score = synthesized
        existing.evaluation_status = "COMPLETED"
    elif completed >= 1:
        existing.synthesized_score = None
        existing.evaluation_status = "IN_PROGRESS"
    else:
        existing.synthesized_score = None
        existing.evaluation_status = "SUBMITTED"
    if feedback_status is not None:
        existing.feedback_status = feedback_status
    db.flush()
    return existing


def _upsert_failure(
    db: Session,
    *,
    document_id: uuid.UUID,
    evaluation_id: uuid.UUID | None,
    program: str | None,
    domain_scores: dict[str, dict[str, Any]] | None,
    flag_count: int,
    feedback_status: str,
    effective_target: str | None,
) -> MonitoringMatrix:
    """Record a failure without discarding previously completed domains."""
    try:
        existing = (
            db.query(MonitoringMatrix).filter_by(document_id=document_id).one_or_none()
        )
    except Exception:
        existing = None

    if existing is None:
        doc = db.get(Document, document_id)
        if doc is not None and getattr(doc, "source_type", None) == "slm":
            existing = (
                db.query(MonitoringMatrix)
                .join(Document, MonitoringMatrix.document_id == Document.document_id)
                .filter(
                    Document.source_type == "slm",
                    func.lower(Document.title) == doc.title.strip().lower(),
                    func.lower(Document.program) == (doc.program or "").strip().lower(),
                )
                .order_by(MonitoringMatrix.last_updated.desc())
                .first()
            )

    if existing is None:
        row = MonitoringMatrix(
            document_id=document_id,
            evaluation_id=evaluation_id,
            faculty_name=None,
            program=program,
            evaluation_status="FAILED",
            synthesized_score=None,
            domain_scores_json=domain_scores,
            flag_count=flag_count or 0,
            feedback_status=feedback_status,
        )
        try:
            db.add(row)
            db.flush()
            return row
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(MonitoringMatrix).filter_by(document_id=document_id).one()
            )
        else:
            return row
    completed = _completed_domain_count(
        existing.domain_scores_json
        if isinstance(existing.domain_scores_json, dict)
        else {}
    )
    existing.evaluation_id = evaluation_id
    if completed >= 1:
        # Retain prior completed domains; record the failure implicitly by
        # keeping the progressive status.
        if completed >= 4:
            existing.evaluation_status = "COMPLETED"
        else:
            existing.evaluation_status = "IN_PROGRESS"
    else:
        existing.evaluation_status = "FAILED"
        if domain_scores is not None:
            existing.domain_scores_json = domain_scores
    db.flush()
    return existing


def _classify_matrix_score_values(
    domain_scores: dict[str, Any] | None,
    synthesized_score: float | int | None,
) -> tuple[float | None, str | None, bool]:
    """Derive reliable 1-4 overall score, adjectival rating, and passing flag.

    Returns:
        (overall_score, adjectival_rating, is_passing)

    Resolution order:
    1. If `domain_scores` contains all four required domain subtotals with successful
       status ('OK' or 'COMPLETED') and valid score in [0.0, 4.0], compute the weighted
       overall (1-4) score and rating from AGENT_WEIGHTS.
       Do NOT normalize over partial domain subsets for a completed evaluation row.
    2. Fallback if no full trustworthy breakdown:
       - If synthesized_score > 4.0 and <= 100.0 (progressive percentage), convert
         to 1-4 scale via (synthesized_score / 100.0) * 4.0. Passing (>= 2.50)
         requires raw unrounded value >= 2.50 (i.e. >= 62.5%). Raw 2.496 (62.4%)
         is NOT passing (evaluates to false before any display rounding).
       - If synthesized_score <= 4.0 without explicit trustworthy four-domain breakdown,
         the scale is ambiguous (modern 1-4% overlaps legacy 1-4 scale). Therefore:
         adjectival_rating is None, overall_score is None, and it is NOT passing.
         (Denominator still includes the completed row).
       - If synthesized_score is None or out of range (< 0.0 or > 100.0),
         it is not passing and adjectival_rating is None.
    """
    if isinstance(domain_scores, dict) and all(
        agent in domain_scores and isinstance(domain_scores[agent], dict)
        for agent in PROGRESSIVE_AGENT_IDS
    ):
        valid = True
        extracted_subtotals: dict[str, float] = {}
        for agent in PROGRESSIVE_AGENT_IDS:
            d = domain_scores[agent]
            status = d.get("status")
            subtotal = d.get("subtotal")
            if status not in ("OK", "COMPLETED") or subtotal is None:
                valid = False
                break
            try:
                s_val = float(subtotal)
            except (TypeError, ValueError):
                valid = False
                break
            if not (0.0 <= s_val <= 4.0):
                valid = False
                break
            extracted_subtotals[agent] = s_val

        if valid:
            weighted_overall = sum(
                AGENT_WEIGHTS[a] * extracted_subtotals[a] for a in PROGRESSIVE_AGENT_IDS
            )
            overall = round(weighted_overall, 2)
            rating = score_to_adjectival(weighted_overall)
            is_passing = weighted_overall >= 2.50
            return overall, rating, is_passing

    # Fallback when no full trustworthy 4-domain breakdown is present
    if synthesized_score is not None:
        try:
            val = float(synthesized_score)
        except (TypeError, ValueError):
            return None, None, False

        # Modern progressive percentage (> 4.0 up to 100.0):
        # Overall (1-4 scale) = (val / 100.0) * 4.0.
        # Passing threshold and rating use raw_overall (unrounded)
        # to ensure rating and is_passing are strictly consistent
        # (e.g. 62.4% -> raw 2.496 is Needs Improvement and NOT passing).
        if 4.0 < val <= 100.0:
            raw_overall = (val / 100.0) * 4.0
            converted_overall = round(raw_overall, 2)
            rating = score_to_adjectival(raw_overall)
            is_passing = raw_overall >= 2.50
            return converted_overall, rating, is_passing

        # Score <= 4.0 without full domain provenance:
        # Ambiguous between modern percentage (0-4%) and legacy 1-4 scale.
        # ADR guidance: adjective null, not passing, denominator includes row.
        return None, None, False

    return None, None, False


def _escape_sql_like(term: str) -> str:
    """Escape SQL LIKE special wildcard characters (%, _, \\)."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_monitoring_matrix(
    program: str | None,
    status: str | None,
    page: int,
    page_size: int,
    db: Any,
    search: str | None = None,
) -> MatrixListResponse:
    """Assemble the monitoring matrix list response with filtering and pagination.

    Raises ``UnsupportedProgramFilterError`` when the ``program`` filter is
    not a supported program (so the router can map it to a 422).
    """
    query = db.query(MonitoringMatrix)

    search_term = search.strip() if search else None
    if search_term:
        query = query.outerjoin(
            Document, MonitoringMatrix.document_id == Document.document_id
        )
        escaped_search = _escape_sql_like(search_term.lower())
        search_pattern = f"%{escaped_search}%"
        query = query.filter(
            or_(
                func.lower(Document.title).like(search_pattern, escape="\\"),
                func.lower(MonitoringMatrix.faculty_name).like(
                    search_pattern, escape="\\"
                ),
                func.lower(MonitoringMatrix.program).like(search_pattern, escape="\\"),
            )
        )

    if program:
        canonical_program = canonicalize_supported_program(program)
        if canonical_program is None:
            raise UnsupportedProgramFilterError(
                "Unsupported program filter. Only BSCS and BSInfoTech are "
                "supported; BSIT is accepted as an alias."
            )
        values = [canonical_program]
        if canonical_program == "BSInfoTech":
            values.append("BSIT")
        query = query.filter(
            func.lower(MonitoringMatrix.program).in_(
                [value.lower() for value in values]
            )
        )
    if status:
        query = query.filter(MonitoringMatrix.evaluation_status == status)

    total = query.count()

    # SQL aggregates over the identical filtered row set (before pagination)
    agg_row = query.with_entities(
        func.count(case((MonitoringMatrix.evaluation_status == "COMPLETED", 1))).label(
            "completed_count"
        ),
        func.count(case((func.coalesce(MonitoringMatrix.flag_count, 0) > 0, 1))).label(
            "flagged_count"
        ),
        func.coalesce(
            func.sum(
                case(
                    (
                        func.coalesce(MonitoringMatrix.flag_count, 0) > 0,
                        MonitoringMatrix.flag_count,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("total_flags"),
    ).one()

    completed_count = int(agg_row.completed_count or 0)
    flagged_count = int(agg_row.flagged_count or 0)
    total_flags = int(agg_row.total_flags or 0)

    # Stream only completed rows' minimal score columns to classify passing
    passing_count = 0
    if completed_count > 0:
        completed_score_stream = (
            query.filter(MonitoringMatrix.evaluation_status == "COMPLETED")
            .with_entities(
                MonitoringMatrix.domain_scores_json,
                MonitoringMatrix.synthesized_score,
            )
            .yield_per(500)
        )
        for domain_scores_json, synthesized_score in completed_score_stream:
            _overall, _rating, is_passing = _classify_matrix_score_values(
                domain_scores_json,
                synthesized_score,
            )
            if is_passing:
                passing_count += 1

    quality_pass_rate: float | None = None
    if completed_count > 0:
        quality_pass_rate = round((100.0 * passing_count) / completed_count, 2)

    metrics = MatrixMetrics(
        completed_count=completed_count,
        passing_count=passing_count,
        flagged_count=flagged_count,
        total_flags=total_flags,
        quality_pass_rate=quality_pass_rate,
    )

    # Fetch page rows with a single one-to-one outer join to Document for title
    # (avoid re-joining Document if search already added outerjoin)
    paginated_query = query
    if not search_term:
        paginated_query = paginated_query.outerjoin(
            Document, MonitoringMatrix.document_id == Document.document_id
        )

    paginated_results = (
        paginated_query.with_entities(
            MonitoringMatrix, Document.title.label("document_title")
        )
        .order_by(
            MonitoringMatrix.last_updated.desc(),
            MonitoringMatrix.matrix_id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for row, doc_title in paginated_results:
        _overall, adjectival_rating, _is_passing = _classify_matrix_score_values(
            row.domain_scores_json,
            row.synthesized_score,
        )
        items.append(
            MatrixRowItem(
                matrix_id=row.matrix_id,
                document_id=row.document_id,
                evaluation_id=row.evaluation_id,
                faculty_name=row.faculty_name,
                program=row.program,
                document_title=doc_title,
                evaluation_status=row.evaluation_status,
                synthesized_score=float(row.synthesized_score)
                if row.synthesized_score is not None
                else None,
                adjectival_rating=adjectival_rating,
                domain_scores=row.domain_scores_json,
                flag_count=row.flag_count,
                feedback_status=row.feedback_status,
                last_updated=row.last_updated,
            )
        )

    return MatrixListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        metrics=metrics,
    )
