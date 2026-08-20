from __future__ import annotations

import json

import pytest
from server.core.config import get_settings
from server.core.llm import CompletionResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.runtime.llm import RunLLMClient
from server.modules.agents.sme.group_execution import execute_group

CODES = ("A-02", "A-05")
TITLES = {"A-02": "Varied Assessment Tools", "A-05": "Objective Gauging"}
DESCRIPTIONS = {
    "A-02": "Teachers can easily assess students' progress.",
    "A-05": "Objectives are gauged effectively.",
}


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


class _LLM:
    model = "primary"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []
        self.calls = []

    def generate_result(
        self, prompt, *, temperature, max_new_tokens, deadline, response_contract
    ):
        self.prompts.append(prompt)
        self.calls.append(
            {
                "prompt": prompt,
                "temperature": temperature,
                "max_new_tokens": max_new_tokens,
                "deadline": deadline,
                "response_contract": response_contract,
            }
        )
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


def test_execute_group_returns_scores_and_prompt_text(monkeypatch):
    monkeypatch.setenv("LLM_RESPONSE_MODE", "json_schema")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.2")
    monkeypatch.setenv("LLM_MAX_NEW_TOKENS", "1500")
    get_settings.cache_clear()

    llm = _LLM([_response(4)])
    client = RunLLMClient(llm, "sme")
    scores, prompt_text, snapshot = execute_group(
        "assessment_alignment", CODES, TITLES, DESCRIPTIONS, client, "some SLM text"
    )
    assert [s.criterion_id for s in scores] == list(CODES)
    assert all(s.score == 4 for s in scores)
    assert '"group": "assessment_alignment"' in prompt_text
    assert snapshot["summary"] == "ok"
    assert len(snapshot["criterion_scores"]) == 2
    assert all(c["score"] == 4 for c in snapshot["criterion_scores"])
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["temperature"] == 0.2
    assert call["max_new_tokens"] == 1500
    assert call["response_contract"].mode == "json_schema"
    assert call["response_contract"].schema_name == "sme_group_assessment_alignment"
    assert call["deadline"] is not None


def test_execute_group_repairs_once_on_bad_json(monkeypatch):
    monkeypatch.setenv("LLM_RESPONSE_MODE", "json_schema")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.1")
    monkeypatch.setenv("LLM_MAX_NEW_TOKENS", "1800")
    get_settings.cache_clear()

    llm = _LLM(["{broken", _response(3)])
    client = RunLLMClient(llm, "sme")
    scores, prompt_returned, snapshot = execute_group(
        "assessment_alignment", CODES, TITLES, DESCRIPTIONS, client, "text"
    )
    assert len(llm.prompts) == 2
    assert len(llm.calls) == 2
    assert all(s.score == 3 for s in scores)
    assert snapshot["summary"] == "ok"
    assert len(snapshot["criterion_scores"]) == 2
    assert all(c["score"] == 3 for c in snapshot["criterion_scores"])

    first_call, repair_call = llm.calls
    # Assert shared deadline, identical temperature, and token cap
    assert first_call["deadline"] == repair_call["deadline"]
    assert first_call["temperature"] == repair_call["temperature"] == 0.1
    assert first_call["max_new_tokens"] == repair_call["max_new_tokens"] == 1800
    assert (
        first_call["response_contract"].schema_name
        == "sme_group_assessment_alignment"
    )
    assert (
        repair_call["response_contract"].schema_name
        == "sme_group_assessment_alignment"
    )

    # Assert repair prompt text structure
    assert "VALIDATOR_FAILURE category=SME_GROUP_INVALID:" in repair_call["prompt"]
    assert (
        "Regenerate ONLY the complete JSON response; do not include commentary."
        in repair_call["prompt"]
    )
    assert repair_call["prompt"].startswith(first_call["prompt"])

    # Assert original prompt snapshot is returned after repair
    assert prompt_returned == first_call["prompt"]


def test_execute_group_raises_after_repair_also_fails():
    llm = _LLM(["{broken", "{still broken"])
    client = RunLLMClient(llm, "sme")
    with pytest.raises(AgentExecutionError):
        execute_group(
            "assessment_alignment", CODES, TITLES, DESCRIPTIONS, client, "text"
        )
    assert len(llm.prompts) == 2
