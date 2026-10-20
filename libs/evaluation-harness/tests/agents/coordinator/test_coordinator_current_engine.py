"""Offline public-contract tests for the current Coordinator engine."""

from __future__ import annotations

import json
from dataclasses import replace
from uuid import uuid4

import pytest
from equiped_harness import (
    CompletionResult,
    EvaluationRequest,
    ExecutionConfig,
    evaluate,
)
from equiped_harness.agents.coordinator.task_execution import _parse_json
from equiped_harness.agents.coordinator.validation import validate_coordinator_coverage
from equiped_harness.contracts import (
    CountBandConfig,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    ObjectiveGaugingConfig,
    RatioBandConfig,
)
from equiped_harness.contracts.snapshots import build_evaluation_form_snapshot
from equiped_harness.exceptions import AgentExecutionError

SOURCE = (
    "Learning Objectives:\n1. Explain arrays.\n2. Apply arrays.\n3. Compare arrays.\n"
    "4. Design arrays.\n5. Evaluate arrays.\nAssessment Tasks:\n"
    "Task one applies arrays. Task two compares arrays.\n"
)


def _prompt_context(user_context: str) -> dict:
    """Read the current task's labeled rubric/source context blocks."""
    rubric_marker = "=== UNTRUSTED RUBRIC CONTEXT ===\n"
    source_marker = "\n=== UNTRUSTED SOURCE CONTEXT ===\n"
    if rubric_marker in user_context:
        rubric_text, source_text = user_context.split(source_marker, 1)
        rubric_text = rubric_text.removeprefix(rubric_marker).split(
            "\n=== END UNTRUSTED RUBRIC CONTEXT ===", 1
        )[0]
        source_text = source_text.split("\n=== END UNTRUSTED SOURCE CONTEXT ===", 1)[0]
        return {**json.loads(rubric_text), **json.loads(source_text)}
    return json.loads(user_context)


class CurrentFake:
    model = "fake"

    def __init__(self, *, invalid_first: bool = False):
        self.calls = 0
        self.invalid_first = invalid_first
        self.first_context = None
        self.prompts = []

    def generate_result(self, prompt, **kwargs):
        self.calls += 1
        self.prompts.append(prompt)
        if self.calls == 1:
            self.first_context = _prompt_context(prompt.user_context)
        try:
            context = _prompt_context(prompt.user_context)
        except json.JSONDecodeError:
            context = self.first_context
        if self.invalid_first and self.calls == 2:
            return CompletionResult(json.dumps({"results": []}), "fake")
        if self.invalid_first and self.calls == 1:
            payload = {
                "results": [{"criteria": ["Topics are coherent from Unit to Chapter."]}]
            }
            return CompletionResult(json.dumps(payload), "fake")
        task_id = context["task_id"]
        if task_id == "objective-assessment":
            objective_ids = [row["objective_id"] for row in context["objectives"]]
            source_id = context["source_catalog"][0]["source_id"]
            rows = [
                {"objective_id": oid, "source_ids": [source_id]}
                for oid in objective_ids[:4]
            ]
            rows += [{"objective_id": objective_ids[4], "source_ids": []}]
            payload = {"results": rows}
        elif task_id == "curriculum":
            objective_ids = [row["objective_id"] for row in context["objectives"]]
            source_id = context["source_catalog"][0]["source_id"]
            payload = {
                "results": [
                    {"objective_id": oid, "source_ids": [source_id]}
                    for oid in objective_ids
                ]
            }
        else:
            rows = []
            for shape in context["row_shapes"]:
                if "score" in shape:
                    rows.append(
                        {"status": "supported", "score": 4, "evidence_id": "slm-0001"}
                    )
                elif "instance_ids" in shape:
                    rows.append({"status": "supported", "instance_ids": ["slm-0001"]})
                else:
                    rows.append(
                        {
                            "status": "supported",
                            "unit_ids": ["slm-0001"],
                            "qualifying_unit_ids": ["slm-0001"],
                        }
                    )
            payload = {"results": rows}
        return CompletionResult(json.dumps(payload), "fake")


def request(*, source: str = SOURCE) -> EvaluationRequest:
    strategies = (
        RatioBandConfig(threshold_4=80, threshold_3=50, threshold_2=20),
        CountBandConfig(threshold_4=3, threshold_3=2, threshold_2=1),
        LlmRubricGuidanceConfig(guidance="Judge the source."),
        RatioBandConfig(threshold_4=80, threshold_3=50, threshold_2=20),
        CountBandConfig(threshold_4=3, threshold_3=2, threshold_2=1),
        RatioBandConfig(threshold_4=80, threshold_3=50, threshold_2=20),
        CountBandConfig(threshold_4=3, threshold_3=2, threshold_2=1),
        RatioBandConfig(threshold_4=80, threshold_3=50, threshold_2=20),
        CountBandConfig(threshold_4=3, threshold_3=2, threshold_2=1),
        ObjectiveGaugingConfig(),
    )
    criteria = tuple(
        CriterionDefinition(
            rubric_criterion_id=uuid4(),
            criterion_code=code,
            title=code,
            description=code,
            display_order=index,
            strategy_config=strategy,
        )
        for index, (code, strategy) in enumerate(
            zip(
                tuple(f"OP-{i:02d}" for i in range(1, 6))
                + tuple(f"A-{i:02d}" for i in range(1, 6)),
                strategies,
                strict=True,
            )
        )
    )
    form = FormDefinition(
        rubric_set_id=uuid4(),
        name="Coordinator",
        agent_id="coordinator",
        adapter_key="coordinator",
        adapter_version=3,
        version_number=5,
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid4(),
                code="coord",
                title="Coordinator",
                display_order=1,
                criteria=criteria,
            ),
        ),
    )
    evaluation_id = uuid4()
    return EvaluationRequest(
        evaluation_id=evaluation_id,
        document_id=uuid4(),
        form_snapshot=build_evaluation_form_snapshot(evaluation_id, form),
        chunk_infos=({"chunk_id": "chunk-1", "text": source},),
        canonical_source_text=source,
        curriculum_id=uuid4(),
        curriculum_context="Arrays are applied in programming tasks.",
    )


def test_current_matrix_scores_and_persists_contract_facts():
    client = CurrentFake()
    result = evaluate(request(), client, ExecutionConfig())
    assert result.metadata["execution_contract"] == "coordinator_current.v1"
    assert [score.criterion_id for score in result.criterion_scores] == [
        *(f"OP-{i:02d}" for i in range(1, 6)),
        *(f"A-{i:02d}" for i in range(1, 6)),
    ]
    assert (
        next(
            score for score in result.criterion_scores if score.criterion_id == "A-05"
        ).score
        == 4
    )
    validate_coordinator_coverage(result)
    assert result.advisory_outputs.score == 4
    assert client.calls == 11
    ordinary = [
        generation
        for generation in result.generations
        if generation.unit_key.startswith("ordinary-")
    ]
    assert [generation.unit_key for generation in ordinary] == [
        *(f"ordinary-OP-{i:02d}" for i in range(1, 6)),
        *(f"ordinary-A-{i:02d}" for i in range(1, 5)),
    ]
    assert all(len(generation.criterion_ids) == 1 for generation in ordinary)
    assert all(
        len(_prompt_context(generation.prompt_messages[1]["content"])["criteria"]) == 1
        for generation in ordinary
    )
    assert result.metadata["envelope_status"]["ordinary-OP-01"] == "ok"
    assert result.provenance["grouped_calls"] == 11


def test_current_prompt_contains_strategy_specific_canonical_shapes():
    client = CurrentFake()
    result = evaluate(request(), client, ExecutionConfig())

    ordinary_system = {
        generation.unit_key: generation.prompt_messages[0]["content"]
        for generation in result.generations
        if generation.unit_key.startswith("ordinary-")
    }
    assert (
        '{"results":[{"status":"supported","score":3,"evidence_id":"slm-0001"}]}'
        in ordinary_system["ordinary-OP-03"]
    )
    assert (
        '{"results":[{"status":"supported","instance_ids":["slm-0001"]}]}'
        in ordinary_system["ordinary-OP-02"]
    )
    assert (
        '{"results":[{"status":"supported","unit_ids":["slm-0001"],'
        '"qualifying_unit_ids":["slm-0001"]}]}' in ordinary_system["ordinary-OP-01"]
    )
    assert all(
        "untrusted reference data" in system and "criteria key" in system
        for system in ordinary_system.values()
    )
    assert all(
        "=== UNTRUSTED RUBRIC CONTEXT ===" in prompt.user_context
        and "=== UNTRUSTED SOURCE CONTEXT ===" in prompt.user_context
        for prompt in client.prompts
    )


def test_current_no_assessment_scores_a05_one_but_curriculum_runs():
    source = "Learning Objectives:\n1. Explain arrays.\nReferences:\nBook.\n"
    client = CurrentFake()
    result = evaluate(request(source=source), client, ExecutionConfig())
    assert (
        next(
            score for score in result.criterion_scores if score.criterion_id == "A-05"
        ).score
        == 1
    )
    assert result.advisory_outputs.score == 4
    assert "objective-assessment" not in result.metadata["group_responses"]


class FencedCurrentFake(CurrentFake):
    """Model-shaped client that wraps every valid response in one JSON fence."""

    def generate_result(self, prompt, **kwargs):
        result = super().generate_result(prompt, **kwargs)
        return CompletionResult(f"```json\n{result.content}\n```", "fake")


class BareObjectiveRowsFake(CurrentFake):
    """Model-shaped client that omits only the objective task wrapper."""

    def generate_result(self, prompt, **kwargs):
        result = super().generate_result(prompt, **kwargs)
        context = _prompt_context(prompt.user_context)
        if context["task_id"] in {"objective-assessment", "curriculum"}:
            payload = json.loads(result.content)
            result = CompletionResult(json.dumps(payload["results"]), "fake")
        return CompletionResult(f"```json\n{result.content}\n```", "fake")


def test_current_engine_accepts_fenced_valid_responses_without_repair():
    client = FencedCurrentFake()
    result = evaluate(request(), client, ExecutionConfig())

    assert result.success is True
    assert client.calls == 11
    assert result.provenance["repair_occurred"] is False
    assert result.processing_seconds > 0
    assert all(status == "ok" for status in result.metadata["envelope_status"].values())


def test_current_engine_normalizes_bare_objective_rows():
    client = BareObjectiveRowsFake()
    result = evaluate(request(), client, ExecutionConfig())

    assert result.success is True
    assert client.calls == 11
    assert result.provenance["repair_occurred"] is False


def test_current_engine_requires_document_chunks():
    client = CurrentFake()
    with pytest.raises(AgentExecutionError, match="document chunks"):
        evaluate(
            replace(request(), chunk_infos=()),
            client,
            ExecutionConfig(),
        )
    assert client.calls == 0


@pytest.mark.parametrize(
    "response",
    [
        '{"results":[]}',
        '```json\n{"results":[]}\n```',
        '```\n{"results":[]}\n```',
        '  ``` JsOn \n {"results":[]} \n```  ',
    ],
)
def test_current_parser_accepts_bare_and_single_full_json_fences(response):
    assert _parse_json(response) == {"results": []}


@pytest.mark.parametrize(
    "response",
    [
        '```json\n{"results":[],"results":[]}\n```',
        '```json\n{"results":[]\n```',
        'prose {"results":[]}',
        '```json\n{"results":[]}\n```\n```json\n{"results":[]}\n```',
    ],
)
def test_current_parser_rejects_invalid_fences_and_prose(response):
    with pytest.raises(AgentExecutionError):
        _parse_json(response)


class FencedRepairFake(CurrentFake):
    def generate_result(self, prompt, **kwargs):
        result = super().generate_result(prompt, **kwargs)
        if self.calls == 1:
            return CompletionResult('```json\n{"results":[]}\n```', "fake")
        return CompletionResult(f"```\n{result.content}\n```", "fake")


def test_public_evaluate_accepts_fenced_initial_and_repair_responses():
    client = FencedRepairFake()
    result = evaluate(request(), client, ExecutionConfig())

    assert result.provenance["repair_occurred"] is True
    assert result.provenance["grouped_calls"] == 11
    assert client.calls == 12
    assert result.metadata["envelope_status"]["ordinary-OP-01"] == "repaired"


def test_current_malformed_criteria_row_gets_one_bounded_repair_only():
    client = CurrentFake(invalid_first=True)
    with pytest.raises(AgentExecutionError):
        evaluate(request(), client, ExecutionConfig())
    assert client.calls == 2
    assert len(client.prompts[1].system_instruction) < 2_000
    assert (
        '{"results":[{"status":"supported","unit_ids":["slm-0001"],'
        '"qualifying_unit_ids":["slm-0001"]}]}' in client.prompts[1].system_instruction
    )
    assert "criteria key" in client.prompts[1].system_instruction


class EmptyMeasurementsFake(CurrentFake):
    def generate_result(self, prompt, **kwargs):
        response = super().generate_result(prompt, **kwargs)
        context = _prompt_context(prompt.user_context)
        if context["task_id"].startswith("ordinary-"):
            data = json.loads(response.content)
            row = data["results"][0]
            if "instance_ids" in row:
                row = {"status": "absent", "instance_ids": []}
            elif "unit_ids" in row:
                row = {"status": "absent", "unit_ids": [], "qualifying_unit_ids": []}
            data["results"] = [row]
            return CompletionResult(json.dumps(data), "fake")
        return response


def test_absent_count_and_ratio_evidence_scores_one_and_survives_replay():
    client = EmptyMeasurementsFake()
    result = evaluate(request(), client, ExecutionConfig())
    validate_coordinator_coverage(result)
    assert all(
        s.score == 1
        for s in result.criterion_scores
        if s.criterion_id not in {"OP-03", "A-05"}
    )
    assert client.calls == 11


class UnqualifiedRatioFake(CurrentFake):
    def generate_result(self, prompt, **kwargs):
        response = super().generate_result(prompt, **kwargs)
        data = json.loads(response.content)
        for row in data["results"]:
            if "qualifying_unit_ids" in row:
                row["qualifying_unit_ids"] = []
        return CompletionResult(json.dumps(data), "fake")


def test_frozen_short_sample_scoring_survives_current_bundle_replay():
    from equiped_harness.contracts import ShortSampleConfig

    original = request()
    form = original.form_snapshot.form
    domains = tuple(
        d.model_copy(
            update={
                "criteria": tuple(
                    c.model_copy(
                        update={
                            "strategy_config": c.strategy_config.model_copy(
                                update={
                                    "short_sample": ShortSampleConfig(
                                        min_units=4,
                                        max_issues_4=0,
                                        max_issues_3=1,
                                        max_issues_2=2,
                                    )
                                }
                            )
                        }
                    )
                    if isinstance(c.strategy_config, RatioBandConfig)
                    else c
                    for c in d.criteria
                )
            }
        )
        for d in form.domains
    )
    snapshot = build_evaluation_form_snapshot(
        original.evaluation_id, form.model_copy(update={"domains": domains})
    )
    result = evaluate(
        replace(original, form_snapshot=snapshot),
        UnqualifiedRatioFake(),
        ExecutionConfig(),
    )
    assert (
        next(s.score for s in result.criterion_scores if s.criterion_id == "OP-01") == 3
    )
    validate_coordinator_coverage(result)
