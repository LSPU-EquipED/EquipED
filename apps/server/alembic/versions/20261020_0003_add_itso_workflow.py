"""Add ITSO policies, exact consent and append-only assessment artifacts.

Revision ID: 20261020_0003
Revises: 20261020_0002
"""

import hashlib

import sqlalchemy as sa
from alembic import op

revision = "20261020_0003"
down_revision = "20261020_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    unbound = op.get_bind().scalar(
        sa.text(
            "SELECT COUNT(*) FROM itso_assessments a WHERE NOT EXISTS "
            "(SELECT 1 FROM evaluation_form_snapshots f WHERE "
            "f.evaluation_id = a.evaluation_id AND f.agent_id = 'itso' "
            "AND f.adapter_version = 2)"
        )
    )
    if unbound:
        raise RuntimeError(
            "ITSO history requires a valid frozen v2 form before upgrade"
        )
    op.create_table(
        "itso_policy_versions",
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("scope", sa.String(length=100), nullable=False),
        sa.Column("criterion_id", sa.String(length=10), nullable=False),
        sa.Column("source_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('egress','institutional','rule')", name="ck_itso_policy_kind"
        ),
        sa.CheckConstraint("version > 0", name="ck_itso_policy_version"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["document_source_snapshots.snapshot_id"],
        ),
        sa.PrimaryKeyConstraint("policy_version_id"),
        sa.UniqueConstraint(
            "lineage_id", "version", name="uq_itso_policy_lineage_version"
        ),
    )
    op.create_table(
        "itso_preflight_authorizations",
        sa.Column("preflight_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("source_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("effective_policy_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_versions", sa.JSON(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("reservation", sa.Integer(), nullable=False),
        sa.Column("external_verification", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_evaluation_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "reservation BETWEEN 0 AND 95", name="ck_itso_preflight_reservation"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["consumed_evaluation_id"],
            ["evaluation_jobs.evaluation_id"],
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.document_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["document_source_snapshots.snapshot_id"],
        ),
        sa.PrimaryKeyConstraint("preflight_id"),
        sa.UniqueConstraint(
            "consumed_evaluation_id", name="uq_itso_preflight_evaluation"
        ),
        sa.UniqueConstraint("token_hash", name="uq_itso_preflight_token"),
    )
    op.create_table(
        "itso_document_attachments",
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("visibility", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "visibility IN ('owned','approved_reference')",
            name="ck_itso_attachment_visibility",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.document_id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["itso_policy_versions.policy_version_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["document_source_snapshots.snapshot_id"],
        ),
        sa.PrimaryKeyConstraint("attachment_id"),
        sa.UniqueConstraint(
            "document_id", "source_snapshot_id", "kind", name="uq_itso_attachment_scope"
        ),
    )
    op.create_table(
        "itso_policy_approvals",
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approve','reject')", name="ck_itso_policy_approval_decision"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["itso_policy_versions.policy_version_id"],
        ),
        sa.PrimaryKeyConstraint("approval_id"),
        sa.UniqueConstraint(
            "policy_version_id", name="uq_itso_policy_approval_version"
        ),
    )
    op.create_table(
        "itso_assessment_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["itso_assessments.assessment_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "itso_assessment_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("fact_id", sa.String(length=100), nullable=False),
        sa.Column("criterion_id", sa.String(length=10), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["itso_assessments.assessment_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "fact_id", name="uq_itso_assessment_fact"),
    )
    op.create_table(
        "itso_assessment_policies",
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["itso_assessments.assessment_id"],
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["itso_policy_versions.policy_version_id"],
        ),
        sa.PrimaryKeyConstraint("assessment_id", "policy_version_id"),
    )
    op.create_table(
        "itso_policy_activation_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["itso_policy_approvals.approval_id"],
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["itso_policy_versions.policy_version_id"],
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_table(
        "itso_policy_activations",
        sa.Column("activation_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("scope", sa.String(length=100), nullable=False),
        sa.Column("criterion_id", sa.String(length=10), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["itso_policy_approvals.approval_id"],
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["itso_policy_versions.policy_version_id"],
        ),
        sa.PrimaryKeyConstraint("activation_id"),
        sa.UniqueConstraint(
            "kind", "scope", "criterion_id", name="uq_itso_policy_active_slot"
        ),
    )
    op.create_table(
        "itso_verification_runs",
        sa.Column("plan_hash", sa.String(length=64), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("plan_payload", sa.JSON(), nullable=False),
        sa.Column("reservation", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= reservation AND reservation <= 95",
            name="ck_itso_tool_global_budget",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["itso_assessments.assessment_id"],
        ),
        sa.PrimaryKeyConstraint("plan_hash"),
    )
    op.create_table(
        "itso_fact_decisions",
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("fact_row_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("input_value", sa.Boolean(), nullable=True),
        sa.Column("predicate", sa.String(length=100), nullable=False),
        sa.Column("input_field", sa.String(length=100), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_hash", sa.String(length=64), nullable=False),
        sa.Column("rule_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('confirm','reject','unknown')", name="ck_itso_fact_decision"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["itso_assessments.assessment_id"],
        ),
        sa.ForeignKeyConstraint(
            ["fact_row_id"],
            ["itso_assessment_facts.id"],
        ),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint(
            "assessment_id", "revision", name="uq_itso_decision_revision"
        ),
    )
    op.create_table(
        "itso_verification_tasks",
        sa.Column("plan_hash", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=80), nullable=False),
        sa.Column("started", sa.Boolean(), nullable=False),
        sa.Column("reservation", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("capture_payload", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= reservation AND reservation <= 5",
            name="ck_itso_tool_lane_budget",
        ),
        sa.ForeignKeyConstraint(
            ["plan_hash"],
            ["itso_verification_runs.plan_hash"],
        ),
        sa.PrimaryKeyConstraint("plan_hash", "task_id"),
    )
    op.create_table(
        "itso_assessment_revisions",
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["itso_assessments.assessment_id"],
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["itso_fact_decisions.decision_id"],
        ),
        sa.PrimaryKeyConstraint("revision_id"),
        sa.UniqueConstraint(
            "assessment_id", "revision", name="uq_itso_effective_revision"
        ),
    )
    op.create_table(
        "itso_tool_attempts",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("plan_hash", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=80), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("request_class", sa.String(length=30), nullable=False),
        sa.Column("destination_hash", sa.String(length=64), nullable=False),
        sa.Column("started_monotonic", sa.Float(), nullable=False),
        sa.Column("elapsed", sa.Float(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.CheckConstraint("ordinal BETWEEN 1 AND 5", name="ck_itso_attempt_ordinal"),
        sa.ForeignKeyConstraint(
            ["plan_hash", "task_id"],
            ["itso_verification_tasks.plan_hash", "itso_verification_tasks.task_id"],
            name="fk_itso_attempt_task",
        ),
        sa.ForeignKeyConstraint(
            ["plan_hash"],
            ["itso_verification_runs.plan_hash"],
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint(
            "plan_hash", "task_id", "ordinal", name="uq_itso_tool_attempt_ordinal"
        ),
    )
    # Earlier foundation assessments must have a real frozen form. Refuse to
    # invent a binding or discard populated history if it cannot be resolved.
    with op.batch_alter_table("itso_assessments") as batch:
        batch.add_column(sa.Column("form_snapshot_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("effective_policy_hash", sa.String(64), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "review_revision", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch.create_foreign_key(
            "fk_itso_assessment_form",
            "evaluation_form_snapshots",
            ["form_snapshot_id"],
            ["snapshot_id"],
        )
        batch.create_check_constraint("ck_itso_review_revision", "review_revision >= 0")
    op.get_bind().execute(
        sa.text(
            "UPDATE itso_assessments SET form_snapshot_id = "
            "(SELECT snapshot_id FROM evaluation_form_snapshots WHERE "
            "evaluation_form_snapshots.evaluation_id = "
            "itso_assessments.evaluation_id AND "
            "agent_id = 'itso' AND adapter_version = 2)"
        )
    )
    if op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM itso_assessments WHERE form_snapshot_id IS NULL")
    ):
        raise RuntimeError(
            "ITSO history requires a valid frozen v2 form before upgrade"
        )
    empty_hash = hashlib.sha256(
        b'{"attachments":[],"policy_hash":"'
        + hashlib.sha256(b"[]").hexdigest().encode()
        + b'"}'
    ).hexdigest()
    op.get_bind().execute(
        sa.text("UPDATE itso_assessments SET effective_policy_hash = :hash"),
        {"hash": empty_hash},
    )
    with op.batch_alter_table("itso_assessments") as batch:
        batch.alter_column("form_snapshot_id", existing_type=sa.Uuid(), nullable=False)
        batch.alter_column(
            "effective_policy_hash", existing_type=sa.String(64), nullable=False
        )


def downgrade() -> None:
    tables = [
        "itso_policy_versions",
        "itso_preflight_authorizations",
        "itso_document_attachments",
        "itso_policy_approvals",
        "itso_assessment_evidence",
        "itso_assessment_facts",
        "itso_assessment_policies",
        "itso_policy_activation_events",
        "itso_policy_activations",
        "itso_verification_runs",
        "itso_fact_decisions",
        "itso_verification_tasks",
        "itso_assessment_revisions",
        "itso_tool_attempts",
        "itso_assessments",
    ]
    for name in tables:
        if op.get_bind().scalar(sa.text(f"SELECT COUNT(*) FROM {name}")):
            raise RuntimeError("Downgrade refuses to delete ITSO workflow history")
    op.drop_table("itso_tool_attempts")
    op.drop_table("itso_assessment_revisions")
    op.drop_table("itso_verification_tasks")
    op.drop_table("itso_fact_decisions")
    op.drop_table("itso_verification_runs")
    op.drop_table("itso_policy_activations")
    op.drop_table("itso_policy_activation_events")
    op.drop_table("itso_assessment_policies")
    op.drop_table("itso_assessment_facts")
    op.drop_table("itso_assessment_evidence")
    op.drop_table("itso_policy_approvals")
    op.drop_table("itso_document_attachments")
    op.drop_table("itso_preflight_authorizations")
    op.drop_table("itso_policy_versions")
    with op.batch_alter_table("itso_assessments") as batch:
        batch.drop_constraint("fk_itso_assessment_form", type_="foreignkey")
        batch.drop_constraint("ck_itso_review_revision", type_="check")
        batch.drop_column("form_snapshot_id")
        batch.drop_column("effective_policy_hash")
        batch.drop_column("review_revision")
