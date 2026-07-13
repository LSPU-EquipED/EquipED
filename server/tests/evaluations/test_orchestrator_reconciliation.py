"""Tests for orchestrator._reconcile_coordinator_result.

Coordinator's own run() (dispatched in parallel with SME by Supervisor,
unchanged) only computes A-05 -- this reconciliation step, run after both
agents finish, either splices in SME's other 9 scores or falls back to
Coordinator's full independent scoring if SME failed. Supervisor itself is
never touched by this design -- these tests exercise the reconciliation
function in isolation, with no real DB/LLM required.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.coordinator import Coordinator, ProgramCoordinator
from server.modules.agents.scoring import registry
from server.modules.evaluations.orchestrator import _reconcile_coordinator_result


def _fake_job(*, syllabus_id=None, curriculum_id=None) -> SimpleNamespace:
    return SimpleNamespace(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        syllabus_id=syllabus_id,
        curriculum_id=curriculum_id,
    )


def _fake_chunk(text: str, page_number: int = 1):
    return SimpleNamespace(chunk_id=uuid.uuid4(), page_number=page_number, text=text)


def _sme_result(*, success=True) -> AgentEvaluationResult:
    scores = tuple(
        CriterionScore(
            criterion_id=code,
            criterion_title=f"{code} SME Title",
            score=3,
            justification=f"{code} sme justification",
            evidence=(),
        )
        for code in sorted(registry.REGISTERED_CODES)
    )
    return AgentEvaluationResult(
        agent_name="sme",
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        subtotal=3.0,
        criterion_scores=scores if success else (),
        summary="",
        model_name="sme-model",
        processing_seconds=1.0,
        token_count=100,
        success=success,
        error_message=None if success else "sme failed",
    )


def _coordinator_result(*, success=True) -> AgentEvaluationResult:
    a05 = CriterionScore(
        criterion_id="A-05",
        criterion_title="A-05 Coordinator Title",
        score=4,
        justification="Curriculum-grounded: 1/1 objective(s) addressed.",
        evidence=("curriculum quote",),
    )
    return AgentEvaluationResult(
        agent_name="coordinator",
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        subtotal=4.0,
        criterion_scores=(a05,) if success else (),
        summary="",
        model_name="coord-model",
        processing_seconds=0.2,
        token_count=20,
        success=success,
        error_message=None if success else "coordinator failed",
    )


def _gad_itso_results() -> list[AgentEvaluationResult]:
    return [
        AgentEvaluationResult(
            agent_name=name,
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            subtotal=3.0,
            criterion_scores=(),
            summary="",
            model_name="m",
            processing_seconds=0.1,
            token_count=10,
            success=True,
        )
        for name in ("gad", "itso")
    ]


class TestReconcileHappyPath:
    def test_merges_when_both_sme_and_coordinator_succeed(self) -> None:
        sme_result = _sme_result()
        coordinator_result = _coordinator_result()
        agent_results = [sme_result, coordinator_result, *_gad_itso_results()]

        reconciled = _reconcile_coordinator_result(
            agent_results,
            job=_fake_job(curriculum_id=uuid.uuid4()),
            slm_chunks=[_fake_chunk("one")],
            slm_text="one",
            session=None,
        )

        merged_coordinator = next(
            r for r in reconciled if r.agent_name == "coordinator"
        )
        assert len(merged_coordinator.criterion_scores) == 10
        assert merged_coordinator is not coordinator_result
        # SME's own entry and the other agents pass through untouched.
        assert next(r for r in reconciled if r.agent_name == "sme") is sme_result
        assert len(reconciled) == 4


class TestReconcileNoCoordinator:
    def test_returns_unchanged_when_no_coordinator_present(self) -> None:
        # e.g. partial_without_curriculum -- Supervisor never included Coordinator.
        agent_results = [_sme_result(), *_gad_itso_results()]

        reconciled = _reconcile_coordinator_result(
            agent_results,
            job=_fake_job(),
            slm_chunks=[_fake_chunk("one")],
            slm_text="one",
            session=None,
        )

        assert reconciled is agent_results


class TestReconcileFallback:
    def test_sme_failure_triggers_independent_fallback(self, monkeypatch) -> None:
        sme_result = _sme_result(success=False)
        coordinator_result = _coordinator_result()
        agent_results = [sme_result, coordinator_result, *_gad_itso_results()]

        fallback_result = AgentEvaluationResult(
            agent_name="coordinator",
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            subtotal=3.0,
            criterion_scores=tuple(
                CriterionScore(
                    criterion_id=code,
                    criterion_title=code,
                    score=3,
                    justification="independent",
                    evidence=(),
                )
                for code in sorted(registry.REGISTERED_CODES)
            ),
            summary="",
            model_name="coord-model",
            processing_seconds=5.0,
            token_count=500,
            success=True,
        )

        captured_kwargs = {}

        def fake_run_full_independent(self, **kwargs):
            captured_kwargs.update(kwargs)
            return fallback_result

        monkeypatch.setattr(
            Coordinator, "run_full_independent", fake_run_full_independent
        )
        monkeypatch.setattr(
            "server.modules.evaluations.orchestrator.get_llm_client_for_agent",
            lambda agent_name: "fake-client",
        )

        job = _fake_job(curriculum_id=uuid.uuid4())
        reconciled = _reconcile_coordinator_result(
            agent_results,
            job=job,
            slm_chunks=[_fake_chunk("one")],
            slm_text="one",
            session="fake-session",
        )

        result = next(r for r in reconciled if r.agent_name == "coordinator")
        assert result is fallback_result
        assert len(result.criterion_scores) == 10
        assert captured_kwargs["evaluation_id"] == job.evaluation_id
        assert captured_kwargs["document_id"] == job.document_id
        assert captured_kwargs["db"] == "fake-session"
        assert captured_kwargs["reference_document_ids"] == {
            "curriculum": job.curriculum_id
        }

    def test_coordinators_own_call_failure_triggers_independent_fallback(
        self, monkeypatch
    ) -> None:
        sme_result = _sme_result(success=True)
        coordinator_result = _coordinator_result(success=False)
        agent_results = [sme_result, coordinator_result]

        fallback_result = _coordinator_result(success=True)
        monkeypatch.setattr(
            Coordinator,
            "run_full_independent",
            lambda self, **kwargs: fallback_result,
        )
        monkeypatch.setattr(
            "server.modules.evaluations.orchestrator.get_llm_client_for_agent",
            lambda agent_name: "fake-client",
        )

        reconciled = _reconcile_coordinator_result(
            agent_results,
            job=_fake_job(),
            slm_chunks=[_fake_chunk("one")],
            slm_text="one",
            session=None,
        )

        result = next(r for r in reconciled if r.agent_name == "coordinator")
        assert result is fallback_result

    def test_fallback_itself_failing_marks_coordinator_failed_not_crash(
        self, monkeypatch
    ) -> None:
        sme_result = _sme_result(success=False)
        coordinator_result = _coordinator_result()
        agent_results = [sme_result, coordinator_result]

        def raise_error(self, **kwargs):
            raise RuntimeError("llm unavailable")

        monkeypatch.setattr(Coordinator, "run_full_independent", raise_error)
        monkeypatch.setattr(
            "server.modules.evaluations.orchestrator.get_llm_client_for_agent",
            lambda agent_name: "fake-client",
        )

        reconciled = _reconcile_coordinator_result(
            agent_results,
            job=_fake_job(),
            slm_chunks=[_fake_chunk("one")],
            slm_text="one",
            session=None,
        )

        result = next(r for r in reconciled if r.agent_name == "coordinator")
        assert result.success is False
        assert "llm unavailable" in result.error_message

    def test_merge_raising_also_triggers_fallback(self, monkeypatch) -> None:
        # Both agents report success, but merge_with_sme itself misbehaves --
        # reconciliation must not propagate that, it should fall back too.
        sme_result = _sme_result(success=True)
        coordinator_result = _coordinator_result(success=True)
        agent_results = [sme_result, coordinator_result]

        def raise_merge_error(coordinator_result, sme_result):
            raise ValueError("merge exploded")

        fallback_result = _coordinator_result(success=True)
        monkeypatch.setattr(
            ProgramCoordinator, "merge_with_sme", staticmethod(raise_merge_error)
        )
        monkeypatch.setattr(
            Coordinator,
            "run_full_independent",
            lambda self, **kwargs: fallback_result,
        )
        monkeypatch.setattr(
            "server.modules.evaluations.orchestrator.get_llm_client_for_agent",
            lambda agent_name: "fake-client",
        )

        reconciled = _reconcile_coordinator_result(
            agent_results,
            job=_fake_job(),
            slm_chunks=[_fake_chunk("one")],
            slm_text="one",
            session=None,
        )

        result = next(r for r in reconciled if r.agent_name == "coordinator")
        assert result is fallback_result
