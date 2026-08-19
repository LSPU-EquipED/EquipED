"""Contract tests for the ITSO response schema and execution budget."""

from __future__ import annotations

import copy
import json
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator
from server.core.llm import CompletionResult
from server.modules.agents.itso.execution import execute as run_itso_execution
from server.modules.agents.itso.response import (
    ITSO_CHUNK_ID_MAX,
    ITSO_CRITERIA,
    ITSO_CRITERIA_TITLES,
    ITSO_RESPONSE_SCHEMA,
    ITSO_TEXT_MAX,
    build_response_schema,
    criterion_scores,
)
from server.modules.agents.itso.response import (
    parse_response as parse_itso_response,
)
from server.modules.agents.runtime.context import ITSOExecutionContext


def _payload(summary="summary"):
    return {
        "summary": summary,
        "criterion_scores": [
            {
                "criterion_id": criterion_id,
                "criterion_title": ITSO_CRITERIA_TITLES[criterion_id],
                "score": 3,
                "justification": "justification",
                "chunk_ids": ["c1"],
                "evidence": ["evidence"],
            }
            for criterion_id in ITSO_CRITERIA
        ],
    }


def _assert_rejected(payload):
    assert list(Draft202012Validator(ITSO_RESPONSE_SCHEMA).iter_errors(payload))
    with pytest.raises(Exception):
        parse_itso_response(json.dumps(payload), known_chunk_ids=("c1",))


def test_canonical_schema_and_parser_are_equivalent():
    payload = _payload()
    assert not list(Draft202012Validator(ITSO_RESPONSE_SCHEMA).iter_errors(payload))
    assert parse_itso_response(json.dumps(payload), known_chunk_ids=("c1",)) == payload
    scores = ITSO_RESPONSE_SCHEMA["properties"]["criterion_scores"]
    assert (scores["minItems"], scores["maxItems"]) == (5, 5)
    assert scores["items"]["type"] == "object"
    assert scores["unevaluatedItems"] is False
    for item, criterion_id in zip(scores["prefixItems"], ITSO_CRITERIA):
        assert item["properties"]["criterion_id"] == {"const": criterion_id}
        assert item["properties"]["criterion_title"] == {
            "const": ITSO_CRITERIA_TITLES[criterion_id]
        }


def test_task_schema_and_parser_share_chunk_id_bounds():
    payload = _payload()
    payload["criterion_scores"][0]["chunk_ids"] = ["c1", "c1"]
    schema = build_response_schema(("c1",))
    assert not list(Draft202012Validator(schema).iter_errors(payload))
    assert parse_itso_response(json.dumps(payload), known_chunk_ids=("c1",)) == payload

    unknown = copy.deepcopy(payload)
    unknown["criterion_scores"][0]["chunk_ids"] = ["unknown"]
    assert list(Draft202012Validator(schema).iter_errors(unknown))
    with pytest.raises(Exception):
        parse_itso_response(json.dumps(unknown), known_chunk_ids=("c1",))

    empty_schema = build_response_schema(())
    empty = _payload()
    for item in empty["criterion_scores"]:
        item["chunk_ids"] = []
    assert not list(Draft202012Validator(empty_schema).iter_errors(empty))
    assert parse_itso_response(json.dumps(empty), known_chunk_ids=()) == empty
    too_many = copy.deepcopy(payload)
    too_many["criterion_scores"][0]["chunk_ids"] = ["c1"] * 9
    assert list(Draft202012Validator(schema).iter_errors(too_many))
    with pytest.raises(Exception):
        parse_itso_response(json.dumps(too_many), known_chunk_ids=("c1",))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["criterion_scores"][1].update(criterion_id="ITSO-01"),
        lambda p: p["criterion_scores"].pop(),
        lambda p: p["criterion_scores"].append(
            copy.deepcopy(p["criterion_scores"][-1])
        ),
        lambda p: p.update(extra=True),
        lambda p: p["criterion_scores"][0].update(score=True),
        lambda p: p["criterion_scores"][0].update(score="3"),
        lambda p: p["criterion_scores"][0].update(score=3.5),
        lambda p: p["criterion_scores"][0].update(score=0),
        lambda p: p["criterion_scores"][0].update(score=5),
        lambda p: p["criterion_scores"][0].update(
            justification="x" * (ITSO_TEXT_MAX + 1)
        ),
        lambda p: p["criterion_scores"][0].update(
            chunk_ids=["x" * (ITSO_CHUNK_ID_MAX + 1)]
        ),
        lambda p: p["criterion_scores"][0].update(evidence=["x" * (ITSO_TEXT_MAX + 1)]),
        lambda p: p.update(summary="x" * (ITSO_TEXT_MAX + 1)),
    ],
)
def test_mutations_fail_schema_and_parser(mutation):
    payload = _payload()
    mutation(payload)
    _assert_rejected(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(summary=""),
        lambda p: p["criterion_scores"].reverse(),
        lambda p: p["criterion_scores"][0].update(criterion_title="wrong title"),
        lambda p: p["criterion_scores"][0].update(justification=""),
    ],
)
def test_mutations_accepted_by_resilient_parser(mutation):
    payload = _payload()
    mutation(payload)
    parsed = parse_itso_response(json.dumps(payload), known_chunk_ids=("c1",))
    scores = criterion_scores(parsed, known_chunk_ids=("c1",))
    assert len(scores) == 5


class _CapturingClient:
    model = "primary"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []
        self.deadlines = []

    def generate_result(
        self,
        prompt,
        *,
        temperature,
        max_new_tokens,
        deadline,
        response_contract,
    ):
        self.prompts.append(prompt)
        self.deadlines.append(deadline)
        return CompletionResult(
            next(self.responses), "primary", 1, 1, 1, "stop", attempts=1
        )


def _context(client):
    return ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=(
            {"chunk_id": "c1", "page_number": 1, "text": "security evidence"},
        ),
        llm_client=client,
        precomputed_context={"rubric_itso": ["rubric"], "syllabus": ["reference"]},
    )


def _settings(budget=8000):
    class Settings:
        agent_total_prompt_budget_chars = budget
        agent_max_chunks = 12
        agent_max_excerpt_chars = 800
        agent_prompt_budget_chars = 5000
        agent_small_doc_threshold = 6
        llm_max_new_tokens = 2048
        llm_request_timeout_seconds = 120

        def get_agent_temperature(self, name):
            return 0.0

    return Settings()


def test_real_execution_regenerates_once_with_bounded_prompts(monkeypatch):
    monkeypatch.setattr(
        "server.modules.agents.itso.execution.get_settings", lambda: _settings()
    )
    client = _CapturingClient(["invalid", json.dumps(_payload())])
    result = run_itso_execution(_context(client))
    assert len(client.prompts) == 2
    assert all(len(prompt) <= 8000 for prompt in client.prompts)
    assert client.prompts[1].startswith(client.prompts[0])
    assert "invalid" not in client.prompts[1]
    assert client.deadlines[1] <= client.deadlines[0]
    assert result.raw_response is None
    assert result.metadata["response_schema_version"] == "itso-response-v1"
