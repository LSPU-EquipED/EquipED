"""End-to-end contract for immutable SME prompt dispatch."""

from __future__ import annotations

import json
import uuid
from typing import Any

from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.sme.agent import SME
from server.modules.agents.supervision.context import PromptSnapshot
from server.modules.agents.supervision.dispatch import AgentDispatcher
from server.tests.agents.helpers import _make_dummy_snapshot

_MANAGED_PROMPT = "MANAGED SME PROMPT -- immutable dispatch contract"


class StrictSMEClient:
    """Fake client that asserts transport call shape and managed prompt presence."""

    model = "strict-sme-model"

    def __init__(self, response_payload: str) -> None:
        self.response_payload = response_payload
        self.prompts: list[str] = []
        self.calls = 0

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None = None,
        response_contract: ResponseContract | None = None,
    ) -> CompletionResult:
        assert isinstance(temperature, float)
        assert isinstance(max_new_tokens, int)
        assert deadline is None or isinstance(deadline, float)
        assert response_contract is not None
        assert response_contract.mode == "json_object"
        self.prompts.append(prompt)
        self.calls += 1
        return CompletionResult(
            self.response_payload,
            self.model,
            prompt_tokens=20,
            completion_tokens=40,
            total_tokens=60,
            finish_reason="stop",
            attempts=1,
        )


def test_dispatch_passes_immutable_prompt_to_sme(monkeypatch):
    payload = json.dumps(
        {
            "summary": "ok",
            "criterion_measurements": [
                {
                    "criterion_id": "OP-01",
                    "criterion_title": "sme Criterion",
                    "score": 3,
                    "evidence": "Canonical SLM text",
                }
            ],
        }
    )
    client = StrictSMEClient(payload)
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
        "server.modules.agents.supervision.dispatch.get_llm_client_for_agent", factory
    )
    monkeypatch.setattr(SME, "run", capture_run)

    evaluation_id, document_id = uuid.uuid4(), uuid.uuid4()
    snapshot = PromptSnapshot(version_id="sme-prompt-42", prompt_text=_MANAGED_PROMPT)
    form_snapshot = _make_dummy_snapshot("sme", evaluation_id)
    result, failures = AgentDispatcher([SME()]).dispatch(
        evaluation_id=evaluation_id,
        document_id=document_id,
        chunk_infos=({"chunk_id": "chunk-1", "page_number": 1, "text": "SLM"},),
        form_snapshots=(form_snapshot,),
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
    assert client.calls >= 1
    assert all(
        (
            prompt.system_instruction
            if hasattr(prompt, "system_instruction")
            else str(prompt)
        ).startswith(_MANAGED_PROMPT)
        for prompt in client.prompts
    )
    assert len(dispatched_kwargs) == 1
    assert "db" not in dispatched_kwargs[0]
    assert "session" not in dispatched_kwargs[0]
    assert _MANAGED_PROMPT not in json.dumps(result[0].provenance)
