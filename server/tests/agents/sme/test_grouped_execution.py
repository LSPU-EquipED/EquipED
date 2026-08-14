from __future__ import annotations

import json

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.runtime.llm import RunLLMClient
from server.modules.agents.sme.grouped_execution import execute_group

CODES = ("A-02", "A-05")
TITLES = {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"}


class _LLM:
    model = "primary"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def generate_result(
        self, prompt, *, temperature, max_new_tokens, deadline, response_contract
    ):
        self.prompts.append(prompt)
        return CompletionResult(
            next(self.responses), "primary", 10, 20, 30, "stop", attempts=1
        )


def _response(score=3):
    entries = [
        {
            "criterion_id": code,
            "criterion_title": TITLES[code],
            "score": score,
            "justification": "justification",
            "evidence": ["evidence"],
        }
        for code in CODES
    ]
    return json.dumps({"summary": "ok", "criterion_scores": entries})


def test_execute_group_returns_scores_and_prompt_text():
    client = RunLLMClient(_LLM([_response(4)]), "sme")
    scores, prompt_text = execute_group(
        "assessment_alignment", CODES, TITLES, client, "some SLM text"
    )
    assert [s.criterion_id for s in scores] == list(CODES)
    assert all(s.score == 4 for s in scores)
    assert '"group": "assessment_alignment"' in prompt_text


def test_execute_group_repairs_once_on_bad_json():
    llm = _LLM(["{broken", _response(3)])
    client = RunLLMClient(llm, "sme")
    scores, _ = execute_group("assessment_alignment", CODES, TITLES, client, "text")
    assert len(llm.prompts) == 2
    assert all(s.score == 3 for s in scores)


def test_execute_group_raises_after_repair_also_fails():
    llm = _LLM(["{broken", "{still broken"])
    client = RunLLMClient(llm, "sme")
    with pytest.raises(AgentExecutionError):
        execute_group("assessment_alignment", CODES, TITLES, client, "text")
    assert len(llm.prompts) == 2
