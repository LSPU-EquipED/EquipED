"""Regression tests for ITSO repair behaviour."""

from uuid import uuid4

from server.modules.agents.itso import execution
from server.modules.agents.itso.agent import ITSO
from server.modules.agents.runtime import llm as runtime_llm


def test_repair_uses_sequential_responses_and_marks_repair(monkeypatch):
    class Client:
        model = "primary"

    responses = iter(
        [("{bad", "primary"), ('{"summary":"ok","criterion_scores":[]}', "fallback")]
    )
    monkeypatch.setattr(runtime_llm, "call_llm", lambda *a, **k: next(responses))
    monkeypatch.setattr(
        execution,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "agent_total_prompt_budget_chars": 8000,
                "agent_max_chunks": 12,
                "agent_max_excerpt_chars": 800,
                "agent_prompt_budget_chars": 5000,
                "agent_small_doc_threshold": 6,
                "llm_max_new_tokens": 2048,
                "get_agent_temperature": lambda s, n: 0.0,
            },
        )(),
    )
    result = ITSO(llm_client=Client()).run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c", "text": "x"}],
    )
    assert result.provenance["repair_occurred"] is True
    assert result.provenance["fallback_occurred"] is True
    assert "{bad" not in (result.raw_response or "")
