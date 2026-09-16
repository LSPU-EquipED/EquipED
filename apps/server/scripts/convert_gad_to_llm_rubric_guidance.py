"""One-off migration: convert GAD's 5 criteria (GAD-01..05) from
count_band/ratio_band to llm_rubric_guidance, bumping the rubric to
adapter_version=2 (see manifests.GAD_MANIFEST_V2).

The qualitative guidance/level-descriptor text below was originally
authored on an abandoned branch that converted the DB directly without
also fixing gad/agent.py's hardcoded adapter-version gate -- see project
memory gad-agent-py-manifest-bug for what went wrong. That text is
reproduced verbatim here (recovered from the orphaned rubric_set that
branch left behind, rubric_set_id 3af606c8-be6d-46d0-bf4f-0263baafddfc in
the shared dev DB) so this script is self-contained and does not depend
on that orphaned row still existing.

Unlike convert_sme_to_llm_rubric_guidance.py and
convert_coordinator_to_llm_rubric_guidance.py, this script does NOT reuse
_qualitative_rewrites.py's run_qualitative_conversion: GAD's conversion
requires bumping adapter_version (1 -> 2), which that shared helper does
not support (SME and Coordinator's conversions never needed a version
bump -- see this script's companion implementation plan for why).

This script PUBLISHES the v2 rubric set but does NOT activate it -- GAD's
live evaluations keep using v1 until rubric_agent_activations is
repointed as a separate, deliberate step (mirroring how the v1 rollback
was done manually and verified before this conversion was written).

Usage (from repo root):

    cd apps && uv run --project server python -m \
        server.scripts.convert_gad_to_llm_rubric_guidance
"""

from __future__ import annotations

import logging
from typing import Any

# Force registration of models referenced by rubric FKs before any
# query/flush touches them (same reason _qualitative_rewrites.py does this).
import server.modules.auth.models  # noqa: F401
from server.core.database import get_session_factory
from server.modules.rubrics.authoring import update_criterion
from server.modules.rubrics.contracts import LlmRubricGuidanceConfig, LlmScoreDescriptor
from server.modules.rubrics.models import RubricCriterion, RubricDomain
from server.modules.rubrics.repository import (
    create_draft_from_active,
    publish_draft_revision,
)

logger = logging.getLogger(__name__)

AGENT_ID = "gad"
TARGET_ADAPTER_VERSION = 2

# criterion_code -> {guidance, bands: {score: descriptor}, scoring_rule}
# Recovered verbatim from the abandoned branch's orphaned rubric_set.
GAD_QUALITATIVE_REWRITES: dict[str, dict[str, Any]] = {
    "GAD-01": {
        "guidance": (
            "Judge how free the material is from gender stereotypes or "
            "gender-biased portrayals (content that reinforces stereotypes "
            "about gender roles, abilities, behaviors, occupations, or "
            "characteristics). Do not count discussions of stereotypes "
            "presented for educational, analytical, historical, or "
            "critical purposes."
        ),
        "bands": {
            4: "No gender stereotypes or biased portrayals found anywhere "
            "in the material.",
            3: "At most one isolated instance of gender stereotyping or bias.",
            2: "A few instances of gender stereotyping or bias, but not pervasive.",
            1: "Gender stereotypes or biased portrayals are frequent or "
            "pervasive throughout the material.",
        },
        "scoring_rule": (
            "4 = none found. 3 = at most one isolated instance. 2 = a few "
            "instances, not pervasive. 1 = frequent or pervasive."
        ),
    },
    "GAD-02": {
        "guidance": (
            "Judge how equally the material represents females and males: "
            "named individuals, characters, illustrations, examples with "
            "people, and gendered pronouns. Do not infer gender when "
            "ambiguous; ignore gender-neutral references."
        ),
        "bands": {
            4: "Female and male are represented in nearly equal numbers "
            "throughout the material.",
            3: "Female and male representation is fairly balanced, with "
            "only a modest difference.",
            2: "Noticeable imbalance between female and male representation.",
            1: "Representation is heavily skewed toward one gender, with "
            "little to no presence of the other.",
        },
        "scoring_rule": (
            "4 = nearly equal representation. 3 = fairly balanced, modest "
            "difference. 2 = noticeable imbalance. 1 = heavily skewed "
            "toward one gender."
        ),
    },
    "GAD-03": {
        "guidance": (
            "Judge whether the material portrays both genders with equal "
            "respect, capability, and opportunity (freedom from content "
            "portraying one gender as less capable, less respected, less "
            "deserving, or as having fewer opportunities than the other). "
            "Do not count discussions of discrimination presented for "
            "educational, analytical, historical, or critical purposes."
        ),
        "bands": {
            4: "Both genders are consistently portrayed with equal "
            "respect, capability, and opportunity; no instances of one "
            "gender being diminished.",
            3: "At most one or two isolated instances suggesting one "
            "gender is less capable, respected, or deserving.",
            2: "Several instances portray one gender as less capable, "
            "respected, or deserving of opportunity.",
            1: "The material frequently portrays one gender as less "
            "capable, respected, or deserving than the other.",
        },
        "scoring_rule": (
            "4 = consistently equal respect/capability/opportunity. 3 = at "
            "most one or two isolated instances. 2 = several instances. "
            "1 = frequent."
        ),
    },
    "GAD-04": {
        "guidance": (
            "Judge whether the material reflects the needs and life "
            "experiences of both male and female students equally "
            "(freedom from excluding one gender's experiences, "
            "disproportionately favoring one gender, or assuming an "
            "activity, role, or interest belongs primarily to one gender). "
            "Do not count gender-neutral examples or discussions presented "
            "for educational, analytical, historical, or critical "
            "purposes."
        ),
        "bands": {
            4: "The material reflects the needs and life experiences of "
            "both male and female students equally, with no exclusion or "
            "assumed gender-specific roles.",
            3: "At most one or two instances where the material leans "
            "toward one gender's experiences or assumes an activity/role "
            "belongs to one gender.",
            2: "Several instances exclude one gender's experiences or "
            "assume gender-specific roles or activities.",
            1: "The material consistently excludes or disproportionately "
            "favors one gender's experiences, needs, or roles.",
        },
        "scoring_rule": (
            "4 = equal reflection of both genders' needs/experiences. "
            "3 = at most one or two instances leaning one way. 2 = several "
            "instances. 1 = consistent exclusion/favoritism."
        ),
    },
    "GAD-05": {
        "guidance": (
            "Judge whether the material promotes peace and equality "
            "regardless of gender, race, social class, disability, "
            "religion, sexual orientation, or ethnic background (freedom "
            "from discriminatory, prejudicial, exclusionary, or "
            "inequality-promoting content). Do not count historical, "
            "educational, analytical, or critical discussions of "
            "discrimination."
        ),
        "bands": {
            4: "No discriminatory, prejudicial, exclusionary, or "
            "inequality-promoting content related to gender, race, class, "
            "disability, religion, orientation, or ethnicity.",
            3: "At most one or two isolated instances of such content.",
            2: "Several instances of discriminatory, prejudicial, or "
            "exclusionary content.",
            1: "Discriminatory, prejudicial, or exclusionary content "
            "appears frequently throughout the material.",
        },
        "scoring_rule": (
            "4 = none found. 3 = at most one or two isolated instances. "
            "2 = several instances. 1 = frequent."
        ),
    },
}


def _build_config(rewrite: dict[str, Any]) -> LlmRubricGuidanceConfig:
    return LlmRubricGuidanceConfig(
        guidance=rewrite["guidance"],
        level_descriptors=tuple(
            LlmScoreDescriptor(score=score, descriptor=text)
            for score, text in rewrite["bands"].items()
        ),
    )


def run_gad_conversion(session: Any) -> None:
    """Create, populate, and publish (but do not activate) a v2 GAD draft."""
    draft = create_draft_from_active(session, AGENT_ID, is_system=True)
    logger.info(
        "Created draft rubric set %s (version %d) for agent '%s'",
        draft.rubric_set_id,
        draft.version_number,
        AGENT_ID,
    )

    # GAD is the first agent whose conversion needs a version bump --
    # create_draft_from_active always copies the active set's existing
    # adapter_version, so it must be raised explicitly before publish
    # validates the draft against GAD_MANIFEST_V2.
    draft.adapter_version = TARGET_ADAPTER_VERSION
    session.flush()

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
        rewrite = GAD_QUALITATIVE_REWRITES.get(criterion.criterion_code)
        if rewrite is None:
            continue
        update_criterion(
            session,
            criterion.rubric_criterion_id,
            strategy_config=_build_config(rewrite),
            scoring_rule=rewrite["scoring_rule"],
        )
        updated += 1
        logger.info("Converted %s to llm_rubric_guidance", criterion.criterion_code)

    if updated != len(GAD_QUALITATIVE_REWRITES):
        found = {c.criterion_code for c in criteria}
        missing = set(GAD_QUALITATIVE_REWRITES) - found
        raise RuntimeError(
            f"Expected to convert {len(GAD_QUALITATIVE_REWRITES)} criteria, "
            f"converted {updated}. Missing from draft: {sorted(missing)}"
        )

    # activate=False: publish only. Activation is a deliberate, separate,
    # manual step -- see this script's module docstring.
    published_set, _activation = publish_draft_revision(
        session, draft.rubric_set_id, is_system=True, activate=False
    )
    session.commit()
    logger.info(
        "Published GAD rubric v%d (%s) at adapter_version=%d. NOT activated -- "
        "repoint rubric_agent_activations manually when ready.",
        published_set.version_number,
        published_set.rubric_set_id,
        published_set.adapter_version,
    )


def main(session: Any | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    owns_session = session is None
    if session is None:
        session = get_session_factory()()
    try:
        run_gad_conversion(session)
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


if __name__ == "__main__":
    main()
