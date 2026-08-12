"""Characterization tests for the hardened SME extraction boundary.

These tests intentionally describe the contract at the SME seam; production
code is not patched by this file.
"""

from __future__ import annotations

import json
import uuid

import pytest
from server.core.llm import ResponseContract
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.sme import extraction, registry
from server.modules.agents.sme.agent import SME
from server.tests.agents.helpers import _ALL_BASKETS_IN_ORDER, SequencedFakeClient

PREAMBLE = "MANAGED SME PREAMBLE -- causal-test"
PROMPT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


class RecordingClient(SequencedFakeClient):
    def __init__(self, responses):
        super().__init__(responses)
        self.prompts: list[str] = []
        self.contracts: list[ResponseContract] = []

    def generate(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        self.contracts.append(kwargs["response_contract"])
        return super().generate(prompt, **kwargs)


def test_managed_preamble_is_consumed_by_all_six_baskets(monkeypatch):
    client = RecordingClient(list(_ALL_BASKETS_IN_ORDER))
    for name, *_ in registry._BASKETS:
        getattr(extraction, f"extract_basket_{name.lower()}")(
            client, "canonical text", prompt_preamble=PREAMBLE
        )
    assert len(client.prompts) == 6
    assert all(prompt.startswith(PREAMBLE + "\n\n") for prompt in client.prompts)


def test_managed_preamble_is_consumed_by_criterion_fallback(monkeypatch):
    calls = []

    class Client:
        primary_client = None

        def generate(self, prompt, **kwargs):
            calls.append((prompt, kwargs["response_contract"]))
            return json.dumps({"mechanisms": []})

    registry.run_criterion("A-03", Client(), "canonical text", prompt_preamble=PREAMBLE)
    assert calls and calls[0][0].startswith(PREAMBLE + "\n\n")


def test_managed_prompt_id_is_causal_and_absent_without_text(monkeypatch):
    managed = type("Managed", (), {"prompt_text": PREAMBLE, "version_id": PROMPT_ID})()
    monkeypatch.setattr(
        "server.modules.agents.sme.agent.get_active_prompt", lambda *_: managed
    )
    # The real path must pass the managed text into scoring and return its ID.
    captured = {}

    def fake_run(self, **kwargs):
        captured.update(kwargs)
        return AgentEvaluationResult(
            "sme",
            kwargs["evaluation_id"],
            kwargs["document_id"],
            0,
            (),
            "",
            "model",
            0,
            0,
        )

    monkeypatch.setattr(SME, "_run_full_engine_scoring", fake_run)
    result = SME().run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=[{"x": 1}],
        canonical_source_text="text",
        db=object(),
    )
    assert captured["prompt_preamble"] == PREAMBLE
    assert result.prompt_version_id == PROMPT_ID

    monkeypatch.setattr(
        "server.modules.agents.sme.agent.get_active_prompt",
        lambda *_: (_ for _ in ()).throw(ValueError()),
    )
    result = SME().run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=[{"x": 1}],
        canonical_source_text="text",
        db=object(),
    )
    assert result.prompt_version_id is None


@pytest.mark.parametrize("name", ["A1", "A2", "A3", "A4", "B1", "B2"])
def test_fixed_slice_caps_are_not_trimmed(name):
    cap = extraction._SLICE_CAPS[name]
    assert (
        len(
            getattr(extraction, f"slice_for_basket_{name.lower()}")("x" * (cap + 100))[
                :cap
            ]
        )
        == cap
    )


def test_grouped_overflow_only_falls_back_for_missing_criteria(monkeypatch):
    grouped = {"A-01": (2, "j", ())}
    fallback = []
    monkeypatch.setattr(registry, "run_grouped", lambda *a, **k: grouped)
    monkeypatch.setattr(
        registry,
        "run_criterion",
        lambda code, *a, **k: fallback.append(code) or (1, "j", ()),
    )
    scores, count = SME()._score_via_engine(object(), "canonical")
    assert set(fallback) == registry.REGISTERED_CODES - {"A-01"}
    assert count == 9 and set(scores) == registry.REGISTERED_CODES


def test_fallback_overflow_is_honest(monkeypatch):
    monkeypatch.setattr(registry, "run_grouped", lambda *a, **k: {})
    monkeypatch.setattr(
        registry,
        "run_criterion",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("overflow")),
    )
    with pytest.raises(AgentExecutionError, match="failed in both"):
        SME()._score_via_engine(object(), "canonical")


def test_sme_uses_canonical_text_only():
    with pytest.raises(AgentExecutionError, match="canonical source text"):
        SME()._resolve_full_text(uuid.uuid4(), "context", [{"text": "pdf/chunk"}], None)


def test_configured_response_mode_selects_json_schema_and_identity(monkeypatch):
    class Settings:
        llm_response_mode = "json_schema"

    monkeypatch.setattr(extraction, "get_settings", lambda: Settings())
    client = object()
    contract = extraction._contract(client, "A3")
    assert contract.mode == "json_schema"
    assert contract.schema_name == "sme_a3"
    monkeypatch.setattr(
        extraction,
        "get_settings",
        lambda: type("Settings", (), {"llm_response_mode": "json_object"})(),
    )
    assert extraction._contract(object(), "A3").mode == "json_object"


def test_grouped_is_exactly_six_calls_and_missing_only(monkeypatch):
    client = RecordingClient(
        list(_ALL_BASKETS_IN_ORDER[:2]) + [None] + list(_ALL_BASKETS_IN_ORDER[3:])
    )
    result = registry.run_grouped(client, "canonical")
    assert client.calls == 6
    assert set(result) == registry.REGISTERED_CODES - {"A-03"}
