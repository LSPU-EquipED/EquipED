"""Persist agent outputs for evaluation reporting."""

from __future__ import annotations

import json
import uuid
from typing import Any

from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.documents.models import DocumentChunk
from server.modules.synthesis.models import AgentResult, CriterionScore, EvaluationFlag


def persist_agent_outputs(
    db: Any,
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
    agent_results: list[AgentEvaluationResult],
) -> None:
    for agent_result in agent_results:
        result_row = AgentResult(
            agent_result_id=uuid.uuid4(),
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_name=agent_result.agent_name,
            subtotal=agent_result.subtotal,
            processing_seconds=agent_result.processing_seconds,
            token_count=agent_result.token_count,
            model_name=agent_result.model_name,
            summary=agent_result.summary,
            success=agent_result.success,
            error_message=agent_result.error_message,
            raw_response=agent_result.raw_response,
        )
        db.add(result_row)
        db.flush()

        for score in agent_result.criterion_scores:
            valid_chunk_ids = _validated_chunk_ids(db, score.chunk_ids)
            score_row = CriterionScore(
                agent_result_id=result_row.agent_result_id,
                evaluation_id=evaluation_id,
                document_id=document_id,
                criterion_id=score.criterion_id,
                criterion_title=score.criterion_title,
                score=score.score,
                justification=score.justification,
                evidence=(json.dumps(list(score.evidence)) if score.evidence else None),
                chunk_ids=(
                    json.dumps([str(chunk_id) for chunk_id in valid_chunk_ids])
                    if valid_chunk_ids
                    else None
                ),
            )
            db.add(score_row)
            db.flush()

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

    db.commit()


def persist_evaluation_results(
    db: Any,
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
    agent_results: list[AgentEvaluationResult],
) -> None:
    """Compatibility wrapper for orchestrator callers."""

    persist_agent_outputs(db, evaluation_id, document_id, agent_results)


def _validated_chunk_ids(db: Any, chunk_ids: tuple[str, ...]) -> list[uuid.UUID]:
    valid_chunk_ids: list[uuid.UUID] = []
    for chunk_id in chunk_ids:
        try:
            parsed_chunk_id = uuid.UUID(str(chunk_id))
        except (TypeError, ValueError, AttributeError):
            continue
        if db.get(DocumentChunk, parsed_chunk_id) is None:
            continue
        if parsed_chunk_id not in valid_chunk_ids:
            valid_chunk_ids.append(parsed_chunk_id)
    return valid_chunk_ids


__all__ = ["persist_agent_outputs", "persist_evaluation_results"]
