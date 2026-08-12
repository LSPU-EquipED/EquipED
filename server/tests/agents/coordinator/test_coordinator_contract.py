"""Coordinator's frozen, curriculum-authoritative package contract."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.coordinator import curriculum, extraction, reconciliation
from server.modules.agents.coordinator.agent import Coordinator
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.sme import registry

_COORDINATOR_PAYLOAD = {
    "objectives": [{"id": 1, "text": "Objective"}],
    "curriculum_alignment": [],
}
_ROADMAP_TEST_PAYLOAD = {
    "objectives": [{"id": 1, "text": "Objective"}],
    "curriculum_alignment": [
        {"objective_id": 1, "is_addressed": False, "evidence": ""}
    ],
}


class Client:
    model = "assigned"

    def __init__(self, payload=None):
        self.payload = payload or _COORDINATOR_PAYLOAD
        self.calls = []

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return json.dumps(self.payload)

    def generate_result(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return CompletionResult(json.dumps(self.payload), self.model, "stop")


def _run(client, **kwargs):
    return Coordinator(llm_client=client).run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=[{"text": "SLM", "chunk_id": "c1"}],
        context_text="SLM",
        canonical_source_text="SLM",
        curriculum_id=uuid.uuid4(),
        curriculum_context="Official curriculum outcome",
        **kwargs,
    )


def test_curriculum_is_required_and_prompt_contains_exact_authoritative_context():
    client = Client(
        {
            **_COORDINATOR_PAYLOAD,
            "curriculum_alignment": [
                {
                    "objective_id": 1,
                    "is_addressed": True,
                    "evidence": "Official curriculum outcome",
                }
            ],
        }
    )
    result = _run(client)
    assert result.criterion_scores[0].score == 4
    assert client.calls[0][0].count("Official curriculum outcome") == 1
    with pytest.raises(AgentExecutionError):
        Coordinator(llm_client=Client()).run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=[{"text": "SLM"}],
            context_text="SLM",
            curriculum_id=None,
            curriculum_context="Official curriculum outcome",
        )


def test_no_retrieval_global_client_summary_or_independent_calls(monkeypatch):
    client = Client(
        {
            **_COORDINATOR_PAYLOAD,
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    monkeypatch.setattr(
        "server.modules.agents.runtime.llm.get_llm_client",
        lambda: (_ for _ in ()).throw(AssertionError()),
    )
    result = _run(client)
    assert len(client.calls) == 1
    assert result.summary == (
        "Objective-curriculum alignment: "
        "Curriculum-grounded (coordinator-only): 0/1 objective(s) addressed "
        "by this course's curriculum content. Score 1."
    )
    assert result.provenance["summary_calls"] == 0
    assert result.prompt_version_id is None


def test_response_contract_follows_configured_response_mode(monkeypatch):
    for expected in ("json_schema", "json_object"):
        settings = replace(extraction.get_settings(), llm_response_mode=expected)
        monkeypatch.setattr(extraction, "get_settings", lambda: settings)
        client = Client(
            {
                **_COORDINATOR_PAYLOAD,
                "curriculum_alignment": [
                    {"objective_id": 1, "is_addressed": False, "evidence": ""}
                ],
            },
        )
        _run(client)
        assert client.calls[0][1]["response_contract"].mode == expected


@pytest.mark.parametrize(
    "mutation",
    [
        lambda rows: (
            rows + [{"objective_id": 1, "is_addressed": False, "evidence": ""}]
        ),
        lambda rows: rows + [dict(rows[0])],
    ],
)
def test_alignment_rows_are_exact_bounded_and_unique(mutation):
    rows = [
        {
            "objective_id": 1,
            "is_addressed": True,
            "evidence": "Official curriculum outcome",
        }
    ]
    client = Client({**_COORDINATOR_PAYLOAD, "curriculum_alignment": mutation(rows)})
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client)


def test_sme_payload_fields_are_rejected():
    client = Client(
        {
            **_COORDINATOR_PAYLOAD,
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": True, "evidence": "evidence"}
            ],
            "assessments": [],
            "alignment": [],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client)


def _result(codes):
    scores = tuple(CriterionScore(c, c, 3, c) for c in codes)
    return AgentEvaluationResult(
        "sme", uuid.uuid4(), uuid.uuid4(), 3, scores, "", "m", 0, 0, True
    )


def test_merge_requires_canonical_ten_and_replaces_only_a05():
    coord = _result(("A-05",))
    coord = replace(coord, agent_name="coordinator")
    ordered = tuple(sorted(registry.REGISTERED_CODES))
    for codes in (
        (set(registry.REGISTERED_CODES) - {"A-05"}),
        tuple(registry.REGISTERED_CODES) + ("A-05",),
        ordered[:-1] + ("X",),
    ):
        with pytest.raises(AgentExecutionError):
            reconciliation.merge_with_sme(coord, _result(tuple(codes)))


def test_grounding_and_empty_alignment_score_one():
    result = curriculum.compute(
        [{"id": 1}],
        [{"objective_id": 1, "is_addressed": True, "evidence": "elsewhere"}],
        "curriculum",
    )
    assert result.aligned == 0 and result.score == 1
    empty = curriculum.compute([], [], "curriculum")
    assert empty.score == 1


def test_canonical_roadmap_is_one_advisory_prompt_insertion():
    client = Client(_ROADMAP_TEST_PAYLOAD)
    roadmap = {
        "course_code": "CS101",
        "course_title": "Algorithms",
        "year": 1,
        "semester": "First",
        "tech_stack": "Python",
        "competency_stage": "Developing",
        "course_status": "Active",
    }
    _run(client, roadmap_context=roadmap)
    assert len(client.calls) == 1
    prompt = client.calls[0][0]
    assert "SUPPLEMENTARY PROGRAM ROADMAP CONTEXT" in prompt
    for value in roadmap.values():
        assert str(value) in prompt
    assert (
        "EXACT PRECOMPUTED CURRICULUM CONTEXT:\nOfficial curriculum outcome" in prompt
    )


@pytest.mark.parametrize(
    "roadmap", [None, {}, [], {"nested": {"course_code": "CS101"}}]
)
def test_missing_or_invalid_roadmap_has_no_supplementary_section(roadmap):
    client = Client(_ROADMAP_TEST_PAYLOAD)
    _run(client, roadmap_context=roadmap)
    assert len(client.calls) == 1
    assert "SUPPLEMENTARY PROGRAM ROADMAP CONTEXT" not in client.calls[0][0]


def test_roadmap_only_alignment_evidence_is_rejected_without_fallback():
    client = Client(
        {
            **_COORDINATOR_PAYLOAD,
            "objectives": [{"id": 1, "text": "Objective"}],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": True, "evidence": "Python"}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client, roadmap_context={"tech_stack": "Python"})
    assert len(client.calls) == 1


def test_roadmap_note_counts_toward_complete_prompt_budget(monkeypatch):
    settings = extraction.get_settings()
    constrained = replace(settings, agent_total_prompt_budget_chars=560)
    monkeypatch.setattr(extraction, "get_settings", lambda: constrained)
    _run(Client(_ROADMAP_TEST_PAYLOAD))
    overflow_client = Client()
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(overflow_client, roadmap_context={"course_title": "A" * 20})
    assert overflow_client.calls == []


def test_format_roadmap_note_is_canonical_bounded_and_flat():
    note = curriculum.format_roadmap_note(
        {
            "course_code": "CS101",
            "course_title": "Algorithms",
            "year": 1,
            "semester": "First",
            "tech_stack": "Python",
            "competency_stage": "Developing",
            "course_status": "Active",
            "unknown": "ignore me",
            "nested": {"course_code": "bad"},
        }
    )
    assert len(note) <= 1000
    assert "ignore me" not in note and "bad" not in note
    assert all(label in note for label in ("Course code", "Title", "Year", "Semester"))
