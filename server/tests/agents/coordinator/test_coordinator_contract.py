"""Coordinator's frozen, curriculum-authoritative package contract."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import replace
from typing import Any

import pytest
from pydantic import ValidationError
from server.core.llm import CompletionResult
from server.modules.agents.coordinator import curriculum, extraction
from server.modules.agents.coordinator.agent import Coordinator
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    DomainDefinition,
    FormDefinition,
)
from server.modules.rubrics.snapshot_contracts import (
    EvaluationFormSnapshotDTO,
    build_evaluation_form_snapshot,
)

_COORDINATOR_PAYLOAD = {
    "objectives": [{"id": 1, "text": "SLM Objective"}],
    "curriculum_alignment": [],
}
_ROADMAP_TEST_PAYLOAD = {
    "objectives": [{"id": 1, "text": "SLM Objective"}],
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


def _make_snapshot(
    eval_id: uuid.UUID | None = None,
    criterion_code: str = "A-05",
    title: str = "Curriculum Alignment",
    description: str = "Evaluates alignment of course objectives with the curriculum.",
    scoring_rule: str | None = "Scored based on ratio of aligned objectives.",
    guidance: str | None = "Verify curriculum alignment.",
    agent_id: str = "coordinator",
    adapter_key: str = "coordinator",
    adapter_version: int = 1,
    strategy_config: Any | None = None,
    criteria: tuple[CriterionDefinition, ...] | None = None,
) -> EvaluationFormSnapshotDTO:
    eval_id = eval_id or uuid.uuid4()
    set_id = uuid.uuid4()
    if strategy_config is None:
        strategy_config = CurriculumAlignmentConfig(guidance=guidance)
    if criteria is None:
        crit = CriterionDefinition(
            rubric_criterion_id=uuid.uuid4(),
            criterion_code=criterion_code,
            title=title,
            description=description,
            scoring_rule=scoring_rule,
            display_order=0,
            strategy_config=strategy_config,
        )
        criteria = (crit,)
    dom = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="DOM-01",
        title="Domain 1",
        display_order=0,
        criteria=criteria,
    )
    form = FormDefinition(
        rubric_set_id=set_id,
        agent_id=agent_id,
        name=f"{agent_id} Form",
        version_number=1,
        adapter_key=adapter_key,
        adapter_version=adapter_version,
        domains=(dom,),
    )
    return build_evaluation_form_snapshot(eval_id, form)


def _run(client, form_snapshot: EvaluationFormSnapshotDTO | None = None, **kwargs):
    eval_id = kwargs.get("evaluation_id") or uuid.uuid4()
    if form_snapshot is None:
        form_snapshot = _make_snapshot(eval_id=eval_id)
    default_slm = (
        "SLM Objective: Understand sorting algorithms. Implement binary search. "
        "Objective 1. Objective 2. Objective 3. Objective 4. Objective 5. "
        "Canonical objective. Alias objective."
    )
    run_kwargs = {
        "evaluation_id": eval_id,
        "document_id": uuid.uuid4(),
        "chunk_infos": [{"text": default_slm, "chunk_id": "c1"}],
        "context_text": default_slm,
        "canonical_source_text": default_slm,
        "curriculum_id": uuid.uuid4(),
        "curriculum_context": "Official curriculum outcome",
        "form_snapshot": form_snapshot,
    }
    run_kwargs.update(kwargs)
    return Coordinator(llm_client=client).run(**run_kwargs)


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
        eval_id = uuid.uuid4()
        Coordinator(llm_client=Client()).run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            chunk_infos=[{"text": "SLM"}],
            context_text="SLM",
            curriculum_id=None,
            curriculum_context="Official curriculum outcome",
            form_snapshot=_make_snapshot(eval_id=eval_id),
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


def test_coordinator_returns_independent_single_a05_criterion_without_sme_merge():
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
    assert result.agent_name == "coordinator"
    assert len(result.criterion_scores) == 1
    assert tuple(c.criterion_id for c in result.criterion_scores) == ("A-05",)
    assert result.subtotal == float(result.criterion_scores[0].score)


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
    assert "EXACT PRECOMPUTED CURRICULUM CONTEXT" in prompt
    assert "Official curriculum outcome" in prompt


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
    result = _run(client, roadmap_context={"tech_stack": "Python"})
    assert len(client.calls) == 1
    assert result.success is True
    assert result.criterion_scores[0].score == 1
    assert result.provenance["grounding_rejected_count"] == 1
    assert result.criterion_scores[0].evidence == ()


def test_roadmap_note_counts_toward_complete_prompt_budget(monkeypatch):
    settings = extraction.get_settings()
    constrained = replace(settings, agent_total_prompt_budget_chars=2500)
    monkeypatch.setattr(extraction, "get_settings", lambda: constrained)
    _run(Client(_ROADMAP_TEST_PAYLOAD))
    overflow_client = Client()
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(
            overflow_client,
            roadmap_context={"course_title": "A" * 200},
        )
    assert overflow_client.calls == []


def test_production_shaped_payload_fits_default_budget_and_calls_llm(
    caplog, monkeypatch
):
    from server.core.config import get_settings

    monkeypatch.setenv("AGENT_TOTAL_PROMPT_BUDGET_CHARS", "32000")
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")
    get_settings.cache_clear()
    monkeypatch.setattr(extraction, "get_settings", get_settings)

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
    client = Client(
        {
            "objectives": [
                {
                    "id": 1,
                    "text": "Course Module Concept Overview and Content Section.",
                }
            ],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with caplog.at_level(logging.INFO):
        result = _run(
            client,
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


def test_canonical_payload_passes():
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
    result = _run(client)
    assert len(client.calls) == 1
    assert result.success is True
    assert result.criterion_scores[0].score == 3
    assert result.prompt_version_id is None


def test_exact_alias_payload_normalizes_and_passes_in_single_call(caplog):
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
        result = _run(client)
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


def test_mixed_canonical_and_alias_objectives_fails():
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
        _run(client)
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
def test_missing_extra_or_unknown_keys_in_objectives_fails(bad_obj):
    client = Client(
        {
            "objectives": [bad_obj],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client)
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
def test_non_positive_int_or_wrong_type_id_fails(bad_id):
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
        _run(client_can)
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
        _run(client_alias)
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
def test_empty_or_nonstring_objective_text_fails(bad_text):
    client = Client(
        {
            "objectives": [{"id": 1, "text": bad_text}],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client)
    assert len(client.calls) == 1


def test_cardinality_mismatch_8_objectives_12_alignments_fails():
    objectives = [{"id": i, "text": f"Objective {i}"} for i in range(1, 9)]
    alignments = [
        {"objective_id": i, "is_addressed": False, "evidence": ""} for i in range(1, 13)
    ]
    client = Client({"objectives": objectives, "curriculum_alignment": alignments})
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client)
    assert len(client.calls) == 1


def test_duplicate_missing_or_unknown_alignment_ids_fail():
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
        _run(client_dup_obj)

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
        _run(client_missing_align)

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
        _run(client_unknown_id)


def test_row_level_grounding_rejection_and_exact_substring(caplog):
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


def test_all_grounding_rejected_yields_success_score_1(caplog):
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


def test_false_alignment_with_nonempty_evidence_fails_structural_validation():
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
        _run(client)
    assert len(client.calls) == 1


def test_live_shape_alias_with_ungrounded_nested_values_governed_by_top_level(
    caplog,
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
            curriculum_context=curriculum_text,
        )
    assert len(client.calls) == 1
    assert result.success is True
    assert result.criterion_scores[0].score == 3
    assert result.provenance["grounding_rejected_count"] == 0
    assert result.criterion_scores[0].evidence == (
        "Official curriculum outcome: Systems Architecture.",
    )


def test_invalid_outputs_make_exactly_one_call_no_retry():
    client = Client({"invalid": "json payload"})
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client)
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


# ---------------------------------------------------------------------------
# Phase-3 Snapshot Adapter & Validation Tests
# ---------------------------------------------------------------------------


def test_snapshot_title_and_guidance_used_in_output_and_prompt():
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
    eval_id = uuid.uuid4()
    snapshot = _make_snapshot(
        eval_id=eval_id,
        criterion_code="A-05",
        title="Authoritative Syllabus Alignment",
        description="Assesses syllabus alignment against approved competencies.",
        scoring_rule="High ratio gives 4, zero gives 1.",
        guidance="Specific coordinator syllabus guidance token 12345.",
    )
    result = _run(client, form_snapshot=snapshot, evaluation_id=eval_id)
    assert len(client.calls) == 1
    prompt = client.calls[0][0]

    # Evaluator instructions delimited in prompt
    assert "=== EVALUATOR CRITERION INSTRUCTIONS ===" in prompt
    assert "Rubric Criterion A-05: Authoritative Syllabus Alignment" in prompt
    assert (
        "Description: Assesses syllabus alignment against approved competencies."
        in prompt
    )
    assert "Scoring Rule: High ratio gives 4, zero gives 1." in prompt
    assert "Guidance: Specific coordinator syllabus guidance token 12345." in prompt
    assert "=== END EVALUATOR CRITERION INSTRUCTIONS ===" in prompt

    # Untrusted delimiters
    assert "=== UNTRUSTED AUTHORITATIVE SLM TEXT ===" in prompt
    assert "=== UNTRUSTED EXACT PRECOMPUTED CURRICULUM CONTEXT ===" in prompt

    # CriterionScore code and title come directly from snapshot
    assert result.criterion_scores[0].criterion_id == "A-05"
    assert (
        result.criterion_scores[0].criterion_title == "Authoritative Syllabus Alignment"
    )
    assert result.criterion_scores[0].score == 4


def test_missing_form_snapshot_fails_before_llm_call():
    client = Client(_COORDINATOR_PAYLOAD)
    with pytest.raises(AgentExecutionError, match="EvaluationFormSnapshotDTO"):
        Coordinator(llm_client=client).run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=[{"text": "SLM"}],
            canonical_source_text="SLM",
            curriculum_id=uuid.uuid4(),
            curriculum_context="Curriculum text",
            form_snapshot=None,  # type: ignore[arg-type]
        )
    assert len(client.calls) == 0


def test_wrong_agent_id_snapshot_fails_before_llm_call():
    client = Client(_COORDINATOR_PAYLOAD)
    eval_id = uuid.uuid4()
    # Build a snapshot for 'gad' instead of 'coordinator'
    gad_crit = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="GAD-01",
        title="GAD Criterion",
        description="GAD description",
        scoring_rule="Scoring rule",
        display_order=0,
        strategy_config=CountBandConfig(
            mode="maximum_count",
            threshold_4=0,
            threshold_3=1,
            threshold_2=2,
        ),
    )
    gad_form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="GAD Form",
        version_number=1,
        adapter_key="gad",
        adapter_version=1,
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="DOM-01",
                title="Domain 1",
                display_order=0,
                criteria=(gad_crit,),
            ),
        ),
    )
    snapshot = build_evaluation_form_snapshot(eval_id, gad_form)

    with pytest.raises(AgentExecutionError, match="agent_id 'gad' does not match"):
        Coordinator(llm_client=client).run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            chunk_infos=[{"text": "SLM"}],
            canonical_source_text="SLM",
            curriculum_id=uuid.uuid4(),
            curriculum_context="Curriculum text",
            form_snapshot=snapshot,
        )
    assert len(client.calls) == 0


def test_evaluation_id_mismatch_snapshot_fails_before_llm_call():
    client = Client(_COORDINATOR_PAYLOAD)
    eval_id_run = uuid.uuid4()
    eval_id_snapshot = uuid.uuid4()
    snapshot = _make_snapshot(eval_id=eval_id_snapshot)

    with pytest.raises(AgentExecutionError, match="Snapshot evaluation_id"):
        Coordinator(llm_client=client).run(
            evaluation_id=eval_id_run,
            document_id=uuid.uuid4(),
            chunk_infos=[{"text": "SLM"}],
            canonical_source_text="SLM",
            curriculum_id=uuid.uuid4(),
            curriculum_context="Curriculum text",
            form_snapshot=snapshot,
        )
    assert len(client.calls) == 0


def test_tampered_wrong_criterion_code_snapshot_fails_before_llm_call():
    client = Client(_COORDINATOR_PAYLOAD)
    eval_id = uuid.uuid4()
    snapshot = _make_snapshot(eval_id=eval_id, criterion_code="A-01")

    with pytest.raises(
        AgentExecutionError, match="criterion must be 'A-05', found 'A-01'"
    ):
        Coordinator(llm_client=client).run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            chunk_infos=[{"text": "SLM"}],
            canonical_source_text="SLM",
            curriculum_id=uuid.uuid4(),
            curriculum_context="Curriculum text",
            form_snapshot=snapshot,
        )
    assert len(client.calls) == 0


def test_multiple_criteria_snapshot_fails_before_llm_call():
    client = Client(_COORDINATOR_PAYLOAD)
    eval_id = uuid.uuid4()
    crit1 = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="A-05",
        title="A-05 Title",
        description="A-05 Desc",
        scoring_rule=None,
        display_order=0,
        strategy_config=CurriculumAlignmentConfig(guidance="g1"),
    )
    crit2 = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="A-06",
        title="A-06 Title",
        description="A-06 Desc",
        scoring_rule=None,
        display_order=1,
        strategy_config=CurriculumAlignmentConfig(guidance="g2"),
    )
    snapshot = _make_snapshot(eval_id=eval_id, criteria=(crit1, crit2))

    with pytest.raises(
        AgentExecutionError, match="must contain exactly 1 criterion, found 2"
    ):
        Coordinator(llm_client=client).run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            chunk_infos=[{"text": "SLM"}],
            canonical_source_text="SLM",
            curriculum_id=uuid.uuid4(),
            curriculum_context="Curriculum text",
            form_snapshot=snapshot,
        )
    assert len(client.calls) == 0


def test_wrong_strategy_config_snapshot_fails_before_llm_call():
    client = Client(_COORDINATOR_PAYLOAD)
    eval_id = uuid.uuid4()
    count_strategy = CountBandConfig(
        mode="maximum_count",
        threshold_4=0,
        threshold_3=1,
        threshold_2=2,
    )
    snapshot = _make_snapshot(
        eval_id=eval_id,
        criterion_code="A-05",
        strategy_config=count_strategy,
    )

    with pytest.raises(
        AgentExecutionError,
        match="strategy must be CurriculumAlignmentConfig, found CountBandConfig",
    ):
        Coordinator(llm_client=client).run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            chunk_infos=[{"text": "SLM"}],
            canonical_source_text="SLM",
            curriculum_id=uuid.uuid4(),
            curriculum_context="Curriculum text",
            form_snapshot=snapshot,
        )
    assert len(client.calls) == 0


def test_frozen_dto_immutability_behavior():
    eval_id = uuid.uuid4()
    snapshot = _make_snapshot(eval_id=eval_id)
    with pytest.raises(ValidationError):
        snapshot.agent_id = "modified"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        snapshot.snapshot_payload.agent_id = "modified"  # type: ignore[misc]


def test_revision_2_a05_parity():
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
                    "evidence": "Official curriculum outcome",
                },
                {"objective_id": 2, "is_addressed": False, "evidence": ""},
            ],
        }
    )
    eval_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    snapshot = _make_snapshot(
        eval_id=eval_id,
        criterion_code="A-05",
        title="Curriculum Alignment A-05",
    )
    result = _run(
        client,
        form_snapshot=snapshot,
        evaluation_id=eval_id,
        document_id=doc_id,
    )
    assert result.agent_name == "coordinator"
    assert result.evaluation_id == eval_id
    assert result.document_id == doc_id
    assert result.success is True
    assert len(result.criterion_scores) == 1
    assert result.criterion_scores[0].criterion_id == "A-05"
    assert result.criterion_scores[0].criterion_title == "Curriculum Alignment A-05"
    assert result.criterion_scores[0].score == 3
    assert result.subtotal == 3.0
    assert result.provenance == {
        "requested_model": "assigned",
        "actual_model": "assigned",
        "fallback_occurred": False,
        "extraction_calls": 1,
        "summary_calls": 0,
        "grounding_rejected_count": 0,
    }
    assert result.summary.startswith("Objective-curriculum alignment:")
    assert len(client.calls) == 1


# ---------------------------------------------------------------------------
# Council Remediation: Substring Grounding, Duplicate Rejection & Envelope Bounds
# ---------------------------------------------------------------------------


def test_hallucinated_or_paraphrased_objective_rejected_before_scoring():
    client = Client(
        {
            "objectives": [
                {
                    "id": 1,
                    "text": "Completely hallucinated objective not in SLM text",
                }
            ],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(
            client,
            canonical_source_text="Actual SLM content describing topics.",
            context_text="Actual SLM content describing topics.",
        )
    assert len(client.calls) == 1


def test_exact_source_objective_accepted():
    exact_obj_text = "Master object-oriented programming concepts"
    slm_text = f"Course Syllabus: 1. {exact_obj_text}. 2. Practical exercises."
    client = Client(
        {
            "objectives": [{"id": 1, "text": exact_obj_text}],
            "curriculum_alignment": [
                {
                    "objective_id": 1,
                    "is_addressed": True,
                    "evidence": "Master object-oriented programming concepts",
                }
            ],
        }
    )
    result = _run(
        client,
        canonical_source_text=slm_text,
        context_text=slm_text,
        curriculum_context=(
            "Authoritative curriculum: Master object-oriented programming concepts"
        ),
    )
    assert result.success is True
    assert result.criterion_scores[0].score == 4


def test_case_mismatched_or_fuzzy_objective_rejected():
    exact_obj_text = "Master object-oriented programming concepts"
    slm_text = f"Course Syllabus: 1. {exact_obj_text}."
    # Objective text has lowercase 'master' -> exact codepoint matching must reject
    client = Client(
        {
            "objectives": [
                {"id": 1, "text": "master object-oriented programming concepts"}
            ],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(
            client,
            canonical_source_text=slm_text,
            context_text=slm_text,
        )


@pytest.mark.parametrize(
    "dup_pair",
    [
        (
            "Implement binary search",
            "implement binary search",
        ),  # casefold difference
        (
            "Implement binary search",
            "Implement   binary   search",
        ),  # whitespace collapse
        (
            "Implement binary search",
            "  IMPLEMENT   BINARY SEARCH  ",
        ),  # both
    ],
)
def test_normalized_duplicate_objectives_rejected(dup_pair):
    slm_text = f"Module content: {dup_pair[0]} and also {dup_pair[1]}."
    client = Client(
        {
            "objectives": [
                {"id": 1, "text": dup_pair[0]},
                {"id": 2, "text": dup_pair[1]},
            ],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""},
                {"objective_id": 2, "is_addressed": False, "evidence": ""},
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(
            client,
            canonical_source_text=slm_text,
            context_text=slm_text,
        )


def test_duplicate_json_keys_rejected():
    dup_keys_raw = (
        '{"objectives": [{"id": 1, "text": "SLM Objective"}], '
        '"objectives": [{"id": 1, "text": "SLM Objective"}], '
        '"curriculum_alignment": ['
        '{"objective_id": 1, "is_addressed": False, "evidence": ""}]}'
    )

    class RawClient(Client):
        def generate_result(self, prompt, **kwargs):
            self.calls.append((prompt, kwargs))
            return CompletionResult(dup_keys_raw, self.model, "stop")

    with pytest.raises((ValueError, AgentExecutionError)):
        _run(RawClient())


def test_duplicate_inner_json_keys_rejected():
    dup_inner_raw = (
        '{"objectives": [{"id": 1, "id": 1, "text": "SLM Objective"}], '
        '"curriculum_alignment": ['
        '{"objective_id": 1, "is_addressed": False, "evidence": ""}]}'
    )

    class RawClient(Client):
        def generate_result(self, prompt, **kwargs):
            self.calls.append((prompt, kwargs))
            return CompletionResult(dup_inner_raw, self.model, "stop")

    with pytest.raises((ValueError, AgentExecutionError)):
        _run(RawClient())


def test_oversized_objective_text_rejected():
    oversized_text = "A" * (extraction.COORDINATOR_TEXT_MAX + 1)
    slm_text = f"Content: {oversized_text}"
    client = Client(
        {
            "objectives": [{"id": 1, "text": oversized_text}],
            "curriculum_alignment": [
                {"objective_id": 1, "is_addressed": False, "evidence": ""}
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(
            client,
            canonical_source_text=slm_text,
            context_text=slm_text,
        )


def test_oversized_curriculum_evidence_rejected():
    oversized_evidence = "E" * (extraction.COORDINATOR_TEXT_MAX + 1)
    client = Client(
        {
            "objectives": [{"id": 1, "text": "SLM Objective"}],
            "curriculum_alignment": [
                {
                    "objective_id": 1,
                    "is_addressed": True,
                    "evidence": oversized_evidence,
                }
            ],
        }
    )
    with pytest.raises((ValueError, AgentExecutionError)):
        _run(client)


@pytest.mark.parametrize(
    ("objective", "evidence", "message"),
    [
        (
            " Understand sorting algorithms ",
            "Official curriculum outcome",
            "objective text grounding or length",
        ),
        (
            "Understand sorting algorithms",
            " Official curriculum outcome ",
            "evidence must be trimmed",
        ),
    ],
)
def test_objective_and_alignment_evidence_must_arrive_trimmed(
    objective, evidence, message
):
    client = Client(
        {
            "objectives": [{"id": 1, "text": objective}],
            "curriculum_alignment": [
                {
                    "objective_id": 1,
                    "is_addressed": True,
                    "evidence": evidence,
                }
            ],
        }
    )

    with pytest.raises(ValueError, match=message):
        _run(client, canonical_source_text=" Understand sorting algorithms ")
