import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from equiped_harness import ExecutionConfig, ToolConfig, evaluate
from equiped_harness.agents.itso.tools.contracts import Code, VerificationError
from equiped_harness.agents.itso.tools.reference_search import (
    ReferenceToolsUnavailable,
    build_public_reference_report,
    extract_bibliography,
)
from equiped_harness.contracts.snapshots import SnapshotIntegrityError
from equiped_harness.tools.http import Response
from test_evaluate import prepared_request


class ScriptedTransport:
    def __init__(self):
        self.requests = []

    async def get(self, request, deadline):
        self.requests.append(request)
        return Response(503, {}, b"")


class UnusedModel:
    model = "unused"

    def generate_result(self, *args, **kwargs):
        raise AssertionError("model must not run")


def adapter3_request(**kwargs):
    request, _ = prepared_request("itso")
    return replace(
        request,
        context_text="References:\nSmith, J. (2020). Privacy Engineering.",
        **kwargs,
    )


def test_bibliography_extraction_stops_at_section_boundary():
    items = extract_bibliography(
        "Learning Objectives:\nProtect data.\nReferences:\n"
        "Smith, J. (2020). Privacy Engineering.\nAssessment:\nPrivate learner notes."
    )

    assert len(items) == 1
    assert items[0].reference.title == "Privacy Engineering"
    assert "Private learner notes" not in items[0].query


def test_search_requires_explicit_enabled_config_and_transport():
    with pytest.raises(ReferenceToolsUnavailable) as error:
        asyncio.run(
            build_public_reference_report(
                "References:\nSmith, J. (2020). Privacy Engineering.",
                enabled=True,
            )
        )

    assert error.value.code == Code.DISABLED


def test_public_search_uses_injected_transport_and_preserves_error_code():
    transport = ScriptedTransport()

    with pytest.raises(VerificationError) as error:
        asyncio.run(
            build_public_reference_report(
                "References:\nSmith, J. (2020). Privacy Engineering.",
                enabled=True,
                settings=type("EnabledTools", (), {"enabled": True})(),
                transport=transport,
            )
        )

    assert error.value.code == Code.HTTP
    assert transport.requests[0].kind == "duckduckgo"


def test_public_evaluate_requires_tools_even_with_precomputed_report():
    request = adapter3_request(
        precomputed_context={"public_reference_verification": ["client report"]}
    )

    with pytest.raises(ValueError, match="requires enabled public-reference tools"):
        evaluate(request, UnusedModel(), ExecutionConfig())


def test_public_evaluate_rejects_disabled_tool_authorization_before_io():
    request = adapter3_request()
    transport = ScriptedTransport()
    tools = ToolConfig(enabled=False, transport=transport)

    with pytest.raises(ValueError, match="requires enabled public-reference tools"):
        evaluate(request, UnusedModel(), ExecutionConfig(), tools=tools)

    assert transport.requests == []


@pytest.mark.parametrize("enabled", [None, "false", 0])
def test_tool_config_rejects_non_boolean_authorization(enabled):
    with pytest.raises(TypeError, match="enabled must be bool"):
        ToolConfig(enabled=enabled, transport=ScriptedTransport())


def test_public_evaluate_replaces_client_report_before_model(monkeypatch):
    transport = ScriptedTransport()
    request = adapter3_request(
        precomputed_context={"public_reference_verification": ["client report"]}
    )

    with pytest.raises(VerificationError) as error:
        evaluate(
            request,
            UnusedModel(),
            ExecutionConfig(),
            tools=ToolConfig(enabled=True, transport=transport),
        )

    assert error.value.code == Code.HTTP
    assert transport.requests[0].kind == "duckduckgo"


@pytest.mark.parametrize("corruption", ["binding", "hash", "manifest_metadata"])
def test_public_evaluate_preflights_snapshot_before_public_search(corruption):
    request = adapter3_request()
    if corruption == "binding":
        request = replace(request, evaluation_id=uuid4())
    elif corruption == "hash":
        snapshot = request.form_snapshot.model_copy(update={"snapshot_hash": "0" * 64})
        request = replace(request, form_snapshot=snapshot)
    else:
        snapshot = request.form_snapshot.model_copy(update={"adapter_version": 99})
        request = replace(request, form_snapshot=snapshot)
    transport = ScriptedTransport()

    with pytest.raises(SnapshotIntegrityError):
        evaluate(
            request,
            UnusedModel(),
            ExecutionConfig(),
            tools=ToolConfig(enabled=True, transport=transport),
        )

    assert transport.requests == []
