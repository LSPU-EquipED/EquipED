"""Server adapters for the qualitative Coordinator v4 result contract."""

from equiped_harness.agents.coordinator.contracts import CoordinatorAlignmentJudgment
from equiped_harness.agents.coordinator.rubric import guidance_for
from equiped_harness.contracts.snapshots import build_evaluation_form_snapshot
from equiped_harness.envelope_map import envelope_criteria_map_from_snapshot
from server.modules.synthesis.matrix import compute_synthesized_score
from server.tests.agents.helpers import make_coordinator_snapshot


def _v4_snapshot():
    old = make_coordinator_snapshot()[0]
    domains = tuple(
        domain.model_copy(
            update={
                "criteria": tuple(
                    criterion.model_copy(
                        update={
                            "strategy_config": guidance_for(criterion.criterion_code)
                        }
                    )
                    for criterion in domain.criteria
                )
            }
        )
        for domain in old.form.domains
    )
    form = old.form.model_copy(update={"adapter_version": 4, "domains": domains})
    return build_evaluation_form_snapshot(old.evaluation_id, form)


def test_v6_envelope_and_official_matrix_exclude_advisory_criterion():
    snapshot = _v4_snapshot()
    envelope_map = envelope_criteria_map_from_snapshot(
        snapshot, "coordinator", execution_contract="coordinator_current.v6"
    )
    official_codes = {
        c.criterion_code for criteria in envelope_map.values() for c in criteria
    }
    assert len(official_codes) == 10
    assert "C-01" not in official_codes

    result = type(
        "Result",
        (),
        {
            "agent_name": "coordinator",
            "success": True,
            "subtotal": 3.0,
            "advisory_outputs": {"contract": "coordinator_alignment.v2", "score": 1},
        },
    )()
    matrix = compute_synthesized_score([result])
    coordinator = matrix["domain_scores"]["coordinator"]
    assert coordinator["subtotal"] == 3.0
    assert coordinator["advisory_outputs"]["score"] == 1


def test_v2_alignment_advisory_parses_as_its_versioned_contract():
    data = {
        "contract": "coordinator_alignment.v2",
        "criterion_id": "C-01",
        "criterion_title": "Curriculum Alignment",
        "advisory_only": True,
        "score": 3,
        "justification": (
            "The reviewed concepts align directly, with one limited gap in depth."
        ),
        "evidence": [
            {"source": "slm", "excerpt": "Students explain integer addition."},
            {"source": "curriculum", "excerpt": "Students perform integer addition."},
        ],
        "objective_matches": [],
    }
    from equiped_harness.contracts.results import parse_advisory_output

    parsed = parse_advisory_output(data)
    assert isinstance(parsed, CoordinatorAlignmentJudgment)
    assert parsed.to_dict() == data
