"""Coordinator Rubric v3: 10-criterion independent scoring, adapter_version 2

Revision ID: 20260902_0001
Revises: 20260830_0002
Create Date: 2026-09-02
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from alembic import op

revision = "20260902_0001"
down_revision = "20260830_0002"
branch_labels = None
depends_on = None

# Verbatim data — migrations must not import app code that can change.
# Must stay identical to seed_coordinator_v3_if_needed in
# server/scripts/seed_rubrics.py so migration-path and script-path DBs converge.

_DOMAINS = (
    ("OP", "Organization & Presentation", 1),
    ("A", "Assessment", 2),
)

# (code, domain_code, display_order, title, description, scoring_strategy, config)
_CRITERIA: tuple[tuple[str, str, int, str, str, str, dict[str, Any]], ...] = (
    (
        "OP-01",
        "OP",
        1,
        "Topic Coherence",
        "Topics are coherent from Unit to Chapter.",
        "ratio_band",
        {
            "strategy": "ratio_band",
            "mode": "coverage_percentage",
            "threshold_4": 80.0,
            "threshold_3": 50.0,
            "threshold_2": 20.0,
            "short_sample": {
                "min_units": 4,
                "max_issues_4": 0,
                "max_issues_3": 1,
                "max_issues_2": 2,
            },
        },
    ),
    (
        "OP-02",
        "OP",
        2,
        "Interactivity",
        "Material is interactive in each lesson which makes life-long "
        "learning easier.",
        "count_band",
        {
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 4,
            "threshold_3": 2,
            "threshold_2": 1,
        },
    ),
    (
        "OP-03",
        "OP",
        3,
        "Clear Directions",
        "Directions are clear and complete enough for students to perform "
        "required tasks.",
        "ratio_band",
        {
            "strategy": "ratio_band",
            "mode": "coverage_percentage",
            "threshold_4": 80.0,
            "threshold_3": 50.0,
            "threshold_2": 20.0,
        },
    ),
    (
        "OP-04",
        "OP",
        4,
        "Accurate Sections",
        "Paragraphs and sections have clear and accurate information.",
        "ratio_band",
        {
            "strategy": "ratio_band",
            "mode": "coverage_percentage",
            "threshold_4": 80.0,
            "threshold_3": 50.0,
            "threshold_2": 20.0,
        },
    ),
    (
        "OP-05",
        "OP",
        5,
        "Enhancement Activities",
        "Enhancement activities for students are provided.",
        "count_band",
        {
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 3,
            "threshold_3": 2,
            "threshold_2": 1,
        },
    ),
    (
        "A-01",
        "A",
        1,
        "Learner Transformation",
        "Students are engaged in transforming what they learn.",
        "ratio_band",
        {
            "strategy": "ratio_band",
            "mode": "coverage_percentage",
            "threshold_4": 80.0,
            "threshold_3": 50.0,
            "threshold_2": 20.0,
        },
    ),
    (
        "A-02",
        "A",
        2,
        "Varied Assessment Tools",
        "Teachers can easily assess students' progress by using varied "
        "assessment tools.",
        "count_band",
        {
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 5,
            "threshold_3": 3,
            "threshold_2": 2,
        },
    ),
    (
        "A-03",
        "A",
        3,
        "Progress Monitoring",
        "The material keeps an on-going record of students' progress and "
        "allows the teacher to monitor student performance.",
        "count_band",
        {
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 4,
            "threshold_3": 2,
            "threshold_2": 1,
        },
    ),
    (
        "A-04",
        "A",
        4,
        "Prescriptive Feedback",
        "Positive, meaningful feedback, and prescriptive guides for "
        "interventions are provided.",
        "count_band",
        {
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 3,
            "threshold_3": 2,
            "threshold_2": 1,
        },
    ),
    (
        "A-05",
        "A",
        5,
        "Curriculum Alignment",
        "Evaluate alignment between the student learning material's stated "
        "objectives and the confirmed course curriculum/syllabus topics.",
        "curriculum_alignment",
        {"strategy": "curriculum_alignment"},
    ),
)

# Verbatim copy of
# server/modules/agents/coordinator/scoring_rules.py::COORDINATOR_SCORING_RULES
# at the time of writing. Embedded because migrations must not import app code
# that can change. Keep the two in sync. Backfills the nullable scoring_rule
# column so CID admins see editable text in the Rubric Editor.
_SCORING_RULES: dict[str, str] = {
    "OP-01": (
        "If there are fewer than 4 topic-to-topic transitions total, score "
        "by issue count instead (a short module with 0 issues is coherent, "
        "not deficient): 0 issues -> 4, 1 -> 3, 2 -> 2, 3+ issues -> 1. "
        "Otherwise (4+ transitions), score the percentage of transitions "
        "that are coherent (each topic logically follows the last) on the "
        "moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. No "
        "topics at all -> 1."
    ),
    "OP-02": (
        "Count genuine interactive elements with real task content (not "
        "just a label like 'Activity 1' with no actual task). Score: "
        "4+ elements -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
    "OP-03": (
        "Score the percentage of tasks with clear, complete directions on "
        "the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "OP-04": (
        "Score the percentage of sections that are clear and internally "
        "consistent (no contradictions or garbled content) on the moderate "
        "scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "OP-05": (
        "Count genuine enhancement activities beyond the core lesson "
        "content. Score: 3+ activities -> 4, 2 -> 3, 1 -> 2, 0 -> 1."
    ),
    "A-01": (
        "Score the percentage of tasks that engage higher-order thinking "
        "(apply/analyze/evaluate/create, not just remember/understand) on "
        "the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. "
        "No tasks found -> 1."
    ),
    "A-02": (
        "Count distinct assessment TYPES used (objective test, written, "
        "reflection, performance task, project, oral, self-assessment). "
        "Score: 5+ types -> 4, 3-4 types -> 3, 2 types -> 2, <=1 type -> 1."
    ),
    "A-03": (
        "Count genuine progress-monitoring mechanisms, spanning up to 4 "
        "types (checkpoint, self-assessment, reflection, cumulative). "
        "Score: 4+ mechanisms -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
    "A-04": (
        "Count distinct feedback/intervention mechanism TYPES (answer key, "
        "rubric, remediation referral, positive reinforcement). Score: "
        "3-4 types -> 4, 2 types -> 3, 1 type -> 2, 0 types -> 1."
    ),
    "A-05": (
        "Score the percentage of the SLM's stated objectives that are "
        "addressed by the confirmed course curriculum on the moderate "
        "scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. An objective "
        "counts as addressed only when a verbatim span of the CURRICULUM "
        "CONTEXT supports it. No objectives found, or none addressed by the "
        "curriculum -> 1."
    ),
}


def _bind_uuid(is_postgres: bool, val: Any) -> tuple[sa.types.TypeEngine, Any]:
    """Dialect adapter: native sa.Uuid + UUID on PG; sa.String + str on SQLite."""
    if is_postgres:
        u = val if isinstance(val, uuid.UUID) else uuid.UUID(str(val))
        return sa.Uuid(as_uuid=True), u
    return sa.String(), str(val)


def _coordinator_set_id(bind: Any, version_number: int) -> Any | None:
    row = bind.execute(
        sa.text(
            "SELECT rubric_set_id FROM rubric_sets "
            "WHERE agent_id = 'coordinator' AND version_number = :v"
        ),
        {"v": version_number},
    ).fetchone()
    return row[0] if row is not None else None


def _point_activation(bind: Any, set_type: Any, set_param: Any, now: datetime) -> None:
    exists = bind.execute(
        sa.text(
            "SELECT 1 FROM rubric_agent_activations WHERE agent_id = 'coordinator'"
        )
    ).fetchone()
    if exists is not None:
        bind.execute(
            sa.text(
                "UPDATE rubric_agent_activations "
                "SET rubric_set_id = :sid, updated_at = :now "
                "WHERE agent_id = 'coordinator'"
            ).bindparams(sa.bindparam("sid", type_=set_type)),
            {"sid": set_param, "now": now},
        )
    else:
        bind.execute(
            sa.text(
                "INSERT INTO rubric_agent_activations "
                "(agent_id, rubric_set_id, updated_by, updated_at) "
                "VALUES ('coordinator', :sid, NULL, :now)"
            ).bindparams(sa.bindparam("sid", type_=set_type)),
            {"sid": set_param, "now": now},
        )


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    now = datetime.now(UTC)

    existing_v3 = _coordinator_set_id(bind, 3)

    if existing_v3 is None:
        set_id = uuid.uuid4()
        set_type, set_param = _bind_uuid(is_postgres, set_id)
        bind.execute(
            sa.text(
                "INSERT INTO rubric_sets (rubric_set_id, agent_id, name, "
                "version_number, status, adapter_key, adapter_version, "
                "published_at, created_at) VALUES (:sid, 'coordinator', "
                "'Coordinator Rubric v3', 3, 'published', 'coordinator', 2, "
                ":now, :now)"
            ).bindparams(sa.bindparam("sid", type_=set_type)),
            {"sid": set_param, "now": now},
        )

        domain_params: dict[str, tuple[Any, Any]] = {}
        for code, title, order in _DOMAINS:
            dtype, dparam = _bind_uuid(is_postgres, uuid.uuid4())
            domain_params[code] = (dtype, dparam)
            bind.execute(
                sa.text(
                    "INSERT INTO rubric_domains (rubric_domain_id, "
                    "rubric_set_id, code, title, display_order) "
                    "VALUES (:did, :sid, :code, :title, :order)"
                ).bindparams(
                    sa.bindparam("did", type_=dtype),
                    sa.bindparam("sid", type_=set_type),
                ),
                {
                    "did": dparam,
                    "sid": set_param,
                    "code": code,
                    "title": title,
                    "order": order,
                },
            )

        for code, dom, order, title, desc, strat, cfg in _CRITERIA:
            dtype, dparam = domain_params[dom]
            ctype, cparam = _bind_uuid(is_postgres, uuid.uuid4())
            bind.execute(
                sa.text(
                    "INSERT INTO rubric_criteria (rubric_criterion_id, "
                    "rubric_domain_id, criterion_code, title, description, "
                    "scoring_rule, scoring_strategy, strategy_config, "
                    "display_order) VALUES (:cid, :did, :code, :title, :desc, "
                    ":rule, :strat, :cfg, :order)"
                ).bindparams(
                    sa.bindparam("cid", type_=ctype),
                    sa.bindparam("did", type_=dtype),
                    sa.bindparam("rule", type_=sa.String),
                    sa.bindparam("strat", type_=sa.String),
                    sa.bindparam("cfg", type_=sa.JSON),
                ),
                {
                    "cid": cparam,
                    "did": dparam,
                    "code": code,
                    "title": title,
                    "desc": desc,
                    "rule": _SCORING_RULES[code],
                    "strat": strat,
                    "cfg": cfg,
                    "order": order,
                },
            )
        target_type, target_param = set_type, set_param
    else:
        target_type, target_param = _bind_uuid(is_postgres, existing_v3)

    # One-shot migration: unconditionally repoint coordinator activation to v3.
    # (Unlike seed_coordinator_v3_if_needed, which preserves an admin's manual
    # activation choice, the migration is the deploy's single source of truth.)
    _point_activation(bind, target_type, target_param, now)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    now = datetime.now(UTC)

    fallback = _coordinator_set_id(bind, 2)
    if fallback is None:
        row = bind.execute(
            sa.text(
                "SELECT rubric_set_id FROM rubric_sets "
                "WHERE agent_id = 'coordinator' AND version_number <> 3 "
                "ORDER BY version_number DESC"
            )
        ).fetchone()
        fallback = row[0] if row is not None else None

    if fallback is not None:
        ftype, fparam = _bind_uuid(is_postgres, fallback)
        _point_activation(bind, ftype, fparam, now)
    else:
        bind.execute(
            sa.text(
                "DELETE FROM rubric_agent_activations "
                "WHERE agent_id = 'coordinator'"
            )
        )

    bind.execute(
        sa.text(
            "DELETE FROM rubric_criteria WHERE rubric_domain_id IN ("
            "SELECT d.rubric_domain_id FROM rubric_domains d "
            "JOIN rubric_sets rs ON rs.rubric_set_id = d.rubric_set_id "
            "WHERE rs.agent_id = 'coordinator' AND rs.version_number = 3)"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM rubric_domains WHERE rubric_set_id IN ("
            "SELECT rubric_set_id FROM rubric_sets "
            "WHERE agent_id = 'coordinator' AND version_number = 3)"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM rubric_sets "
            "WHERE agent_id = 'coordinator' AND version_number = 3"
        )
    )
