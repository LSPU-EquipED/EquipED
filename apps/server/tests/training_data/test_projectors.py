"""Unit tests for response contract projection functions."""

from __future__ import annotations

import json
from uuid import uuid4

from server.modules.feedback.state import EffectiveCriterionCorrection
from server.modules.synthesis.models import AgentGeneration
from server.modules.training_data.projectors import (
    project_criterion_measurements_v1,
    project_gad_extraction_v1,
    project_itso_scores_v1,
)


def test_project_criterion_measurements_score_edit():
    gen_id = uuid4()
    eval_id = uuid4()
    doc_id = uuid4()
    rev_id = uuid4()

    orig_response = {
        "summary": "original summary",
        "criterion_measurements": [
            {
                "criterion_id": "A-01",
                "criterion_title": "Criterion A-01",
                "score": 1,
                "reasoning": "Needs improvement",
            },
            {
                "criterion_id": "A-02",
                "criterion_title": "Criterion A-02",
                "score": 3,
                "reasoning": "Good",
            },
        ],
    }

    gen = AgentGeneration(
        generation_id=gen_id,
        agent_result_id=uuid4(),
        evaluation_id=eval_id,
        document_id=doc_id,
        agent_id="sme",
        unit_key="envelope_0",
        criterion_ids=["A-01", "A-02"],
        prompt_text="Prompt for envelope_0",
        response_text=json.dumps(orig_response),
        response_json=orig_response,
        response_contract_key="criterion_measurements.v1",
        response_contract_version=1,
        model_name="gemma-3-4b",
        envelope_status="ok",
        prompt_sha256="abc",
        response_sha256="def",
    )

    corrections = {
        "A-01": EffectiveCriterionCorrection(
            log_id=uuid4(),
            evaluation_id=eval_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            score=4,
            justification="Exemplary work shown.",
            user_id=rev_id,
        )
    }

    res = project_criterion_measurements_v1(gen, corrections, {})
    assert res.skip_reason is None
    assert res.pair is not None
    assert res.pair.pair_id == str(gen_id)
    assert res.pair.agent_id == "sme"
    assert res.pair.reviewer_ids == frozenset([rev_id])

    chosen_json = json.loads(res.pair.chosen)
    m0 = chosen_json["criterion_measurements"][0]
    assert m0["criterion_id"] == "A-01"
    assert m0["score"] == 4
    assert m0["reasoning"] == "Exemplary work shown."

    m1 = chosen_json["criterion_measurements"][1]
    assert m1["criterion_id"] == "A-02"
    assert m1["score"] == 3


def test_project_criterion_measurements_item_rejection():
    gen_id = uuid4()
    eval_id = uuid4()
    doc_id = uuid4()
    rev_id = uuid4()

    orig_response = {
        "summary": "original summary",
        "criterion_measurements": [
            {
                "criterion_id": "OP-01",
                "criterion_title": "Criterion OP-01",
                "instances": [
                    {"excerpt": "valid item"},
                    {"excerpt": "invalid item"},
                ],
            }
        ],
    }

    gen = AgentGeneration(
        generation_id=gen_id,
        agent_result_id=uuid4(),
        evaluation_id=eval_id,
        document_id=doc_id,
        agent_id="coordinator",
        unit_key="envelope_0",
        criterion_ids=["OP-01"],
        prompt_text="Prompt for envelope_0",
        response_text=json.dumps(orig_response),
        response_json=orig_response,
        response_contract_key="criterion_measurements.v1",
        response_contract_version=1,
        model_name="gemma-3-4b",
        envelope_status="ok",
        prompt_sha256="abc",
        response_sha256="def",
    )

    rejections = {
        "OP-01": (frozenset(["instance_1"]), frozenset([rev_id]))
    }

    res = project_criterion_measurements_v1(gen, {}, rejections)
    assert res.skip_reason is None
    assert res.pair is not None
    assert res.pair.reviewer_ids == frozenset([rev_id])

    chosen_json = json.loads(res.pair.chosen)
    instances = chosen_json["criterion_measurements"][0]["instances"]
    assert len(instances) == 1
    assert instances[0]["excerpt"] == "valid item"


def test_project_criterion_measurements_reject_action_skips():
    gen = AgentGeneration(
        generation_id=uuid4(),
        agent_result_id=uuid4(),
        evaluation_id=uuid4(),
        document_id=uuid4(),
        agent_id="sme",
        unit_key="envelope_0",
        criterion_ids=["A-01"],
        prompt_text="Prompt",
        response_text="{}",
        response_json={
            "criterion_measurements": [{"criterion_id": "A-01", "score": 2}]
        },
        response_contract_key="criterion_measurements.v1",
        response_contract_version=1,
        model_name="gemma-3-4b",
        envelope_status="ok",
        prompt_sha256="abc",
        response_sha256="def",
    )

    corrections = {
        "A-01": EffectiveCriterionCorrection(
            log_id=uuid4(),
            evaluation_id=gen.evaluation_id,
            agent_name="sme",
            criterion_id="A-01",
            action="REJECT",
        )
    }

    res = project_criterion_measurements_v1(gen, corrections, {})
    assert res.skip_reason == "envelope_contains_rejection"
    assert res.pair is None


def test_project_itso_scores_edit():
    gen_id = uuid4()
    eval_id = uuid4()
    doc_id = uuid4()
    rev_id = uuid4()

    orig_response = {
        "summary": "itso summary",
        "criterion_scores": [
            {
                "criterion_id": "ITSO-01",
                "criterion_title": "No IP Issue",
                "score": 2,
                "justification": "Moderate compliance",
                "chunk_ids": ["c1"],
                "evidence": ["e1"],
            }
        ],
    }

    gen = AgentGeneration(
        generation_id=gen_id,
        agent_result_id=uuid4(),
        evaluation_id=eval_id,
        document_id=doc_id,
        agent_id="itso",
        unit_key="envelope_0",
        criterion_ids=["ITSO-01"],
        prompt_text="ITSO Prompt",
        response_text=json.dumps(orig_response),
        response_json=orig_response,
        response_contract_key="itso_scores.v1",
        response_contract_version=1,
        model_name="gemma-3-4b",
        envelope_status="ok",
        prompt_sha256="abc",
        response_sha256="def",
    )

    corrections = {
        "ITSO-01": EffectiveCriterionCorrection(
            log_id=uuid4(),
            evaluation_id=eval_id,
            agent_name="itso",
            criterion_id="ITSO-01",
            action="EDIT",
            score=4,
            justification="Fully compliant with citations.",
            user_id=rev_id,
        )
    }

    res = project_itso_scores_v1(gen, corrections)
    assert res.skip_reason is None
    assert res.pair is not None
    assert res.pair.reviewer_ids == frozenset([rev_id])

    chosen_json = json.loads(res.pair.chosen)
    score_entry = chosen_json["criterion_scores"][0]
    assert score_entry["score"] == 4
    assert score_entry["justification"] == "Fully compliant with citations."


def test_project_gad_extraction_skips():
    gen = AgentGeneration(
        generation_id=uuid4(),
        agent_result_id=uuid4(),
        evaluation_id=uuid4(),
        document_id=uuid4(),
        agent_id="gad",
        unit_key="envelope_0",
        criterion_ids=["gad-01"],
        prompt_text="GAD Prompt",
        response_text="{}",
        response_json={},
        response_contract_key="gad_extraction.v1",
        response_contract_version=1,
        model_name="gemma-3-4b",
        envelope_status="ok",
        prompt_sha256="abc",
        response_sha256="def",
    )

    res = project_gad_extraction_v1(gen, {})
    assert res.skip_reason == "gad_score_edit_ineligible_for_extraction_contract"
    assert res.pair is None
