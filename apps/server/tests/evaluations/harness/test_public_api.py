"""Evaluation integration exposes supervision and explicit DB envelope helpers."""

import pytest

import server.modules.evaluations.runner as integration
from server.modules.evaluations.runner import Supervisor


def test_backend_public_api_is_evaluation_integration():
    assert integration.__all__ == [
        "Supervisor",
        "SupervisorResult",
    ]
    assert Supervisor.__module__ == "server.modules.evaluations.runner"
    assert integration.Supervisor is Supervisor
    from server.modules.rubrics import envelopes

    assert callable(envelopes.get_envelope_criteria_map)
    assert callable(envelopes.get_criterion_envelope_key)
    assert "envelope_criteria_map_from_snapshot" not in envelopes.__all__
    assert "__getattr__" not in vars(integration)
    for removed in ("SME", "Coordinator", "GAD", "ITSO", "AgentEvaluationResult"):
        with pytest.raises(AttributeError):
            getattr(integration, removed)


def test_rubrics_public_api_retains_backend_ownership_only():
    import server.modules.rubrics as rubrics

    assert "RubricSet" in rubrics.__all__
    assert "persist_evaluation_form_snapshots" in rubrics.__all__
    assert "lock_and_load_requested_active_forms" in rubrics.__all__
    for name in ("FormDefinition", "get_agent_manifest", "compute_snapshot_hash"):
        assert name not in rubrics.__all__
        assert not hasattr(rubrics, name)


def test_harness_public_api_exposes_actual_pipelines():
    import equiped_harness as harness

    assert callable(harness.evaluate)
    assert harness.EvaluationRequest.__dataclass_params__.frozen
    assert harness.ExecutionConfig.__dataclass_params__.frozen
    expected_modules = {
        "SME": "equiped_harness.agents.sme.agent",
        "Coordinator": "equiped_harness.agents.coordinator.agent",
        "GAD": "equiped_harness.agents.gad.agent",
        "ITSO": "equiped_harness.agents.itso.agent",
    }
    for name, module in expected_modules.items():
        assert name in harness.__all__
        assert getattr(harness, name).__module__ == module
