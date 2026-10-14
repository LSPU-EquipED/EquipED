"""Installed-package pipelines run without backend settings, transport, or retrieval."""

import json
from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest
from equiped_harness import (
    AgentEvaluationResult,
    CompletionResult,
    EvaluationRequest,
    ExecutionConfig,
    ResponseContract,
    envelope_criteria_map_from_snapshot,
    evaluate,
    execution_scope,
)
from equiped_harness.config import current_execution_config
from equiped_harness.contracts import (
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    ObjectiveGaugingConfig,
)
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.scoring import validate_coordinator_coverage
from equiped_harness.snapshot_contracts import build_evaluation_form_snapshot

SOURCE = (
    "Learning Objectives:\n1. Add integers.\nAssessment:\n"
    "Compute 2 + 2.\nReferences:\nA book.\n"
)
CURRICULUM = "Students add integers."


class FakeClient:
    model = "requested"

    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.calls = []

    def generate_result(
        self,
        prompt,
        *,
        temperature,
        max_new_tokens,
        deadline=None,
        response_contract=None,
    ):
        assert isinstance(response_contract, ResponseContract)
        self.calls.append(
            (prompt, temperature, max_new_tokens, deadline, response_contract)
        )
        return CompletionResult(
            json.dumps(next(self.payloads)),
            "served",
            2,
            3,
            5,
            "stop",
            attempts=2,
        )


def prepared_request(agent):
    codes = {
        "sme": ("SME-01",),
        "gad": ("GAD-01",),
        "itso": tuple(f"ITSO-{i:02d}" for i in range(1, 6)),
        "coordinator": tuple(f"OP-{i:02d}" for i in range(1, 6))
        + tuple(f"A-{i:02d}" for i in range(1, 6)),
    }[agent]
    criteria = tuple(
        CriterionDefinition(
            rubric_criterion_id=uuid4(),
            criterion_code=code,
            title=code,
            description=code,
            display_order=i,
            strategy_config=ObjectiveGaugingConfig()
            if agent == "coordinator" and code == "A-05"
            else LlmRubricGuidanceConfig(guidance="Use verbatim evidence."),
        )
        for i, code in enumerate(codes)
    )
    version = {"sme": 1, "gad": 2, "itso": 1, "coordinator": 3}[agent]
    form = FormDefinition(
        rubric_set_id=uuid4(),
        name=agent,
        agent_id=agent,
        adapter_key=agent,
        adapter_version=version,
        version_number=1,
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid4(),
                code="D1",
                title="Domain",
                display_order=1,
                criteria=criteria,
            ),
        ),
    )
    evaluation_id = uuid4()
    snapshot = build_evaluation_form_snapshot(evaluation_id, form)
    request = EvaluationRequest(
        evaluation_id=evaluation_id,
        document_id=uuid4(),
        form_snapshot=snapshot,
        chunk_infos=({"chunk_id": "c1", "text": SOURCE},),
        canonical_source_text=SOURCE,
        curriculum_id=uuid4(),
        curriculum_context=CURRICULUM,
        prompt_version_id=uuid4(),
    )
    if agent in {"sme", "coordinator"}:
        payloads = []
        for packed in envelope_criteria_map_from_snapshot(snapshot, agent).values():
            if agent == "coordinator" and packed[0].criterion_code == "A-05":
                payloads.append(
                    {
                        "objective_matches": [
                            {
                                "objective_id": "OBJ-0001",
                                "assessment_matched": True,
                                "assessment_excerpt": "Compute 2 + 2.",
                                "curriculum_matched": True,
                                "curriculum_excerpt": CURRICULUM,
                            }
                        ]
                    }
                )
            else:
                payloads.append(
                    {
                        "summary": "Supported.",
                        "criterion_measurements": [
                            {
                                "criterion_id": c.criterion_code,
                                "criterion_title": c.title,
                                "score": 4,
                                "evidence": "Compute 2 + 2.",
                                "reasoning": "Supported.",
                            }
                            for c in packed
                        ],
                    }
                )
    elif agent == "gad":
        payloads = [
            {
                "gad-01": {
                    "score": 4,
                    "evidence": "Compute 2 + 2.",
                    "chunk_id": "c1",
                    "reasoning": "Supported.",
                    "summary": "Supported.",
                }
            }
        ]
    else:
        payloads = [
            {
                "summary": "Supported.",
                "criterion_scores": [
                    {
                        "criterion_id": c.criterion_code,
                        "criterion_title": c.title,
                        "score": 3,
                        "justification": "Supported.",
                        "chunk_ids": ["c1"],
                        "evidence": ["Compute 2 + 2."],
                    }
                    for c in criteria
                ],
            }
        ]
    return request, payloads


@pytest.mark.parametrize("agent", ["sme", "coordinator", "gad", "itso"])
def test_public_evaluate_runs_actual_specialist(agent):
    request, payloads = prepared_request(agent)
    client = FakeClient(payloads)
    config = ExecutionConfig(
        llm_temperature=0.37, llm_temperature_itso=0.12, llm_max_new_tokens=777
    )
    result = evaluate(request, client, config)
    assert isinstance(result, AgentEvaluationResult)
    assert result.success and result.agent_name == agent
    assert result.evaluation_id == request.evaluation_id
    assert result.document_id == request.document_id
    assert result.prompt_version_id == request.prompt_version_id
    assert result.model_name == "served"
    assert len(result.criterion_scores) == len(request.form_snapshot.criterion_codes)
    expected_temperature = (
        0.0 if agent == "gad" else config.get_agent_temperature(agent)
    )
    assert all(
        call[1] == expected_temperature and call[2] == 777 for call in client.calls
    )
    assert len(result.generations) == len(client.calls)
    if agent == "coordinator":
        assert len(result.criterion_scores) == 10
        assert "C-01" not in {s.criterion_id for s in result.criterion_scores}
        assert result.advisory_outputs.criterion_id == "C-01"
        validate_coordinator_coverage(result)


def test_public_coordinator_evaluate_uses_complete_five_objective_inventory():
    request, payloads = prepared_request("coordinator")
    source = (
        "Lesson Learning Outcomes\nIntended Learning Outcomes\n"
        "At the end of this lesson, the students should be able to:\n"
        "• Identify a concept.\n• Explain a concept.\n• Compare examples.\n"
        "• Apply a method.\n• Evaluate a result.\n"
        "Student Learning Strategies\nGroup discussion.\nAssessment Tasks\n"
        "Task A.\nTask B.\n"
    )
    request = replace(
        request,
        canonical_source_text=source,
        chunk_infos=({"chunk_id": "c1", "text": source},),
    )
    payloads = []
    for packed in envelope_criteria_map_from_snapshot(
        request.form_snapshot, "coordinator"
    ).values():
        if packed[0].criterion_code == "A-05":
            payloads.append(
                {
                    "objective_matches": [
                        {
                            "objective_id": f"OBJ-{i:04}",
                            "assessment_matched": i <= 2,
                            "assessment_excerpt": "Task A."
                            if i == 1
                            else "Task B."
                            if i == 2
                            else "",
                            "curriculum_matched": i <= 4,
                            "curriculum_excerpt": CURRICULUM if i <= 4 else "",
                        }
                        for i in range(1, 6)
                    ]
                }
            )
        else:
            payloads.append(
                {
                    "summary": "Supported.",
                    "criterion_measurements": [
                        {
                            "criterion_id": c.criterion_code,
                            "criterion_title": c.title,
                            "score": 4,
                            "evidence": "Task A.",
                            "reasoning": "Supported.",
                        }
                        for c in packed
                    ],
                }
            )
    result = evaluate(request, FakeClient(payloads), ExecutionConfig())
    assert len(result.criterion_scores) == 10
    assert [row.criterion_id for row in result.criterion_scores].count("A-05") == 1
    assert len(result.advisory_outputs.objective_matches) == 5
    assert [row.objective_id for row in result.advisory_outputs.objective_matches] == [
        f"OBJ-{i:04}" for i in range(1, 6)
    ]
    a05 = next(row for row in result.criterion_scores if row.criterion_id == "A-05")
    assert "2/5 objectives supported" in a05.justification
    assert a05.score == 2
    assert result.advisory_outputs.score == 4
    assert result.subtotal == 3.8


def test_request_and_config_are_immutable_and_scope_resets_on_error():
    request, payloads = prepared_request("sme")
    with pytest.raises(TypeError):
        request.chunk_infos[0]["text"] = "mutated"
    with pytest.raises(FrozenInstanceError):
        ExecutionConfig().llm_temperature = 1
    outer = ExecutionConfig(llm_temperature=0.66)
    original = current_execution_config()
    with execution_scope(outer):
        with pytest.raises(AgentExecutionError, match="canonical source text"):
            evaluate(
                replace(request, canonical_source_text=None),
                FakeClient(payloads),
                ExecutionConfig(llm_temperature=0.11),
            )
        assert current_execution_config() is outer
    assert current_execution_config() is original
    with pytest.raises(TypeError, match="explicitly supplied"):
        evaluate(request, None, ExecutionConfig())


def test_repair_uses_same_explicit_controls_and_shared_completion():
    request, payloads = prepared_request("sme")
    client = FakeClient([{}, payloads[0]])
    result = evaluate(request, client, ExecutionConfig(llm_max_new_tokens=321))
    assert result.success and result.provenance["repair_occurred"]
    assert result.provenance["physical_attempts"] == 4
    assert len(client.calls) == 2
    assert all(call[2] == 321 for call in client.calls)


def test_request_copies_all_nested_mappings():
    request, _ = prepared_request("itso")
    nested = {"nested": [{"values": [1, 2]}]}
    request = replace(
        request,
        precomputed_context=nested,
        policy_evidence=nested,
        roadmap_context=nested,
        reference_document_ids=nested,
        provenance=nested,
    )
    nested["nested"][0]["values"].append(3)
    for field in (
        "precomputed_context",
        "policy_evidence",
        "roadmap_context",
        "reference_document_ids",
        "provenance",
    ):
        value = getattr(request, field)
        assert value["nested"][0]["values"] == (1, 2)
        with pytest.raises(TypeError):
            value["nested"][0]["values"] = ()


def test_evaluation_snapshot_binding_still_fails_before_transport():
    request, payloads = prepared_request("sme")
    client = FakeClient(payloads)
    with pytest.raises(AgentExecutionError, match="Snapshot evaluation_id"):
        evaluate(replace(request, evaluation_id=uuid4()), client, ExecutionConfig())
    assert not client.calls


def test_concurrent_scopes_and_exception_reset_are_thread_local():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)
    original = current_execution_config()

    def run(temperature):
        before = current_execution_config()
        config = ExecutionConfig(llm_temperature=temperature)
        with pytest.raises(RuntimeError):
            with execution_scope(config):
                barrier.wait(timeout=3)
                assert current_execution_config() is config
                raise RuntimeError("scope unwind")
        assert current_execution_config() is before
        return before

    with execution_scope(ExecutionConfig(llm_temperature=0.88)):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run, t) for t in (0.11, 0.77)]
            assert all(f.result() is original for f in futures)
        assert current_execution_config().llm_temperature == 0.88
    assert current_execution_config() is original


@pytest.mark.parametrize(
    "prefix",
    [
        "An unnumbered target about the module",
        "At the end of this module,",
        "At the beginning of this module, students should be able to:",
    ],
)
def test_unsupported_objective_prefix_fails_before_model_calls(prefix):
    request, _ = prepared_request("coordinator")
    source = f"Objectives:\n{prefix}\n1. Marked objective.\nAssessment:\nTask A.\n"
    request = replace(
        request,
        canonical_source_text=source,
        chunk_infos=({"chunk_id": "c1", "text": source},),
    )
    client = FakeClient([])
    with pytest.raises(AgentExecutionError):
        evaluate(request, client, ExecutionConfig())
    assert client.calls == []
