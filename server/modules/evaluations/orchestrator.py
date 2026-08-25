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

import logging
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.coordinator.reconciliation import merge_with_sme
from server.modules.agents.runtime.llm import error_reference
from server.modules.agents.supervision.supervisor import Supervisor
from server.modules.curriculum.service import resolve_roadmap_course_context
from server.modules.documents.curriculum.service import check_curriculum_readiness
from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.documents.models import Document
from server.modules.documents.persistence import get_document_chunks
from server.modules.evaluations.exceptions import (
    EvaluationExecutionOwnershipError,
    EvaluationPipelineFailure,
    EvaluationPipelineUnavailableError,
)
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.service import (
    acquire_next_evaluation_execution,
    heartbeat_evaluation_execution,
    recover_stale_evaluation_execution,
    seconds_until_stale_evaluation_execution,
    transition_evaluation_status,
)
from server.modules.synthesis.matrix import (
    compute_synthesized_score,
    upsert_monitoring_matrix,
)
from server.modules.synthesis.models import AgentResult, EvaluationFlag
from server.modules.synthesis.service import persist_agent_outputs

logger = logging.getLogger(__name__)
_DRAIN_LOCK = threading.Lock()


def _safe_failure(exc: BaseException) -> tuple[str, str]:
    """Return bounded, non-sensitive failure attribution."""
    return type(exc).__name__[:64], error_reference(exc)


def _persist_layer3_and_transition(
    session: Any,
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
    results: list[AgentEvaluationResult],
    execution_token: uuid.UUID,
) -> None:
    """Atomically persist Layer 3 outputs and enter synthesis."""
    try:
        _verify_token_ownership(
            session, evaluation_id, execution_token, for_update=True
        )
        persist_agent_outputs(
            session,
            evaluation_id,
            document_id,
            results,
            verify_ownership=lambda db: _verify_token_ownership(
                db, evaluation_id, execution_token
            ),
            commit=False,
        )
        transition_evaluation_status(
            evaluation_id,
            EvaluationStatus.SYNTHESIZING,
            session,
            execution_token=execution_token,
            expected_status=EvaluationStatus.EVALUATING,
            commit=False,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise


def _execute_claimed_evaluation(
    evaluation_id: uuid.UUID,
    execution_token: uuid.UUID,
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

    execution_acquired = False
    session = db_session_factory()
    try:
        job = session.get(EvaluationJob, evaluation_id)
        if job is None:
            raise EvaluationPipelineUnavailableError("Evaluation job not found.")

        # The drainer is the only production claimant. This seam may execute
        # only a lease that was already issued by the admission service.
        acquired = bool(
            job.execution_token == execution_token
            and job.admission_slot == 1
            and job.status == EvaluationStatus.PREPROCESSING.value
        )
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

        if not job.partial_without_curriculum:
            if job.curriculum_id is None:
                raise EvaluationPipelineUnavailableError(
                    "Full evaluation requires an authoritative curriculum."
                )
            curriculum_readiness = check_curriculum_readiness(
                job.curriculum_id,
                job.confirmed_program,
                session,
            )
            if not curriculum_readiness.is_ready:
                raise EvaluationPipelineUnavailableError(
                    "Curriculum is not ready for evaluation: "
                    f"{curriculum_readiness.reason}"
                )
            curriculum_available = True
        else:
            curriculum_available = False

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
            if job.partial_without_curriculum:
                from server.modules.agents.gad.agent import GAD
                from server.modules.agents.itso.agent import ITSO
                from server.modules.agents.sme.agent import SME

                supervisor = Supervisor(agents=[SME(), GAD(), ITSO()], db=session)
            else:
                # A full-intent run must attempt Coordinator even when its
                # curriculum is unavailable; its absence is a terminal
                # lifecycle failure, not an implicit partial evaluation.
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

            def owner_heartbeat() -> None:
                if not heartbeat_evaluation_execution(
                    session, evaluation_id, execution_token
                ):
                    raise EvaluationExecutionOwnershipError("Lost evaluation ownership")

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
                    "confirmed_program": job.confirmed_program,
                },
                heartbeat_callback=owner_heartbeat,
            )
            if not supervisor_result.agent_results:
                raise EvaluationPipelineUnavailableError(
                    "Layer 3 produced no usable agent outputs."
                )
            # Coordinator's parallel run computes only A-05. Reconciliation
            # purely merges that successful result with SME's other scores;
            # it never performs a fallback or second agent pass.
            supervisor_result.agent_results = _reconcile_coordinator_result(
                supervisor_result.agent_results
            )
            _verify_token_ownership(session, evaluation_id, execution_token)
            # Heartbeat after all agent futures complete.
            heartbeat_evaluation_execution(session, evaluation_id, execution_token)
            _persist_layer3_and_transition(
                session,
                evaluation_id,
                job.document_id,
                supervisor_result.agent_results,
                execution_token,
            )
        else:
            logger.info(
                "Resuming evaluation %s: %d AgentResult row(s) already present; "
                "skipping supervisor.",
                evaluation_id,
                existing_results,
            )

        _verify_token_ownership(session, evaluation_id, execution_token)
        if existing_results:
            transition_evaluation_status(
                evaluation_id,
                EvaluationStatus.SYNTHESIZING,
                session,
                execution_token=execution_token,
                expected_status=EvaluationStatus.EVALUATING,
                commit=True,
            )

        agent_results = (
            session.query(AgentResult).filter_by(evaluation_id=evaluation_id).all()
        )
        if not job.partial_without_curriculum:
            final_readiness = (
                check_curriculum_readiness(
                    job.curriculum_id,
                    job.confirmed_program,
                    session,
                )
                if job.curriculum_id is not None
                else None
            )
            curriculum_available = (
                final_readiness.is_ready if final_readiness is not None else False
            )
        else:
            curriculum_available = False

        validation_error = _validate_required_agent_results(
            agent_results,
            partial_without_curriculum=job.partial_without_curriculum,
            curriculum_available=curriculum_available,
        )
        synthesis_result = compute_synthesized_score(
            agent_results,
            force_partial=job.partial_without_curriculum,
            partial_reason=job.partial_reason,
        )
        flag_count = (
            session.query(EvaluationFlag).filter_by(evaluation_id=evaluation_id).count()
        )

        if validation_error is not None:
            final_status = EvaluationStatus.FAILED
            matrix_status = "FAILED"
            partial_error = validation_error
        else:
            final_status = EvaluationStatus.COMPLETED
            matrix_status = (
                "COMPLETED_PARTIAL" if job.partial_without_curriculum else "COMPLETED"
            )
            partial_error = None

        upsert_monitoring_matrix(
            db=session,
            document_id=job.document_id,
            evaluation_id=evaluation_id,
            evaluation_status=matrix_status,
            synthesized_score=synthesis_result["synthesized_score"],
            domain_scores=synthesis_result["domain_scores"],
            flag_count=flag_count,
        )

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
            except Exception as exc:
                category, reference = _safe_failure(exc)
                logger.warning(
                    "Model-validation postprocessing failed for evaluation %s"
                    " — evaluation will still complete normally: category=%s "
                    "reference=%s",
                    evaluation_id,
                    category,
                    reference,
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
        category, reference = _safe_failure(exc)
        if execution_acquired:
            try:
                job_row = session.get(EvaluationJob, evaluation_id)
                if job_row is not None:
                    upsert_monitoring_matrix(
                        db=session,
                        document_id=job_row.document_id,
                        evaluation_id=evaluation_id,
                        evaluation_status="FAILED",
                    )
                transition_evaluation_status(
                    evaluation_id,
                    EvaluationStatus.FAILED,
                    session,
                    error_message=f"{category} (reference: {reference})",
                    execution_token=execution_token,
                )
            except Exception as transition_exc:
                transition_category, transition_reference = _safe_failure(
                    transition_exc
                )
                logger.error(
                    "Failed to record FAILED transition for evaluation %s: "
                    "category=%s reference=%s",
                    evaluation_id,
                    transition_category,
                    transition_reference,
                )
        else:
            logger.warning(
                "Pre-claim failure for evaluation %s; ownership not acquired, "
                "skipping FAILED transition. category=%s reference=%s",
                evaluation_id,
                *_safe_failure(exc),
            )
        raise EvaluationPipelineFailure(
            f"EvaluationPipelineFailure (category={category}, reference={reference})"
        ) from None
    finally:
        session.close()


def _validate_required_agent_results(
    agent_results: list[AgentResult],
    *,
    partial_without_curriculum: bool,
    curriculum_available: bool,
) -> str | None:
    """Validate the execution contract before accepting synthesized output."""
    required = {"sme", "gad", "itso"}
    if not partial_without_curriculum:
        required.add("coordinator")
        if not curriculum_available:
            return "Full evaluation requires an authoritative curriculum."

    by_name = {result.agent_name: result for result in agent_results}
    missing = sorted(required - by_name.keys())
    if missing:
        return f"Required agent result missing: {', '.join(missing)}."
    failed = sorted(name for name in required if not by_name[name].success)
    if failed:
        return f"Required agent failed: {', '.join(failed)}."
    return None


def _verify_token_ownership(
    session: object,
    evaluation_id: uuid.UUID,
    execution_token: uuid.UUID,
    *,
    for_update: bool = False,
) -> None:
    """Raise if the runner no longer owns the evaluation job.

    This guards against stale runners (e.g. after a recovery cycle)
    doing expensive or persistent work on a job that has been re-claimed.
    """

    from sqlalchemy import select

    query = select(EvaluationJob).where(EvaluationJob.evaluation_id == evaluation_id)
    if for_update and session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.execute(query).scalar_one_or_none()
    if row is None or row.execution_token != execution_token:
        raise EvaluationExecutionOwnershipError(
            f"Lost ownership of evaluation {evaluation_id}"
        )


def _reconcile_coordinator_result(
    agent_results: list[AgentEvaluationResult],
) -> list[AgentEvaluationResult]:
    """Reconcile Coordinator's A-05 result with SME's complete scores."""
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
            merged = merge_with_sme(
                coordinator_result,
                sme_result,
            )
            return [merged if r is coordinator_result else r for r in agent_results]
        except Exception as exc:
            category, reference = _safe_failure(exc)
            failed = AgentEvaluationResult(
                agent_name="coordinator",
                evaluation_id=coordinator_result.evaluation_id,
                document_id=coordinator_result.document_id,
                subtotal=0.0,
                criterion_scores=(),
                summary="",
                model_name=coordinator_result.model_name,
                processing_seconds=coordinator_result.processing_seconds,
                token_count=0,
                success=False,
                error_message=f"{category} (reference: {reference})",
                prompt_version_id=None,
                raw_response=None,
                metadata={},
                provenance=None,
                advisory_outputs=None,
            )
            return [failed if r is coordinator_result else r for r in agent_results]
    reason = "CoordinatorFailure"
    if sme_result is None:
        reason = "SMEResultMissing"
    elif not sme_result.success:
        reason = "SMEFailure"
    elif not coordinator_result.success:
        reason = "CoordinatorFailure"
    reference = error_reference(RuntimeError(reason))
    failed = AgentEvaluationResult(
        agent_name="coordinator",
        evaluation_id=coordinator_result.evaluation_id,
        document_id=coordinator_result.document_id,
        subtotal=0.0,
        criterion_scores=(),
        summary="",
        model_name=coordinator_result.model_name[:128],
        processing_seconds=coordinator_result.processing_seconds,
        token_count=0,
        success=False,
        error_message=f"{reason} (reference: {reference})",
        prompt_version_id=None,
        raw_response=None,
        metadata={},
        provenance=None,
        advisory_outputs=None,
    )
    return [failed if r is coordinator_result else r for r in agent_results]


def recover_interrupted_evaluation_jobs(db_session_factory: object) -> int:
    """Requeue stale or tokenless nonterminal evaluation jobs.

    At startup, any job in PREPROCESSING, EVALUATING, or SYNTHESIZING is
    considered stuck — whether it holds a stale execution_token (classic
    crashed-runner case) or has no token at all (e.g. a crash during a
    terminal transition that cleared the token before completing). This
    helper:

      1. Finds all jobs with one of those stuck statuses (regardless of
         execution_token).
      2. Atomically resets them to clean SUBMITTED, clearing the execution
         token, timestamps, and any prior transient error_message.
      3. Sequentially re-runs each one through the claimed executor,
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
        from server.core.config import get_settings

        cutoff = datetime.now(UTC) - timedelta(
            seconds=get_settings().evaluation_heartbeat_stale_seconds
        )
        candidate_ids, recovered_count = recover_stale_evaluation_execution(
            session, cutoff
        )
    finally:
        session.close()

    logger.info(
        "Recovering %d interrupted evaluation job(s): %s",
        recovered_count,
        candidate_ids,
    )

    return recovered_count


__all__ = [
    "_execute_claimed_evaluation",
    "recover_interrupted_evaluation_jobs",
    "drain_evaluation_queue",
]


def drain_evaluation_queue(
    db_session_factory=None, *, stop_event: threading.Event | None = None
) -> None:
    """Drain the single local admission slot; DB ownership is authoritative."""
    if not _DRAIN_LOCK.acquire(blocking=False):
        return
    try:
        if db_session_factory is None:
            from server.core.database import get_session_factory

            db_session_factory = get_session_factory()
        while True:
            if stop_event is not None and stop_event.is_set():
                return
            token = uuid.uuid4()
            session = db_session_factory()
            try:
                evaluation_id = acquire_next_evaluation_execution(session, token)
            except Exception as exc:
                session.rollback()
                category, reference = _safe_failure(exc)
                logger.warning(
                    "Evaluation queue claim failed: category=%s reference=%s",
                    category,
                    reference,
                )
                return
            finally:
                session.close()
            if evaluation_id is None:
                from server.core.config import get_settings

                lease_session = db_session_factory()
                try:
                    try:
                        wait_seconds = seconds_until_stale_evaluation_execution(
                            lease_session,
                            get_settings().evaluation_heartbeat_stale_seconds,
                        )
                    except Exception as exc:
                        category, reference = _safe_failure(exc)
                        logger.warning(
                            "Evaluation lease inspection failed: category=%s "
                            "reference=%s",
                            category,
                            reference,
                        )
                        return
                finally:
                    lease_session.close()
                if wait_seconds is None:
                    return
                if stop_event is not None:
                    if stop_event.wait(timeout=min(wait_seconds, 1.0)):
                        return
                elif wait_seconds > 0:
                    time.sleep(min(wait_seconds, 1.0))
                recovery_session = db_session_factory()
                try:
                    cutoff = datetime.now(UTC) - timedelta(
                        seconds=get_settings().evaluation_heartbeat_stale_seconds
                    )
                    recover_stale_evaluation_execution(recovery_session, cutoff)
                finally:
                    recovery_session.close()
                continue
            try:
                _execute_claimed_evaluation(
                    evaluation_id,
                    db_session_factory=db_session_factory,
                    execution_token=token,
                )
            except Exception as exc:
                category, reference = _safe_failure(exc)
                logger.warning(
                    "Evaluation drain failed: category=%s reference=%s",
                    category,
                    reference,
                )
            if stop_event is not None and stop_event.is_set():
                return
    finally:
        _DRAIN_LOCK.release()


def is_evaluation_admission_schema_ready(session_factory) -> bool:
    from server.modules.evaluations.service import admission_schema_ready

    session = session_factory()
    try:
        return admission_schema_ready(session)
    finally:
        session.close()
