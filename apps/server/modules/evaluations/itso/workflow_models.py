"""Durable policy, consent and append-only assessment artifacts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from server.core.database import Base
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


class PolicyVersion(Base):
    __tablename__ = "itso_policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "lineage_id", "version", name="uq_itso_policy_lineage_version"
        ),
        CheckConstraint(
            "kind IN ('egress','institutional','rule')", name="ck_itso_policy_kind"
        ),
        CheckConstraint("version > 0", name="ck_itso_policy_version"),
    )
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    lineage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, default=uuid.uuid4
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    criterion_id: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    source_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_source_snapshots.snapshot_id"), nullable=False
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class PolicyApproval(Base):
    __tablename__ = "itso_policy_approvals"
    __table_args__ = (
        UniqueConstraint("policy_version_id", name="uq_itso_policy_approval_version"),
        CheckConstraint(
            "decision IN ('approve','reject')", name="ck_itso_policy_approval_decision"
        ),
    )
    approval_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_policy_versions.policy_version_id"), nullable=False
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class PolicyActivation(Base):
    __tablename__ = "itso_policy_activations"
    __table_args__ = (
        UniqueConstraint(
            "kind", "scope", "criterion_id", name="uq_itso_policy_active_slot"
        ),
    )
    activation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    criterion_id: Mapped[str] = mapped_column(String(10), nullable=False)
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_policy_versions.policy_version_id"), nullable=False
    )
    approval_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_policy_approvals.approval_id"), nullable=False
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class PolicyActivationEvent(Base):
    __tablename__ = "itso_policy_activation_events"
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_policy_versions.policy_version_id"), nullable=False
    )
    approval_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_policy_approvals.approval_id"), nullable=False
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class DocumentAttachment(Base):
    __tablename__ = "itso_document_attachments"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "source_snapshot_id", "kind", name="uq_itso_attachment_scope"
        ),
        CheckConstraint(
            "visibility IN ('owned','approved_reference')",
            name="ck_itso_attachment_visibility",
        ),
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.document_id"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    source_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_source_snapshots.snapshot_id"), nullable=False
    )
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("itso_policy_versions.policy_version_id"), nullable=True
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    visibility: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class PreflightAuthorization(Base):
    __tablename__ = "itso_preflight_authorizations"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_itso_preflight_token"),
        UniqueConstraint("consumed_evaluation_id", name="uq_itso_preflight_evaluation"),
        CheckConstraint(
            "reservation BETWEEN 0 AND 95", name="ck_itso_preflight_reservation"
        ),
    )
    preflight_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.document_id"), nullable=False
    )
    source_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_source_snapshots.snapshot_id"), nullable=False
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_versions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reservation: Mapped[int] = mapped_column(Integer, nullable=False)
    external_verification: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_jobs.evaluation_id"), nullable=True
    )


class AssessmentPolicy(Base):
    __tablename__ = "itso_assessment_policies"
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_assessments.assessment_id"), primary_key=True
    )
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_policy_versions.policy_version_id"), primary_key=True
    )


class AssessmentFact(Base):
    __tablename__ = "itso_assessment_facts"
    __table_args__ = (
        UniqueConstraint("assessment_id", "fact_id", name="uq_itso_assessment_fact"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_assessments.assessment_id"), nullable=False
    )
    fact_id: Mapped[str] = mapped_column(String(100), nullable=False)
    criterion_id: Mapped[str] = mapped_column(String(10), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AssessmentEvidence(Base):
    __tablename__ = "itso_assessment_evidence"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_assessments.assessment_id"), nullable=False
    )
    # Protected prompts/generations/packets are never projected by the public reader.
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class FactDecision(Base):
    __tablename__ = "itso_fact_decisions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "revision", name="uq_itso_decision_revision"),
        CheckConstraint(
            "decision IN ('confirm','reject','unknown')", name="ck_itso_fact_decision"
        ),
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_assessments.assessment_id"), nullable=False
    )
    fact_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_assessment_facts.id"), nullable=False
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    input_value: Mapped[bool | None] = mapped_column(nullable=True)
    predicate: Mapped[str] = mapped_column(String(100), nullable=False)
    input_field: Mapped[str] = mapped_column(String(100), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class AssessmentRevision(Base):
    __tablename__ = "itso_assessment_revisions"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id", "revision", name="uq_itso_effective_revision"
        ),
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_assessments.assessment_id"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_fact_decisions.decision_id"), nullable=False
    )
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


def _immutable(_mapper, _connection, _target):
    raise ValueError("immutable_itso_record")


for _model in (
    PolicyVersion,
    PolicyApproval,
    PolicyActivationEvent,
    PreflightAuthorization,
    DocumentAttachment,
    AssessmentPolicy,
    AssessmentFact,
    AssessmentEvidence,
    FactDecision,
    AssessmentRevision,
):
    event.listen(_model, "before_update", _immutable)
    event.listen(_model, "before_delete", _immutable)
