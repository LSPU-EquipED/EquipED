"""Tests for the house-rule correction script (adapter validation)."""

from __future__ import annotations

import csv
import hashlib
import json
import types
import uuid
from datetime import UTC, datetime

import pytest
from server.modules.auth.models import User, UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.feedback.state import get_effective_criterion_corrections_batch
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.modules.synthesis.models import AgentGeneration, AgentResult
from server.modules.training_data.exporter import export_dpo_package
from server.modules.training_data.projectors import _is_score_shaped
from server.scripts import seed_house_rule_edits as tool
from server.scripts import seed_synthetic_dpo_pairs as old_seeder
from server.tests.scripts import test_seed_synthetic_dpo_pairs as _seed_tests

# Re-exported fixture: seeds the active SME rubric (OP-01..05, A-01..05, all
# llm_rubric_guidance) into the in-memory test database.
seeded_sme_rubric = _seed_tests.seeded_sme_rubric


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


def test_plan_run_aborts_on_any_bad_evaluation_and_writes_nothing(
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


def test_plan_run_is_read_only(db_session, user, seeded_sme_rubric):
    train, _ = make_evaluation(db_session, user, FULL_ANSWER, title="Train")
    reference, _ = make_evaluation(db_session, user, FULL_ANSWER, title="Held out")
    models = (PreferenceLog, AgentGeneration, EvaluationJob)
    before = [db_session.query(m).count() for m in models]
    run = tool.plan_run(
        db_session,
        train_ids=[train],
        reference_ids=[reference],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    assert run.writes
    assert not db_session.new
    assert not db_session.dirty
    assert not db_session.deleted
    assert [db_session.query(m).count() for m in models] == before


@pytest.mark.parametrize(
    "resolution",
    [
        None,
        {},
        {"other": {"requested": "x", "applied": "x", "reason": None}},
        {"sme": {"requested": "sme-v1", "applied": None, "reason": "not_loaded"}},
        {"sme": {"requested": "base", "applied": None, "reason": None}},
    ],
)
def test_adapter_guard_passes_when_no_sme_adapter_was_applied(
    db_session, user, seeded_sme_rubric, resolution
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    job = db_session.get(EvaluationJob, evaluation_id)
    job.adapter_resolution = resolution
    db_session.commit()
    plan = tool.plan_evaluation(
        db_session, evaluation_id, group="train", edit_codes=("OP-01",)
    )
    assert plan.writes


def _log(evaluation_id, user, **overrides):
    fields = {
        "evaluation_id": evaluation_id,
        "user_id": user.user_id,
        "agent_name": "sme",
        "criterion_id": "OP-01",
        "action": "ACCEPT",
    }
    fields.update(overrides)
    return PreferenceLog(**fields)


def _op01(plan):
    return next(c for c in plan.criteria if c.criterion_code == "OP-01")


def test_a_log_on_another_evaluation_does_not_cause_a_skip(
    db_session, user, seeded_sme_rubric
):
    mine, _ = make_evaluation(db_session, user, FULL_ANSWER)
    other, _ = make_evaluation(db_session, user, FULL_ANSWER)
    db_session.add(_log(other, user))
    db_session.commit()
    plan = tool.plan_evaluation(db_session, mine, group="train", edit_codes=("OP-01",))
    assert _op01(plan).skip_reason is None
    assert _op01(plan).new_score == 3


def test_a_log_without_a_criterion_id_is_ignored(db_session, user, seeded_sme_rubric):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    db_session.add(_log(evaluation_id, user, criterion_id=None))
    db_session.commit()
    plan = tool.plan_evaluation(
        db_session, evaluation_id, group="train", edit_codes=("OP-01",)
    )
    assert _op01(plan).skip_reason is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "REJECT"},
        {"action": "ITEM_REJECT", "item_id": "item-1"},
        {"agent_name": "SME"},
    ],
)
def test_reject_item_and_uppercase_agent_logs_count_as_existing(
    db_session, user, seeded_sme_rubric, overrides
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    db_session.add(_log(evaluation_id, user, **overrides))
    db_session.commit()
    plan = tool.plan_evaluation(
        db_session, evaluation_id, group="train", edit_codes=("OP-01",)
    )
    assert _op01(plan).skip_reason == "existing_log"


def test_parse_ids_accepts_commas_lines_and_comments():
    first, second = uuid.uuid4(), uuid.uuid4()
    text = f"# my run\n{first}, {second}\n\n"
    assert tool.parse_ids(text) == [first, second]
    with pytest.raises(ValueError):
        tool.parse_ids("not-a-uuid")


def test_read_ids_file(tmp_path):
    first = uuid.uuid4()
    path = tmp_path / "ids.txt"
    path.write_text(f"{first}  # trailing comment\n", encoding="utf-8")
    assert tool.read_ids_file(path) == [first]


def test_suggest_limits_rounds_up_with_a_margin():
    assert tool.estimate_tokens(15850) == 3963
    assert tool.suggest_limits(3963) == (4608, 6144)


def test_suggest_limits_uses_exact_integer_math():
    # 1.15 * 1280 = 1472 exactly -> 6 * 256; no float noise may push it to 7.
    assert tool.suggest_limits(1280) == (1536, 3072)
    assert tool.suggest_limits(1) == (256, 1792)


def test_report_lists_evaluations_totals_skips_and_prompt_lengths(
    db_session, user, seeded_sme_rubric
):
    train, _ = make_evaluation(
        db_session, user, FULL_ANSWER, title="Train SLM", prompt_chars=15800
    )
    held_out, _ = make_evaluation(
        db_session, user, FULL_ANSWER, title="Held-out SLM", prompt_chars=15800
    )
    run = tool.plan_run(
        db_session,
        train_ids=[train],
        reference_ids=[held_out],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )

    text = tool.render_report(run, mode="DRY RUN")

    assert "House-rule report (DRY RUN)" in text
    assert "Edited criteria: OP-01, OP-03, OP-05, A-01, A-03, A-05" in text
    assert "[train]" in text and "[reference]" in text
    assert "Train SLM" in text and "Held-out SLM" in text
    assert "corrections planned: 5" in text
    assert "expected new pairs: 2" in text
    assert "already_max=" in text
    assert "2 of 2" in text  # generations above the notebook's prompt limit
    assert "max_prompt_length=4608" in text and "MAX_SEQ_LENGTH=6144" in text
    assert "never publish" in text.lower()
    assert "do not start another sme training job" in text.lower()


def test_report_survives_a_windows_console(db_session, user, seeded_sme_rubric):
    evaluation_id, _ = make_evaluation(
        db_session, user, FULL_ANSWER, title="Módulo – 1"
    )
    run = tool.plan_run(
        db_session,
        train_ids=[evaluation_id],
        reference_ids=[],
        edit_codes=("OP-01",),
    )
    tool.render_report(run, mode="DRY RUN").encode("cp1252")


@pytest.fixture()
def cli(monkeypatch, db_session):
    """Run main() against the in-memory database with the safety checks stubbed."""
    monkeypatch.setattr(tool, "validate_environment", lambda: "development")

    def run(*argv):
        return tool.main(list(argv), session_factory=lambda: db_session)

    return run


def test_cli_dry_run_prints_the_report_and_writes_nothing(
    cli, capsys, db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)

    code = cli("--train-evaluations", str(evaluation_id))

    out = capsys.readouterr().out
    assert code == 0
    assert "House-rule report (DRY RUN)" in out
    assert "Dry run: nothing was written" in out
    assert db_session.query(PreferenceLog).count() == 0


def test_cli_reads_ids_from_files(
    cli, capsys, tmp_path, db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    path = tmp_path / "train.txt"
    path.write_text(f"{evaluation_id}\n", encoding="utf-8")
    assert cli("--train-evaluations-file", str(path)) == 0
    assert "[train]" in capsys.readouterr().out


def test_cli_aborts_with_exit_2_and_a_message(cli, capsys, seeded_sme_rubric):
    assert cli("--train-evaluations", str(uuid.uuid4())) == 2
    assert "ABORTED" in capsys.readouterr().out
    assert cli("--train-evaluations", "nope") == 2


def test_cli_refuses_production(monkeypatch, capsys):
    def refuse():
        raise PermissionError("production refused")

    monkeypatch.setattr(tool, "validate_environment", refuse)
    assert tool.main(["--train-evaluations", str(uuid.uuid4())]) == 3
    assert "REFUSED" in capsys.readouterr().out


def test_parser_help_carries_the_publish_rule():
    assert "never be published" in tool.build_parser().format_help().lower()


def test_count_exportable_pairs_counts_what_the_exporter_would_use(
    db_session, seeded_sme_rubric
):
    assert tool.count_exportable_pairs(db_session) == 0
    old_seeder.generate(db_session, count=2)
    assert tool.count_exportable_pairs(db_session) == 2


def test_report_warns_when_pairs_already_exist():
    run = tool.RunPlan(plans=(), edit_codes=("OP-01",))
    clean = tool.render_report(run, mode="DRY RUN", baseline_pairs=0)
    dirty = tool.render_report(run, mode="DRY RUN", baseline_pairs=25)
    assert "Existing exportable SME pairs already in the database: 0." in clean
    assert "WARNING" not in clean
    assert "already in the database: 25." in dirty
    assert "WARNING: these pairs would be trained on" in dirty


def test_cli_verify_export_flags_existing_synthetic_pairs(
    cli, capsys, db_session, user, seeded_sme_rubric
):
    old_seeder.generate(db_session, count=3)
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)

    assert cli("--train-evaluations", str(evaluation_id), "--verify-export") == 0

    out = capsys.readouterr().out
    assert "already in the database: 3." in out
    assert "WARNING" in out
    # still read-only: only the 3 synthetic corrections exist
    assert db_session.query(PreferenceLog).count() == 3


def _two_runs_of_one_slm(db_session, user):
    doc = uuid.uuid4()
    first, _ = make_evaluation(
        db_session,
        user,
        [[measurement("OP-01", 2), measurement("OP-02", 2)]],
        title="SLM A",
        document_id=doc,
    )
    second, _ = make_evaluation(
        db_session,
        user,
        [[measurement("OP-01", 3), measurement("OP-02", 2)]],
        title="SLM A",
        document_id=doc,
    )
    return first, second


def test_csv_rows_are_per_slm_and_criterion_with_the_rule_applied(
    db_session, user, seeded_sme_rubric
):
    first, second = _two_runs_of_one_slm(db_session, user)
    held_out, _ = make_evaluation(
        db_session,
        user,
        [[measurement("OP-01", 4), measurement("OP-02", 1)]],
        title="SLM B",
    )
    run = tool.plan_run(
        db_session,
        train_ids=[first, second],
        reference_ids=[held_out],
        edit_codes=("OP-01",),
    )

    rows = tool.build_expected_scores_rows(run)

    by_key = {(r["document_title"], r["criterion_code"]): r for r in rows}
    edited = by_key[("SLM A", "OP-01")]
    assert edited["group"] == "train" and edited["role"] == "edited"
    assert edited["run_count"] == "2"
    assert sorted(edited["base_scores"].split(";")) == ["2", "3"]
    assert edited["base_reference"] == "3"  # mean 2.5 rounds half up
    assert edited["expected_score"] == "4"
    control = by_key[("SLM A", "OP-02")]
    assert control["role"] == "control"
    assert (control["base_reference"], control["expected_score"]) == ("2", "2")
    ceiling = by_key[("SLM B", "OP-01")]
    assert ceiling["group"] == "reference"
    assert (ceiling["base_reference"], ceiling["expected_score"]) == ("4", "4")
    assert by_key[("SLM B", "OP-02")]["expected_score"] == "1"
    assert [r["group"] for r in rows] == sorted(
        (r["group"] for r in rows), key={"train": 0, "reference": 1}.get
    )


def test_cli_writes_the_csv_and_nothing_else(
    cli, tmp_path, capsys, db_session, user, seeded_sme_rubric
):
    first, second = _two_runs_of_one_slm(db_session, user)
    target = tmp_path / "out" / "expected.csv"

    code = cli(
        "--train-evaluations",
        f"{first},{second}",
        "--edit-criteria",
        "OP-01",
        "--report-csv",
        str(target),
    )

    assert code == 0
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == list(tool.CSV_COLUMNS)
    assert {r["criterion_code"] for r in rows} == {"OP-01", "OP-02"}
    assert "Expected-scores CSV written" in capsys.readouterr().out
    assert db_session.query(PreferenceLog).count() == 0


@pytest.fixture()
def write_cli(monkeypatch, cli):
    """The CLI with the database-target checks pointed at a local target."""
    monkeypatch.setattr(
        tool,
        "get_settings",
        lambda: types.SimpleNamespace(database_url="sqlite:///:memory:"),
    )
    monkeypatch.setattr(tool, "validate_database_target", lambda: "f" * 64)
    return cli


def _eval_for_writing(db_session, user):
    return make_evaluation(db_session, user, FULL_ANSWER)[0]


def test_write_corrections_inserts_score_only_tagged_rows(
    db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    run = tool.plan_run(
        db_session,
        train_ids=[evaluation_id],
        reference_ids=[],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    run_id = uuid.uuid4()

    written = tool.write_corrections(db_session, run, run_id=run_id)

    rows = db_session.query(PreferenceLog).all()
    assert written == len(rows) == 5
    house = db_session.query(User).filter_by(email=tool.HOUSE_USER_EMAIL).one()
    for row in rows:
        assert row.action == "EDIT"
        assert row.agent_name == "sme"
        assert row.user_id == house.user_id
        assert row.notes == f"house-rule-seed:{run_id}"
        assert set(row.edited_json) == {"score"}
        assert row.generation_id is not None
    assert {r.criterion_id for r in rows} == {"OP-01", "OP-05", "A-01", "A-03", "A-05"}


def test_write_is_all_or_nothing(db_session, user, seeded_sme_rubric, monkeypatch):
    evaluation_id = _eval_for_writing(db_session, user)
    run = tool.plan_run(
        db_session,
        train_ids=[evaluation_id],
        reference_ids=[],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    real_commit = db_session.commit

    def failing_commit():
        raise RuntimeError("disk full")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    with pytest.raises(RuntimeError, match="disk full"):
        tool.write_corrections(db_session, run, run_id=uuid.uuid4())
    monkeypatch.setattr(db_session, "commit", real_commit)
    assert db_session.query(PreferenceLog).count() == 0
    assert (
        db_session.query(User).filter_by(email=tool.HOUSE_USER_EMAIL).one_or_none()
        is None
    )


def test_the_exporter_turns_the_rows_into_pairs_that_differ_only_in_the_scores(
    db_session, user, seeded_sme_rubric, tmp_path
):
    evaluation_id = _eval_for_writing(db_session, user)
    run = tool.plan_run(
        db_session,
        train_ids=[evaluation_id],
        reference_ids=[],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    tool.write_corrections(db_session, run, run_id=uuid.uuid4())

    manifest = export_dpo_package(db_session, "sme", tmp_path / "package")

    assert manifest.pair_count == 2
    lines = (tmp_path / "package" / "pairs.jsonl").read_text("utf-8").splitlines()
    edited = set(tool.DEFAULT_EDIT_CRITERIA)
    for line in lines:
        pair = json.loads(line)
        chosen = json.loads(pair["chosen"])["criterion_measurements"]
        rejected = json.loads(pair["rejected"])["criterion_measurements"]
        assert len(chosen) == len(rejected) == 5
        for new, old in zip(chosen, rejected, strict=True):
            code = old["criterion_id"]
            expected = old["score"] + 1 if code in edited and old["score"] < 4 else None
            assert new["score"] == (expected or old["score"])
            # everything except the score is identical (reasoning untouched)
            assert {k: v for k, v in new.items() if k != "score"} == {
                k: v for k, v in old.items() if k != "score"
            }


def test_cli_write_requires_both_confirmations(
    write_cli, capsys, db_session, user, seeded_sme_rubric
):
    evaluation_id = str(_eval_for_writing(db_session, user))
    base = ["--train-evaluations", evaluation_id]
    assert write_cli(*base, "--confirm", "SEED") == 3
    assert write_cli(*base, "--confirm-target", "LOCAL") == 3
    assert write_cli(*base, "--confirm", "WRITE", "--confirm-target", "LOCAL") == 3
    assert write_cli(*base, "--confirm", "SEED", "--confirm-target", "wrong") == 3
    assert "REFUSED" in capsys.readouterr().out
    assert db_session.query(PreferenceLog).count() == 0
    assert (
        db_session.query(User).filter_by(email=tool.HOUSE_USER_EMAIL).one_or_none()
        is None
    )


def test_cli_write_refuses_an_unsafe_database_target(
    monkeypatch, write_cli, db_session, user, seeded_sme_rubric
):
    def refuse():
        raise PermissionError("unsafe target")

    monkeypatch.setattr(tool, "validate_database_target", refuse)
    evaluation_id = str(_eval_for_writing(db_session, user))
    code = write_cli(
        "--train-evaluations",
        evaluation_id,
        "--confirm",
        "SEED",
        "--confirm-target",
        "LOCAL",
    )
    assert code == 3
    assert db_session.query(PreferenceLog).count() == 0
    assert (
        db_session.query(User).filter_by(email=tool.HOUSE_USER_EMAIL).one_or_none()
        is None
    )


def test_cli_write_then_verify_export_then_second_run_writes_nothing(
    write_cli, capsys, db_session, user, seeded_sme_rubric
):
    evaluation_id = str(_eval_for_writing(db_session, user))
    argv = [
        "--train-evaluations",
        evaluation_id,
        "--verify-export",
        "--confirm",
        "SEED",
        "--confirm-target",
        "LOCAL",
    ]

    assert write_cli(*argv) == 0
    out = capsys.readouterr().out
    assert "Wrote 5 correction(s)" in out
    assert "expected 2 (OK)" in out
    assert "never publish" in out.lower()
    assert "--cleanup --run-id" in out
    assert db_session.query(PreferenceLog).count() == 5

    assert write_cli(*argv) == 0  # the criteria now have logs, so all are skipped
    assert "Nothing to write" in capsys.readouterr().out
    assert db_session.query(PreferenceLog).count() == 5


def test_reference_evaluations_are_never_written(
    write_cli, db_session, user, seeded_sme_rubric
):
    train = str(_eval_for_writing(db_session, user))
    held_out = make_evaluation(db_session, user, FULL_ANSWER, title="Held out")[0]
    code = write_cli(
        "--train-evaluations",
        train,
        "--reference-evaluations",
        str(held_out),
        "--confirm",
        "SEED",
        "--confirm-target",
        "LOCAL",
    )
    assert code == 0
    written = {r.evaluation_id for r in db_session.query(PreferenceLog).all()}
    assert written == {uuid.UUID(train)}


def _house_rows(db_session, user, evaluation_id, run_id, *, agent="sme"):
    house = tool.get_or_create_house_user(db_session)
    log = PreferenceLog(
        evaluation_id=evaluation_id,
        user_id=house.user_id,
        agent_name=agent,
        criterion_id="OP-01",
        action="EDIT",
        edited_json={"score": 3},
        notes=tool.format_note(run_id),
    )
    db_session.add(log)
    db_session.commit()
    return log


def test_cleanup_removes_exactly_the_tagged_rows(db_session, user, seeded_sme_rubric):
    evaluation_id = _eval_for_writing(db_session, user)
    run = tool.plan_run(
        db_session,
        train_ids=[evaluation_id],
        reference_ids=[],
        edit_codes=tool.DEFAULT_EDIT_CRITERIA,
    )
    mine, other = uuid.uuid4(), uuid.uuid4()
    tool.write_corrections(db_session, run, run_id=mine)
    survivor = _house_rows(db_session, user, evaluation_id, other)

    removed = tool.cleanup(db_session, run_id=mine)

    assert removed == 5
    remaining = db_session.query(PreferenceLog).all()
    assert [r.log_id for r in remaining] == [survivor.log_id]
    # real evaluation data is untouched
    assert db_session.query(AgentGeneration).count() == 2
    assert db_session.query(EvaluationJob).count() == 1


def test_cleanup_restores_the_earlier_effective_correction(
    db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    earlier = PreferenceLog(
        evaluation_id=evaluation_id,
        user_id=user.user_id,
        agent_name="sme",
        criterion_id="OP-01",
        action="EDIT",
        edited_json={"score": 1},
        notes="real reviewer",
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    db_session.add(earlier)
    db_session.commit()
    run_id = uuid.uuid4()
    _house_rows(db_session, user, evaluation_id, run_id)

    def effective():
        batch = get_effective_criterion_corrections_batch(db_session, [evaluation_id])
        return batch[evaluation_id][("sme", "OP-01")].score

    assert effective() == 3  # the house row is the latest
    assert tool.cleanup(db_session, run_id=run_id) == 1
    assert effective() == 1  # the reviewer's earlier decision is back


def test_cleanup_aborts_if_a_tagged_row_is_not_for_the_sme_agent(
    db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    run_id = uuid.uuid4()
    _house_rows(db_session, user, evaluation_id, run_id)
    _house_rows(db_session, user, evaluation_id, run_id, agent="gad")

    with pytest.raises(tool.IneligibleRunError, match="not for the SME agent"):
        tool.cleanup(db_session, run_id=run_id)
    assert db_session.query(PreferenceLog).count() == 2


def test_cleanup_ignores_rows_with_the_tag_from_another_user(
    db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    run_id = uuid.uuid4()
    db_session.add(
        PreferenceLog(
            evaluation_id=evaluation_id,
            user_id=user.user_id,
            agent_name="sme",
            criterion_id="OP-01",
            action="EDIT",
            edited_json={"score": 3},
            notes=tool.format_note(run_id),
        )
    )
    db_session.commit()
    assert tool.cleanup(db_session, run_id=run_id) == 0
    assert db_session.query(PreferenceLog).count() == 1


def test_cleanup_with_no_house_user_removes_nothing(db_session):
    assert tool.cleanup(db_session, run_id=uuid.uuid4()) == 0


def test_cli_cleanup_needs_both_confirmations_and_a_run_id(
    write_cli, capsys, db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    run_id = uuid.uuid4()
    _house_rows(db_session, user, evaluation_id, run_id)

    assert write_cli("--cleanup", "--run-id", str(run_id)) == 3
    assert (
        write_cli(
            "--cleanup",
            "--run-id",
            str(run_id),
            "--confirm",
            "SEED",
            "--confirm-target",
            "LOCAL",
        )
        == 3
    )
    assert (
        write_cli(
            "--cleanup",
            "--run-id",
            str(run_id),
            "--confirm",
            "CLEANUP",
            "--confirm-target",
            "wrong",
        )
        == 3
    )
    assert (
        write_cli("--cleanup", "--confirm", "CLEANUP", "--confirm-target", "LOCAL") == 2
    )
    assert (
        write_cli(
            "--cleanup",
            "--run-id",
            "nope",
            "--confirm",
            "CLEANUP",
            "--confirm-target",
            "LOCAL",
        )
        == 2
    )
    assert db_session.query(PreferenceLog).count() == 1

    assert (
        write_cli(
            "--cleanup",
            "--run-id",
            str(run_id),
            "--confirm",
            "CLEANUP",
            "--confirm-target",
            "LOCAL",
        )
        == 0
    )
    assert "Removed 1 correction(s)" in capsys.readouterr().out
    assert db_session.query(PreferenceLog).count() == 0


def test_cli_missing_ids_file_is_a_clean_error_not_a_refusal(
    cli, capsys, tmp_path, seeded_sme_rubric
):
    code = cli("--train-evaluations-file", str(tmp_path / "missing.txt"))
    out = capsys.readouterr().out
    assert code == 2
    assert "ERROR" in out and "missing.txt" in out
    assert "REFUSED" not in out and "Traceback" not in out
    assert len(out.strip().splitlines()) == 1  # one line
    out.encode("ascii")


def test_cli_unwritable_report_csv_is_a_clean_error(
    cli, capsys, tmp_path, db_session, user, seeded_sme_rubric
):
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")  # a file where a directory is needed
    code = cli(
        "--train-evaluations",
        str(evaluation_id),
        "--report-csv",
        str(blocker / "out.csv"),
    )
    out = capsys.readouterr().out
    assert code == 2
    assert "ERROR" in out and "REFUSED" not in out
    assert db_session.query(PreferenceLog).count() == 0


def test_cli_abort_and_refusal_messages_are_ascii_safe(
    cli, capsys, monkeypatch, db_session, user, seeded_sme_rubric
):
    def refuse(*_args, **_kwargs):
        raise tool.IneligibleRunError("bad ó title – x")

    monkeypatch.setattr(tool, "plan_run", refuse)
    assert cli("--train-evaluations", str(uuid.uuid4())) == 2
    out = capsys.readouterr().out
    assert "ABORTED" in out
    out.encode("ascii")

    def deny():
        raise PermissionError("no ó way")

    monkeypatch.setattr(tool, "validate_environment", deny)
    assert cli("--train-evaluations", str(uuid.uuid4())) == 3
    out = capsys.readouterr().out
    assert "REFUSED" in out
    out.encode("ascii")


def test_cli_without_verify_export_never_calls_the_exporter(
    cli, capsys, monkeypatch, db_session, user, seeded_sme_rubric
):
    def boom(_session):
        raise AssertionError("exporter must not run")

    monkeypatch.setattr(tool, "count_exportable_pairs", boom)
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    assert cli("--train-evaluations", str(evaluation_id)) == 0
    assert "Existing exportable SME pairs" not in capsys.readouterr().out


def test_dry_run_footer_tells_you_to_rerun_with_the_confirmations(
    cli, capsys, monkeypatch, db_session, user, seeded_sme_rubric
):
    monkeypatch.setattr(
        tool,
        "get_settings",
        lambda: types.SimpleNamespace(database_url="sqlite:///:memory:"),
    )
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    assert cli("--train-evaluations", str(evaluation_id)) == 0
    out = capsys.readouterr().out
    assert "re-run the same command with --confirm SEED --confirm-target LOCAL" in out


def test_dry_run_footer_does_not_suggest_a_command_without_a_target(
    cli, capsys, monkeypatch, db_session, user, seeded_sme_rubric
):
    monkeypatch.setattr(
        tool, "get_settings", lambda: types.SimpleNamespace(database_url="")
    )
    evaluation_id, _ = make_evaluation(db_session, user, FULL_ANSWER)
    assert cli("--train-evaluations", str(evaluation_id)) == 0
    out = capsys.readouterr().out
    assert "--confirm SEED" not in out
    assert "DATABASE_URL" in out


def test_cleanup_hints_when_the_run_id_matches_nothing(
    write_cli, capsys, db_session, user, seeded_sme_rubric
):
    tool.get_or_create_house_user(db_session)
    db_session.commit()
    code = write_cli(
        "--cleanup",
        "--run-id",
        str(uuid.uuid4()),
        "--confirm",
        "CLEANUP",
        "--confirm-target",
        "LOCAL",
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "Removed 0 rows. Check the run id" in out


def test_cleanup_leaves_old_synthetic_rows_and_non_edit_tagged_rows(
    db_session, user, seeded_sme_rubric
):
    evaluation_id = _eval_for_writing(db_session, user)
    run_id = uuid.uuid4()
    old_seeder.generate(db_session, count=2)
    synthetic_before = db_session.query(PreferenceLog).count()
    assert synthetic_before > 0
    synthetic_user = (
        db_session.query(User).filter_by(email=old_seeder.SYNTHETIC_USER_EMAIL).one()
    )
    house = tool.get_or_create_house_user(db_session)
    # the old seeder's rows also carry a note prefix; make sure they are untouched
    assert all(
        r.notes.startswith("synthetic-dpo-seed:")
        for r in db_session.query(PreferenceLog).filter_by(
            user_id=synthetic_user.user_id
        )
    )
    accept = PreferenceLog(
        evaluation_id=evaluation_id,
        user_id=house.user_id,
        agent_name="sme",
        criterion_id="OP-01",
        action="ACCEPT",
        notes=tool.format_note(run_id),
    )
    db_session.add(accept)
    db_session.commit()
    _house_rows(db_session, user, evaluation_id, run_id)

    assert tool.cleanup(db_session, run_id=run_id) == 1

    assert db_session.query(PreferenceLog).count() == synthetic_before + 1
    assert db_session.get(PreferenceLog, accept.log_id) is not None
