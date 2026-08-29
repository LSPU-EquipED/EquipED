"""backfill scoring_rule for GAD rubric criteria

Revision ID: 20260829_0002
Revises: 20260829_0001
Create Date: 2026-08-29
"""

import sqlalchemy as sa

from alembic import op

revision = "20260829_0002"
down_revision = "20260829_0001"
branch_labels = None
depends_on = None

# Verbatim copy of server/modules/agents/gad/prompt.py's
# FALLBACK_GAD_INSTRUCTIONS at the time of writing. Embedded here because
# migrations must not import app code that can change.
_GAD_RULES = {
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

_SCOPE = (
    " AND rubric_domain_id IN ("
    "  SELECT rd.rubric_domain_id FROM rubric_domains rd "
    "  JOIN rubric_sets rs ON rs.rubric_set_id = rd.rubric_set_id "
    "  WHERE rs.agent_id = 'gad')"
)


def upgrade():
    bind = op.get_bind()
    for code, rule in _GAD_RULES.items():
        bind.execute(
            sa.text(
                "UPDATE rubric_criteria SET scoring_rule = :rule "
                "WHERE criterion_code = :code" + _SCOPE
            ),
            {"rule": rule, "code": code},
        )


def downgrade():
    bind = op.get_bind()
    for code in _GAD_RULES:
        bind.execute(
            sa.text(
                "UPDATE rubric_criteria SET scoring_rule = NULL "
                "WHERE criterion_code = :code" + _SCOPE
            ),
            {"code": code},
        )
