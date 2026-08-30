"""Regression tests for ITSO repair behaviour."""

from uuid import uuid4

from server.core.llm import CompletionResult
from server.modules.agents.itso import execution
from server.modules.agents.itso.agent import ITSO
from server.modules.agents.itso.response import ITSO_CRITERIA_TITLES
from server.tests.agents.itso.conftest_helper import make_itso_test_snapshot


def test_repair_uses_sequential_responses_and_marks_repair(monkeypatch):
    class Client:
        model = "primary"

        def __init__(self):
            self.prompts = []
            self.responses = iter(["{bad", _response("ok")])

        def generate_result(
            self, prompt, *, temperature, max_new_tokens, deadline, response_contract
        ):
            self.prompts.append(prompt)
            return CompletionResult(
                next(self.responses), "primary", 2, 3, 5, "stop", attempts=1
            )

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
    client = Client()
    eval_id = uuid4()
    result = ITSO(llm_client=client).run(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c", "text": "x"}],
        form_snapshot=make_itso_test_snapshot(eval_id),
    )
    assert result.provenance["repair_occurred"] is True
    assert result.provenance["fallback_occurred"] is False
    assert result.provenance["actual_model"] == "primary"
    assert len(client.prompts) == 2
    assert "{bad" not in (result.raw_response or "")


def _response(summary):
    import json

    return json.dumps(
        {
            "summary": summary,
            "criterion_scores": [
                {
                    "criterion_id": f"ITSO-0{i}",
                    "criterion_title": ITSO_CRITERIA_TITLES[f"ITSO-0{i}"],
                    "score": 3,
                    "justification": "justification",
                    "chunk_ids": [],
                    "evidence": [],
                }
                for i in range(1, 6)
            ],
        }
    )
