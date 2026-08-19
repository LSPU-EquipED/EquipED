"""Characterization tests for the hardened SME extraction boundary.

These tests intentionally describe the contract at the SME seam; production
code is not patched by this file.
"""

from __future__ import annotations

import json
import uuid

import pytest
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.sme.agent import SME
from server.modules.agents.sme.oracle import registry

PREAMBLE = "MANAGED SME PREAMBLE -- causal-test"
PROMPT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


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

    monkeypatch.setattr(SME, "_run_full_llm_scoring", fake_run)
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


def test_sme_uses_canonical_text_only():
    with pytest.raises(AgentExecutionError, match="canonical source text"):
        SME()._resolve_full_text(uuid.uuid4(), "context", [{"text": "pdf/chunk"}], None)
