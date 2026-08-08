"""
BackgroundTask orchestrator for evaluations jobs.

Phase 1 execution is sequential via FastAPI BackgroundTasks. The
orchestrator generates a per-run execution token, atomically claims the
job, heartbeats around major phases, and clears the token on terminal
transitions. If the supervisor has already produced outputs for the
evaluation (e.g. after a startup recovery), the orchestrator skips
re-running the supervisor and resumes from synthesis/finalization.
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from typing import Any

from server.core.llm import get_llm_client_for_agent
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.coordinator import ProgramCoordinator
from server.modules.agents.supervisor import Supervisor
from server.modules.curriculum.service import resolve_roadmap_course_context
from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.documents.models import Document
from server.modules.documents.service import get_document_chunks
from server.modules.evaluations.exceptions import (
    EvaluationExecutionOwnershipError,
    EvaluationPipelineUnavailableError,
)
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.service import (
    acquire_evaluation_execution,
    heartbeat_evaluation_execution,
    transition_evaluation_status,
)
from server.modules.synthesis.matrix import (
    compute_synthesized_score,
    upsert_monitoring_matrix,
)
from server.modules.synthesis.models import AgentResult, EvaluationFlag
from server.modules.synthesis.service import persist_agent_outputs
from sqlalchemy import update

logger = logging.getLogger(__name__)


def run_evaluation_job(
    evaluation_id: uuid.UUID,
    db_session_factory=None,
) -> None:
    """Run the lifecycle through honest Phase 3 transitions.

    The runner is idempotent at the evaluation level: if a previous
    attempt already persisted AgentResult rows (e.g. after a crash that
    the startup recovery helper detected), the supervisor is skipped
    and the orchestrator resumes from synthesis/finalization.
    """

    if db_session_factory is None:
        from server.core.database import get_session_factory

        db_session_factory = get_session_factory()

    execution_token = uuid.uuid4()
    execution_acquired = False
    session = db_session_factory()
    try:
        job = session.get(EvaluationJob, evaluation_id)
        if job is None:
            raise EvaluationPipelineUnavailableError("Evaluation job not found.")

        # 1) Atomic claim — no-op if missing, terminal, or already owned.
        acquired = acquire_evaluation_execution(session, evaluation_id, execution_token)
        if not acquired:
            logger.info(
                "Skipping evaluation %s: not claimable (terminal or already owned).",
                evaluation_id,
            )
            return
        execution_acquired = True

        # Re-read the row with the freshly attached token for the rest of
        # the lifecycle. Subsequent status transitions carry the token.
        job = session.get(EvaluationJob, evaluation_id)
        if job is None or job.execution_token != execution_token:
            # Lost the race between acquire and the next read.
            return

        document = session.get(Document, job.document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {job.document_id} not found")

        if job.syllabus_id is not None:
            syllabus = session.get(Document, job.syllabus_id)
            if syllabus is None:
                raise DocumentNotFoundError(f"Document {job.syllabus_id} not found")

        if job.curriculum_id is not None:
            curriculum = session.get(Document, job.curriculum_id)
            if curriculum is None:
                logger.warning(
                    "Curriculum document %s for historical job %s not found "
                    "(cleared or purged); proceeding.",
                    job.curriculum_id, evaluation_id
                )

        transition_evaluation_status(
            evaluation_id,
            EvaluationStatus.PREPROCESSING,
            session,
            execution_token=execution_token,
        )
        heartbeat_evaluation_execution(session, evaluation_id, execution_token)

        slm_chunks = get_document_chunks(job.document_id, db=session)
        if not slm_chunks:
            raise EvaluationPipelineUnavailableError(
                "Document has no chunks for evaluation."
            )
        slm_text = "\n".join(
            [chunk.text for chunk in slm_chunks if getattr(chunk, "text", None)]
        )

        transition_evaluation_status(
            evaluation_id,
            EvaluationStatus.EVALUATING,
            session,
            execution_token=execution_token,
        )
        heartbeat_evaluation_execution(session, evaluation_id, execution_token)

        # 2) Idempotency check: if a prior attempt already persisted
        #    AgentResult rows, do not re-run the supervisor. Resume from
        #    synthesis/finalization instead.
        existing_results = (
            session.query(AgentResult).filter_by(evaluation_id=evaluation_id).count()
        )
        if existing_results == 0:
            _verify_token_ownership(session, evaluation_id, execution_token)
            # Heartbeat before dispatching parallel agents.
            heartbeat_evaluation_execution(session, evaluation_id, execution_token)
            if job.partial_without_curriculum or job.curriculum_id is None:
                # No-curriculum partial or new curriculum-retired run: construct
                # Supervisor without ProgramCoordinator so coordinator review
                # is skipped entirely.
                from server.modules.agents.gad import GADAgent
                from server.modules.agents.itso import ITSOAgent
                from server.modules.agents.sme import SMEAgent

                supervisor = Supervisor(
                    agents=[SMEAgent(), GADAgent(), ITSOAgent()],
                    db=session,
                )
            else:
                supervisor = Supervisor(db=session)
            # Resolve program-roadmap context once, before the supervisor
            # context is built. Advisory-only: any failure yields None and
            # leaves the evaluation unaffected.
            roadmap_ctx = None
            try:
                roadmap_ctx = resolve_roadmap_course_context(
                    program=job.confirmed_program,
                    course_code=document.course_code,
                    db=session,
                )
            except Exception:
                roadmap_ctx = None
            supervisor_result = supervisor.run_evaluation(
                evaluation_id=evaluation_id,
                document_id=job.document_id,
                chunks=slm_chunks,
                query_text=slm_text,
                context={
                    "reference_document_ids": {
                        **({"syllabus": job.syllabus_id} if job.syllabus_id else {}),
                        **(
                            {"curriculum": job.curriculum_id}
                            if job.curriculum_id
                            else {}
                        ),
                    },
                    **({"roadmap": roadmap_ctx} if roadmap_ctx else {}),
                },
            )
            if not supervisor_result.agent_results:
                raise EvaluationPipelineUnavailableError(
                    "Layer 3 produced no usable agent outputs."
                )
            # Coordinator's own run() (dispatched in parallel with SME by
            # Supervisor, unchanged) only computes A-05 -- splice in SME's
            # other 9 scores now that both have finished, or fall back to
            # Coordinator's full independent pass if SME failed. See
            # coordinator.py's module docstring for why.
            supervisor_result.agent_results = _reconcile_coordinator_result(
                supervisor_result.agent_results,
                job=job,
                slm_chunks=slm_chunks,
                slm_text=slm_text,
                session=session,
                roadmap_context=roadmap_ctx,
            )
            _verify_token_ownership(session, evaluation_id, execution_token)
            # Heartbeat after all agent futures complete.
            heartbeat_evaluation_execution(session, evaluation_id, execution_token)
            persist_agent_outputs(
                session,
                evaluation_id,
                job.document_id,
                supervisor_result.agent_results,
            )
        else:
            logger.info(
                "Resuming evaluation %s: %d AgentResult row(s) already present; "
                "skipping supervisor.",
                evaluation_id,
                existing_results,
            )

        heartbeat_evaluation_execution(session, evaluation_id, execution_token)
        _verify_token_ownership(session, evaluation_id, execution_token)
        transition_evaluation_status(
            evaluation_id,
            EvaluationStatus.SYNTHESIZING,
            session,
            execution_token=execution_token,
        )

        agent_results = (
            session.query(AgentResult).filter_by(evaluation_id=evaluation_id).all()
        )
        synthesis_result = compute_synthesized_score(
            agent_results,
            force_partial=job.partial_without_curriculum,
            partial_reason=job.partial_reason,
        )
        flag_count = (
            session.query(EvaluationFlag).filter_by(evaluation_id=evaluation_id).count()
        )

        heartbeat_evaluation_execution(session, evaluation_id, execution_token)
        upsert_monitoring_matrix(
            db=session,
            document_id=job.document_id,
            evaluation_id=evaluation_id,
            evaluation_status=(
                "COMPLETED"
                if not synthesis_result["is_partial"]
                else "COMPLETED_PARTIAL"
            ),
            synthesized_score=synthesis_result["synthesized_score"],
            domain_scores=synthesis_result["domain_scores"],
            flag_count=flag_count,
        )

        # Deliberate no-curriculum partial evaluations (and curriculum-retired
        # runs) always complete successfully (the user chose or system enforced
        # the degraded path). Accidental
        # partials caused by agent failures still end as FAILED.
        if job.partial_without_curriculum or job.curriculum_id is None:
            final_status = EvaluationStatus.COMPLETED
            partial_error = None
        elif synthesis_result["is_partial"]:
            final_status = EvaluationStatus.FAILED
            failed_errors = [
                f"{r.agent_name}: {r.error_message}"
                for r in agent_results
                if not r.success and r.error_message
            ]
            partial_error = (
                "; ".join(failed_errors)
                if failed_errors
                else "Partial: some agents failed"
            )
        else:
            final_status = EvaluationStatus.COMPLETED
            partial_error = None
        _verify_token_ownership(session, evaluation_id, execution_token)

        # Durable finalization: execute model-validation criterion-score
        # matching and toxicity assessment BEFORE the linked evaluation
        # transitions to a terminal state. If postprocessing fails, the
        # evaluation still completes normally — the error is logged and
        # the validation record retains null actual scores / unavailable
        # toxicity. A failure here must never make normal eval data
        # disappear or prevent a legitimate COMPLETED transition.
        if final_status == EvaluationStatus.COMPLETED:
            from server.modules.admin.model_validation_service import (
                assess_model_validation_toxicity,
                sync_model_validation_criterion_results,
            )

            try:
                sync_model_validation_criterion_results(evaluation_id, session)
                assess_model_validation_toxicity(evaluation_id, session)
            except Exception:
                logger.exception(
                    "Model-validation postprocessing failed for evaluation %s"
                    " — evaluation will still complete normally.",
                    evaluation_id,
                )

        transition_evaluation_status(
            evaluation_id,
            final_status,
            session,
            error_message=partial_error,
            execution_token=execution_token,
        )
    except Exception as exc:
        session.rollback()
        if execution_acquired:
            try:
                transition_evaluation_status(
                    evaluation_id,
                    EvaluationStatus.FAILED,
                    session,
                    error_message=str(exc),
                    execution_token=execution_token,
                )
            except Exception:
                logger.exception(
                    "Failed to record FAILED transition for evaluation %s",
                    evaluation_id,
                )
        else:
            logger.warning(
                "Pre-claim failure for evaluation %s; ownership not acquired, "
                "skipping FAILED transition. Error: %s",
                evaluation_id,
                str(exc)[:500],
            )
        raise
    finally:
        session.close()


def _verify_token_ownership(
    session: object,
    evaluation_id: uuid.UUID,
    execution_token: uuid.UUID,
) -> None:
    """Raise if the runner no longer owns the evaluation job.

    This guards against stale runners (e.g. after a recovery cycle)
    doing expensive or persistent work on a job that has been re-claimed.
    """

    row = session.get(EvaluationJob, evaluation_id)  # type: ignore[attr-defined]
    if row is None or row.execution_token != execution_token:
        raise EvaluationExecutionOwnershipError(
            f"Lost ownership of evaluation {evaluation_id}"
        )


def _reconcile_coordinator_result(
    agent_results: list[AgentEvaluationResult],
    *,
    job: EvaluationJob,
    slm_chunks: list[Any],
    slm_text: str,
    session: Any,
    roadmap_context: dict[str, Any] | None = None,
) -> list[AgentEvaluationResult]:
    """Complete Coordinator's result using SME's, or fall back to
    Coordinator's own full independent scoring.

    Coordinator's ``run()`` (dispatched in parallel with SME via Supervisor,
    unchanged) only computes A-05 -- this splices in SME's other 9 scores
    now that both have finished, avoiding 5 redundant LLM calls per
    evaluation. If SME failed (or Coordinator's own call failed, or the
    merge itself raises), falls back to ``Coordinator.run_full_independent``
    so a stuck SME never takes Coordinator down with it.
    """
    sme_result = next((r for r in agent_results if r.agent_name == "sme"), None)
    coordinator_result = next(
        (r for r in agent_results if r.agent_name == "coordinator"), None
    )
    if coordinator_result is None:
        # e.g. partial_without_curriculum, which already excludes Coordinator
        # entirely -- nothing to reconcile.
        return agent_results

    if sme_result is not None and sme_result.success and coordinator_result.success:
        try:
            merged = ProgramCoordinator.merge_with_sme(
                coordinator_result,
                sme_result,
                llm_client=get_llm_client_for_agent("coordinator"),
            )
            return [
                merged if r is coordinator_result else r for r in agent_results
            ]
        except Exception as exc:
            logger.warning(
                "Coordinator/SME merge failed for evaluation %s, falling back "
                "to independent scoring: %s",
                job.evaluation_id,
                str(exc)[:200],
            )

    chunk_infos = [
        {
            "chunk_id": str(chunk.chunk_id),
            "page_number": chunk.page_number,
            "text": chunk.text,
        }
        for chunk in slm_chunks
        if getattr(chunk, "text", None)
    ]
    reference_document_ids = {
        **({"syllabus": job.syllabus_id} if job.syllabus_id else {}),
        **({"curriculum": job.curriculum_id} if job.curriculum_id else {}),
    }
    try:
        fallback_result = ProgramCoordinator().run_full_independent(
            evaluation_id=job.evaluation_id,
            document_id=job.document_id,
            chunk_infos=chunk_infos,
            context_text=slm_text,
            prompt_version_id=None,
            db=session,
            llm_client=get_llm_client_for_agent("coordinator"),
            reference_document_ids=reference_document_ids,
            roadmap_context=roadmap_context,
        )
    except Exception as exc:
        logger.warning(
            "Coordinator independent fallback also failed for evaluation "
            "%s: %s",
            job.evaluation_id,
            str(exc)[:200],
        )
        fallback_result = dataclasses.replace(
            coordinator_result,
            success=False,
            error_message=str(exc)[:500],
            criterion_scores=(),
            subtotal=0.0,
        )

    return [fallback_result if r is coordinator_result else r for r in agent_results]


def recover_interrupted_evaluation_jobs(db_session_factory: object) -> int:
    """Recover evaluation jobs stuck in non-terminal, non-SUBMITTED statuses.

    At startup, any job in PREPROCESSING, EVALUATING, or SYNTHESIZING is
    considered stuck — whether it holds a stale execution_token (classic
    crashed-runner case) or has no token at all (e.g. a crash during a
    terminal transition that cleared the token before completing). This
    helper:

      1. Finds all jobs with one of those stuck statuses (regardless of
         execution_token).
      2. Atomically resets them to clean SUBMITTED, clearing the execution
         token, timestamps, and any prior transient error_message.
      3. Sequentially re-runs each one through :func:`run_evaluation_job`,
         which is idempotent: if AgentResult rows already exist for the
         evaluation, the supervisor is skipped and the orchestrator
         resumes from synthesis/finalization.

    Terminal jobs (COMPLETED/FAILED) and clean SUBMITTED jobs are never
    touched.

    Returns the number of recovered jobs.
    """

    if db_session_factory is None:
        return 0

    session = db_session_factory()
    try:
        stuck_statuses = (
            EvaluationStatus.PREPROCESSING.value,
            EvaluationStatus.EVALUATING.value,
            EvaluationStatus.SYNTHESIZING.value,
        )
        candidate_ids = [
            row[0]
            for row in session.query(EvaluationJob.evaluation_id)
            .filter(EvaluationJob.status.in_(stuck_statuses))
            .all()
        ]
        if not candidate_ids:
            return 0

        # Unconditionally reset interrupted jobs back to a fresh,
        # queueable state and clear the stale ownership fields in a
        # single UPDATE so the next run can re-claim the job. This is
        # safe at startup because no other runner is alive yet. The
        # orchestrator's idempotency check (existing AgentResult rows)
        # prevents duplicate supervisor work if the previous attempt
        # had already persisted Layer 3 outputs.
        session.execute(
            update(EvaluationJob)
            .where(EvaluationJob.evaluation_id.in_(candidate_ids))
            .values(
                status=EvaluationStatus.SUBMITTED.value,
                execution_token=None,
                execution_started_at=None,
                execution_heartbeat_at=None,
                error_message=None,
            )
        )
        session.commit()
    finally:
        session.close()

    logger.info(
        "Recovering %d interrupted evaluation job(s): %s",
        len(candidate_ids),
        candidate_ids,
    )

    for evaluation_id in candidate_ids:
        try:
            run_evaluation_job(
                evaluation_id,
                db_session_factory=db_session_factory,
            )
        except Exception:
            logger.exception(
                "Recovery run failed for evaluation %s",
                evaluation_id,
            )

    return len(candidate_ids)


__all__ = ["run_evaluation_job", "recover_interrupted_evaluation_jobs"]
