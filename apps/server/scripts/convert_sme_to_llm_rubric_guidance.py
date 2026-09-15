"""One-off migration: convert SME's 10 criteria from count_band/ratio_band to
llm_rubric_guidance, with qualitative (non-numeric) score-level descriptors.

Rationale: SME's calculator-based criteria never had the LLM output a score
directly, so a plain reviewer score correction had no field to attach to for
DPO purposes (see docs/superpowers/specs -- this reverts SME to the same
LLM-direct scoring shape ITSO already uses). Numeric percentage/count
thresholds are replaced with qualitative bands (e.g. "most" instead of
"80%") because several of these criteria measure an open-ended, self-defined
set (topics, tasks, sections) where the percentage was never a hard fact to
begin with -- see the design discussion for the full reasoning. A-02/A-03/
A-04 (closed, named category counts) are intentionally converted too, per
explicit decision, even though their original counts were genuinely
checkable facts.

Uses the existing rubric authoring workflow (draft -> edit -> publish ->
activate) rather than mutating the DB directly, so validation, versioning,
and the publish/activate invariants all still apply.

Usage (from repo root):

    cd apps && uv run --project server python -m \
        server.scripts.convert_sme_to_llm_rubric_guidance
"""

from __future__ import annotations

import logging
from typing import Any

from server.core.database import get_session_factory

# Force registration of models referenced by rubric FKs (e.g. RubricSet's
# published_by/retired_by -> users.user_id) before any query/flush touches
# them -- otherwise SQLAlchemy can't resolve the foreign key at flush time.
import server.modules.auth.models  # noqa: F401
from server.modules.rubrics.authoring import update_criterion
from server.modules.rubrics.contracts import LlmRubricGuidanceConfig, LlmScoreDescriptor
from server.modules.rubrics.models import RubricCriterion, RubricDomain
from server.modules.rubrics.repository import (
    create_draft_from_active,
    publish_draft_revision,
)

logger = logging.getLogger(__name__)

AGENT_ID = "sme"


def _cfg(guidance: str, bands: dict[int, str]) -> LlmRubricGuidanceConfig:
    return LlmRubricGuidanceConfig(
        guidance=guidance,
        level_descriptors=tuple(
            LlmScoreDescriptor(score=score, descriptor=text)
            for score, text in bands.items()
        ),
    )


# criterion_code -> (guidance, {score: descriptor}, scoring_rule summary)
QUALITATIVE_REWRITES: dict[str, dict[str, Any]] = {
    "OP-01": {
        "guidance": "Judge how logically topics flow from one to the next "
        "throughout the module.",
        "bands": {
            4: "Topics flow logically throughout almost the entire module; "
            "transitions feel natural and well-organized.",
            3: "Most topics flow logically, with a few noticeable gaps or "
            "abrupt jumps.",
            2: "Only some topics connect logically; the organization feels "
            "disjointed in multiple places.",
            1: "Topics feel scattered or unconnected, with little to no "
            "logical flow, or no discernible topic structure at all.",
        },
        "scoring_rule": "4 = topics flow logically almost throughout. "
        "3 = most topics flow logically, a few gaps. "
        "2 = only some topics connect logically. "
        "1 = topics feel scattered or unconnected.",
    },
    "OP-02": {
        "guidance": "Judge how rich the module is in genuine interactive "
        "activities with real task content (not just an empty label like "
        "'Activity 1').",
        "bands": {
            4: "Rich with genuine interactive activities that give students "
            "real tasks to complete.",
            3: "A handful of genuine interactive activities.",
            2: "At most one genuine interactive activity.",
            1: "No genuine interactive activities (any 'activities' present "
            "are empty labels with no real task).",
        },
        "scoring_rule": "4 = rich with genuine interactive activities. "
        "3 = a handful. 2 = at most one. 1 = none.",
    },
    "OP-03": {
        "guidance": "Judge how clear and complete the directions are for "
        "tasks students must perform.",
        "bands": {
            4: "Nearly all tasks have clear, complete directions students "
            "could follow without confusion.",
            3: "Most tasks have clear directions, though a few are "
            "incomplete or ambiguous.",
            2: "Only some tasks have clear directions; many leave students "
            "uncertain what to do.",
            1: "Few or no tasks have clear directions; students would "
            "likely be confused about what's expected.",
        },
        "scoring_rule": "4 = nearly all tasks have clear directions. "
        "3 = most do, a few incomplete. 2 = only some do. 1 = few or none do.",
    },
    "OP-04": {
        "guidance": "Judge how clear and internally consistent the "
        "module's sections are (no contradictions or garbled content).",
        "bands": {
            4: "Nearly all sections are clear and internally consistent, "
            "with no contradictions or garbled content.",
            3: "Most sections are clear and consistent, with a few "
            "exceptions.",
            2: "Only some sections are clear and consistent; several "
            "contain confusing or contradictory content.",
            1: "Most sections are unclear, garbled, or contradictory.",
        },
        "scoring_rule": "4 = nearly all sections clear/consistent. "
        "3 = most are, a few exceptions. 2 = only some are. 1 = most are not.",
    },
    "OP-05": {
        "guidance": "Judge how many genuine enhancement activities the "
        "module offers beyond the core lesson content.",
        "bands": {
            4: "Several genuine enhancement activities beyond the core "
            "content.",
            3: "A couple of genuine enhancement activities.",
            2: "At most one genuine enhancement activity.",
            1: "No enhancement activities beyond the core content.",
        },
        "scoring_rule": "4 = several enhancement activities. 3 = a couple. "
        "2 = at most one. 1 = none.",
    },
    "A-01": {
        "guidance": "Judge how many of the module's tasks engage "
        "higher-order thinking (apply/analyze/evaluate/create), not just "
        "recall/understanding.",
        "bands": {
            4: "Nearly all tasks engage higher-order thinking, not just "
            "recall.",
            3: "Most tasks engage higher-order thinking, with some limited "
            "to recall/understanding.",
            2: "Only some tasks engage higher-order thinking; most are "
            "limited to recall or understanding.",
            1: "Tasks are almost entirely limited to recall/understanding, "
            "or there are no tasks at all.",
        },
        "scoring_rule": "4 = nearly all tasks are higher-order. 3 = most "
        "are. 2 = only some are. 1 = almost none are, or no tasks exist.",
    },
    "A-02": {
        "guidance": "Judge the variety of distinct assessment TYPES used "
        "(objective test, written, reflection, performance task, project, "
        "oral, self-assessment).",
        "bands": {
            4: "Wide variety of assessment types used.",
            3: "Moderate variety of assessment types.",
            2: "Very limited variety in assessment types.",
            1: "Essentially one assessment type, or no clear assessment at "
            "all.",
        },
        "scoring_rule": "4 = wide variety of assessment types. 3 = "
        "moderate variety. 2 = very limited variety. 1 = essentially one "
        "type or none.",
    },
    "A-03": {
        "guidance": "Judge how many genuine progress-monitoring mechanisms "
        "(checkpoint, self-assessment, reflection, cumulative) the module "
        "provides.",
        "bands": {
            4: "Multiple genuine ways to track ongoing progress.",
            3: "A couple of genuine progress-monitoring mechanisms.",
            2: "At most one genuine progress-monitoring mechanism.",
            1: "No meaningful way to monitor student progress.",
        },
        "scoring_rule": "4 = multiple progress-monitoring mechanisms. "
        "3 = a couple. 2 = at most one. 1 = none.",
    },
    "A-04": {
        "guidance": "Judge the variety of distinct feedback/intervention "
        "mechanism types (answer key, rubric, remediation referral, "
        "positive reinforcement) the module provides.",
        "bands": {
            4: "Several distinct types of feedback/intervention support.",
            3: "A couple of distinct types of feedback/intervention "
            "support.",
            2: "One type of feedback/intervention support.",
            1: "No meaningful feedback or intervention support.",
        },
        "scoring_rule": "4 = several feedback/intervention types. "
        "3 = a couple. 2 = one. 1 = none.",
    },
    "A-05": {
        "guidance": "Judge how many of the module's stated objectives are "
        "actually measured by a real assessment.",
        "bands": {
            4: "Nearly all stated objectives are measured by a real "
            "assessment in the module.",
            3: "Most stated objectives are measured, with some gaps.",
            2: "Only some stated objectives are measured; many are not "
            "assessed at all.",
            1: "Few or none of the stated objectives are measured by any "
            "real assessment.",
        },
        "scoring_rule": "4 = nearly all objectives are measured. 3 = most "
        "are, some gaps. 2 = only some are. 1 = few or none are.",
    },
}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    session = get_session_factory()()
    try:
        draft = create_draft_from_active(session, AGENT_ID, is_system=True)
        logger.info(
            "Created draft rubric set %s (version %d) for agent '%s'",
            draft.rubric_set_id,
            draft.version_number,
            AGENT_ID,
        )

        criteria = (
            session.query(RubricCriterion)
            .join(
                RubricDomain,
                RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
            )
            .filter(RubricDomain.rubric_set_id == draft.rubric_set_id)
            .all()
        )

        updated = 0
        for criterion in criteria:
            rewrite = QUALITATIVE_REWRITES.get(criterion.criterion_code)
            if rewrite is None:
                continue
            strategy_config = _cfg(rewrite["guidance"], rewrite["bands"])
            update_criterion(
                session,
                criterion.rubric_criterion_id,
                strategy_config=strategy_config,
                scoring_rule=rewrite["scoring_rule"],
            )
            updated += 1
            logger.info("Converted %s to llm_rubric_guidance", criterion.criterion_code)

        if updated != len(QUALITATIVE_REWRITES):
            found = {c.criterion_code for c in criteria}
            missing = set(QUALITATIVE_REWRITES) - found
            raise RuntimeError(
                f"Expected to convert {len(QUALITATIVE_REWRITES)} criteria, "
                f"converted {updated}. Missing from draft: {sorted(missing)}"
            )

        published_set, activation = publish_draft_revision(
            session, draft.rubric_set_id, is_system=True, activate=True
        )
        session.commit()
        logger.info(
            "Published and activated SME rubric v%d (%s); active revision now %s",
            published_set.version_number,
            published_set.rubric_set_id,
            activation.rubric_set_id if activation else "unchanged",
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
