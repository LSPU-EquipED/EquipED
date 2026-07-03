"""Compatibility aggregator for GAD criterion prompts and scoring.

Manual edits should happen in the criterion-specific modules:
- gad_criterion_01.py
- gad_criterion_02.py
- gad_criterion_03.py
- gad_criterion_04.py
- gad_criterion_05.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .gad_criterion_01 import (
    CRITERION_ID as GAD_01_ID,
    CRITERION_KIND as GAD_01_KIND,
    CRITERION_TITLE as GAD_01_TITLE,
    GAD_ROW_1_PROMPT,
    score_stereotype_instances,
)
from .gad_criterion_02 import (
    CRITERION_ID as GAD_02_ID,
    CRITERION_KIND as GAD_02_KIND,
    CRITERION_TITLE as GAD_02_TITLE,
    GAD_ROW_2_PROMPT,
    score_representation_balance,
)
from .gad_criterion_03 import (
    CRITERION_ID as GAD_03_ID,
    CRITERION_KIND as GAD_03_KIND,
    CRITERION_TITLE as GAD_03_TITLE,
    GAD_ROW_3_PROMPT,
    score_respect_potential_instances,
)
from .gad_criterion_04 import (
    CRITERION_ID as GAD_04_ID,
    CRITERION_KIND as GAD_04_KIND,
    CRITERION_TITLE as GAD_04_TITLE,
    GAD_ROW_4_PROMPT,
    score_life_experience_instances,
)
from .gad_criterion_05 import (
    CRITERION_ID as GAD_05_ID,
    CRITERION_KIND as GAD_05_KIND,
    CRITERION_TITLE as GAD_05_TITLE,
    GAD_ROW_5_PROMPT,
    score_peace_equality_instances,
)

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


GAD_CRITERIA: tuple[GadCriterion, ...] = (
    GadCriterion(
        criterion_id=GAD_01_ID,
        title=GAD_01_TITLE,
        kind=GAD_01_KIND,
        prompt=GAD_ROW_1_PROMPT,
    ),
    GadCriterion(
        criterion_id=GAD_02_ID,
        title=GAD_02_TITLE,
        kind=GAD_02_KIND,
        prompt=GAD_ROW_2_PROMPT,
    ),
    GadCriterion(
        criterion_id=GAD_03_ID,
        title=GAD_03_TITLE,
        kind=GAD_03_KIND,
        prompt=GAD_ROW_3_PROMPT,
    ),
    GadCriterion(
        criterion_id=GAD_04_ID,
        title=GAD_04_TITLE,
        kind=GAD_04_KIND,
        prompt=GAD_ROW_4_PROMPT,
    ),
    GadCriterion(
        criterion_id=GAD_05_ID,
        title=GAD_05_TITLE,
        kind=GAD_05_KIND,
        prompt=GAD_ROW_5_PROMPT,
    ),
)

GAD_CRITERIA_BY_TITLE = {criterion.title: criterion for criterion in GAD_CRITERIA}


__all__ = [
    "GAD_CRITERIA",
    "GAD_CRITERIA_BY_TITLE",
    "GAD_01_ID",
    "GAD_01_KIND",
    "GAD_01_TITLE",
    "GAD_02_ID",
    "GAD_02_KIND",
    "GAD_02_TITLE",
    "GAD_03_ID",
    "GAD_03_KIND",
    "GAD_03_TITLE",
    "GAD_04_ID",
    "GAD_04_KIND",
    "GAD_04_TITLE",
    "GAD_05_ID",
    "GAD_05_KIND",
    "GAD_05_TITLE",
    "GadCriterion",
    "GadCriterionKind",
    "GAD_ROW_1_PROMPT",
    "GAD_ROW_2_PROMPT",
    "GAD_ROW_3_PROMPT",
    "GAD_ROW_4_PROMPT",
    "GAD_ROW_5_PROMPT",
    "score_life_experience_instances",
    "score_peace_equality_instances",
    "score_representation_balance",
    "score_respect_potential_instances",
    "score_stereotype_instances",
]
