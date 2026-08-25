"""Coordinator's frozen, curriculum-authoritative package contract."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import replace

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.coordinator import curriculum, extraction, reconciliation
from server.modules.agents.coordinator.agent import Coordinator
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.sme.rubric import REGISTERED_CODES

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


def _run(client, db=None, **kwargs):
    run_kwargs = {
        "evaluation_id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "chunk_infos": [{"text": "SLM", "chunk_id": "c1"}],
        "context_text": "SLM",
        "canonical_source_text": "SLM",
        "curriculum_id": uuid.uuid4(),
        "curriculum_context": "Official curriculum outcome",
        "db": db,
    }
    run_kwargs.update(kwargs)
    return Coordinator(llm_client=client).run(**run_kwargs)


def test_curriculum_is_required_and_prompt_contains_exact_authoritative_context(
    db_session,
):
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
    result = _run(client, db=db_session)
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
            db=db_session,
        )


def test_no_retrieval_global_client_summary_or_independent_calls(
    monkeypatch, db_session
):
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
    result = _run(client, db=db_session)
    assert len(client.calls) == 1
    assert result.summary == (
        "Objective-curriculum alignment: "
        "Curriculum-grounded (coordinator-only): 0/1 objective(s) addressed "
        "by this course's curriculum content. Score 1."
    )
    assert result.provenance["summary_calls"] == 0
    assert result.prompt_version_id is None


def test_response_contract_follows_configured_response_mode(monkeypatch, db_session):
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
        _run(client, db=db_session)
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
def test_alignment_rows_are_exact_bounded_and_unique(mutation, db_session):
    rows = [
        {
            "objective_id": 1,
            "is_addressed": True,
            "evidence": "Official curriculum outcome",
        }
    ]
    client = Client({**_COORDINATOR_PAYLOAD, "curriculum_alignment": mutation(rows)})
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client, db=db_session)


def test_sme_payload_fields_are_rejected(db_session):
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
        _run(client, db=db_session)


def _result(codes):
    scores = tuple(CriterionScore(c, c, 3, c) for c in codes)
    return AgentEvaluationResult(
        "sme", uuid.uuid4(), uuid.uuid4(), 3, scores, "", "m", 0, 0, True
    )


def test_merge_requires_canonical_ten_and_replaces_only_a05():
    coord = _result(("A-05",))
    coord = replace(coord, agent_name="coordinator")
    ordered = tuple(sorted(REGISTERED_CODES))
    for codes in (
        (set(REGISTERED_CODES) - {"A-05"}),
        tuple(REGISTERED_CODES) + ("A-05",),
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


def test_canonical_roadmap_is_one_advisory_prompt_insertion(db_session):
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
    _run(client, db=db_session, roadmap_context=roadmap)
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
def test_missing_or_invalid_roadmap_has_no_supplementary_section(roadmap, db_session):
    client = Client(_ROADMAP_TEST_PAYLOAD)
    _run(client, db=db_session, roadmap_context=roadmap)
    assert len(client.calls) == 1
    assert "SUPPLEMENTARY PROGRAM ROADMAP CONTEXT" not in client.calls[0][0]


def test_roadmap_only_alignment_evidence_is_rejected_without_fallback(db_session):
    client = Client(
        {
            **_COORDINATOR_PAYLOAD,
            "objectives": [{"id": 1, "text": "Objective"}],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": True, "evidence": "Python"}
            ],
        }
    )
    result = _run(client, db=db_session, roadmap_context={"tech_stack": "Python"})
    assert len(client.calls) == 1
    assert result.success is True
    assert result.criterion_scores[0].score == 1
    assert result.provenance["grounding_rejected_count"] == 1
    assert result.criterion_scores[0].evidence == ()


def test_roadmap_note_counts_toward_complete_prompt_budget(monkeypatch, db_session):
    settings = extraction.get_settings()
    constrained = replace(settings, agent_total_prompt_budget_chars=1450)
    monkeypatch.setattr(extraction, "get_settings", lambda: constrained)
    _run(Client(_ROADMAP_TEST_PAYLOAD), db=db_session)
    overflow_client = Client()
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(
            overflow_client,
            db=db_session,
            roadmap_context={"course_title": "A" * 200},
        )
    assert overflow_client.calls == []


def test_production_shaped_payload_fits_default_budget_and_calls_llm(
    db_session,
    caplog,
):
    # Production full evaluation has ~8,740 chars SLM + ~10,190 chars curriculum
    # + fixed prompt/roadmap (~19.5k total).
    slm_text = ("Course Module Concept Overview and Content Section. " * 170)[:8740]
    curriculum_text = ("Official Institutional Curriculum Learning Outcome. " * 200)[
        :10190
    ]
    assert len(slm_text) == 8740
    assert len(curriculum_text) == 10190

    roadmap = {
        "course_code": "IT301",
        "course_title": "Systems Integration and Architecture",
        "year": 3,
        "semester": "First",
        "tech_stack": "Enterprise Systems",
        "competency_stage": "Proficient",
        "course_status": "Active",
    }
    client = Client(_ROADMAP_TEST_PAYLOAD)
    with caplog.at_level(logging.INFO):
        result = _run(
            client,
            db=db_session,
            canonical_source_text=slm_text,
            context_text=slm_text,
            curriculum_context=curriculum_text,
            roadmap_context=roadmap,
        )
    assert len(client.calls) == 1
    assert "agent=coordinator | phase=prompt_preflight" in caplog.text
    assert "slm_chars=8740" in caplog.text
    assert "curriculum_chars=10190" in caplog.text
    assert "budget_chars=32000" in caplog.text
    assert result.prompt_version_id is None
    assert result.agent_name == "coordinator"
    assert result.success is True


def test_canonical_payload_passes(db_session):
    client = Client(
        {
            "objectives": [
                {"id": 1, "text": "Understand sorting algorithms"},
                {"id": 2, "text": "Implement binary search"},
            ],
            "curriculum_alignment": [
                {
                    "objective_id": 1,
                    "is_addressed": True,
                    "evidence": "Official curriculum outcome",
                },
                {"objective_id": 2, "is_addressed": False, "evidence": ""},
            ],
        }
    )
    result = _run(client, db=db_session)
    assert len(client.calls) == 1
    assert result.success is True
    assert result.criterion_scores[0].score == 3
    assert result.prompt_version_id is None


def test_exact_alias_payload_normalizes_and_passes_in_single_call(db_session, caplog):
    client = Client(
        {
            "objectives": [
                {
                    "objective_id": 1,
                    "objective": "Understand sorting algorithms",
                    "curriculum_alignment": False,
                    "evidence": "IGNORED NESTED ALIGNMENT",
                },
                {
                    "objective_id": 2,
                    "objective": "Implement binary search",
                    "curriculum_alignment": True,
                    "evidence": "IGNORED NESTED EVIDENCE",
                },
            ],
            "curriculum_alignment": [
                {
                    "objective_id": 1,
                    "is_addressed": True,
                    "evidence": "Official curriculum outcome",
                },
                {"objective_id": 2, "is_addressed": False, "evidence": ""},
            ],
        }
    )
    with caplog.at_level(logging.INFO):
        result = _run(client, db=db_session)
    assert len(client.calls) == 1
    assert result.success is True
    assert (
        "[COORDINATOR_NORMALIZATION] normalized_alias_objectives count=2" in caplog.text
    )
    # Ensure nested alias evidence/curriculum_alignment was ignored
    # and top-level governed: objective 1 is_addressed=True with official
    # curriculum outcome -> aligned=1/2 -> score 3
    assert result.criterion_scores[0].score == 3
    assert "IGNORED NESTED" not in str(result.criterion_scores[0].evidence)


def test_mixed_canonical_and_alias_objectives_fails(db_session):
    client = Client(
        {
            "objectives": [
                {"id": 1, "text": "Canonical objective"},
                {
                    "objective_id": 2,
                    "objective": "Alias objective",
                    "curriculum_alignment": False,
                    "evidence": "",
                },
            ],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""},
                {"objective_id": 2, "is_addressed": False, "evidence": ""},
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client, db=db_session)
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "bad_obj",
    [
        {"id": 1},  # missing text
        {"text": "only text"},  # missing id
        {"id": 1, "text": "text", "extra": "extra"},  # extra key on canonical
        {
            "objective_id": 1,
            "objective": "obj",
            "curriculum_alignment": True,
        },  # missing evidence in alias
        {
            "objective_id": 1,
            "objective": "obj",
            "curriculum_alignment": True,
            "evidence": "",
            "extra": 123,
        },  # extra key in alias
        {"unknown_id": 1, "unknown_text": "text"},  # unknown alias
    ],
)
def test_missing_extra_or_unknown_keys_in_objectives_fails(bad_obj, db_session):
    client = Client(
        {
            "objectives": [bad_obj],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client, db=db_session)
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "bad_id",
    [
        "1",  # digit string
        1.0,  # float
        True,  # bool
        0,  # zero
        -1,  # negative
    ],
)
def test_non_positive_int_or_wrong_type_id_fails(bad_id, db_session):
    # Canonical test
    client_can = Client(
        {
            "objectives": [{"id": bad_id, "text": "Valid text"}],
            "curriculum_alignment": [
                {"objective_id": bad_id, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client_can, db=db_session)
    assert len(client_can.calls) == 1

    # Alias test
    client_alias = Client(
        {
            "objectives": [
                {
                    "objective_id": bad_id,
                    "objective": "Valid text",
                    "curriculum_alignment": False,
                    "evidence": "",
                }
            ],
            "curriculum_alignment": [
                {"objective_id": bad_id, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client_alias, db=db_session)
    assert len(client_alias.calls) == 1


@pytest.mark.parametrize(
    "bad_text",
    [
        "",  # empty string
        "   ",  # whitespace string
        123,  # int
        None,  # None
        ["list"],  # list
    ],
)
def test_empty_or_nonstring_objective_text_fails(bad_text, db_session):
    client = Client(
        {
            "objectives": [{"id": 1, "text": bad_text}],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client, db=db_session)
    assert len(client.calls) == 1


def test_cardinality_mismatch_8_objectives_12_alignments_fails(db_session):
    objectives = [{"id": i, "text": f"Objective {i}"} for i in range(1, 9)]
    alignments = [
        {"objective_id": i, "is_addressed": False, "evidence": ""} for i in range(1, 13)
    ]
    client = Client({"objectives": objectives, "curriculum_alignment": alignments})
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client, db=db_session)
    assert len(client.calls) == 1


def test_duplicate_missing_or_unknown_alignment_ids_fail(db_session):
    # Duplicate ID in objectives
    client_dup_obj = Client(
        {
            "objectives": [
                {"id": 1, "text": "Objective A"},
                {"id": 1, "text": "Objective B"},
            ],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client_dup_obj, db=db_session)

    # Missing alignment for objective 2
    client_missing_align = Client(
        {
            "objectives": [
                {"id": 1, "text": "Objective 1"},
                {"id": 2, "text": "Objective 2"},
            ],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""},
                {"objective_id": 1, "is_addressed": False, "evidence": ""},
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client_missing_align, db=db_session)

    # Unknown ID in alignment
    client_unknown_id = Client(
        {
            "objectives": [{"id": 1, "text": "Objective 1"}],
            "curriculum_alignment": [
                {"objective_id": 99, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client_unknown_id, db=db_session)


def test_row_level_grounding_rejection_and_exact_substring(db_session, caplog):
    curriculum_text = (
        "Official curriculum outcome: Introduction to Python 3.12 (OCR artifact: [x])."
    )
    # Row 1: exact substring with OCR noise -> accepted
    # Row 2: paraphrase -> demoted to false+empty
    # Row 3: case difference -> demoted to false+empty
    # Row 4: whitespace difference / internal modification -> demoted to false+empty
    # Row 5: empty evidence with is_addressed: true -> demoted to false+empty
    client = Client(
        {
            "objectives": [
                {"id": 1, "text": "Objective 1"},
                {"id": 2, "text": "Objective 2"},
                {"id": 3, "text": "Objective 3"},
                {"id": 4, "text": "Objective 4"},
                {"id": 5, "text": "Objective 5"},
            ],
            "curriculum_alignment": [
                {
                    "objective_id": 1,
                    "is_addressed": True,
                    "evidence": "Introduction to Python 3.12 (OCR artifact: [x])",
                },
                {
                    "objective_id": 2,
                    "is_addressed": True,
                    "evidence": "Intro to Python 3.12 with artifacts",
                },
                {
                    "objective_id": 3,
                    "is_addressed": True,
                    "evidence": "official curriculum outcome",
                },
                {
                    "objective_id": 4,
                    "is_addressed": True,
                    "evidence": "Introduction  to  Python 3.12",
                },
                {
                    "objective_id": 5,
                    "is_addressed": True,
                    "evidence": "",
                },
            ],
        }
    )
    with caplog.at_level(logging.INFO):
        result = _run(
            client,
            db=db_session,
            curriculum_context=curriculum_text,
        )
    assert len(client.calls) == 1
    assert result.success is True
    # 1 of 5 aligned -> score 2 on moderate scale
    assert result.criterion_scores[0].score == 2
    assert result.provenance["grounding_rejected_count"] == 4
    assert (
        "[COORDINATOR_GROUNDING]" in caplog.text
        and "grounding_rejected_count=4" in caplog.text
    )
    assert (
        "Curriculum-grounded (coordinator-only): 1/5 objective(s) addressed "
        "by this course's curriculum content (4 unsupported claim(s) rejected). "
        "Score 2." == result.criterion_scores[0].justification
    )
    # Evidence only contains accepted row 1
    assert result.criterion_scores[0].evidence == (
        "Introduction to Python 3.12 (OCR artifact: [x])",
    )


def test_all_grounding_rejected_yields_success_score_1(db_session, caplog):
    curriculum_text = "Official curriculum outcome: Algorithms and Data Structures."
    client = Client(
        {
            "objectives": [
                {"id": 1, "text": "Objective 1"},
                {"id": 2, "text": "Objective 2"},
            ],
            "curriculum_alignment": [
                {
                    "objective_id": 1,
                    "is_addressed": True,
                    "evidence": "Paraphrased algorithm text",
                },
                {
                    "objective_id": 2,
                    "is_addressed": True,
                    "evidence": "Completely hallucinated evidence",
                },
            ],
        }
    )
    with caplog.at_level(logging.INFO):
        result = _run(
            client,
            db=db_session,
            curriculum_context=curriculum_text,
        )
    assert len(client.calls) == 1
    assert result.success is True
    assert result.criterion_scores[0].score == 1
    assert result.provenance["grounding_rejected_count"] == 2
    assert (
        "[COORDINATOR_GROUNDING]" in caplog.text
        and "grounding_rejected_count=2" in caplog.text
    )
    assert (
        "Curriculum-grounded (coordinator-only): 0/2 objective(s) addressed "
        "by this course's curriculum content (2 unsupported claim(s) rejected). "
        "Score 1." == result.criterion_scores[0].justification
    )
    assert result.criterion_scores[0].evidence == ()


def test_false_alignment_with_nonempty_evidence_fails_structural_validation(
    db_session,
):
    client = Client(
        {
            "objectives": [{"id": 1, "text": "Objective"}],
            "curriculum_alignment": [
                {
                    "objective_id": 1,
                    "is_addressed": False,
                    "evidence": "Official curriculum outcome",
                }
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client, db=db_session)
    assert len(client.calls) == 1


def test_live_shape_alias_with_ungrounded_nested_values_governed_by_top_level(
    db_session, caplog
):
    curriculum_text = "Official curriculum outcome: Systems Architecture."
    client = Client(
        {
            "objectives": [
                {
                    "objective_id": 1,
                    "objective": "Objective 1",
                    "curriculum_alignment": True,
                    "evidence": "UNGROUNDED NESTED EVIDENCE",
                },
                {
                    "objective_id": 2,
                    "objective": "Objective 2",
                    "curriculum_alignment": False,
                    "evidence": "",
                },
            ],
            "curriculum_alignment": [
                {
                    "objective_id": 1,
                    "is_addressed": True,
                    "evidence": "Official curriculum outcome: Systems Architecture.",
                },
                {"objective_id": 2, "is_addressed": False, "evidence": ""},
            ],
        }
    )
    with caplog.at_level(logging.INFO):
        result = _run(
            client,
            db=db_session,
            curriculum_context=curriculum_text,
        )
    assert len(client.calls) == 1
    assert result.success is True
    assert result.criterion_scores[0].score == 3
    assert result.provenance["grounding_rejected_count"] == 0
    assert result.criterion_scores[0].evidence == (
        "Official curriculum outcome: Systems Architecture.",
    )


def test_invalid_outputs_make_exactly_one_call_no_retry(db_session):
    client = Client({"invalid": "json payload"})
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client, db=db_session)
    assert len(client.calls) == 1


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
