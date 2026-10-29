"""Regression checks for retired Coordinator execution adapters."""

from __future__ import annotations

import runpy
from dataclasses import fields, replace
from pathlib import Path

import pytest
from equiped_harness import ExecutionConfig, evaluate
from equiped_harness.agents.coordinator.agent import Coordinator
from equiped_harness.contracts.snapshots import build_evaluation_form_snapshot
from equiped_harness.exceptions import AgentExecutionError
from test_coordinator_helpers import request


class NoCallClient:
    model = "must-not-run"

    def __init__(self):
        self.calls = 0

    def generate_result(self, prompt, **kwargs):
        self.calls += 1
        raise AssertionError("retired snapshot reached the model")


@pytest.mark.parametrize("version", [1, 2, 3])
def test_retired_adapters_fail_before_direct_agent_model_call(version):
    current = request()
    old_form = current.form_snapshot.form.model_copy(
        update={"adapter_version": version}
    )
    snapshot = build_evaluation_form_snapshot(current.evaluation_id, old_form)
    retired = replace(current, form_snapshot=snapshot)
    client = NoCallClient()
    with pytest.raises(AgentExecutionError, match="adapter 4 only"):
        Coordinator().run(
            **{field.name: getattr(retired, field.name) for field in fields(retired)},
            llm_client=client,
        )
    assert client.calls == 0


def test_real_frozen_v3_snapshot_remains_readable_but_cannot_execute():
    fixture_path = Path(__file__).resolve().parent / "historical_fixture.py"
    fixture = runpy.run_path(str(fixture_path))
    snapshot, _ = fixture["load_historical_fixture"](3)
    client = NoCallClient()
    with pytest.raises(AgentExecutionError):
        evaluate(
            replace(
                request(),
                evaluation_id=snapshot.evaluation_id,
                form_snapshot=snapshot,
            ),
            client,
            ExecutionConfig(),
        )
    assert client.calls == 0
