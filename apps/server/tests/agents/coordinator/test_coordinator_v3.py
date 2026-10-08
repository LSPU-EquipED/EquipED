"""V3 contract: fixed source denominator, independent official/advisory coverage."""

import json
from dataclasses import replace
from uuid import uuid4

import pytest
from server.modules.agents.contracts import (
    CoordinatorAlignmentAdvisory,
    parse_advisory_output,
)
from server.modules.agents.coordinator.agent import Coordinator
from server.modules.agents.coordinator.objective_gauging import (
    coverage_score,
    inventory_source,
    validate_matches,
)
from server.modules.agents.coordinator.packing import pack_domains
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.rubrics.contracts import (
    LlmRubricGuidanceConfig,
    ObjectiveGaugingConfig,
)
from server.modules.rubrics.manifests import get_agent_manifest, validate_form
from server.modules.rubrics.snapshot_contracts import build_evaluation_form_snapshot
from server.modules.synthesis.exceptions import EvaluationResultIntegrityError
from server.modules.synthesis.result_integrity import build_persistable_agent_result
from server.tests.agents.helpers import SequencedFakeClient, make_coordinator_snapshot

SOURCE = (
    "Learning Objectives:\n1. Add two integers.\n2. Explain integer addition.\n"
    "Assessment:\nCompute 2 + 2.\nReferences:\nA book.\n"
)
CURRICULUM = "Students perform integer addition and explain its properties."


def make_v3_snapshot(evaluation_id=None, form=None):
    if form is None:
        form = make_coordinator_snapshot(evaluation_id)[0].form
    domains = tuple(
        d.model_copy(
            update={
                "criteria": tuple(
                    c.model_copy(
                        update={
                            "strategy_config": ObjectiveGaugingConfig()
                            if c.criterion_code == "A-05"
                            else LlmRubricGuidanceConfig(
                                guidance="Evaluate using direct SLM evidence."
                            ),
                            **(
                                {
                                    "title": "Objective Gauging",
                                    "description": "Objectives are gauged effectively.",
                                }
                                if c.criterion_code == "A-05"
                                else {}
                            ),
                        }
                    )
                    for c in d.criteria
                )
            }
        )
        for d in form.domains
    )
    form = form.model_copy(update={"adapter_version": 3, "domains": domains})
    return build_evaluation_form_snapshot(evaluation_id or uuid4(), form)


def matches(*, curriculum=True):
    return {
        "objective_matches": [
            {
                "objective_id": f"OBJ-{i:04d}",
                "assessment_matched": i == 1,
                "assessment_excerpt": "Compute 2 + 2." if i == 1 else "",
                "curriculum_matched": curriculum,
                "curriculum_excerpt": CURRICULUM if curriculum else "",
            }
            for i in (1, 2)
        ]
    }


def run_v3(snapshot=None, document_id=None, extra_responses=None, source=SOURCE):
    snapshot = snapshot or make_v3_snapshot()
    envelopes = []
    for packed in pack_domains(snapshot.form.domains):
        criteria = [c for c in packed if c.criterion_code != "A-05"]
        if not criteria:
            continue
        envelopes.append(
            {
                "summary": "review",
                "criterion_measurements": [
                    {
                        "criterion_id": c.criterion_code,
                        "criterion_title": c.title,
                        "score": 4,
                        "evidence": "Compute 2 + 2.",
                        "reasoning": "Supported.",
                    }
                    for c in criteria
                ],
            }
        )
    fake = SequencedFakeClient(envelopes + (extra_responses or [matches()]))
    result = Coordinator(llm_client=fake).run(
        evaluation_id=snapshot.evaluation_id,
        document_id=document_id or uuid4(),
        form_snapshot=snapshot,
        chunk_infos=[{"chunk_id": str(uuid4())}],
        canonical_source_text=source,
        curriculum_id=uuid4(),
        curriculum_context=CURRICULUM,
    )
    return snapshot, result


def test_inventory_preserves_exact_multiline_spans_and_multiple_sections():
    source = (
        "# Objectives\n- Add integers\n  using a number line.\n# Content\n"
        "Discussion\n# Learning Outcomes\n1) Explain addition.\n"
        "# Quiz\nExplain addition.\n"
    )
    inventory = inventory_source(source)
    assert len(inventory.objectives) == 2
    assert inventory.objectives[0].text == "Add integers\n  using a number line."
    for objective in inventory.objectives:
        assert objective.text == source[objective.start : objective.end]
    assert inventory.assessment_sections == ("Explain addition.",)


@pytest.mark.parametrize(
    "source",
    [
        "Objectives:\n1. Add.\n2. Add.\nAssessment:\nAdd 1 + 1.",
        "Objectives:\nUnnumbered objective.\nAssessment:\nA task.",
        "Objectives:\nAssessment:\nA task.",
        "Objectives:\n1. Add.\nUnknown Section:\n2. Not an objective.",
        "Goals and Objectives:\n1. Add.",
        "Objectives:\n1. Add.\n3. Subtract.",
        "Objectives:\n- Add.\n  - A nested sub-item.",
        "Objectives:\n1. Add.\n- A mixed bullet list.",
        "A lesson without an explicit inventory.",
        "Assessment:\nObjectives:\n1. An embedded exercise objective.",
    ],
)
def test_ambiguous_inventory_fails_closed(source):
    with pytest.raises(AgentExecutionError):
        inventory_source(source)


def test_inventory_accepts_uppercase_entries_and_preserves_trimmed_spans():
    source = (
        "OBJECTIVES:\r\n1. ADD TWO INTEGERS.  \r\nASSESSMENT:\r\n1. COMPUTE 2 + 2.\r\n"
    )
    inventory = inventory_source(source)
    objective = inventory.objectives[0]
    assert objective.text == "ADD TWO INTEGERS."
    assert source[objective.start : objective.end] == objective.text
    assert inventory.assessment_sections == ("1. COMPUTE 2 + 2.",)


def test_inventory_overflow_and_truncation_fail():
    from server.modules.agents.runtime.slicing import GAP_MARKER

    for source in (SOURCE + "x" * 200000, SOURCE + GAP_MARKER):
        with pytest.raises(AgentExecutionError):
            inventory_source(source)


@pytest.mark.parametrize(
    "matched,total,score",
    [(0, 5, 1), (1, 5, 2), (2, 5, 2), (1, 2, 3), (4, 5, 4), (5, 5, 4)],
)
def test_fixed_coverage_bands(matched, total, score):
    assert coverage_score(matched, total) == score


def test_missing_assessments_keep_objectives_unmatched():
    inventory = inventory_source(
        "Objectives:\n1. Add two integers.\nContent:\nA lesson."
    )
    payload = matches()
    payload["objective_matches"] = payload["objective_matches"][:1]
    row = validate_matches(json.dumps(payload), inventory, CURRICULUM)[
        "objective_matches"
    ][0]
    assert row["assessment_matched"] is False
    assert row["assessment_rejected"] is True


def test_unsupported_matches_do_not_shrink_denominator():
    payload = matches()
    payload["objective_matches"][0].update(
        assessment_excerpt="Add two integers.", curriculum_excerpt="Add two integers."
    )
    rows = validate_matches(json.dumps(payload), inventory_source(SOURCE), CURRICULUM)[
        "objective_matches"
    ]
    assert len(rows) == 2
    assert rows[0]["assessment_matched"] is False
    assert rows[0]["curriculum_matched"] is False
    assert rows[0]["assessment_rejected"] is True
    assert rows[0]["curriculum_rejected"] is True


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown", "boolean"])
def test_model_cannot_shrink_or_replace_inventory(mutation):
    payload = matches()
    if mutation == "missing":
        payload["objective_matches"].pop()
    elif mutation == "duplicate":
        payload["objective_matches"][1]["objective_id"] = "OBJ-0001"
    elif mutation == "unknown":
        payload["objective_matches"][1]["objective_id"] = "OBJ-9999"
    else:
        payload["objective_matches"][0]["assessment_matched"] = 1
    with pytest.raises(AgentExecutionError):
        validate_matches(json.dumps(payload), inventory_source(SOURCE), CURRICULUM)


def test_v3_official_mean_is_ten_rows_and_advisory_is_independent():
    snap, result = run_v3()
    assert len(result.criterion_scores) == 10
    assert result.criterion_scores[-1].criterion_id == "A-05"
    assert result.criterion_scores[-1].score == 3
    assert "Measured objectives: OBJ-0001" in result.criterion_scores[-1].justification
    assert (
        "Unmeasured objectives: OBJ-0002" in result.criterion_scores[-1].justification
    )
    assert result.subtotal == 3.9
    assert "Objective gauging (A-05)" in result.summary
    assert "Curriculum alignment (A-05)" not in result.summary
    assert result.advisory_outputs.score == 4
    assert (
        result.generations[-1].response_contract_key
        == "coordinator_objective_coverage.v1"
    )
    assert result.generations[-1].criterion_ids == ("A-05",)
    persisted = build_persistable_agent_result(result, snap)
    assert (
        parse_advisory_output(json.loads(persisted.advisory_outputs_json))
        == result.advisory_outputs
    )


def test_full_reference_overflow_fails_before_llm_call():
    from server.modules.agents.coordinator.execution import execute_objective_envelope
    from server.modules.agents.runtime.llm import RunLLMClient

    fake = SequencedFakeClient([])
    with pytest.raises(AgentExecutionError, match="full-source prompt budget"):
        execute_objective_envelope(
            inventory_source(SOURCE),
            RunLLMClient(fake, "coordinator"),
            CURRICULUM * 1000,
        )
    assert fake.calls == 0


def test_v3_respects_frozen_domain_order_despite_envelope_affinity():
    form = make_coordinator_snapshot()[0].form
    form = form.model_copy(
        update={
            "domains": tuple(
                d.model_copy(update={"display_order": 1 - d.display_order})
                for d in form.domains
            )
        }
    )
    snapshot, result = run_v3(snapshot=make_v3_snapshot(form=form))
    assert (
        tuple(s.criterion_id for s in result.criterion_scores)
        == snapshot.criterion_codes
    )
    assert result.subtotal == 3.9
    build_persistable_agent_result(result, snapshot)


def test_lower_advisory_score_does_not_change_official_mean():
    _, high = run_v3()
    _, low = run_v3(extra_responses=[matches(curriculum=False)])
    assert high.advisory_outputs.score == 4
    assert low.advisory_outputs.score == 1
    assert high.subtotal == low.subtotal == 3.9


def test_old_contract_rejects_new_scored_advisory():
    snapshot, result = run_v3()
    old = make_coordinator_snapshot(snapshot.evaluation_id)[0]
    with pytest.raises(
        EvaluationResultIntegrityError, match="does not support advisory_outputs"
    ):
        build_persistable_agent_result(result, old)


def test_missing_objective_rows_repair_once_then_fail():
    with pytest.raises(AgentExecutionError, match="bounded repair"):
        run_v3(extra_responses=[{"objective_matches": []}, {"objective_matches": []}])


def test_missing_objective_rows_can_repair_without_changing_inventory():
    _, result = run_v3(extra_responses=[{"objective_matches": []}, matches()])
    assert result.metadata["envelope_status"]["envelope_2"] == "repaired"
    assert len(result.advisory_outputs.objective_matches) == 2


def test_no_c01_or_forged_a05_cannot_persist():
    snapshot, result = run_v3()
    for forged in (
        replace(result, advisory_outputs=None),
        replace(
            result,
            criterion_scores=result.criterion_scores[:-1]
            + (replace(result.criterion_scores[-1], score=4),),
        ),
        replace(result, subtotal=4.0),
    ):
        with pytest.raises(EvaluationResultIntegrityError):
            build_persistable_agent_result(forged, snapshot)
    payload = result.advisory_outputs.to_dict()
    payload["score"] = 1
    with pytest.raises(ValueError):
        CoordinatorAlignmentAdvisory.from_dict(payload)


def test_default_manifest_and_historical_snapshots_are_unchanged():
    assert get_agent_manifest("coordinator").adapter_version == 2
    assert get_agent_manifest("coordinator", 1).required_criterion_strategies == (
        ("A-05", "curriculum_alignment"),
    )
    old = make_coordinator_snapshot()[0]
    assert validate_form(old.form, get_agent_manifest("coordinator", 2)).is_valid
    assert not validate_form(old.form, get_agent_manifest("coordinator", 3)).is_valid
