"""Evaluation results assembly and domain presentation for synthesis."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from server.modules.agents.envelope_map import envelope_criteria_map_from_snapshot
from server.modules.agents.sme.scoring import score_criterion_measurement
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.feedback.items import (
    RawMeasurementItem,
    apply_item_rejections,
    extract_raw_items,
    get_effective_item_rejections_batch,
)
from server.modules.feedback.state import (
    EffectiveCriterionCorrection,
    get_effective_criterion_corrections,
)
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    RatioBandConfig,
)
from server.modules.rubrics.models import EvaluationFormSnapshot
from server.modules.rubrics.presentation import (
    EvaluationFormPresentation,
    build_evaluation_form_presentation,
)
from server.modules.rubrics.snapshot_contracts import (
    EvaluationFormSnapshotDTO,
    SnapshotIntegrityError,
)
from server.modules.rubrics.snapshots import load_verified_evaluation_snapshots
from server.modules.synthesis.exceptions import (
    EvaluationResultIntegrityError,
    EvaluationResultsNotFoundError,
)
from server.modules.synthesis.matrix import compute_synthesized_score
from server.modules.synthesis.models import (
    AgentResult,
    CriterionScore,
    EvaluationFlag,
)
from server.modules.synthesis.persistence import _scheduled_ids_for_job
from server.modules.synthesis.schemas import (
    CriterionScoreItem,
    DomainScoreBlock,
    EvaluationFlagItem,
    EvaluationResultsResponse,
    RawMeasurementItemOut,
)

logger = logging.getLogger(__name__)

# Item-level correction display (raw item checklist + live-recomputed score)
# only applies to agents whose score is code-computed from LLM-extracted
# items -- see server/modules/feedback/items.py.
_ITEM_LEVEL_AGENTS = ("sme", "coordinator")


def _reviewer_correction_payload(
    correction: EffectiveCriterionCorrection | None,
) -> dict[str, Any] | None:
    if correction is None:
        return None
    return {
        "action": correction.action,
        "score": correction.score,
        "justification": correction.justification,
    }


def _item_correction_payload(
    result: AgentResult,
    agent_id: str,
    snap_crit: CriterionDefinition,
    envelope_key_by_code: dict[str, str],
    rejections_batch: dict[tuple[str, str], frozenset[str]],
) -> tuple[list[RawMeasurementItemOut] | None, int | None]:
    """Return (raw_items, corrected_score) for one criterion, or (None, None).

    Best-effort/defensive: this is display enrichment, not a persisted
    invariant, so any lookup failure (missing envelope, malformed stored
    response, etc.) degrades to "no item-level info" rather than failing
    the whole results response.
    """
    if agent_id not in _ITEM_LEVEL_AGENTS:
        return None, None
    if not isinstance(snap_crit.strategy_config, (CountBandConfig, RatioBandConfig)):
        return None, None
    if not result.group_responses:
        return None, None

    envelope_key = envelope_key_by_code.get(snap_crit.criterion_code)
    if envelope_key is None:
        return None, None

    try:
        envelope_response = result.group_responses.get(envelope_key) or {}
        measurement = next(
            (
                m
                for m in envelope_response.get("criterion_measurements", [])
                if m.get("criterion_id") == snap_crit.criterion_code
            ),
            None,
        )
        if measurement is None:
            return None, None

        raw_items: tuple[RawMeasurementItem, ...] = extract_raw_items(measurement)
        rejected_ids = rejections_batch.get(
            (agent_id, snap_crit.criterion_code), frozenset()
        )

        items_out = [
            RawMeasurementItemOut(
                item_id=item.item_id,
                text=item.text,
                included=item.included,
                rejected=item.item_id in rejected_ids,
            )
            for item in raw_items
        ]

        corrected_score: int | None = None
        if rejected_ids:
            corrected_measurement = apply_item_rejections(measurement, rejected_ids)
            corrected_score = score_criterion_measurement(
                snap_crit, corrected_measurement
            ).score

        return items_out, corrected_score
    except Exception:
        logger.warning(
            "Failed to compute item-level correction display for criterion '%s' "
            "(agent '%s'); omitting raw_items/corrected_score",
            snap_crit.criterion_code,
            agent_id,
            exc_info=True,
        )
        return None, None


def get_evaluation_results(
    evaluation_id: uuid.UUID,
    current_user_id: uuid.UUID,
    db: Any,
    evaluator_permissions: tuple[str, ...] | list[str] | None = None,
    current_user_role: str = "faculty",
) -> EvaluationResultsResponse:
    """Assemble the full evaluation results response for an owner.

    Ownership is enforced here: a missing job or a job not submitted by
    ``current_user_id`` raises ``EvaluationResultsNotFoundError`` so the
    router can mask non-ownership as a 404.
    """
    job = db.get(EvaluationJob, evaluation_id)
    if job is None or job.submitted_by != current_user_id:
        raise EvaluationResultsNotFoundError("Evaluation not found")
    if current_user_role == "faculty" and evaluator_permissions:
        target = getattr(job, "target_agent", None) or "all"
        valid_targets = ("sme", "coordinator", "gad", "itso")
        if target == "all":
            if not set(valid_targets).issubset(set(evaluator_permissions)):
                raise EvaluationResultsNotFoundError("Evaluation not found")
        elif target not in evaluator_permissions:
            raise EvaluationResultsNotFoundError("Evaluation not found")
    document = db.get(Document, job.document_id)
    agent_results = db.query(AgentResult).filter_by(evaluation_id=evaluation_id).all()
    agent_name_map = {r.agent_result_id: r.agent_name for r in agent_results}
    criterion_scores = (
        db.query(CriterionScore).filter_by(evaluation_id=evaluation_id).all()
    )
    flags = db.query(EvaluationFlag).filter_by(evaluation_id=evaluation_id).all()

    # Latest reviewer correction per (agent, criterion) for reviewable agents.
    # Human review is authoritative across all four domain agents.
    reviewable_agents = ("sme", "coordinator", "gad", "itso")
    corrections = get_effective_criterion_corrections(
        db,
        evaluation_id,
        agent_names=reviewable_agents,
    )

    _job_target = getattr(job, "target_agent", "all") or "all"
    _is_single = _job_target in ("sme", "coordinator", "gad", "itso")
    synthesis_result = compute_synthesized_score(
        agent_results,
        force_partial=False if _is_single else bool(job.partial_without_curriculum),
        partial_reason=None if _is_single else job.partial_reason,
    )

    criteria_by_result: dict[uuid.UUID, list[CriterionScore]] = {}
    for score in criterion_scores:
        criteria_by_result.setdefault(score.agent_result_id, []).append(score)

    # Build a lookup from criterion_score_id -> CriterionScore for flag resolution
    criterion_by_id: dict[uuid.UUID, CriterionScore] = {
        score.criterion_score_id: score for score in criterion_scores
    }

    scheduled_ids = _scheduled_ids_for_job(job)

    snapshot_rows_count = (
        db.query(EvaluationFormSnapshot).filter_by(evaluation_id=evaluation_id).count()
    )

    if not job.is_pre_snapshot_legacy and len(agent_results) == 0:
        if job.status not in (
            EvaluationStatus.SUBMITTED.value,
            EvaluationStatus.PREPROCESSING.value,
        ):
            raise EvaluationResultIntegrityError(
                "Missing evaluation results in execution or terminal state"
            )

        duration_seconds = None
        if job.completed_at and job.submitted_at:
            duration_seconds = (job.completed_at - job.submitted_at).total_seconds()

        return EvaluationResultsResponse(
            evaluation_id=job.evaluation_id,
            document_id=job.document_id,
            syllabus_id=job.syllabus_id,
            document_title=document.title if document else None,
            program=document.program if document else None,
            synthesized_score=float(synthesis_result["synthesized_score"]),
            overall_score=synthesis_result.get("overall_score"),
            adjectival_rating=synthesis_result.get("adjectival_rating"),
            domain_scores={},
            flags=[],
            active_agents=list(synthesis_result["active_agents"]),
            failed_agents=list(synthesis_result["failed_agents"]),
            is_partial=bool(synthesis_result["is_partial"]),
            partial_reason=(
                synthesis_result.get("partial_reason")
                if bool(synthesis_result["is_partial"])
                else None
            ),
            evaluation_status=job.status,
            submitted_at=job.submitted_at,
            completed_at=job.completed_at,
            duration_seconds=duration_seconds,
            forms={},
            legacy_notice=None,
        )

    forms_dict: dict[str, EvaluationFormPresentation] = {}
    legacy_notice: str | None = None
    domain_scores: dict[str, DomainScoreBlock] = {}

    if job.is_pre_snapshot_legacy:
        # Coherence invariants for pre-snapshot legacy:
        # 1. Must have >= 1 AgentResult row
        # 2. All AgentResult rows must have form_snapshot_id == NULL
        # 3. Exactly zero EvaluationFormSnapshot rows in DB
        if (
            len(agent_results) == 0
            or any(r.form_snapshot_id is not None for r in agent_results)
            or snapshot_rows_count != 0
        ):
            raise EvaluationResultIntegrityError(
                "Incoherent pre-snapshot legacy evaluation state"
            )

        legacy_notice = "Legacy — form snapshot unavailable"
        for result in agent_results:
            raw_scores = criteria_by_result.get(result.agent_result_id, [])
            criteria_items = [
                CriterionScoreItem(
                    criterion_id=score.criterion_id,
                    criterion_text=score.criterion_title,
                    score=score.score,
                    justification=score.justification,
                    evidence=score.evidence,
                    is_ungrounded=False,
                    reviewer_correction=(
                        _reviewer_correction_payload(
                            corrections.get((result.agent_name, score.criterion_id))
                        )
                        if result.agent_name in reviewable_agents
                        else None
                    ),
                )
                for score in raw_scores
            ]
            domain_scores[result.agent_name] = DomainScoreBlock(
                criteria=criteria_items,
                subtotal=float(result.subtotal),
                max_score=4,
                status="OK" if result.success else "ERROR",
                adjectival_rating=synthesis_result["domain_scores"]
                .get(result.agent_name, {})
                .get("adjectival_rating"),
                summary=result.summary,
            )
    else:
        # Non-legacy evaluation requires valid immutable snapshot bindings
        if any(r.form_snapshot_id is None for r in agent_results):
            raise EvaluationResultIntegrityError(
                "Non-legacy evaluation contains unlinked AgentResult "
                "without form_snapshot_id"
            )

        try:
            verified_snapshots = load_verified_evaluation_snapshots(
                db, evaluation_id, scheduled_ids
            )
        except SnapshotIntegrityError as exc:
            raise EvaluationResultIntegrityError(
                "Failed to load verified evaluation snapshots"
            ) from exc

        snapshot_by_agent: dict[str, EvaluationFormSnapshotDTO] = {
            s.agent_id: s for s in verified_snapshots
        }

        result_by_agent: dict[str, AgentResult] = {
            r.agent_name: r for r in agent_results
        }
        if len(agent_results) != len(scheduled_ids) or set(
            result_by_agent.keys()
        ) != set(scheduled_ids):
            raise EvaluationResultIntegrityError(
                "Persisted agent results set mismatch against scheduled agents"
            )

        for r in agent_results:
            expected_snapshot = snapshot_by_agent.get(r.agent_name)
            if (
                expected_snapshot is None
                or r.form_snapshot_id != expected_snapshot.snapshot_id
            ):
                raise EvaluationResultIntegrityError(
                    "Persisted agent result form_snapshot_id mismatch "
                    "against verified snapshot"
                )

        ungrounded_cids = {f.criterion_id for f in flags if f.chunk_id is None}
        item_rejections_batch = get_effective_item_rejections_batch(
            db, evaluation_id, _ITEM_LEVEL_AGENTS
        )

        for agent_id in scheduled_ids:
            result = result_by_agent[agent_id]
            snapshot = snapshot_by_agent[agent_id]
            first_domain = snapshot.form.domains[0] if snapshot.form.domains else None
            domain_id = first_domain.rubric_domain_id if first_domain else None
            domain_name = first_domain.title if first_domain else None
            domain_display_order = first_domain.display_order if first_domain else None

            envelope_key_by_code: dict[str, str] = {}
            if agent_id in _ITEM_LEVEL_AGENTS:
                try:
                    envelope_map = envelope_criteria_map_from_snapshot(
                        snapshot, agent_id
                    )
                    envelope_key_by_code = {
                        c.criterion_code: key
                        for key, criteria in envelope_map.items()
                        for c in criteria
                    }
                except Exception:
                    logger.warning(
                        "Failed to reconstruct envelope map for agent '%s'; "
                        "item-level correction display will be omitted",
                        agent_id,
                        exc_info=True,
                    )

            db_scores = criteria_by_result.get(result.agent_result_id, [])
            db_scores_by_cid = {s.criterion_id: s for s in db_scores}

            canonical_snapshot_criteria = [
                criterion
                for domain in snapshot.form.domains
                for criterion in domain.criteria
            ]
            expected_cids = [c.criterion_code for c in canonical_snapshot_criteria]

            reconstructed_criteria: list[CriterionScoreItem] = []
            if result.success:
                if len(db_scores) != len(expected_cids) or set(
                    db_scores_by_cid.keys()
                ) != set(expected_cids):
                    raise EvaluationResultIntegrityError(
                        "Persisted criterion score codes mismatch against snapshot "
                        f"for agent '{agent_id}'"
                    )

                for snap_crit in canonical_snapshot_criteria:
                    score_row = db_scores_by_cid[snap_crit.criterion_code]
                    if score_row.criterion_title != snap_crit.title:
                        raise EvaluationResultIntegrityError(
                            f"Criterion title mismatch: '{score_row.criterion_title}' "
                            f"!= '{snap_crit.title}'"
                        )
                    is_ungrounded = score_row.criterion_id in ungrounded_cids
                    raw_items, corrected_score = _item_correction_payload(
                        result,
                        agent_id,
                        snap_crit,
                        envelope_key_by_code,
                        item_rejections_batch,
                    )
                    reconstructed_criteria.append(
                        CriterionScoreItem(
                            rubric_criterion_id=snap_crit.rubric_criterion_id,
                            criterion_id=score_row.criterion_id,
                            criterion_text=score_row.criterion_title,
                            description=snap_crit.description,
                            display_order=snap_crit.display_order,
                            score=score_row.score,
                            justification=score_row.justification,
                            evidence=score_row.evidence,
                            is_ungrounded=is_ungrounded,
                            reviewer_correction=(
                                _reviewer_correction_payload(
                                    corrections.get(
                                        (result.agent_name, score_row.criterion_id)
                                    )
                                )
                                if result.agent_name in reviewable_agents
                                else None
                            ),
                            raw_items=raw_items,
                            corrected_score=corrected_score,
                        )
                    )
            else:
                if len(db_scores) != 0:
                    raise EvaluationResultIntegrityError(
                        f"Failed agent result '{agent_id}' must not have "
                        "persisted criterion scores"
                    )

            form_presentation = build_evaluation_form_presentation(snapshot)
            forms_dict[agent_id] = form_presentation

            domain_scores[agent_id] = DomainScoreBlock(
                form_snapshot_id=snapshot.snapshot_id,
                rubric_set_id=snapshot.rubric_set_id,
                version=snapshot.form.version_number,
                snapshot_hash=snapshot.snapshot_hash,
                adapter_key=snapshot.adapter_key,
                adapter_version=snapshot.adapter_version,
                domain_id=domain_id,
                domain_name=domain_name,
                domain_display_order=domain_display_order,
                criteria=reconstructed_criteria,
                subtotal=float(result.subtotal),
                max_score=4,
                status="OK" if result.success else "ERROR",
                adjectival_rating=synthesis_result["domain_scores"]
                .get(result.agent_name, {})
                .get("adjectival_rating"),
                summary=result.summary,
            )

    duration_seconds = None
    if job.completed_at and job.submitted_at:
        duration_seconds = (job.completed_at - job.submitted_at).total_seconds()

    return EvaluationResultsResponse(
        evaluation_id=job.evaluation_id,
        document_id=job.document_id,
        syllabus_id=job.syllabus_id,
        document_title=document.title if document else None,
        program=document.program if document else None,
        synthesized_score=float(synthesis_result["synthesized_score"]),
        overall_score=synthesis_result.get("overall_score"),
        adjectival_rating=synthesis_result.get("adjectival_rating"),
        domain_scores=domain_scores,
        flags=[
            EvaluationFlagItem(
                flag_id=flag.evaluation_flag_id,
                evaluation_id=flag.evaluation_id,
                agent_id=agent_name_map.get(
                    flag.agent_result_id, str(flag.agent_result_id)
                ),
                criterion_id=flag.criterion_id,
                criterion_text=criterion_by_id[flag.criterion_score_id].criterion_title
                if flag.criterion_score_id in criterion_by_id
                else flag.criterion_id,
                score=flag.score,
                justification=flag.reason,
                chunk_id=flag.chunk_id,
            )
            for flag in flags
        ],
        active_agents=list(synthesis_result["active_agents"]),
        failed_agents=list(synthesis_result["failed_agents"]),
        is_partial=bool(synthesis_result["is_partial"]),
        partial_reason=(
            synthesis_result.get("partial_reason")
            if bool(synthesis_result["is_partial"])
            else None
        ),
        evaluation_status=job.status,
        submitted_at=job.submitted_at,
        completed_at=job.completed_at,
        duration_seconds=duration_seconds,
        forms=forms_dict,
        legacy_notice=legacy_notice,
    )


__all__ = [
    "get_evaluation_results",
    "_reviewer_correction_payload",
]
