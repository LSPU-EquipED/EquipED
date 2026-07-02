"""Prompt and scoring definitions for the GAD agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GadCriterionKind = Literal[
    "stereotype_instances",
    "representation_balance",
    "respect_potential_instances",
    "life_experience_instances",
    "peace_equality_instances",
]


@dataclass(frozen=True, slots=True)
class GadCriterion:
    criterion_id: str
    title: str
    kind: GadCriterionKind
    prompt: str


GAD_ROW_1_PROMPT = (
    "Analyze the learning material and identify instances of gender stereotypes "
    "or gender-biased representations.\n\n"
    "Count an instance if it:\n\n"
    "- Reinforces stereotypes about gender roles, abilities, behaviors, "
    "occupations, or characteristics.\n"
    "- Explicitly or implicitly portrays one gender using stereotypical "
    "assumptions.\n\n"
    "Do not count:\n\n"
    "- Discussions of gender stereotypes presented for educational, analytical, "
    "historical, or critical purposes.\n"
    "- Gender-neutral content.\n\n"
    "Count each unique instance once.\n\n"
    "Return only valid JSON\n"
    "{\n"
    '  "criterion": "The material is free from gender stereotypes",\n'
    '  "instance_count": 0,\n'
    '  "instances": [\n'
    "    {\n"
    '      "excerpt": "",\n'
    '      "explanation": ""\n'
    "    }\n"
    "  ],\n"
    '  "summary": ""\n'
    "}"
)

GAD_ROW_2_PROMPT = (
    "Analyze the learning material and count the number of meaningful female "
    "and male representations.\n\n"
    "A meaningful representation includes:\n\n"
    "- Named individuals\n"
    "- Characters\n"
    "- Illustrations depicting people\n"
    "- Examples, scenarios, or case studies involving people\n"
    "- Explicit gender references (e.g., woman, man, girl, boy, female, male)\n"
    "- Gender-specific pronouns (e.g., she, her, he, him)\n\n"
    "Count each meaningful representation only once within the same discussion, "
    "example, scenario, or case study.\n\n"
    "If the same individual appears in different examples or scenarios, count "
    "each appearance separately.\n\n"
    "Do not infer gender when it is ambiguous.\n\n"
    "Ignore gender-neutral references.\n\n"
    "If no meaningful female or male representations are present, return 0 for "
    "both counts.\n\n"
    "Return only valid JSON\n"
    "{\n"
    '  "criterion": "The material shows females and males an equal number of '
    'times",\n'
    '  "female_count": 0,\n'
    '  "male_count": 0,\n'
    '  "summary": ""\n'
    "}"
)

GAD_ROW_3_PROMPT = (
    "Analyze the learning material and identify instances that portray one "
    "gender as less capable, less respected, less deserving, or having fewer "
    "opportunities than another.\n\n"
    "Do not count discussions of discrimination presented for educational, "
    "analytical, historical, or critical purposes.\n\n"
    "Count each unique instance once.\n\n"
    "Females and males are presented with equal respect and potential.\n"
    "Return only valid JSON\n"
    "{\n"
    '  "criterion": "The material shows females and males with equal respect '
    'and potential",\n'
    '  "instance_count": 0,\n'
    '  "instances": [\n'
    "    {\n"
    '      "excerpt": "",\n'
    '      "explanation": ""\n'
    "    }\n"
    "  ],\n"
    '  "summary": ""\n'
    "}"
)

GAD_ROW_4_PROMPT = (
    "Analyze the learning material and identify instances where the material:\n\n"
    "- Excludes one gender's experiences.\n"
    "- Disproportionately favors one gender's experiences.\n"
    "- Assumes that activities, roles, responsibilities, interests, or "
    "aspirations belong primarily to one gender.\n\n"
    "Do not count:\n\n"
    "- Gender-neutral examples.\n"
    "- Discussions presented for educational, analytical, historical, or "
    "critical purposes.\n\n"
    "Count each unique instance once.\n\n"
    "Return only valid JSON\n"
    "{\n"
    '  "criterion": "The material reflects the needs and life experiences of '
    'both male and female students",\n'
    '  "instance_count": 0,\n'
    '  "instances": [\n'
    "    {\n"
    '      "excerpt": "",\n'
    '      "explanation": ""\n'
    "    }\n"
    "  ],\n"
    '  "summary": ""\n'
    "}"
)

GAD_ROW_5_PROMPT = (
    "Analyze the learning material and identify instances of discriminatory, "
    "prejudicial, exclusionary, or inequality-promoting content related to:\n\n"
    "- Gender\n"
    "- Race\n"
    "- Social class\n"
    "- Disability\n"
    "- Religion\n"
    "- Sexual orientation\n"
    "- Ethnic background\n\n"
    "Do not count:\n\n"
    "Historical discussions.\n"
    "Educational discussions.\n"
    "Analytical or critical discussions of discrimination.\n\n"
    "Count each unique instance once.\n\n"
    "Return only valid JSON\n"
    "{\n"
    '  "criterion": "The material promotes peace and equality regardless of '
    'gender, race, class, disability, religion, sexual orientation, or ethnic '
    'background",\n'
    '  "instance_count": 0,\n'
    '  "instances": [\n'
    "    {\n"
    '      "excerpt": "",\n'
    '      "explanation": "",\n'
    '      "category": ""\n'
    "    }\n"
    "  ],\n"
    '  "summary": ""\n'
    "}"
)

GAD_CRITERIA: tuple[GadCriterion, ...] = (
    GadCriterion(
        criterion_id="GAD-01",
        title="The material is free from gender stereotypes",
        kind="stereotype_instances",
        prompt=GAD_ROW_1_PROMPT,
    ),
    GadCriterion(
        criterion_id="GAD-02",
        title="The material shows females and males an equal number of times",
        kind="representation_balance",
        prompt=GAD_ROW_2_PROMPT,
    ),
    GadCriterion(
        criterion_id="GAD-03",
        title="The material shows females and males with equal respect and potential",
        kind="respect_potential_instances",
        prompt=GAD_ROW_3_PROMPT,
    ),
    GadCriterion(
        criterion_id="GAD-04",
        title=(
            "The material reflects the needs and life experiences of both male "
            "and female students"
        ),
        kind="life_experience_instances",
        prompt=GAD_ROW_4_PROMPT,
    ),
    GadCriterion(
        criterion_id="GAD-05",
        title=(
            "The material promotes peace and equality regardless of gender, race, "
            "class, disability, religion, sexual orientation, or ethnic background"
        ),
        kind="peace_equality_instances",
        prompt=GAD_ROW_5_PROMPT,
    ),
)

GAD_CRITERIA_BY_TITLE = {criterion.title: criterion for criterion in GAD_CRITERIA}


def score_stereotype_instances(instance_count: int) -> int:
    if instance_count == 0:
        return 4
    if instance_count == 1:
        return 3
    if instance_count <= 3:
        return 2
    return 1


def score_representation_balance(female_count: int, male_count: int) -> int:
    difference = abs(female_count - male_count)
    if difference <= 2:
        return 4
    if difference <= 5:
        return 3
    if difference <= 10:
        return 2
    return 1


def score_respect_potential_instances(instance_count: int) -> int:
    if instance_count == 0:
        return 4
    if instance_count <= 2:
        return 3
    if instance_count <= 5:
        return 2
    return 1


def score_life_experience_instances(instance_count: int) -> int:
    if instance_count == 0:
        return 4
    if instance_count <= 2:
        return 3
    if instance_count <= 5:
        return 2
    return 1


def score_peace_equality_instances(instance_count: int) -> int:
    if instance_count == 0:
        return 4
    if instance_count <= 2:
        return 3
    if instance_count <= 5:
        return 2
    return 1


__all__ = [
    "GAD_CRITERIA",
    "GAD_CRITERIA_BY_TITLE",
    "GAD_ROW_1_PROMPT",
    "GAD_ROW_2_PROMPT",
    "GAD_ROW_3_PROMPT",
    "GAD_ROW_4_PROMPT",
    "GAD_ROW_5_PROMPT",
    "GadCriterion",
    "score_life_experience_instances",
    "score_peace_equality_instances",
    "score_representation_balance",
    "score_respect_potential_instances",
    "score_stereotype_instances",
]
