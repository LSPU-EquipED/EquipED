"""Transactional migration to the qualitative Coordinator adapter v4 rubric."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from equiped_harness.agents.coordinator.rubric import guidance_for
from server.modules.auth.service import require_approved_admin
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import RubricAgentActivation, RubricCriterion, RubricDomain, RubricSet
from .repository import get_form_definition_by_id, validate_form_definition

_AGENT = "coordinator"
_VERSION = 4
_CODES = (
    "OP-01",
    "OP-02",
    "OP-03",
    "OP-04",
    "OP-05",
    "A-01",
    "A-02",
    "A-03",
    "A-04",
    "A-05",
)


@dataclass(frozen=True)
class CoordinatorHarnessUpgradeResult:
    rubric_set_id: uuid.UUID
    version_number: int
    already_active: bool


def upgrade_coordinator_harness(
    session: Session, *, actor_id: uuid.UUID
) -> CoordinatorHarnessUpgradeResult:
    """Clone the active published rubric, replacing scoring config with v4 guidance."""
    transaction = (
        session.begin_nested() if session.in_transaction() else session.begin()
    )
    with transaction:
        require_approved_admin(session, actor_id)
        activation = session.scalar(
            select(RubricAgentActivation)
            .where(RubricAgentActivation.agent_id == _AGENT)
            .with_for_update()
        )
        revisions = list(
            session.scalars(
                select(RubricSet)
                .where(RubricSet.agent_id == _AGENT)
                .order_by(RubricSet.rubric_set_id)
                .with_for_update()
            )
        )
        if activation is None:
            raise RuntimeError(
                "Coordinator upgrade requires an active published rubric"
            )
        active = next(
            (r for r in revisions if r.rubric_set_id == activation.rubric_set_id), None
        )
        if (
            active is None
            or active.status != "published"
            or active.adapter_key != _AGENT
        ):
            raise RuntimeError(
                "Coordinator activation must point to a published Coordinator rubric"
            )
        if active.adapter_version == _VERSION:
            form = get_form_definition_by_id(session, active.rubric_set_id)
            report = validate_form_definition(form) if form else None
            if report is None or not report.is_valid:
                raise RuntimeError("Active Coordinator v4 rubric failed validation")
            return CoordinatorHarnessUpgradeResult(
                active.rubric_set_id, active.version_number, True
            )
        if active.adapter_version not in (2, 3):
            raise RuntimeError(
                f"Unsupported Coordinator adapter v{active.adapter_version}; "
                "expected v2 or v3"
            )

        inflight = tuple(
            status.value
            for status in (
                EvaluationStatus.SUBMITTED,
                EvaluationStatus.PREPROCESSING,
                EvaluationStatus.EVALUATING,
                EvaluationStatus.SYNTHESIZING,
            )
        )
        jobs = list(
            session.scalars(
                select(EvaluationJob)
                .where(
                    EvaluationJob.target_agent.in_((_AGENT, "all")),
                    EvaluationJob.status.in_(inflight),
                )
                .with_for_update()
            )
        )
        if jobs:
            raise RuntimeError(
                f"Coordinator upgrade blocked by {len(jobs)} in-flight job(s)"
            )
        domains = list(
            session.scalars(
                select(RubricDomain)
                .where(RubricDomain.rubric_set_id == active.rubric_set_id)
                .order_by(RubricDomain.display_order, RubricDomain.code)
            )
        )
        pairs = []
        for domain in domains:
            criteria = session.scalars(
                select(RubricCriterion)
                .where(RubricCriterion.rubric_domain_id == domain.rubric_domain_id)
                .order_by(RubricCriterion.display_order, RubricCriterion.criterion_code)
            )
            pairs.extend((domain, criterion) for criterion in criteria)
        codes = tuple(c.criterion_code for _, c in pairs)
        if len(codes) != 10 or set(codes) != set(_CODES):
            raise RuntimeError(
                "Coordinator upgrade requires the ten canonical criteria; "
                f"found {codes}"
            )

        version = max((r.version_number for r in revisions), default=0) + 1
        upgraded = RubricSet(
            rubric_set_id=uuid.uuid4(),
            agent_id=_AGENT,
            name=f"{active.name} (Qualitative v4)",
            version_number=version,
            # Publish at insert time so the one-draft-per-agent constraint is
            # never transiently violated when an operator already has a draft.
            status="published",
            adapter_key=_AGENT,
            adapter_version=_VERSION,
            published_at=None,
            published_by=None,
            created_by=actor_id,
        )
        session.add(upgraded)
        session.flush()
        domain_map = {}
        for source in domains:
            clone = RubricDomain(
                rubric_domain_id=uuid.uuid4(),
                rubric_set_id=upgraded.rubric_set_id,
                code=source.code,
                title=source.title,
                display_order=source.display_order,
            )
            session.add(clone)
            domain_map[source.rubric_domain_id] = clone
        session.flush()
        for domain, criterion in pairs:
            config = guidance_for(criterion.criterion_code)
            session.add(
                RubricCriterion(
                    rubric_criterion_id=uuid.uuid4(),
                    rubric_domain_id=domain_map[
                        domain.rubric_domain_id
                    ].rubric_domain_id,
                    criterion_code=criterion.criterion_code,
                    title=criterion.title,
                    description=criterion.description,
                    scoring_rule=config.guidance,
                    scoring_strategy="llm_rubric_guidance",
                    strategy_config=config.model_dump(mode="json"),
                    display_order=criterion.display_order,
                )
            )
        session.flush()
        form = get_form_definition_by_id(session, upgraded.rubric_set_id)
        report = validate_form_definition(form) if form else None
        if report is None or not report.is_valid:
            details = (
                "; ".join(f"{i.path}: {i.message}" for i in report.errors)
                if report
                else "form could not be loaded"
            )
            raise RuntimeError(
                f"New Coordinator v4 rubric failed validation: {details}"
            )
        now = datetime.now(UTC)
        upgraded.published_at, upgraded.published_by = now, actor_id
        activation.rubric_set_id, activation.updated_by, activation.updated_at = (
            upgraded.rubric_set_id,
            actor_id,
            now,
        )
        session.flush()
        return CoordinatorHarnessUpgradeResult(upgraded.rubric_set_id, version, False)
