"""Agent output persistence and verification integrity for the synthesis module."""

from __future__ import annotations

import json
import logging
import math
import sys
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
from server.modules.documents.models import DocumentChunk
from server.modules.evaluations.agent_schedule import scheduled_agent_ids
from server.modules.evaluations.models import EvaluationJob
from server.modules.rubrics.snapshot_contracts import (
    EvaluationFormSnapshotDTO,
    SnapshotIntegrityError,
)
from server.modules.rubrics.snapshots import load_verified_evaluation_snapshots
from server.modules.synthesis.exceptions import EvaluationResultIntegrityError
from server.modules.synthesis.models import (
    AgentResult,
    CriterionScore,
    EvaluationFlag,
)
from server.modules.synthesis.result_integrity import (
    PersistableAgentResult,
    build_persistable_agent_result,
    derive_itso_ungrounded_criterion_ids,
)
from sqlalchemy import or_

logger = logging.getLogger(__name__)


def _get_snapshot_loader() -> Callable[..., Any]:
    svc = sys.modules.get("server.modules.synthesis.service")
    if svc is not None and hasattr(svc, "load_verified_evaluation_snapshots"):
        return getattr(svc, "load_verified_evaluation_snapshots")
    return load_verified_evaluation_snapshots


def _scheduled_ids_for_job(job: Any) -> tuple[str, ...]:
    """Resolve scheduled agents preferring targeted single-agent."""
    target = getattr(job, "target_agent", None)
    if target in ("sme", "coordinator", "gad", "itso"):
        return scheduled_agent_ids(target_agent=target)
    if target == "all":
        return scheduled_agent_ids(
            partial_without_curriculum=bool(
                getattr(job, "partial_without_curriculum", False)
            )
        )
    return scheduled_agent_ids(
        partial_without_curriculum=bool(
            getattr(job, "partial_without_curriculum", False)
        )
    )


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

    scheduled_ids = _scheduled_ids_for_job(job)
    loader = _get_snapshot_loader()
    try:
        verified_snapshots = loader(
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

    scheduled_ids = _scheduled_ids_for_job(job)
    loader = _get_snapshot_loader()
    try:
        verified_snapshots = loader(
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


__all__ = [
    "persist_agent_outputs",
    "load_verified_persisted_agent_results",
    "_scheduled_ids_for_job",
    "_validated_chunk_ids",
]
