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
from server.tests.agents.helpers import (
    SME_CRITERION_FALLBACKS,
    GroupScoringFakeClient,
    sme_group_payloads,
)

_MANAGED_PROMPT = "MANAGED SME PROMPT -- immutable dispatch contract"
_TITLES = {code: f"{code} title" for code in registry.REGISTERED_CODES}


class StrictSMEClient(GroupScoringFakeClient):
    """Grouped-scoring fake that also asserts the transport call shape."""

    model = "strict-sme-model"

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
        return super().generate_result(
            prompt,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            deadline=deadline,
            response_contract=response_contract,
        )


def test_dispatch_passes_immutable_prompt_to_grouped_and_fallback_lanes(monkeypatch):
    # ``assessment_alignment`` fails outright, so A-02 and A-05 take the
    # retained per-criterion engine lane -- both lanes must carry the managed
    # prompt.
    payloads = sme_group_payloads(3, titles=_TITLES)
    payloads["assessment_alignment"] = "{not valid json"
    client = StrictSMEClient(
        payloads,
        [SME_CRITERION_FALLBACKS["A-02"], SME_CRITERION_FALLBACKS["A-05"]],
    )
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
        lambda agent_id, db=None: _TITLES,
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
    # 3 grouped calls (one of them retried once by the repair lane) + 2
    # per-criterion fallbacks for the failed group's codes.
    assert client.group_calls == 4
    assert client.fallback_calls == 2
    assert all(prompt.startswith(_MANAGED_PROMPT) for prompt in client.prompts)
    assert len(dispatched_kwargs) == 1
    assert "db" not in dispatched_kwargs[0]
    assert "session" not in dispatched_kwargs[0]
    assert _MANAGED_PROMPT not in json.dumps(result[0].provenance)
    assert result[0].provenance["criterion_fallback_calls"] == 2
