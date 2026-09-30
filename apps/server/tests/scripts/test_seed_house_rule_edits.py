"""Tests for the house-rule correction script (adapter validation)."""

# F811: the re-exported fixture is used as a test argument (standard pytest pattern).
# ruff: noqa: F811

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.modules.synthesis.models import AgentGeneration, AgentResult
from server.modules.training_data.projectors import _is_score_shaped
from server.scripts import seed_house_rule_edits as tool

# Re-exported fixture: seeds the active SME rubric (OP-01..05, A-01..05, all
# llm_rubric_guidance) into the in-memory test database.
from server.tests.scripts.test_seed_synthetic_dpo_pairs import (  # noqa: F401
    seeded_sme_rubric,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1, (2, None)),
        (2, (3, None)),
        (3, (4, None)),
        (4, (None, "already_max")),
        (0, (None, "invalid_score")),
        (5, (None, "invalid_score")),
        (True, (None, "invalid_score")),
        ("3", (None, "invalid_score")),
        (None, (None, "invalid_score")),
        (3.0, (4, None)),
        (2.5, (None, "invalid_score")),
    ],
)
def test_apply_rule_raises_by_one_and_skips_the_ceiling(score, expected):
    assert tool.apply_rule(score) == expected


@pytest.mark.parametrize(
    "measurement",
    [
        {"criterion_id": "OP-01", "score": 2, "reasoning": "r"},
        {"criterion_id": "OP-01", "score": 2, "instances": []},
        {"criterion_id": "OP-01", "score": 2, "total_units": 3},
        {"criterion_id": "OP-01", "instances": []},
        {"criterion_id": "OP-01"},
    ],
)
def test_is_score_shaped_agrees_with_the_projector(measurement):
    assert tool.is_score_shaped(measurement) == _is_score_shaped(measurement)


@pytest.mark.parametrize(
    ("scores", "expected"),
    [([2, 3], 3), ([2, 2, 3], 2), ([3, 4], 4), ([1], 1), ([2, 2], 2)],
)
def test_base_reference_is_the_mean_rounded_half_up(scores, expected):
    assert tool.base_reference(scores) == expected


@pytest.mark.parametrize(
    ("role", "reference", "expected"),
    [("edited", 4, 4), ("edited", 2, 3), ("control", 2, 2), ("control", 4, 4)],
)
def test_expected_score_applies_the_rule_only_to_edited(role, reference, expected):
    assert tool.expected_score(role, reference) == expected


def test_normalize_codes_uppercases_dedupes_and_keeps_order():
    assert tool.normalize_codes([" op-01", "A-03 ", "", "OP-01"]) == ("OP-01", "A-03")


def test_default_edit_set_is_the_six_odd_numbered_criteria():
    assert tool.DEFAULT_EDIT_CRITERIA == (
        "OP-01",
        "OP-03",
        "OP-05",
        "A-01",
        "A-03",
        "A-05",
    )


def test_format_note_tags_the_run():
    run_id = uuid.uuid4()
    assert tool.format_note(run_id) == f"house-rule-seed:{run_id}"


def _criterion(code, *, role="edited", generation=None, new=None, skip=None):
    return tool.CriterionPlan(
        evaluation_id=uuid.UUID(int=1),
        generation_id=generation or uuid.UUID(int=2),
        criterion_code=code,
        role=role,
        base_score=2,
        new_score=new,
        skip_reason=skip,
    )


def _evaluation(group, criteria):
    return tool.EvaluationPlan(
        evaluation_id=uuid.UUID(int=1),
        document_id=uuid.UUID(int=3),
        document_title="Doc",
        group=group,
        generations=(),
        criteria=tuple(criteria),
    )


def test_only_train_plans_write_and_pair_generations_are_counted():
    gen_a, gen_b = uuid.UUID(int=10), uuid.UUID(int=11)
    train = _evaluation(
        "train",
        [
            _criterion("OP-01", generation=gen_a, new=3),
            _criterion("OP-03", generation=gen_a, new=4),
            _criterion("A-01", generation=gen_b, new=2),
            _criterion("A-03", generation=gen_b, skip="already_max"),
            _criterion("OP-02", role="control"),
        ],
    )
    reference = _evaluation("reference", [_criterion("OP-01", new=3)])
    run = tool.RunPlan(plans=(train, reference), edit_codes=("OP-01",))

    assert len(train.writes) == 3
    assert reference.writes == ()
    assert len(run.writes) == 3
    assert run.pair_generation_ids == frozenset({gen_a, gen_b})
    assert run.skip_counts() == {"already_max": 1}


@pytest.fixture()
def user(db_session):
    account = create_user(
        db_session,
        name="Tester",
        email="tester@local.test",
        password=uuid.uuid4().hex,
        role=UserRole.FACULTY,
    )
    db_session.flush()
    return account


def measurement(code, score, reasoning="because"):
    return {
        "criterion_id": code,
        "criterion_title": code,
        "score": score,
        "reasoning": reasoning,
        "evidence": "e",
    }


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_evaluation(
    session,
    user,
    generations,
    *,
    status="COMPLETED",
    title="Test SLM",
    envelope_status="ok",
    document_id=None,
    prompt_chars=200,
):
    """A stored SME evaluation with one generation per list in `generations`."""
    document_id = document_id or uuid.uuid4()
    if session.get(Document, document_id) is None:
        session.add(
            Document(
                document_id=document_id,
                title=title,
                source_type="slm",
                file_path=f"uploads/{document_id}.pdf",
                uploaded_by=user.user_id,
                uploaded_at=datetime.now(UTC),
                page_count=1,
                has_ocr_pages=False,
                processing_status="PROCESSED",
            )
        )
    evaluation_id = uuid.uuid4()
    session.add(
        EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            submitted_by=user.user_id,
            status=status,
            target_agent="sme",
        )
    )
    session.flush()
    resolve_or_reuse_evaluation_snapshots(session, evaluation_id, ("sme",))
    agent_result_id = uuid.uuid4()
    session.add(
        AgentResult(
            agent_result_id=agent_result_id,
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_name="sme",
            model_name="gemma-3-4b-it",
            success=True,
            envelope_status={"envelope_0": "ok"},
        )
    )
    session.flush()
    generation_ids = []
    for index, measurements in enumerate(generations):
        response = {"summary": "s", "criterion_measurements": measurements}
        response_text = json.dumps(response)
        prompt = f"PROMPT-{index}-".ljust(prompt_chars, "x")
        generation_id = uuid.uuid4()
        session.add(
            AgentGeneration(
                generation_id=generation_id,
                agent_result_id=agent_result_id,
                evaluation_id=evaluation_id,
                document_id=document_id,
                agent_id="sme",
                unit_key=f"envelope_{index}",
                criterion_ids=[
                    m["criterion_id"] for m in measurements if "criterion_id" in m
                ],
                prompt_text=prompt,
                response_text=response_text,
                response_json=response,
                response_contract_key="criterion_measurements.v1",
                response_contract_version=1,
                model_name="gemma-3-4b-it",
                envelope_status=envelope_status,
                prompt_sha256=_sha(prompt),
                response_sha256=_sha(response_text),
            )
        )
        generation_ids.append(generation_id)
    session.commit()
    return evaluation_id, generation_ids


FULL_ANSWER = [
    [
        measurement("OP-01", 2),
        measurement("OP-02", 3),
        measurement("OP-03", 4),
        measurement("OP-04", 1),
        measurement("OP-05", 3),
    ],
    [
        measurement("A-01", 1),
        measurement("A-02", 2),
        measurement("A-03", 3),
        measurement("A-04", 4),
        measurement("A-05", 2),
    ],
]


def test_plan_evaluation_applies_the_rule_and_never_touches_controls(
    db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)

    plan = tool.plan_evaluation(
        db_session,
        evaluation_id,
        group="train",
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )

    by_code = {c.criterion_code: c for c in plan.criteria}
    assert by_code["OP-01"].new_score == 3
    assert by_code["OP-03"].new_score is None
    assert by_code["OP-03"].skip_reason == "already_max"
    assert by_code["OP-05"].new_score == 4
    assert (by_code["A-01"].new_score, by_code["A-03"].new_score) == (2, 4)
    assert by_code["A-05"].new_score == 3
    for code in ("OP-02", "OP-04", "A-02", "A-04"):
        assert by_code[code].role == "control"
        assert by_code[code].new_score is None
        assert by_code[code].skip_reason is None
    assert len(plan.generations) == 2
    assert len(plan.writes) == 5
    assert plan.document_title == "Test SLM"


def test_reference_plans_compute_but_never_write(db_session, user, seeded_sme_rubric):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    plan = tool.plan_evaluation(
        db_session,
        evaluation_id,
        group="reference",
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    assert plan.writes == ()
    assert {c.criterion_code for c in plan.criteria if c.role == "edited"} == set(
        tool.DEFAULT_EDIT_CRITERIA
    )


def test_missing_evaluation_aborts(db_session, seeded_sme_rubric):
    with pytest.raises(tool.IneligibleRunError, match="does not exist"):
        tool.plan_evaluation(
            db_session, uuid.uuid4(), group="train", edit_codes=("OP-01",)
        )


def test_evaluation_that_is_not_completed_aborts(db_session, user, seeded_sme_rubric):
    evaluation_id, _ = make_evaluation(
        db_session, user, FULL_ANSWER, status="EVALUATING"
    )
    with pytest.raises(tool.IneligibleRunError, match="not COMPLETED"):
        tool.plan_evaluation(
            db_session, evaluation_id, group="train", edit_codes=("OP-01",)
        )


@pytest.mark.skipif(
    not hasattr(EvaluationJob, "adapter_resolution"),
    reason="adapter_resolution exists only on the per-agent adapter branch",
)
def test_an_evaluation_scored_with_an_adapter_aborts(
    db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    job = db_session.get(EvaluationJob, evaluation_id)
    job.adapter_resolution = {
        "sme": {"requested": "sme-v1", "applied": "sme-v1", "reason": None}
    }
    db_session.commit()
    with pytest.raises(tool.IneligibleRunError, match="base-model answers only"):
        tool.plan_evaluation(
            db_session, evaluation_id, group="train", edit_codes=("OP-01",)
        )


@pytest.mark.parametrize("envelope_status", ["repaired", "fallback"])
def test_only_ok_generations_count_and_none_ok_aborts(
    db_session, user, seeded_sme_rubric, envelope_status
):
    evaluation_id, _ = make_evaluation(
        db_session, user, FULL_ANSWER, envelope_status=envelope_status
    )
    with pytest.raises(tool.IneligibleRunError, match="no usable SME generation"):
        tool.plan_evaluation(
            db_session, evaluation_id, group="train", edit_codes=("OP-01",)
        )


def test_an_existing_real_log_is_skipped_and_left_untouched(
    db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    real = PreferenceLog(
        evaluation_id=evaluation_id,
        user_id=user.user_id,
        agent_name="sme",
        criterion_id="OP-01",
        action="ACCEPT",
    )
    db_session.add(real)
    db_session.commit()

    plan = tool.plan_evaluation(
        db_session,
        evaluation_id,
        group="train",
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )

    op01 = next(c for c in plan.criteria if c.criterion_code == "OP-01")
    assert (op01.new_score, op01.skip_reason) == (None, "existing_log")
    assert db_session.query(PreferenceLog).count() == 1
    assert db_session.get(PreferenceLog, real.log_id).action == "ACCEPT"


def test_a_criterion_in_two_generations_is_skipped(db_session, user, seeded_sme_rubric):
    evaluation_id, _ = make_evaluation(
        db_session,
        user,
        [[measurement("OP-01", 2)], [measurement("OP-01", 3)]],
    )
    plan = tool.plan_evaluation(
        db_session, evaluation_id, group="train", edit_codes=("OP-01",)
    )
    assert plan.writes == ()
    assert {c.skip_reason for c in plan.criteria} == {
        "criterion_in_multiple_generations"
    }


def test_measurements_without_a_criterion_id_are_ignored(
    db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(
        db_session, user, [[{"score": 2}, measurement("OP-01", 2)]]
    )
    plan = tool.plan_evaluation(
        db_session, evaluation_id, group="train", edit_codes=("OP-01",)
    )
    assert [c.criterion_code for c in plan.criteria] == ["OP-01"]


def test_a_measurement_that_is_not_score_shaped_is_skipped(
    db_session, user, seeded_sme_rubric
):
    counted = {"criterion_id": "OP-01", "score": 2, "instances": [], "total_units": 3}
    evaluation_id, _ = make_evaluation(db_session, user, [[counted]])
    plan = tool.plan_evaluation(
        db_session, evaluation_id, group="train", edit_codes=("OP-01",)
    )
    assert plan.criteria[0].skip_reason == "not_score_shaped"
    assert plan.writes == ()


def test_decide_skip_reasons_in_priority_order():
    shaped = measurement("OP-01", 2)
    strategy = tool.LlmRubricGuidanceConfig.model_construct()
    assert tool._decide("control", "OP-02", shaped, strategy, set(), False) == (
        None,
        None,
    )
    assert tool._decide("edited", "ZZ-99", shaped, None, set(), False) == (
        None,
        "not_in_snapshot",
    )
    assert tool._decide("edited", "OP-01", shaped, object(), set(), False) == (
        None,
        "not_llm_rubric_guidance",
    )
    assert tool._decide("edited", "OP-01", shaped, strategy, set(), False) == (3, None)
    assert tool._decide("edited", "OP-01", shaped, strategy, {"OP-01"}, False) == (
        None,
        "existing_log",
    )
    assert tool._decide("edited", "OP-01", shaped, strategy, set(), True) == (
        None,
        "criterion_in_multiple_generations",
    )


def test_plan_run_reads_only_and_aborts_on_any_bad_evaluation(
    db_session, user, seeded_sme_rubric
):
    good, _ = make_evaluation(db_session, user, FULL_ANSWER)
    with pytest.raises(tool.IneligibleRunError, match="does not exist"):
        tool.plan_run(
            db_session,
            train_ids=[good, uuid.uuid4()],
            reference_ids=[],
            edit_codes=tool.DEFAULT_EDIT_CRITERIA,
        )
    assert db_session.query(PreferenceLog).count() == 0


def test_plan_run_rejects_duplicate_ids_and_ids_in_both_lists(
    db_session, user, seeded_sme_rubric
):
    first, _ = make_evaluation(db_session, user, FULL_ANSWER)
    with pytest.raises(tool.IneligibleRunError, match="more than once"):
        tool.plan_run(
            db_session,
            train_ids=[first, first],
            reference_ids=[],
            edit_codes=("OP-01",),
        )
    with pytest.raises(tool.IneligibleRunError, match="more than once"):
        tool.plan_run(
            db_session,
            train_ids=[first],
            reference_ids=[first],
            edit_codes=("OP-01",),
        )


def test_plan_run_rejects_a_document_in_both_train_and_reference(
    db_session, user, seeded_sme_rubric
):
    document_id = uuid.uuid4()
    trained, _ = make_evaluation(db_session, user, FULL_ANSWER, document_id=document_id)
    held_out, _ = make_evaluation(
        db_session, user, FULL_ANSWER, document_id=document_id
    )
    with pytest.raises(tool.IneligibleRunError, match="held-out"):
        tool.plan_run(
            db_session,
            train_ids=[trained],
            reference_ids=[held_out],
            edit_codes=("OP-01",),
        )


def test_plan_run_rejects_an_edit_code_that_no_evaluation_contains(
    db_session, user, seeded_sme_rubric
):
    first, _ = make_evaluation(db_session, user, FULL_ANSWER)
    with pytest.raises(tool.IneligibleRunError, match="never seen"):
        tool.plan_run(
            db_session, train_ids=[first], reference_ids=[], edit_codes=("ZZ-99",)
        )


def test_plan_run_collects_train_and_reference_plans(
    db_session, user, seeded_sme_rubric
):
    train, _ = make_evaluation(db_session, user, FULL_ANSWER, title="Train")
    reference, _ = make_evaluation(db_session, user, FULL_ANSWER, title="Held out")
    run = tool.plan_run(
        db_session,
        train_ids=[train],
        reference_ids=[reference],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    assert [p.group for p in run.plans] == ["train", "reference"]
    assert len(run.writes) == 5
    assert len(run.pair_generation_ids) == 2
