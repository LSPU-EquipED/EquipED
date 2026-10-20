"""Evaluation results assembly and domain presentation for synthesis."""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any
from urllib.parse import urlsplit

from equiped_harness import envelope_criteria_map_from_snapshot
from equiped_harness.contracts import (
    CountBandConfig,
    CriterionDefinition,
    RatioBandConfig,
)
from equiped_harness.itso.document_review import unquoted_review_status
from equiped_harness.itso.execution import (
    cites_public_source,
    readable_reference_justification,
)
from equiped_harness.scoring import score_criterion_measurement
from equiped_harness.snapshot_contracts import (
    EvaluationFormSnapshotDTO,
    SnapshotIntegrityError,
)
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
from server.modules.rubrics.models import EvaluationFormSnapshot
from server.modules.rubrics.presentation import (
    EvaluationFormPresentation,
    build_evaluation_form_presentation,
)
from server.modules.rubrics.snapshots import load_verified_evaluation_snapshots
from server.modules.synthesis.exceptions import (
    EvaluationResultIntegrityError,
    EvaluationResultsNotFoundError,
)
from server.modules.synthesis.matrix import compute_synthesized_score
from server.modules.synthesis.models import (
    AgentGeneration,
    AgentResult,
    CriterionScore,
    EvaluationFlag,
)
from server.modules.synthesis.persistence import (
    _scheduled_ids_for_job,
    load_verified_persisted_agent_results,
)
from server.modules.synthesis.schemas import (
    CriterionScoreItem,
    DomainScoreBlock,
    EvaluationFlagItem,
    EvaluationResultsResponse,
    RawMeasurementItemOut,
)

logger = logging.getLogger(__name__)

_ITSO_SOURCE_MARKER = re.compile(r"\[\s*source\s+([1-9][0-9]*)\s*\]", re.I)
_ITSO_RECEIPT_MARKERS = (
    "Tool-derived public reference verification (",
    " Reviewed extracted-text coverage:",
)


def _captured_itso_context(
    generations: list[AgentGeneration],
) -> tuple[dict | None, dict | None]:
    """Combine saved source-check and document-review facts from user JSON."""
    report = None
    presentation_payload: dict[str, Any] = {}
    for generation in generations:
        if generation.agent_id != "itso" or not isinstance(
            generation.prompt_messages, list
        ):
            continue
        for message in generation.prompt_messages:
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content")
            if not isinstance(content, str):
                continue
            try:
                payload = json.loads(content)
            except (TypeError, ValueError):
                continue
            candidate_report = (
                payload.get("public_reference_verification")
                if isinstance(payload, dict)
                else None
            )
            if (
                report is None
                and isinstance(candidate_report, dict)
                and isinstance(candidate_report.get("references"), list)
            ):
                report = candidate_report
            if isinstance(payload, dict):
                if isinstance(payload.get("document_review_coverage"), dict):
                    presentation_payload["document_review_coverage"] = payload[
                        "document_review_coverage"
                    ]
                if payload.get("local_policy_status") in {"available", "unavailable"}:
                    presentation_payload["local_policy_status"] = payload[
                        "local_policy_status"
                    ]
    return report, presentation_payload if presentation_payload else None


def _usable_itso_source(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    if str(row.get("status", "")).strip().casefold() not in {
        "matched",
        "ambiguous",
        "mismatch",
        "mismatched",
    }:
        return False
    url = row.get("source_url")
    excerpt = row.get("excerpt")
    if (
        not isinstance(url, str)
        or not url
        or not isinstance(excerpt, str)
        or not excerpt.strip()
    ):
        return False
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme.casefold() == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def _public_itso_sources(
    report: dict | None, model_justification: str
) -> list[dict[str, Any]]:
    """Project only cited, usable passages, preserving report position numbers."""
    if report is None:
        return []
    refs = report.get("references")
    if not isinstance(refs, list):
        return []
    cited = {int(value) for value in _ITSO_SOURCE_MARKER.findall(model_justification)}
    cited.update(
        index
        for index, row in enumerate(refs, 1)
        if isinstance(row, dict)
        and isinstance(row.get("source_url"), str)
        and cites_public_source(model_justification, row["source_url"])
    )
    projected: list[dict[str, Any]] = []
    for number in sorted(cited):
        if number < 1 or number > len(refs) or len(projected) >= 5:
            continue
        row = refs[number - 1]
        if not _usable_itso_source(row):
            continue
        title = row.get("title")
        projected.append(
            {
                "number": number,
                "title": title[:300] if isinstance(title, str) else None,
                "url": row["source_url"],
                "excerpt": row["excerpt"].strip()[:700],
            }
        )
    return projected


def _pre_receipt_justification(justification: str) -> str:
    positions = [
        position
        for marker in _ITSO_RECEIPT_MARKERS
        if (position := justification.find(marker)) >= 0
    ]
    return justification[: min(positions)].rstrip() if positions else justification


def _captured_criterion_justification(
    generations: list[AgentGeneration], criterion_id: str, saved_justification: str
) -> str:
    """Return this criterion's original model rationale, never its receipt."""
    found_response_shape = False
    for generation in generations:
        response = generation.response_json
        if not isinstance(response, dict):
            continue
        rows = response.get("criterion_scores")
        if isinstance(rows, dict):
            found_response_shape = True
            row = rows.get(criterion_id)
            if row is None:
                continue
        elif isinstance(rows, list):
            found_response_shape = True
            row = next(
                (
                    item
                    for item in rows
                    if isinstance(item, dict)
                    and item.get("criterion_id") == criterion_id
                ),
                None,
            )
            if row is None:
                continue
        else:
            continue
        return (
            row["justification"]
            if isinstance(row, dict) and isinstance(row.get("justification"), str)
            else ""
        )
    # Captures predating the criterion response shape can still be read safely:
    # only rationale preceding the known appended receipt markers is eligible.
    return (
        "" if found_response_shape else _pre_receipt_justification(saved_justification)
    )


def _has_saved_items(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        if not value.strip():
            return False
        try:
            decoded = json.loads(value)
        except ValueError:
            return True
        return bool(decoded) if isinstance(decoded, list) else bool(decoded)
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(value)


def _itso_result_evidence_status(
    criterion: CriterionDefinition,
    *,
    score: int,
    evidence: Any,
    chunk_ids: Any,
    justification: str,
    is_itso_v3: bool,
) -> str | None:
    if (
        not is_itso_v3
        or criterion.criterion_code not in {"ITSO-04", "ITSO-05"}
        or not justification.strip()
        or _has_saved_items(evidence)
        or _has_saved_items(chunk_ids)
    ):
        return None
    return unquoted_review_status(criterion, score)


def _itso_reference_check_note(report: dict | None) -> str | None:
    if report is None:
        return None
    rows = report.get("references")
    if not isinstance(rows, list):
        return None
    usable_count = sum(_usable_itso_source(row) for row in rows)
    searched_count = len(rows)
    if not searched_count:
        return None
    sentence = (
        f"Readable source text was found for {usable_count} of {searched_count} "
        f"searched reference{'s' if searched_count != 1 else ''}."
    )
    coverage = report.get("coverage")
    skipped = coverage.get("skipped") if isinstance(coverage, dict) else None
    if type(skipped) is int and skipped > 0:
        verb = "was" if skipped == 1 else "were"
        sentence += (
            f" {skipped} additional reference{'s' if skipped != 1 else ''} "
            f"{verb} not searched."
        )
    fields = {
        field
        for row in rows
        if isinstance(row, dict)
        for field in (row.get("unverified_fields") or [])
        if field in {"author", "year"}
    }
    if fields:
        names = " and ".join(name for name in ("author", "year") if name in fields)
        sentence += f" {names.capitalize()} details remain unconfirmed."
    return sentence


def _itso_v3_summary(report: dict | None, payload: dict | None) -> str | None:
    """Build readable presentation from the complete saved v3 review facts."""
    coverage = payload.get("document_review_coverage") if payload else None
    local_status = payload.get("local_policy_status") if payload else None
    rows = report.get("references") if report else None
    if (
        not isinstance(coverage, dict)
        or not isinstance(rows, list)
        or local_status not in {"available", "unavailable"}
    ):
        return None
    reviewed = coverage.get("reviewed_chunk_count")
    supplied = coverage.get("supplied_chunk_count")
    reviewed_chars = coverage.get("reviewed_text_characters")
    supplied_chars = coverage.get("supplied_text_characters")
    if not all(
        type(value) is int and value >= 0
        for value in (reviewed, supplied, reviewed_chars, supplied_chars)
    ):
        return None
    parts = []
    searched = len(rows)
    usable = sum(_usable_itso_source(row) for row in rows)
    parts.append(
        f"Public reference checks found readable source text for {usable} of "
        f"{searched} searched references."
    )
    report_coverage = report.get("coverage")
    skipped = (
        report_coverage.get("skipped") if isinstance(report_coverage, dict) else None
    )
    if type(skipped) is int and skipped > 0:
        parts.append(
            f"{skipped} additional detected reference"
            f"{' was' if skipped == 1 else 's were'} not searched."
        )
    unverified = {
        field
        for row in rows
        if isinstance(row, dict)
        for field in (row.get("unverified_fields") or [])
        if field in {"author", "year"}
    }
    if unverified:
        names = " and ".join(name for name in ("author", "year") if name in unverified)
        parts.append(f"{names.capitalize()} details remain unconfirmed.")
    parts.append(
        f"Document review covered {reviewed} of {supplied} text sections "
        f"({reviewed_chars} of {supplied_chars} characters). Images and "
        "missing extracted text were not assessed."
    )
    parts.append(
        "Institutional policy text was "
        f"{local_status}; ownership and permissions require human review."
    )
    return " ".join(parts)


def _clean_itso_justification(
    justification: str, *, strip_reference: bool, strip_coverage: bool
) -> str:
    markers = ((_ITSO_RECEIPT_MARKERS[0],) if strip_reference else ()) + (
        (_ITSO_RECEIPT_MARKERS[1],) if strip_coverage else ()
    )
    positions = [
        position for marker in markers if (position := justification.find(marker)) >= 0
    ]
    if positions:
        justification = justification[: min(positions)]
    return justification.rstrip()


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

        if any(
            s.agent_id == "coordinator" and s.adapter_version == 3
            for s in verified_snapshots
        ):
            # A completed v3 read must not silently omit or trust a tampered supplement.
            load_verified_persisted_agent_results(db, evaluation_id, job.document_id)

        ungrounded_cids = {f.criterion_id for f in flags if f.chunk_id is None}
        item_rejections_batch = get_effective_item_rejections_batch(
            db, evaluation_id, _ITEM_LEVEL_AGENTS
        )
        itso_v3_snapshot = snapshot_by_agent.get("itso")
        itso_generations_by_result: dict[uuid.UUID, list[AgentGeneration]] = {}
        if itso_v3_snapshot is not None and itso_v3_snapshot.adapter_version == 3:
            itso_result = result_by_agent.get("itso")
            if itso_result is not None:
                captured_generations = (
                    db.query(AgentGeneration)
                    .filter(
                        AgentGeneration.evaluation_id == evaluation_id,
                        AgentGeneration.agent_id == "itso",
                        AgentGeneration.agent_result_id == itso_result.agent_result_id,
                        AgentGeneration.form_snapshot_id
                        == itso_v3_snapshot.snapshot_id,
                    )
                    .all()
                )
                itso_generations_by_result[itso_result.agent_result_id] = (
                    captured_generations
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
                    current_contract = (
                        "coordinator_current.v1"
                        if (
                            agent_id == "coordinator"
                            and isinstance(result.group_responses, dict)
                            and "__current_bundle__" in result.group_responses
                        )
                        else None
                    )
                    envelope_map = envelope_criteria_map_from_snapshot(
                        snapshot, agent_id, execution_contract=current_contract
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
            itso_generations = itso_generations_by_result.get(
                result.agent_result_id, []
            )
            itso_report, itso_payload = (
                _captured_itso_context(itso_generations)
                if agent_id == "itso" and snapshot.adapter_version == 3
                else (None, None)
            )
            itso_reference_note = (
                _itso_reference_check_note(itso_report)
                if agent_id == "itso" and snapshot.adapter_version == 3
                else None
            )
            itso_summary = (
                _itso_v3_summary(itso_report, itso_payload)
                if agent_id == "itso" and snapshot.adapter_version == 3
                else None
            )

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
                    is_itso_v3 = agent_id == "itso" and snapshot.adapter_version == 3
                    source_justification = (
                        _captured_criterion_justification(
                            itso_generations,
                            snap_crit.criterion_code,
                            score_row.justification,
                        )
                        if is_itso_v3
                        else ""
                    )
                    public_sources = (
                        _public_itso_sources(itso_report, source_justification)
                        if is_itso_v3
                        and snap_crit.criterion_code in {"ITSO-01", "ITSO-02"}
                        else []
                    )
                    justification = score_row.justification
                    if is_itso_v3:
                        # Receipts were appended to the persisted audit string in
                        # the old adapter. Keep them if the capture needed to
                        # reconstruct the source bindings is unavailable.
                        has_reference_receipt = any(
                            marker in justification
                            for marker in _ITSO_RECEIPT_MARKERS[:1]
                        )
                        if not has_reference_receipt or public_sources:
                            justification = _clean_itso_justification(
                                justification,
                                strip_reference=bool(public_sources),
                                strip_coverage=itso_summary is not None,
                            )
                            if (
                                snap_crit.criterion_code == "ITSO-02"
                                and itso_reference_note
                                and itso_report
                            ):
                                justification = readable_reference_justification(
                                    justification, itso_report
                                )
                            projected_numbers = {
                                source["number"] for source in public_sources
                            }
                            leading_source = re.match(
                                r"^\s*\[\s*source\s+([1-9][0-9]*)\s*\]\s*:?\s*",
                                justification,
                                re.I,
                            )
                            if (
                                leading_source
                                and int(leading_source.group(1)) in projected_numbers
                            ):
                                justification = justification[leading_source.end() :]
                    evidence_status = _itso_result_evidence_status(
                        snap_crit,
                        score=score_row.score,
                        evidence=score_row.evidence,
                        chunk_ids=score_row.chunk_ids,
                        justification=justification,
                        is_itso_v3=is_itso_v3,
                    )
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
                            justification=justification,
                            evidence=score_row.evidence,
                            is_ungrounded=is_ungrounded,
                            evidence_status=evidence_status,
                            public_sources=public_sources,
                            reference_check_note=(
                                itso_reference_note
                                if is_itso_v3
                                and snap_crit.criterion_code in {"ITSO-01", "ITSO-02"}
                                else None
                            ),
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
                advisory_outputs=(
                    result.advisory_outputs
                    if result.success
                    and agent_id == "coordinator"
                    and snapshot.adapter_version == 3
                    else None
                ),
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
                summary=itso_summary or result.summary,
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
