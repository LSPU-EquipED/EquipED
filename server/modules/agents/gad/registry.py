"""Registry, validation, and rendering for code-scored GAD criteria."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError
from .female_male_count import (
    CRITERION_ID as BALANCE_ID,
)
from .female_male_count import (
    CRITERION_TITLE as BALANCE_TITLE,
)
from .female_male_count import (
    GAD_ROW_2_PROMPT,
    score_representation_balance,
)
from .grounding import MAX_INSTANCES_PER_CRITERION, ground_instances
from .life_experiences import (
    CRITERION_ID as LIFE_ID,
)
from .life_experiences import (
    CRITERION_TITLE as LIFE_TITLE,
)
from .life_experiences import (
    GAD_ROW_4_PROMPT,
    score_life_experience_instances,
)
from .peace_and_equality import (
    CRITERION_ID as PEACE_ID,
)
from .peace_and_equality import (
    CRITERION_TITLE as PEACE_TITLE,
)
from .peace_and_equality import (
    GAD_ROW_5_PROMPT,
    score_peace_equality_instances,
)
from .potential import (
    CRITERION_ID as POTENTIAL_ID,
)
from .potential import (
    CRITERION_TITLE as POTENTIAL_TITLE,
)
from .potential import (
    GAD_ROW_3_PROMPT,
    score_respect_potential_instances,
)
from .stereotypes import (
    CRITERION_ID as STEREOTYPE_ID,
)
from .stereotypes import (
    CRITERION_TITLE as STEREOTYPE_TITLE,
)
from .stereotypes import (
    GAD_ROW_1_PROMPT,
    score_stereotype_instances,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CriterionDefinition:
    criterion_id: str
    title: str
    # Unused since the single-pass rewrite. Live counting guidance is
    # prompt.FALLBACK_GAD_INSTRUCTIONS (DB-overridable via
    # rubric_criteria.scoring_rule).
    prompt: str
    score: Callable[..., int]
    balance: bool = False


CRITERIA: tuple[CriterionDefinition, ...] = (
    CriterionDefinition(
        STEREOTYPE_ID,
        STEREOTYPE_TITLE,
        GAD_ROW_1_PROMPT,
        score_stereotype_instances,
    ),
    CriterionDefinition(
        BALANCE_ID,
        BALANCE_TITLE,
        GAD_ROW_2_PROMPT,
        score_representation_balance,
        balance=True,
    ),
    CriterionDefinition(
        POTENTIAL_ID,
        POTENTIAL_TITLE,
        GAD_ROW_3_PROMPT,
        score_respect_potential_instances,
    ),
    CriterionDefinition(
        LIFE_ID,
        LIFE_TITLE,
        GAD_ROW_4_PROMPT,
        score_life_experience_instances,
    ),
    CriterionDefinition(
        PEACE_ID,
        PEACE_TITLE,
        GAD_ROW_5_PROMPT,
        score_peace_equality_instances,
    ),
)

REGISTRY_VERSION = 1
"""Increment when score-band thresholds change."""

REGISTERED_CODES: frozenset[str] = frozenset(
    definition.criterion_id for definition in CRITERIA
)


# Score adapter — translates combined sections into registry scores
# ---------------------------------------------------------------------------


def score_from_combined(
    combined: dict[str, Any],
    packed_chunks: list[dict[str, Any]],
) -> tuple[list[CriterionScore], int, int, int]:
    """Adapt validated combined sections into registry ``CriterionScore`` values.

    Returns (scores, evidence_candidates, evidence_accepted, evidence_rejected).
    Each criterion section is passed to the corresponding registry scorer
    after grounding evidence. GAD-02 bypasses grounding (counts only).

    ``combined`` MUST already have passed ``parse_combined_response`` so that
    all keys are canonical, all schemas validated, and no numeric-score fields
    remain. This function never defaults ``{}`` for a missing section.
    """
    scores: list[CriterionScore] = []
    evidence_candidates = 0
    evidence_accepted = 0
    evidence_rejected = 0

    for definition in CRITERIA:
        section_key = definition.criterion_id.lower()
        section = combined.get(section_key)
        if section is None or not isinstance(section, dict):
            raise AgentExecutionError(
                f"Missing or invalid section for {definition.criterion_id}: "
                f"section must be present and a dict after parsing"
            )

        if definition.balance:
            # GAD-02: counts only, no grounding
            female_count = int(section.get("female_count", 0))
            male_count = int(section.get("male_count", 0))
            band = definition.score(female_count, male_count)
            difference = abs(female_count - male_count)
            summary = str(section.get("summary", "")).strip()
            justification = (
                f"Female representations: {female_count}; male representations: "
                f"{male_count}; absolute difference: {difference}. {summary}"
            )
            scores.append(
                CriterionScore(
                    criterion_id=definition.criterion_id,
                    criterion_title=definition.title,
                    score=band,
                    justification=justification,
                    chunk_ids=(),
                    evidence=(),
                )
            )
        else:
            # GAD-01/03/04/05: grounded instances
            raw_instances = section.get("instances", [])
            if not isinstance(raw_instances, list):
                raw_instances = []
            # Blocker 2: enforce hard per-criterion instance cap before any
            # scoring/persistence — truncate both the local list AND the
            # combined dict so the persisted raw_response reflects the cap.
            if len(raw_instances) > MAX_INSTANCES_PER_CRITERION:
                raw_instances = raw_instances[:MAX_INSTANCES_PER_CRITERION]
                section["instances"] = raw_instances
                logger.info(
                    "GAD section '%s' truncated to %d instances",
                    definition.criterion_id,
                    MAX_INSTANCES_PER_CRITERION,
                )
            claimed_count = int(section.get("instance_count", 0))
            evidence_candidates += len(raw_instances)

            accepted_excerpts, accepted_ids, rejected = ground_instances(
                section_key, raw_instances, packed_chunks
            )
            evidence_accepted += len(accepted_excerpts)
            evidence_rejected += rejected

            grounded_count = len(accepted_excerpts)
            band = definition.score(grounded_count)
            summary = str(section.get("summary", "")).strip()
            justification = (
                f"Grounded unique instances: {grounded_count} "
                f"(model reported {claimed_count}; {rejected} unsupported "
                f"or invalid instance(s) excluded). {summary}"
            )
            scores.append(
                CriterionScore(
                    criterion_id=definition.criterion_id,
                    criterion_title=definition.title,
                    score=band,
                    justification=justification,
                    chunk_ids=tuple(accepted_ids),
                    evidence=tuple(accepted_excerpts),
                )
            )

    return scores, evidence_candidates, evidence_accepted, evidence_rejected


__all__ = [
    "CRITERIA",
    "REGISTERED_CODES",
    "REGISTRY_VERSION",
    "CriterionDefinition",
    "score_from_combined",
]
