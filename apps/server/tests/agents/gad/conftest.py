"""Shared fixtures and snapshot builders for GAD agent tests."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    RatioBandConfig,
)
from server.modules.rubrics.snapshot_contracts import (
    EvaluationFormSnapshotDTO,
    build_evaluation_form_snapshot,
)

REVISION_1_GAD_RULES: dict[str, str] = {
    "GAD-01": (
        "Count each unique instance of gender stereotypes or gender-biased "
        "representations — content that reinforces stereotypes about gender "
        "roles, abilities, behaviors, occupations, or characteristics, or that "
        "explicitly or implicitly portrays one gender using stereotypical "
        "assumptions. Do NOT count discussions of gender stereotypes presented "
        "for educational, analytical, historical, or critical purposes, or "
        "gender-neutral content. Count each unique instance once."
    ),
    "GAD-02": (
        "Count meaningful female and male representations: named individuals, "
        "names listed under a gender-labeled group or heading, characters, "
        "illustrations depicting people, examples or case studies involving "
        "people, explicit gender references (woman, man, girl, boy, female, "
        "male), and gender-specific pronouns (she, her, he, him). Count each "
        "meaningful representation once within the same discussion, example, or "
        "scenario; if the same individual appears in different examples, count "
        "each appearance separately. Do NOT infer gender when it is ambiguous, "
        "and ignore gender-neutral references."
    ),
    "GAD-03": (
        "Count each unique instance that portrays one gender as less capable, "
        "less respected, less deserving, or as having fewer opportunities than "
        "another. Do NOT count discussions of discrimination presented for "
        "educational, analytical, historical, or critical purposes. Count each "
        "unique instance once."
    ),
    "GAD-04": (
        "Count each unique instance where the material excludes one gender's "
        "experiences, disproportionately favors one gender's experiences, or "
        "assumes that activities, roles, responsibilities, interests, or "
        "aspirations belong primarily to one gender. Do NOT count "
        "gender-neutral examples or discussions presented for educational, "
        "analytical, historical, or critical purposes. Count each unique "
        "instance once."
    ),
    "GAD-05": (
        "Count each unique instance of discriminatory, prejudicial, "
        "exclusionary, or inequality-promoting content related to gender, race, "
        "social class, disability, religion, sexual orientation, or ethnic "
        "background. Do NOT count historical, educational, analytical, or "
        "critical discussions of discrimination. Count each unique instance "
        "once."
    ),
}

REVISION_1_GAD_CRITERIA: tuple[CriterionDefinition, ...] = (
    CriterionDefinition(
        rubric_criterion_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        criterion_code="GAD-01",
        title="The material is free from gender stereotypes",
        description="The material is free from gender stereotypes.",
        scoring_rule=REVISION_1_GAD_RULES["GAD-01"],
        display_order=1,
        strategy_config=CountBandConfig(
            strategy="count_band",
            mode="maximum_count",
            threshold_4=0,
            threshold_3=1,
            threshold_2=3,
        ),
    ),
    CriterionDefinition(
        rubric_criterion_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        criterion_code="GAD-02",
        title="The material shows females and males an equal number of times",
        description="The material shows females and males an equal number of times.",
        scoring_rule=REVISION_1_GAD_RULES["GAD-02"],
        display_order=2,
        strategy_config=RatioBandConfig(
            strategy="ratio_band",
            mode="absolute_difference",
            threshold_4=2.0,
            threshold_3=5.0,
            threshold_2=10.0,
        ),
    ),
    CriterionDefinition(
        rubric_criterion_id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
        criterion_code="GAD-03",
        title="The material shows females and males with equal respect and potential",
        description=(
            "The material shows females and males with equal respect and potential."
        ),
        scoring_rule=REVISION_1_GAD_RULES["GAD-03"],
        display_order=3,
        strategy_config=CountBandConfig(
            strategy="count_band",
            mode="maximum_count",
            threshold_4=0,
            threshold_3=2,
            threshold_2=5,
        ),
    ),
    CriterionDefinition(
        rubric_criterion_id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
        criterion_code="GAD-04",
        title=(
            "The material reflects the needs and life experiences of "
            "both male and female students"
        ),
        description=(
            "The material reflects the needs and life experiences of "
            "both male and female students."
        ),
        scoring_rule=REVISION_1_GAD_RULES["GAD-04"],
        display_order=4,
        strategy_config=CountBandConfig(
            strategy="count_band",
            mode="maximum_count",
            threshold_4=0,
            threshold_3=2,
            threshold_2=5,
        ),
    ),
    CriterionDefinition(
        rubric_criterion_id=uuid.UUID("00000000-0000-0000-0000-000000000005"),
        criterion_code="GAD-05",
        title=(
            "The material promotes peace and equality regardless of gender, race, "
            "class, disability, religion, sexual orientation, or ethnic background"
        ),
        description=(
            "The material promotes peace and equality regardless of gender, race, "
            "class, disability, religion, sexual orientation, or ethnic background."
        ),
        scoring_rule=REVISION_1_GAD_RULES["GAD-05"],
        display_order=5,
        strategy_config=CountBandConfig(
            strategy="count_band",
            mode="maximum_count",
            threshold_4=0,
            threshold_3=2,
            threshold_2=5,
        ),
    ),
)


def make_gad_snapshot(
    evaluation_id: uuid.UUID | None = None,
    criteria: tuple[CriterionDefinition, ...] | list[CriterionDefinition] | None = None,
    rubric_set_id: uuid.UUID | None = None,
    name: str = "GAD Rubric v1",
    version_number: int = 1,
) -> EvaluationFormSnapshotDTO:
    """Build a canonically ordered, hashed EvaluationFormSnapshotDTO for GAD tests."""
    eval_id = evaluation_id or uuid.uuid4()
    set_id = rubric_set_id or uuid.uuid4()
    crit_list = tuple(criteria) if criteria is not None else REVISION_1_GAD_CRITERIA
    dom = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="GAD",
        title="Inclusivity & Gender Sensitivity",
        display_order=1,
        criteria=crit_list,
    )
    form = FormDefinition(
        rubric_set_id=set_id,
        agent_id="gad",
        name=name,
        version_number=version_number,
        adapter_key="gad",
        adapter_version=1,
        domains=(dom,),
    )
    return build_evaluation_form_snapshot(eval_id, form)


@pytest.fixture
def default_gad_snapshot() -> Any:
    return make_gad_snapshot()
