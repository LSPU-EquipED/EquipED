"""Explicit transactional migration to the advisory ITSO adapter v3 rubric."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from equiped_harness.contracts import LlmRubricGuidanceConfig
from server.modules.auth.service import require_approved_admin
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from .repository import get_form_definition_by_id, validate_form_definition

ITSO_AGENT_ID = "itso"
ITSO_ADAPTER_VERSION = 3

CANONICAL_ITSO_CRITERIA = (
    "ITSO-01",
    "ITSO-02",
    "ITSO-03",
    "ITSO-04",
    "ITSO-05",
)


@dataclass(frozen=True)
class ItsoHarnessUpgradeResult:
    rubric_set_id: uuid.UUID
    version_number: int
    already_active: bool


def upgrade_itso_harness(
    session: Session, *, actor_id: uuid.UUID
) -> ItsoHarnessUpgradeResult:
    """Clone/activate the active ITSO revision as grounded advisory adapter v3.

    This method owns a transaction or nested savepoint and either publishes
    and activates the complete v3 revision or rolls it back. Existing revisions
    and evaluation snapshots are read-only inputs; an existing draft stops cutover.
    """
    transaction = (
        session.begin_nested() if session.in_transaction() else session.begin()
    )
    with transaction:
        require_approved_admin(session, actor_id)

        # The shared rubric lock order is activation first, then revision rows.
        activation = session.scalar(
            select(RubricAgentActivation)
            .where(RubricAgentActivation.agent_id == ITSO_AGENT_ID)
            .with_for_update()
        )
        revisions = list(
            session.scalars(
                select(RubricSet)
                .where(RubricSet.agent_id == ITSO_AGENT_ID)
                .order_by(RubricSet.rubric_set_id)
                .with_for_update()
            )
        )
        if activation is None:
            raise RuntimeError("ITSO upgrade requires an active published ITSO rubric")
        active = next(
            (row for row in revisions if row.rubric_set_id == activation.rubric_set_id),
            None,
        )
        if active is None or active.status != "published":
            raise RuntimeError("ITSO activation does not point to a published rubric")
        if active.adapter_key != ITSO_AGENT_ID:
            raise RuntimeError("Active ITSO rubric has an unexpected adapter key")
        if active.adapter_version == ITSO_ADAPTER_VERSION:
            form = get_form_definition_by_id(session, active.rubric_set_id)
            report = validate_form_definition(form) if form is not None else None
            if report is None or not report.is_valid:
                details = (
                    "; ".join(f"{item.path}: {item.message}" for item in report.errors)
                    if report is not None
                    else "active form could not be loaded"
                )
                raise RuntimeError(
                    f"Active ITSO v3 rubric failed validation: {details}"
                )
            return ItsoHarnessUpgradeResult(
                active.rubric_set_id, active.version_number, True
            )
        if active.adapter_version not in (1, 2):
            raise RuntimeError(
                f"Cannot upgrade active ITSO adapter version {active.adapter_version}; "
                "expected v1 or v2"
            )

        in_flight_statuses = (
            EvaluationStatus.SUBMITTED.value,
            EvaluationStatus.PREPROCESSING.value,
            EvaluationStatus.EVALUATING.value,
            EvaluationStatus.SYNTHESIZING.value,
        )
        in_flight_jobs = list(
            session.scalars(
                select(EvaluationJob)
                .where(
                    EvaluationJob.target_agent.in_((ITSO_AGENT_ID, "all")),
                    EvaluationJob.status.in_(in_flight_statuses),
                )
                .order_by(EvaluationJob.evaluation_id)
                .with_for_update()
            )
        )
        if in_flight_jobs:
            raise RuntimeError(
                "ITSO harness upgrade blocked because ITSO evaluation jobs are "
                f"still in flight ({len(in_flight_jobs)}). "
                "Let queued/running jobs finish, "
                "then retry; their saved rubric context remains unchanged."
            )

        domains = list(
            session.scalars(
                select(RubricDomain)
                .where(RubricDomain.rubric_set_id == active.rubric_set_id)
                .order_by(RubricDomain.display_order, RubricDomain.code)
            )
        )
        old_criteria: list[tuple[RubricDomain, RubricCriterion]] = []
        for domain in domains:
            criteria = list(
                session.scalars(
                    select(RubricCriterion)
                    .where(RubricCriterion.rubric_domain_id == domain.rubric_domain_id)
                    .order_by(
                        RubricCriterion.display_order, RubricCriterion.criterion_code
                    )
                )
            )
            old_criteria.extend((domain, criterion) for criterion in criteria)

        # Adapter v2 intentionally has no LLM guidance config. If an original
        # adapter v1 revision remains in history, restore its exact guidance and
        # level descriptors by criterion code while keeping the active revision's
        # titles and descriptions below.
        v1_revisions = [
            row
            for row in revisions
            if row.adapter_version == 1 and row.status in {"published", "retired"}
        ]
        original_guidance: dict[str, LlmRubricGuidanceConfig] = {}
        if active.adapter_version == 1:
            guidance_revision = active
        else:
            guidance_revision = max(
                v1_revisions,
                key=lambda row: (row.version_number, str(row.rubric_set_id)),
                default=None,
            )
        if guidance_revision is not None:
            original_rows = session.scalars(
                select(RubricCriterion)
                .join(RubricDomain)
                .where(RubricDomain.rubric_set_id == guidance_revision.rubric_set_id)
            )
            for row in original_rows:
                raw = row.strategy_config
                if (
                    row.scoring_strategy == "llm_rubric_guidance"
                    and isinstance(raw, dict)
                    and raw.get("strategy") == "llm_rubric_guidance"
                ):
                    original_guidance.setdefault(
                        row.criterion_code,
                        LlmRubricGuidanceConfig.model_validate(raw),
                    )

        actual_codes = tuple(criterion.criterion_code for _, criterion in old_criteria)
        if len(actual_codes) != len(CANONICAL_ITSO_CRITERIA) or set(
            actual_codes
        ) != set(CANONICAL_ITSO_CRITERIA):
            raise RuntimeError(
                "Cannot upgrade ITSO rubric: expected exactly five canonical criteria "
                f"{CANONICAL_ITSO_CRITERIA}, found {actual_codes}. "
                "Reconcile the active "
                "published rubric to the canonical five criteria before retrying."
            )

        existing_drafts = [row for row in revisions if row.status == "draft"]
        if existing_drafts:
            draft_versions = sorted(row.version_number for row in existing_drafts)
            raise RuntimeError(
                "ITSO harness upgrade blocked because an existing ITSO draft must be "
                f"resolved first (draft versions: {draft_versions}). "
                "The draft and active "
                "published revision were preserved; publish or remove the draft "
                "through "
                "the rubric editor, then retry."
            )

        version = max((row.version_number for row in revisions), default=0) + 1
        upgraded = RubricSet(
            rubric_set_id=uuid.uuid4(),
            agent_id=ITSO_AGENT_ID,
            name=f"{active.name} (Advisory v3)",
            version_number=version,
            status="draft",
            adapter_key=ITSO_AGENT_ID,
            adapter_version=ITSO_ADAPTER_VERSION,
            published_at=None,
            published_by=None,
            created_by=actor_id,
        )
        session.add(upgraded)
        session.flush()

        domain_map: dict[uuid.UUID, RubricDomain] = {}
        for source_domain in domains:
            cloned = RubricDomain(
                rubric_domain_id=uuid.uuid4(),
                rubric_set_id=upgraded.rubric_set_id,
                code=source_domain.code,
                title=source_domain.title,
                display_order=source_domain.display_order,
            )
            session.add(cloned)
            domain_map[source_domain.rubric_domain_id] = cloned
        session.flush()

        for source_domain, criterion in old_criteria:
            config = original_guidance.get(criterion.criterion_code)
            if config is None:
                # Legacy v1 imports may not have carried a strategy config.
                config = LlmRubricGuidanceConfig(
                    guidance=(criterion.scoring_rule or criterion.description).strip()
                )
            session.add(
                RubricCriterion(
                    rubric_criterion_id=uuid.uuid4(),
                    rubric_domain_id=domain_map[
                        source_domain.rubric_domain_id
                    ].rubric_domain_id,
                    criterion_code=criterion.criterion_code,
                    title=criterion.title,
                    description=criterion.description,
                    scoring_rule=criterion.scoring_rule,
                    scoring_strategy="llm_rubric_guidance",
                    strategy_config=config.model_dump(mode="json"),
                    display_order=criterion.display_order,
                )
            )
        session.flush()

        form = get_form_definition_by_id(session, upgraded.rubric_set_id)
        if form is None:
            raise RuntimeError("Failed to load the new ITSO v3 rubric for validation")
        report = validate_form_definition(form)
        if not report.is_valid:
            details = "; ".join(
                f"{item.path}: {item.message}" for item in report.errors
            )
            raise RuntimeError(f"New ITSO v3 rubric failed validation: {details}")

        upgraded.status = "published"
        upgraded.published_at = datetime.now(UTC)
        upgraded.published_by = actor_id
        activation.rubric_set_id = upgraded.rubric_set_id
        activation.updated_by = actor_id
        activation.updated_at = datetime.now(UTC)
        session.flush()
        return ItsoHarnessUpgradeResult(upgraded.rubric_set_id, version, False)
