"""Persist agent outputs and assemble evaluation reporting for the synthesis module."""

from __future__ import annotations

import json
import logging
import math
import uuid
from collections.abc import Callable
from typing import Any

from server.modules.agents.contracts import (
    AdvisoryOutput,
    AgentEvaluationResult,
)
from server.modules.agents.contracts import (
    CriterionScore as InputCriterionScore,
)
from server.modules.documents.metadata import canonicalize_supported_program
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.agent_schedule import scheduled_agent_ids
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.feedback.state import (
    EffectiveCriterionCorrection,
    get_effective_criterion_corrections,
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
    UnsupportedProgramFilterError,
)
from server.modules.synthesis.matrix import compute_synthesized_score
from server.modules.synthesis.models import (
    AgentResult,
    CriterionScore,
    EvaluationFlag,
    MonitoringMatrix,
)
from server.modules.synthesis.result_integrity import (
    PersistableAgentResult,
    build_persistable_agent_result,
    derive_itso_ungrounded_criterion_ids,
)
from server.modules.synthesis.schemas import (
    CriterionScoreItem,
    DomainScoreBlock,
    EvaluationFlagItem,
    EvaluationResultsResponse,
    MatrixListResponse,
    MatrixRowItem,
)
from sqlalchemy import func, or_

logger = logging.getLogger(__name__)


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


def persist_agent_outputs(
    db: Any,
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
    agent_results: list[AgentEvaluationResult],
    *,
    verify_ownership: Callable[[Any], None],
    commit: bool = True,
) -> None:
    verify_ownership(db)

    job = db.get(EvaluationJob, evaluation_id)
    if job is None:
        raise EvaluationResultIntegrityError("Evaluation job not found")
    if job.document_id != document_id:
        raise EvaluationResultIntegrityError("Evaluation job document_id mismatch")

    existing_agent_results_count = (
        db.query(AgentResult).filter(AgentResult.evaluation_id == evaluation_id).count()
    )
    if existing_agent_results_count > 0:
        raise EvaluationResultIntegrityError(
            "AgentResult rows already exist for evaluation"
        )

    scheduled_ids = scheduled_agent_ids(
        partial_without_curriculum=job.partial_without_curriculum
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

    if not isinstance(agent_results, (list, tuple)):
        raise EvaluationResultIntegrityError("agent_results must be a sequence")

    if len(agent_results) != len(scheduled_ids):
        raise EvaluationResultIntegrityError(
            "agent_results count does not match scheduled agents count"
        )

    seen_agents: set[str] = set()
    persistable_results: list[PersistableAgentResult] = []
    for result in agent_results:
        if not isinstance(result, AgentEvaluationResult):
            raise EvaluationResultIntegrityError("Invalid agent result item type")
        if result.agent_name in seen_agents:
            raise EvaluationResultIntegrityError("Duplicate agent in agent_results")
        seen_agents.add(result.agent_name)

        if result.agent_name not in snapshot_by_agent:
            raise EvaluationResultIntegrityError("Unexpected agent in agent_results")

        if result.evaluation_id != evaluation_id:
            raise EvaluationResultIntegrityError("Agent result evaluation_id mismatch")
        if result.document_id != document_id:
            raise EvaluationResultIntegrityError("Agent result document_id mismatch")

        snapshot_dto = snapshot_by_agent[result.agent_name]
        persistable = build_persistable_agent_result(result, snapshot_dto)
        persistable_results.append(persistable)

    if seen_agents != set(scheduled_ids):
        raise EvaluationResultIntegrityError(
            "Missing scheduled agents in agent_results"
        )

    parsed_chunk_ids: set[uuid.UUID] = set()
    for p_result in persistable_results:
        for score in p_result.criterion_scores:
            for chunk_id in score.chunk_ids_raw:
                try:
                    parsed_chunk_ids.add(uuid.UUID(str(chunk_id)))
                except (TypeError, ValueError, AttributeError):
                    continue

    owned_chunks = {
        chunk.chunk_id
        for chunk in (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == document_id,
                DocumentChunk.chunk_id.in_(parsed_chunk_ids),
            )
            .all()
        )
    }

    final_owned_chunks_map: dict[str, dict[str, tuple[str, ...]]] = {}
    for p_result in persistable_results:
        final_owned_chunks_map[p_result.agent_name] = {
            score.criterion_id: tuple(
                str(cid)
                for cid in _validated_chunk_ids(score.chunk_ids_raw, owned_chunks)
            )
            for score in p_result.criterion_scores
        }
        if p_result.agent_name == "itso":
            final_itso_ungrounded = derive_itso_ungrounded_criterion_ids(
                p_result.criterion_scores,
                chunk_id_map=final_owned_chunks_map["itso"],
            )
            adv_cids = (
                {
                    u.criterion_id
                    for u in p_result.advisory_output_dto.ungrounded_criteria
                }
                if p_result.advisory_output_dto
                else set()
            )
            if final_itso_ungrounded != adv_cids:
                raise EvaluationResultIntegrityError(
                    "ITSO ungrounded criteria changed after chunk "
                    "ownership verification"
                )

    for p_result in persistable_results:
        result_row = AgentResult(
            agent_result_id=uuid.uuid4(),
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_name=p_result.agent_name,
            prompt_version_id=p_result.prompt_version_id,
            subtotal=p_result.subtotal,
            processing_seconds=p_result.processing_seconds,
            token_count=p_result.token_count,
            model_name=p_result.model_name,
            summary=p_result.summary,
            success=p_result.success,
            error_message=p_result.error_message,
            raw_response=p_result.raw_response,
            prompt_text=p_result.prompt_text,
            group_prompts=(
                json.loads(p_result.group_prompts_json)
                if p_result.group_prompts_json
                else None
            ),
            group_responses=(
                json.loads(p_result.group_responses_json)
                if p_result.group_responses_json
                else None
            ),
            provenance=(
                json.loads(p_result.provenance_json)
                if p_result.provenance_json
                else None
            ),
            advisory_outputs=(
                json.loads(p_result.advisory_outputs_json)
                if p_result.advisory_outputs_json
                else None
            ),
            form_snapshot_id=p_result.form_snapshot_id,
        )
        db.add(result_row)
        db.flush()

        if not p_result.success:
            continue

        criterion_score_map: dict[str, CriterionScore] = {}
        for score in p_result.criterion_scores:
            valid_chunk_str_ids = final_owned_chunks_map[p_result.agent_name][
                score.criterion_id
            ]
            valid_chunk_ids = [uuid.UUID(cid) for cid in valid_chunk_str_ids]
            score_row = CriterionScore(
                agent_result_id=result_row.agent_result_id,
                evaluation_id=evaluation_id,
                document_id=document_id,
                criterion_id=score.criterion_id,
                criterion_title=score.criterion_title,
                score=score.score,
                justification=score.justification,
                evidence=score.evidence_json,
                chunk_ids=(
                    json.dumps([str(chunk_id) for chunk_id in valid_chunk_ids])
                    if valid_chunk_ids
                    else None
                ),
            )
            db.add(score_row)
            db.flush()
            criterion_score_map[score.criterion_id] = score_row

            if score.score <= 2:
                for chunk_id in valid_chunk_ids:
                    flag_row = EvaluationFlag(
                        evaluation_id=evaluation_id,
                        document_id=document_id,
                        agent_result_id=result_row.agent_result_id,
                        criterion_score_id=score_row.criterion_score_id,
                        chunk_id=chunk_id,
                        criterion_id=score.criterion_id,
                        score=score.score,
                        reason=score.justification,
                    )
                    db.add(flag_row)

        if p_result.advisory_output_dto is not None:
            for item in p_result.advisory_output_dto.ungrounded_criteria:
                crit_id = item.criterion_id
                score_row = criterion_score_map[crit_id]
                flag_row = EvaluationFlag(
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    agent_result_id=result_row.agent_result_id,
                    criterion_score_id=score_row.criterion_score_id,
                    chunk_id=None,
                    criterion_id=crit_id,
                    score=score_row.score,
                    reason=item.reason,
                )
                db.add(flag_row)

    verify_ownership(db)
    if commit:
        db.commit()


def load_verified_persisted_agent_results(
    db: Any,
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
) -> list[AgentResult]:
    """Load and verify persisted AgentResult and CriterionScore rows against snapshots.

    Fails closed with EvaluationResultIntegrityError on any missing, corrupt,
    tampered, or NULL snapshot rows.
    """
    job = db.get(EvaluationJob, evaluation_id)
    if job is None:
        raise EvaluationResultIntegrityError("Evaluation job not found")
    if job.document_id != document_id:
        raise EvaluationResultIntegrityError("Evaluation job document_id mismatch")

    scheduled_ids = scheduled_agent_ids(
        partial_without_curriculum=bool(job.partial_without_curriculum)
    )
    try:
        verified_snapshots = load_verified_evaluation_snapshots(
            db, evaluation_id, scheduled_ids
        )
    except SnapshotIntegrityError as exc:
        raise EvaluationResultIntegrityError(
            "Failed to load verified evaluation snapshots"
        ) from exc

    snapshot_by_agent = {s.agent_id: s for s in verified_snapshots}

    agent_results = db.query(AgentResult).filter_by(evaluation_id=evaluation_id).all()

    if len(agent_results) != len(scheduled_ids):
        raise EvaluationResultIntegrityError(
            "Persisted agent results count mismatch against scheduled agents"
        )

    result_by_agent: dict[str, AgentResult] = {r.agent_name: r for r in agent_results}
    if len(result_by_agent) != len(agent_results) or set(result_by_agent.keys()) != set(
        scheduled_ids
    ):
        raise EvaluationResultIntegrityError(
            "Persisted agent results set mismatch against scheduled agents"
        )

    valid_result_ids = {r.agent_result_id for r in agent_results}
    result_by_id = {r.agent_result_id: r for r in agent_results}

    criterion_scores = (
        db.query(CriterionScore)
        .filter(
            or_(
                CriterionScore.evaluation_id == evaluation_id,
                CriterionScore.agent_result_id.in_(valid_result_ids),
            )
        )
        .all()
    )

    score_by_id = {s.criterion_score_id: s for s in criterion_scores}
    valid_score_ids = set(score_by_id.keys())
    scores_by_result_id: dict[uuid.UUID, list[CriterionScore]] = {}
    all_persisted_chunk_uuids: set[uuid.UUID] = set()
    persisted_chunk_ids_by_score_id: dict[uuid.UUID, tuple[uuid.UUID, ...]] = {}

    for score in criterion_scores:
        if score.agent_result_id not in valid_result_ids:
            raise EvaluationResultIntegrityError("Orphan criterion score row found")
        if score.evaluation_id != evaluation_id or score.document_id != document_id:
            raise EvaluationResultIntegrityError(
                "Criterion score evaluation or document mismatch"
            )
        attached_result = result_by_id[score.agent_result_id]
        if (
            score.evaluation_id != attached_result.evaluation_id
            or score.document_id != attached_result.document_id
        ):
            raise EvaluationResultIntegrityError(
                "Criterion score evaluation or document mismatch against result"
            )
        score_chunk_uuids: list[uuid.UUID] = []
        if score.chunk_ids is not None:
            try:
                c_data = json.loads(score.chunk_ids)
            except (json.JSONDecodeError, TypeError) as exc:
                raise EvaluationResultIntegrityError("Invalid chunk_ids JSON") from exc
            if not isinstance(c_data, list):
                raise EvaluationResultIntegrityError("chunk_ids must be a list")
            for v in c_data:
                if not isinstance(v, str):
                    raise EvaluationResultIntegrityError("chunk_id must be a string")
                try:
                    u = uuid.UUID(v)
                except (TypeError, ValueError) as exc:
                    raise EvaluationResultIntegrityError(
                        "Non-canonical chunk ID string"
                    ) from exc
                if str(u) != v:
                    raise EvaluationResultIntegrityError(
                        "Non-canonical chunk ID string"
                    )
                all_persisted_chunk_uuids.add(u)
                score_chunk_uuids.append(u)
            if len(c_data) != len(set(c_data)):
                raise EvaluationResultIntegrityError(
                    "Duplicate chunk ID in criterion score"
                )
        persisted_chunk_ids_by_score_id[score.criterion_score_id] = tuple(
            score_chunk_uuids
        )

        scores_by_result_id.setdefault(score.agent_result_id, []).append(score)

    owned_chunk_rows = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == document_id,
            DocumentChunk.chunk_id.in_(all_persisted_chunk_uuids),
        )
        .all()
        if all_persisted_chunk_uuids
        else []
    )
    owned_chunk_uuid_set = {c.chunk_id for c in owned_chunk_rows}
    if not all_persisted_chunk_uuids.issubset(owned_chunk_uuid_set):
        raise EvaluationResultIntegrityError(
            "Persisted chunk ID does not belong to evaluated document"
        )

    flags = (
        db.query(EvaluationFlag)
        .filter(
            or_(
                EvaluationFlag.evaluation_id == evaluation_id,
                EvaluationFlag.agent_result_id.in_(valid_result_ids),
                EvaluationFlag.criterion_score_id.in_(valid_score_ids),
            )
        )
        .all()
    )

    for flag in flags:
        if flag.agent_result_id not in valid_result_ids:
            raise EvaluationResultIntegrityError(
                "EvaluationFlag agent_result_id not in current results"
            )
        if flag.criterion_score_id not in valid_score_ids:
            raise EvaluationResultIntegrityError(
                "EvaluationFlag criterion_score_id not in current scores"
            )
        target_result = result_by_id[flag.agent_result_id]
        target_score = score_by_id[flag.criterion_score_id]

        if target_score.agent_result_id != flag.agent_result_id:
            raise EvaluationResultIntegrityError(
                "EvaluationFlag score and result relationship mismatch"
            )
        if (
            flag.evaluation_id != evaluation_id
            or flag.document_id != document_id
            or target_score.evaluation_id != evaluation_id
            or target_score.document_id != document_id
            or target_result.evaluation_id != evaluation_id
            or target_result.document_id != document_id
        ):
            raise EvaluationResultIntegrityError(
                "EvaluationFlag cross-evaluation or cross-document reference"
            )
        if (
            flag.criterion_id != target_score.criterion_id
            or flag.score != target_score.score
        ):
            raise EvaluationResultIntegrityError(
                "EvaluationFlag criterion_id or score mismatch against referenced score"
            )
        if flag.chunk_id is not None:
            if flag.chunk_id not in owned_chunk_uuid_set:
                raise EvaluationResultIntegrityError(
                    "EvaluationFlag chunk_id does not belong to document"
                )
            if flag.chunk_id not in persisted_chunk_ids_by_score_id.get(
                target_score.criterion_score_id, ()
            ):
                raise EvaluationResultIntegrityError(
                    "EvaluationFlag chunk_id not present in referenced score chunk_ids"
                )
            if flag.reason != target_score.justification:
                raise EvaluationResultIntegrityError(
                    "EvaluationFlag reason mismatch against score justification"
                )

    for agent_id in scheduled_ids:
        row = result_by_agent[agent_id]
        snapshot_dto = snapshot_by_agent[agent_id]

        if row.evaluation_id != evaluation_id or row.document_id != document_id:
            raise EvaluationResultIntegrityError(
                "Persisted agent result evaluation or document mismatch"
            )
        if (
            row.form_snapshot_id is None
            or row.form_snapshot_id != snapshot_dto.snapshot_id
        ):
            raise EvaluationResultIntegrityError(
                "Persisted agent result form_snapshot_id mismatch or NULL"
            )

        if row.group_prompts is not None and not isinstance(row.group_prompts, dict):
            raise EvaluationResultIntegrityError(
                "Persisted group_prompts must be a dict"
            )
        if row.group_responses is not None and not isinstance(
            row.group_responses, dict
        ):
            raise EvaluationResultIntegrityError(
                "Persisted group_responses must be a dict"
            )
        if row.provenance is not None and not isinstance(row.provenance, dict):
            raise EvaluationResultIntegrityError("Persisted provenance must be a dict")

        if row.advisory_outputs is not None:
            if not isinstance(row.advisory_outputs, dict):
                raise EvaluationResultIntegrityError(
                    "Persisted advisory_outputs must be a dict"
                )
            try:
                adv_dto = AdvisoryOutput.from_dict(row.advisory_outputs)
            except (TypeError, ValueError) as exc:
                raise EvaluationResultIntegrityError(
                    "Invalid advisory outputs"
                ) from exc
        else:
            adv_dto = None

        db_scores = scores_by_result_id.get(row.agent_result_id, [])
        reconstructed_scores = []
        for s in db_scores:
            if (
                isinstance(s.score, bool)
                or not isinstance(s.score, int)
                or not (1 <= s.score <= 4)
            ):
                raise EvaluationResultIntegrityError("Invalid criterion score")
            if s.evidence is not None:
                try:
                    ev_data = json.loads(s.evidence)
                except (json.JSONDecodeError, TypeError) as exc:
                    raise EvaluationResultIntegrityError(
                        "Invalid evidence JSON"
                    ) from exc
                if not isinstance(ev_data, list):
                    raise EvaluationResultIntegrityError("evidence must be a list")
                ev_tuple = tuple(ev_data)
            else:
                ev_tuple = ()

            c_tuple = tuple(
                str(chunk_id)
                for chunk_id in persisted_chunk_ids_by_score_id.get(
                    s.criterion_score_id, ()
                )
            )

            reconstructed_scores.append(
                InputCriterionScore(
                    criterion_id=s.criterion_id,
                    criterion_title=s.criterion_title,
                    score=s.score,
                    justification=s.justification,
                    chunk_ids=c_tuple,
                    evidence=ev_tuple,
                )
            )

        meta = {}
        if row.group_prompts is not None:
            meta["group_prompts"] = row.group_prompts
        if row.group_responses is not None:
            meta["group_responses"] = row.group_responses

        reconstructed_result = AgentEvaluationResult(
            agent_name=row.agent_name,
            evaluation_id=row.evaluation_id,
            document_id=row.document_id,
            subtotal=row.subtotal,
            criterion_scores=tuple(reconstructed_scores),
            summary=row.summary,
            model_name=row.model_name,
            processing_seconds=row.processing_seconds,
            token_count=row.token_count,
            prompt_version_id=row.prompt_version_id,
            success=row.success,
            error_message=row.error_message,
            raw_response=row.raw_response,
            prompt_text=row.prompt_text,
            metadata=meta,
            provenance=row.provenance,
            advisory_outputs=adv_dto,
        )

        persistable = build_persistable_agent_result(reconstructed_result, snapshot_dto)

        if persistable.provenance_json is not None:
            if json.loads(persistable.provenance_json) != row.provenance:
                raise EvaluationResultIntegrityError(
                    "Persisted provenance does not match sanitized provenance"
                )
        elif row.provenance is not None:
            raise EvaluationResultIntegrityError(
                "Persisted provenance does not match sanitized provenance"
            )

        if not math.isclose(
            row.subtotal, persistable.subtotal, rel_tol=1e-5, abs_tol=1e-5
        ):
            raise EvaluationResultIntegrityError(
                "Subtotal mismatch against derived mean"
            )

        if row.success:
            db_scores_by_id = {s.criterion_id: s for s in db_scores}
            for p_score in persistable.criterion_scores:
                db_score = db_scores_by_id[p_score.criterion_id]
                if db_score.criterion_title != p_score.criterion_title:
                    raise EvaluationResultIntegrityError(
                        "Criterion title mismatch against snapshot"
                    )

            if persistable.group_prompts_json is not None:
                if json.loads(persistable.group_prompts_json) != row.group_prompts:
                    raise EvaluationResultIntegrityError(
                        "Persisted group_prompts mismatch"
                    )
            else:
                if row.group_prompts is not None:
                    raise EvaluationResultIntegrityError(
                        "Persisted group_prompts mismatch"
                    )

            if persistable.group_responses_json is not None:
                if json.loads(persistable.group_responses_json) != row.group_responses:
                    raise EvaluationResultIntegrityError(
                        "Persisted group_responses mismatch"
                    )
            else:
                if row.group_responses is not None:
                    raise EvaluationResultIntegrityError(
                        "Persisted group_responses mismatch"
                    )

            if persistable.advisory_outputs_json is not None:
                if (
                    json.loads(persistable.advisory_outputs_json)
                    != row.advisory_outputs
                ):
                    raise EvaluationResultIntegrityError(
                        "Persisted advisory_outputs mismatch"
                    )
            else:
                if row.advisory_outputs is not None:
                    raise EvaluationResultIntegrityError(
                        "Persisted advisory_outputs mismatch"
                    )

            if agent_id == "itso":
                itso_null_flags = [
                    f
                    for f in flags
                    if f.agent_result_id == row.agent_result_id and f.chunk_id is None
                ]
                itso_ungrounded = derive_itso_ungrounded_criterion_ids(
                    persistable.criterion_scores
                )
                if len(itso_null_flags) != len(itso_ungrounded):
                    raise EvaluationResultIntegrityError(
                        "ITSO advisory flag count mismatch"
                    )
                seen_flag_cids = set()
                db_score_by_cid = {s.criterion_id: s for s in db_scores}
                adv_reason_by_cid = (
                    {
                        u.criterion_id: u.reason
                        for u in persistable.advisory_output_dto.ungrounded_criteria
                    }
                    if persistable.advisory_output_dto
                    else {}
                )
                for flag in itso_null_flags:
                    if flag.criterion_id not in itso_ungrounded:
                        raise EvaluationResultIntegrityError(
                            "Unexpected ITSO advisory flag"
                        )
                    if flag.criterion_id in seen_flag_cids:
                        raise EvaluationResultIntegrityError(
                            "Duplicate ITSO advisory flag"
                        )
                    seen_flag_cids.add(flag.criterion_id)
                    target_score = db_score_by_cid.get(flag.criterion_id)
                    if (
                        target_score is None
                        or flag.criterion_score_id != target_score.criterion_score_id
                        or flag.score != target_score.score
                        or flag.reason != adv_reason_by_cid.get(flag.criterion_id)
                        or flag.evaluation_id != evaluation_id
                        or flag.document_id != document_id
                    ):
                        raise EvaluationResultIntegrityError(
                            "ITSO advisory flag metadata mismatch"
                        )
            else:
                if any(
                    f.agent_result_id == row.agent_result_id and f.chunk_id is None
                    for f in flags
                ):
                    raise EvaluationResultIntegrityError(
                        "Non-ITSO agent must not have null-chunk flags"
                    )

    return [result_by_agent[agent_id] for agent_id in scheduled_ids]


def get_evaluation_results(
    evaluation_id: uuid.UUID,
    current_user_id: uuid.UUID,
    db: Any,
) -> EvaluationResultsResponse:
    """Assemble the full evaluation results response for an owner.

    Ownership is enforced here: a missing job or a job not submitted by
    ``current_user_id`` raises ``EvaluationResultsNotFoundError`` so the
    router can mask non-ownership as a 404.
    """
    job = db.get(EvaluationJob, evaluation_id)
    if job is None or job.submitted_by != current_user_id:
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

    synthesis_result = compute_synthesized_score(
        agent_results,
        force_partial=job.partial_without_curriculum,
        partial_reason=job.partial_reason,
    )

    criteria_by_result: dict[uuid.UUID, list[CriterionScore]] = {}
    for score in criterion_scores:
        criteria_by_result.setdefault(score.agent_result_id, []).append(score)

    # Build a lookup from criterion_score_id -> CriterionScore for flag resolution
    criterion_by_id: dict[uuid.UUID, CriterionScore] = {
        score.criterion_score_id: score for score in criterion_scores
    }

    scheduled_ids = scheduled_agent_ids(
        partial_without_curriculum=bool(job.partial_without_curriculum)
    )

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

        for agent_id in scheduled_ids:
            result = result_by_agent[agent_id]
            snapshot = snapshot_by_agent[agent_id]
            first_domain = snapshot.form.domains[0] if snapshot.form.domains else None
            domain_id = first_domain.rubric_domain_id if first_domain else None
            domain_name = first_domain.title if first_domain else None
            domain_display_order = first_domain.display_order if first_domain else None

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


def get_monitoring_matrix(
    program: str | None,
    status: str | None,
    page: int,
    page_size: int,
    db: Any,
) -> MatrixListResponse:
    """Assemble the monitoring matrix list response with filtering and pagination.

    Raises ``UnsupportedProgramFilterError`` when the ``program`` filter is
    not a supported program (so the router can map it to a 422).
    """
    query = db.query(MonitoringMatrix)

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
    rows = (
        query.order_by(MonitoringMatrix.last_updated.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    doc_ids = [row.document_id for row in rows]
    docs = {
        d.document_id: d
        for d in db.query(Document).filter(Document.document_id.in_(doc_ids)).all()
    }

    items = []
    for row in rows:
        doc = docs.get(row.document_id)
        items.append(
            MatrixRowItem(
                matrix_id=row.matrix_id,
                document_id=row.document_id,
                evaluation_id=row.evaluation_id,
                faculty_name=row.faculty_name,
                program=row.program,
                document_title=doc.title if doc else None,
                evaluation_status=row.evaluation_status,
                synthesized_score=float(row.synthesized_score)
                if row.synthesized_score is not None
                else None,
                domain_scores=row.domain_scores_json,
                flag_count=row.flag_count,
                feedback_status=row.feedback_status,
                last_updated=row.last_updated,
            )
        )

    return MatrixListResponse(items=items, total=total, page=page, page_size=page_size)


def _validated_chunk_ids(
    chunk_ids: tuple[str, ...], owned_chunks: set[uuid.UUID]
) -> list[uuid.UUID]:
    valid_chunk_ids: list[uuid.UUID] = []
    for chunk_id in chunk_ids:
        try:
            parsed_chunk_id = uuid.UUID(str(chunk_id))
        except (TypeError, ValueError, AttributeError):
            continue
        if parsed_chunk_id in owned_chunks and parsed_chunk_id not in valid_chunk_ids:
            valid_chunk_ids.append(parsed_chunk_id)
    return valid_chunk_ids


__all__ = [
    "persist_agent_outputs",
    "load_verified_persisted_agent_results",
    "get_evaluation_results",
    "get_monitoring_matrix",
]
