"""Execution controls reject invalid dependencies and cancellation before success."""

import pytest
from equiped_harness import ExecutionConfig, ExecutionControl, evaluate
from equiped_harness.runtime.control import ExecutionCancelledError
from test_evaluate import FakeClient, prepared_request


def test_cancellation_during_final_model_call_does_not_return_success():
    request, payloads = prepared_request("sme")
    control = ExecutionControl()

    class CancellingClient(FakeClient):
        def generate_result(self, *args, **kwargs):
            result = super().generate_result(*args, **kwargs)
            control.cancel()
            return result

    client = CancellingClient(payloads)
    with pytest.raises(ExecutionCancelledError):
        evaluate(request, client, ExecutionConfig(), control=control)
    assert len(client.calls) == 1


@pytest.mark.parametrize("kwargs", [{"tools": object()}, {"control": object()}])
def test_invalid_execution_dependencies_fail_before_model(kwargs):
    request, payloads = prepared_request("sme")
    client = FakeClient(payloads)
    with pytest.raises(TypeError):
        evaluate(request, client, ExecutionConfig(), **kwargs)
    assert client.calls == []
