"""End-to-end contract for immutable SME prompt dispatch."""

from __future__ import annotations

import json
import uuid
from typing import Any

from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.sme import registry
from server.modules.agents.sme.agent import SME
from server.modules.agents.supervision.context import PromptSnapshot
from server.modules.agents.supervision.dispatch import AgentDispatcher
from server.tests.agents.helpers import _ALL_BASKETS_IN_ORDER

_MANAGED_PROMPT = "MANAGED SME PROMPT -- immutable dispatch contract"
_A03_FALLBACK = {
    "mechanisms": [
        {
            "id": 1,
            "text": "Check 1",
            "monitoring_type": "checkpoint",
            "evidence": "quiz",
        }
    ]
}


class StrictSMEClient:
    model = "strict-sme-model"

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = iter(responses)
        self.prompts: list[str] = []
        self.calls = 0

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None,
        response_contract: ResponseContract,
    ) -> CompletionResult:
        assert isinstance(temperature, float)
        assert isinstance(max_new_tokens, int)
        assert deadline is None or isinstance(deadline, float)
        assert response_contract.mode == "json_object"
        self.prompts.append(prompt)
        self.calls += 1
        return CompletionResult(
            content=json.dumps(next(self.responses)),
            served_model=self.model,
            prompt_tokens=10,
            completion_tokens=20,
            finish_reason="stop",
        )


def test_dispatch_passes_immutable_prompt_to_grouped_and_fallback_lanes(monkeypatch):
    responses = list(_ALL_BASKETS_IN_ORDER)
    responses[2] = {"monitoring_mechanisms": None}  # Invalid A3 basket.
    responses.append(_A03_FALLBACK)
    client = StrictSMEClient(responses)
    factory_calls: list[str] = []
    dispatched_kwargs: list[dict[str, Any]] = []

    original_run = SME.run

    def capture_run(self, **kwargs):
        dispatched_kwargs.append(dict(kwargs))
        return original_run(self, **kwargs)

    def factory(agent_name: str) -> StrictSMEClient:
        factory_calls.append(agent_name)
        return client

    monkeypatch.setattr(
        "server.modules.agents.sme.pipeline.get_active_rubric_criteria",
        lambda agent_id, db=None: {
            code: f"{code} title" for code in registry.REGISTERED_CODES
        },
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.dispatch.get_llm_client_for_agent", factory
    )
    monkeypatch.setattr(SME, "run", capture_run)

    evaluation_id, document_id = uuid.uuid4(), uuid.uuid4()
    snapshot = PromptSnapshot(version_id="sme-prompt-42", prompt_text=_MANAGED_PROMPT)
    result, failures = AgentDispatcher([SME()]).dispatch(
        evaluation_id=evaluation_id,
        document_id=document_id,
        chunk_infos=({"chunk_id": "chunk-1", "page_number": 1, "text": "SLM"},),
        context_text="SLM",
        prompt_versions={"sme": snapshot},
        reference_document_ids={},
        precomputed_context={},
        provenance={"managed_prompt": _MANAGED_PROMPT, "safe": "value"},
        policy_evidence=None,
        roadmap_context=None,
        canonical_source_text="Canonical SLM text",
    )

    assert failures == {}
    assert factory_calls == ["sme"]
    assert len(result) == 1 and result[0].success
    assert result[0].prompt_version_id == snapshot.version_id
    assert client.calls == 7
    assert all(prompt.startswith(_MANAGED_PROMPT) for prompt in client.prompts)
    assert len(dispatched_kwargs) == 1
    assert "db" not in dispatched_kwargs[0]
    assert "session" not in dispatched_kwargs[0]
    assert _MANAGED_PROMPT not in json.dumps(result[0].provenance)
    assert result[0].provenance["criterion_fallback_calls"] == 1
