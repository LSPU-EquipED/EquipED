"""Strict public-contract coverage for adapter-4 Coordinator rubric judgments."""

from __future__ import annotations

import copy
import json
import runpy
from dataclasses import replace
from pathlib import Path

import pytest
from equiped_harness import CompletionResult, ExecutionConfig, evaluate
from equiped_harness.agents.coordinator.pipeline import (
    response_contract,
    validate_result,
)
from equiped_harness.contracts.snapshots import build_evaluation_form_snapshot
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.runtime.source_retrieval import source_hash

_helpers = runpy.run_path(str(Path(__file__).with_name("test_coordinator_helpers.py")))
rubric_request = _helpers["request"]


def _input(prompt):
    text = prompt.user_context.split("=== REVIEW INPUT ===\n", 1)[1]
    return json.loads(text.split("\n=== END REVIEW INPUT ===", 1)[0])


class RubricFake:
    model = "synthetic-rubric-model"

    def __init__(self, invalid=None):
        self.prompts = []
        self.invalid = invalid

    def generate_result(self, prompt, **_):
        self.prompts.append(prompt)
        context = _input(prompt)
        group = (
            "alignment"
            if context["criteria"][0]["criterion_id"] == "C-01"
            else (
                "organization"
                if context["criteria"][0]["criterion_id"].startswith("OP-")
                else "assessment"
            )
        )
        available = context["sources"]
        ids = [
            next(s["source_id"] for s in available if s["source"] == kind)
            for kind in (("slm", "curriculum") if group == "alignment" else ("slm",))
        ]
        results = [
            {
                "criterion_id": criterion["criterion_id"],
                "score": 2 if self.invalid == "not_found" else 3,
                "finding": (
                    "The reviewed passages show a specific practice and a "
                    "limitation that supports this judgment."
                ),
                "evidence_status": "present",
                "evidence_ids": ids,
            }
            for criterion in context["criteria"]
        ]
        if self.invalid == "missing_reason":
            results[0]["finding"] = ""
        if self.invalid == "missing_id":
            results[0]["evidence_ids"] = ["unknown-source"]
        if self.invalid == "bad_score":
            results[0]["score"] = 4.0
        if self.invalid == "not_found":
            results[0].update(evidence_status="not_found", evidence_ids=[], score=4)
        response = {"results": results}
        if group == "assessment":
            response["summary"] = (
                "The ten official judgments describe demonstrated practices "
                "and their evidence-based limitations. Together they show "
                "uneven coverage across organization and assessment."
            )
            if self.invalid == "missing_summary":
                response["summary"] = ""
        return CompletionResult(json.dumps(response), self.model)


def test_all_ten_rubric_findings_and_summary_are_captured_with_three_native_calls():
    client = RubricFake()
    request = rubric_request()
    result = evaluate(request, client, ExecutionConfig())
    assert len(client.prompts) == 3
    assert len(result.generations) == 3
    assert [len(g.criterion_ids) for g in result.generations] == [5, 5, 1]
    assert result.generations[-1].criterion_ids == ("C-01",)
    assert len(result.criterion_scores) == 10
    assert all(
        len(score.justification.split()) >= 7 for score in result.criterion_scores
    )
    assert len(result.summary) >= 30
    assert result.advisory_outputs.score == 3
    assert (
        tuple(s.criterion_id for s in result.criterion_scores)
        == request.form_snapshot.criterion_codes
    )
    assert result.subtotal == sum(s.score for s in result.criterion_scores) / 10
    assert result.summary
    assert {generation.unit_key for generation in result.generations} == {
        "organization",
        "assessment",
        "alignment",
    }
    assert [g.envelope_status for g in result.generations] == ["ok"] * 3
    assert result.provenance["grouped_calls"] == 3
    for generation in result.generations:
        assert generation.model_name == client.model
        assert generation.prompt_messages
        assert generation.response_json
    validate_result(result, request.form_snapshot)


@pytest.mark.parametrize(
    "invalid",
    ["missing_reason", "missing_summary", "missing_id", "bad_score", "not_found"],
)
def test_invalid_rubric_output_gets_one_repair_then_fails_without_partial_result(
    invalid,
):
    client = RubricFake(invalid=invalid)
    with pytest.raises(AgentExecutionError):
        evaluate(rubric_request(), client, ExecutionConfig())
    if invalid == "missing_reason":
        assert len(client.prompts) == 2
    else:
        assert len(client.prompts) <= 3
    assert client.prompts[-1].user_context != client.prompts[0].user_context


def test_missing_curriculum_fails_before_model_call():
    client = RubricFake()
    with pytest.raises(AgentExecutionError, match="curriculum"):
        evaluate(
            replace(rubric_request(), curriculum_id=None, curriculum_context=None),
            client,
            ExecutionConfig(),
        )
    assert client.prompts == []


def test_retrieval_rejects_wrong_identity_scope_and_offsets_before_model_call():
    request = rubric_request()
    for field, value in (
        ("source_hash", "wrong"),
        ("document_id", "other-document"),
        (
            "rankings",
            {**request.source_retrieval["rankings"], "organization": ["missing"]},
        ),
        ("passages", {"S1": {"start": 0, "end": 801}}),
    ):
        client = RubricFake()
        with pytest.raises(AgentExecutionError):
            evaluate(
                replace(
                    request, source_retrieval={**request.source_retrieval, field: value}
                ),
                client,
                ExecutionConfig(),
            )
        assert client.prompts == []


@pytest.mark.parametrize(
    "mutation",
    [
        "score",
        "narrative",
        "passage_hash",
        "source_kind",
        "lengths",
        "criteria",
        "contract",
        "raw",
        "prompt",
        "summary",
        "status",
    ],
)
def test_saved_result_rejects_tampered_native_evidence_and_reasoning(mutation):
    request = rubric_request()
    result = evaluate(request, RubricFake(), ExecutionConfig())
    changed = copy.deepcopy(result)
    metadata = changed.metadata
    if mutation == "score":
        changed = replace(
            changed,
            criterion_scores=(
                replace(changed.criterion_scores[0], score=4),
                *changed.criterion_scores[1:],
            ),
        )
    elif mutation == "narrative":
        changed = replace(
            changed,
            criterion_scores=(
                replace(
                    changed.criterion_scores[0],
                    justification="Changed narrative that remains long enough to read.",
                ),
                *changed.criterion_scores[1:],
            ),
        )
    elif mutation == "passage_hash":
        metadata["current_bundle"]["packets"]["organization"][0]["text"] += " altered"
    elif mutation == "source_kind":
        metadata["current_bundle"]["packets"]["organization"][0]["source"] = (
            "curriculum"
        )
    elif mutation == "lengths":
        metadata["current_bundle"]["source_identity"]["slm_chars"] += 1
    elif mutation == "criteria":
        changed = replace(changed, generations=changed.generations[:-1])
    elif mutation == "contract":
        metadata["execution_contract"] = "other"
    elif mutation == "raw":
        changed = replace(
            changed,
            generations=(
                replace(changed.generations[0], response_text="{}"),
                *changed.generations[1:],
            ),
        )
    elif mutation == "prompt":
        first = changed.generations[0]
        changed = replace(
            changed,
            generations=(
                replace(first, prompt_text="tampered"),
                *changed.generations[1:],
            ),
        )
    elif mutation == "summary":
        changed = replace(
            changed, summary="tampered summary that remains nonempty and plausible."
        )
    else:
        metadata["envelope_status"]["organization"] = "fallback"
    with pytest.raises((ValueError, AgentExecutionError)):
        validate_result(changed, request.form_snapshot)


def test_genuinely_absent_practice_can_be_reported_with_low_score_and_no_quote():
    class AbsentFake(RubricFake):
        def generate_result(self, prompt, **kwargs):
            result = super().generate_result(prompt, **kwargs)
            context = _input(prompt)
            if context["criteria"][0]["criterion_id"] == "OP-01":
                payload = json.loads(result.content)
                payload["results"][0].update(
                    score=1,
                    evidence_status="not_found",
                    evidence_ids=[],
                    finding=(
                        "No reviewed passage demonstrates the required practice; "
                        "the selected evidence is silent on this specific criterion."
                    ),
                )
                return CompletionResult(json.dumps(payload), self.model)
            return result

    result = evaluate(rubric_request(), AbsentFake(), ExecutionConfig())
    finding = result.metadata["group_responses"]["organization"]["results"][0]
    assert finding["evidence_status"] == "not_found"
    assert finding["evidence_ids"] == []
    assert finding["score"] == 1


def test_assessment_prompt_and_response_contract_include_alignment_goals_and_tasks():
    request = rubric_request()
    source = (
        "GOAL PASSAGE: Learners will compare local ecosystems using field data.\n"
        "TASK PASSAGE: Learners submit a field report comparing two ecosystems.\n"
        "ORG PASSAGE: The module lists its weekly topics and learning resources."
    )
    spans = {
        "goal": (
            0,
            len(
                "GOAL PASSAGE: Learners will compare local ecosystems using field data."
            ),
        ),
    }
    spans["task"] = (
        source.index("TASK PASSAGE"),
        source.index("\nORG PASSAGE"),
    )
    spans["organization"] = (source.index("ORG PASSAGE"), len(source))
    retrieval = {
        **request.source_retrieval,
        "source_hash": source_hash(source),
        "rankings": {
            "organization": ["organization"],
            "assessment": ["task"],
            "alignment": ["goal"],
        },
        "passages": {
            key: {"start": start, "end": end} for key, (start, end) in spans.items()
        },
    }
    request = replace(request, canonical_source_text=source, source_retrieval=retrieval)

    client = RubricFake()
    evaluate(request, client, ExecutionConfig())

    assessment_prompt = next(
        prompt for prompt in client.prompts if "A-01" in prompt.user_context
    )
    assessment_sources = _input(assessment_prompt)["sources"]
    slm_text = "\n".join(
        item["text"] for item in assessment_sources if item["source"] == "slm"
    )
    assert "GOAL PASSAGE" in slm_text
    assert "TASK PASSAGE" in slm_text

    slm_sources = [item for item in assessment_sources if item["source"] == "slm"]
    contract = response_contract("assessment", ("A-01",), slm_sources)
    assert contract.mode == "json_schema"
    evidence_id_enum = contract.schema["properties"]["results"]["items"]["properties"][
        "evidence_ids"
    ]["items"]["enum"]
    assert set(evidence_id_enum) == {item["source_id"] for item in slm_sources}


def test_saved_result_rejects_a_different_frozen_rubric_snapshot():
    request = rubric_request()
    result = evaluate(request, RubricFake(), ExecutionConfig())
    other = rubric_request()
    changed_domains = list(other.form_snapshot.form.domains)
    first = changed_domains[0]
    changed_criteria = list(first.criteria)
    changed_criteria[0] = changed_criteria[0].model_copy(
        update={"title": "Changed title"}
    )
    changed_domains[0] = first.model_copy(update={"criteria": tuple(changed_criteria)})
    changed_form = other.form_snapshot.form.model_copy(
        update={"domains": tuple(changed_domains)}
    )
    changed_snapshot = build_evaluation_form_snapshot(other.evaluation_id, changed_form)
    with pytest.raises(ValueError, match="criteria|rubric"):
        validate_result(result, changed_snapshot)


def test_excess_known_evidence_ids_receive_actionable_repair_feedback():
    from equiped_harness.agents.coordinator.pipeline import validate_response

    passages = [{"source_id": f"S{i}", "source": "slm"} for i in range(1, 6)]
    response = {
        "results": [
            {
                "criterion_id": "OP-01",
                "score": 3,
                "finding": (
                    "The reviewed passages demonstrate a coherent sequence "
                    "with relevant examples."
                ),
                "evidence_status": "present",
                "evidence_ids": [p["source_id"] for p in passages],
            }
        ]
    }
    with pytest.raises(AgentExecutionError, match="OP-01.*at most four"):
        validate_response(response, "organization", ("OP-01",), passages)
