"""Shared test helpers for ITSO unit and contract suites."""

from __future__ import annotations

from uuid import UUID, uuid4

from server.modules.agents.itso.response import ITSO_CRITERIA_TITLES
from server.modules.rubrics.contracts import (
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    LlmScoreDescriptor,
)
from server.modules.rubrics.snapshot_contracts import (
    EvaluationFormSnapshotDTO,
    build_evaluation_form_snapshot,
)


def make_itso_test_snapshot(
    evaluation_id: UUID | None = None,
    criteria_specs: tuple[tuple[str, str], ...] | None = None,
    adapter_key: str = "itso",
    adapter_version: int = 1,
    agent_id: str = "itso",
) -> EvaluationFormSnapshotDTO:
    """Build a valid EvaluationFormSnapshotDTO for ITSO test suites."""
    eval_id = evaluation_id or uuid4()
    set_id = uuid4()
    specs = (
        criteria_specs
        if criteria_specs is not None
        else tuple(ITSO_CRITERIA_TITLES.items())
    )

    crit_defs = tuple(
        CriterionDefinition(
            rubric_criterion_id=uuid4(),
            criterion_code=cid,
            title=title,
            description=f"Description for {cid}",
            scoring_rule=f"Scoring rule for {cid}",
            display_order=idx,
            strategy_config=LlmRubricGuidanceConfig(
                guidance=f"Guidance for {cid}",
                level_descriptors=(
                    LlmScoreDescriptor(score=1, descriptor=f"Level 1 for {cid}"),
                    LlmScoreDescriptor(score=2, descriptor=f"Level 2 for {cid}"),
                    LlmScoreDescriptor(score=3, descriptor=f"Level 3 for {cid}"),
                    LlmScoreDescriptor(score=4, descriptor=f"Level 4 for {cid}"),
                ),
            ),
        )
        for idx, (cid, title) in enumerate(specs)
    )
    dom = DomainDefinition(
        rubric_domain_id=uuid4(),
        code="DOM-ITSO",
        title="ITSO Domain",
        display_order=0,
        criteria=crit_defs,
    )
    form = FormDefinition(
        rubric_set_id=set_id,
        agent_id=agent_id,
        name="ITSO Form",
        version_number=1,
        adapter_key=adapter_key,
        adapter_version=adapter_version,
        domains=(dom,),
    )
    return build_evaluation_form_snapshot(eval_id, form)
