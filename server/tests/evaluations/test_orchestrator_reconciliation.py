"""Tests for the no-fallback Coordinator reconciliation contract."""

from __future__ import annotations

import re
import uuid
from dataclasses import replace

import pytest
import server.modules.evaluations.orchestrator as orchestrator
from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.sme import registry
from server.modules.evaluations.orchestrator import _reconcile_coordinator_result


def _result(agent: str, *, success: bool = True) -> AgentEvaluationResult:
    scores = tuple(
        CriterionScore(code, f"{code} title", 3, f"{code} justification", ())
        for code in sorted(registry.REGISTERED_CODES)
    )
    if agent == "coordinator":
        scores = (
            CriterionScore("A-05", "A-05 title", 4, "curriculum evidence", ("quote",)),
        )
    return AgentEvaluationResult(
        agent_name=agent,
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        subtotal=3.0 if success else 0.0,
        criterion_scores=scores if success else (),
        summary="",
        model_name=f"{agent}-model",
        processing_seconds=1.0,
        token_count=10,
        success=success,
        error_message=None if success else f"{agent} failed",
    )


def test_success_merges_canonical_ten_criteria() -> None:
    results = [_result("sme"), _result("coordinator"), _result("gad"), _result("itso")]
    reconciled = _reconcile_coordinator_result(results)
    coordinator = next(r for r in reconciled if r.agent_name == "coordinator")
    assert tuple(r.criterion_id for r in coordinator.criterion_scores) == tuple(
        sorted(registry.REGISTERED_CODES)
    )
    assert next(r for r in reconciled if r.agent_name == "sme") is results[0]


def test_missing_coordinator_returns_explicit_partial_unchanged() -> None:
    results = [_result("sme"), _result("gad"), _result("itso")]
    assert _reconcile_coordinator_result(results) is results


@pytest.mark.parametrize("failed_agent", ["sme", "coordinator"])
def test_agent_failure_produces_sanitized_failed_coordinator_without_fallback(
    failed_agent: str, monkeypatch, caplog
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("independent/global LLM fallback must not run")

    monkeypatch.setattr(
        orchestrator, "get_llm_client_for_agent", forbidden, raising=False
    )
    secret = "provider-secret-should-not-leak"
    results = [
        _result("sme", success=failed_agent != "sme"),
        _result("coordinator", success=failed_agent != "coordinator"),
    ]
    results[0] = replace(results[0], error_message=secret)
    reconciled = _reconcile_coordinator_result(results)
    coordinator = next(r for r in reconciled if r.agent_name == "coordinator")
    assert not coordinator.success
    assert coordinator.criterion_scores == ()
    assert coordinator.model_name == "coordinator-model"
    assert len(coordinator.error_message or "") < 256
    assert secret not in (coordinator.error_message or "")
    assert secret not in caplog.text


def test_merge_exception_is_sanitized_failed_coordinator_without_fallback(
    monkeypatch,
) -> None:
    secret = "merge-provider-secret"

    def broken_merge(*args):
        raise RuntimeError(secret)

    monkeypatch.setattr(orchestrator, "merge_with_sme", broken_merge)
    results = [_result("sme"), _result("coordinator")]
    reconciled = _reconcile_coordinator_result(results)
    coordinator = next(r for r in reconciled if r.agent_name == "coordinator")
    assert not coordinator.success
    assert secret not in (coordinator.error_message or "")
    assert re.search(r"reference: [0-9a-f]{16}", coordinator.error_message or "")
    assert coordinator.raw_response is None
    assert coordinator.metadata == {}
    assert coordinator.provenance is None
    assert coordinator.model_name == "coordinator-model"


def test_failure_is_bounded_and_remains_required_job_failure() -> None:
    result = next(
        r
        for r in _reconcile_coordinator_result(
            [_result("sme", success=False), _result("coordinator")]
        )
        if r.agent_name == "coordinator"
    )
    assert result.success is False
    assert result.agent_name == "coordinator"
    assert result.model_name == "coordinator-model"
    assert result.token_count == 0
    assert result.subtotal == 0.0
