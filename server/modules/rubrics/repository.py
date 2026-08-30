"""Database repository and transaction primitives for dynamic CID evaluation forms."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from server.core.config import get_settings
from sqlalchemy import func
from sqlalchemy.orm import Session

from .contracts import (
    MAX_CODE_LENGTH,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    ValidationReport,
    canonicalize_form,
)
from .exceptions import RubricValidationError
from .manifests import (
    get_agent_manifest,
    validate_form,
)
from .models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)


def validate_form_definition(form: FormDefinition) -> ValidationReport:
    """Validate a FormDefinition against manifest and deployed budget setting."""
    agent_id = form.agent_id
    manifest = get_agent_manifest(agent_id)

    setting_name = manifest.prompt_budget_setting
    settings = get_settings()
    budget_val = getattr(settings, setting_name, None)
    if budget_val is None or not isinstance(budget_val, int) or budget_val <= 0:
        raise ValueError(
            f"Invalid or missing prompt budget setting '{setting_name}' "
            f"for agent '{agent_id}'"
        )

    return validate_form(form, manifest, prompt_budget_chars=budget_val)


def orm_to_form_definition(
    rubric_set: RubricSet,
    domains: Sequence[RubricDomain],
    criteria: Sequence[RubricCriterion],
) -> FormDefinition:
    """Convert relational rubric models into a canonical, validated FormDefinition.

    Strategy configs are validated via the frozen Pydantic contracts,
    scoring_strategy is verified to match strategy_config.strategy, and
    domains/criteria are canonically ordered.
    """
    criteria_by_domain: dict[uuid.UUID, list[RubricCriterion]] = {}
    for crit in criteria:
        criteria_by_domain.setdefault(crit.rubric_domain_id, []).append(crit)

    domain_defs: list[DomainDefinition] = []
    for domain in domains:
        crit_defs: list[CriterionDefinition] = []
        for crit in criteria_by_domain.get(domain.rubric_domain_id, []):
            if not crit.scoring_strategy or not crit.scoring_strategy.strip():
                raise ValueError(
                    f"Criterion {crit.criterion_code} ({crit.rubric_criterion_id}) "
                    "is missing required scoring_strategy"
                )
            if crit.strategy_config is None:
                raise ValueError(
                    f"Criterion {crit.criterion_code} ({crit.rubric_criterion_id}) "
                    "is missing required strategy_config"
                )

            crit_def = CriterionDefinition(
                rubric_criterion_id=crit.rubric_criterion_id,
                criterion_code=crit.criterion_code,
                title=crit.title,
                description=crit.description,
                scoring_rule=crit.scoring_rule,
                display_order=crit.display_order,
                strategy_config=crit.strategy_config,
            )
            if crit.scoring_strategy != crit_def.strategy_config.strategy:
                raise ValueError(
                    f"Criterion {crit.criterion_code} scoring_strategy "
                    f"'{crit.scoring_strategy}' does not match strategy_config "
                    f"'{crit_def.strategy_config.strategy}'"
                )

            crit_defs.append(crit_def)

        domain_defs.append(
            DomainDefinition(
                rubric_domain_id=domain.rubric_domain_id,
                code=domain.code,
                title=domain.title,
                display_order=domain.display_order,
                criteria=tuple(crit_defs),
            )
        )

    raw_form = FormDefinition(
        rubric_set_id=rubric_set.rubric_set_id,
        agent_id=rubric_set.agent_id,
        name=rubric_set.name,
        version_number=rubric_set.version_number,
        adapter_key=rubric_set.adapter_key,
        adapter_version=rubric_set.adapter_version,
        domains=tuple(domain_defs),
    )
    return canonicalize_form(raw_form)


def get_active_form_definition(
    session: Session, agent_id: str
) -> FormDefinition | None:
    """Load active form definition for an agent by joining activation pointer."""
    activation = (
        session.query(RubricAgentActivation).filter_by(agent_id=agent_id).one_or_none()
    )
    if activation is None:
        return None

    rubric_set = (
        session.query(RubricSet)
        .filter_by(rubric_set_id=activation.rubric_set_id)
        .one_or_none()
    )
    if rubric_set is None:
        return None

    if rubric_set.agent_id != agent_id:
        raise ValueError(
            f"Active activation pointer agent mismatch: points to "
            f"'{rubric_set.agent_id}', expected '{agent_id}'"
        )

    if rubric_set.status != "published":
        raise ValueError(
            f"Active revision {rubric_set.rubric_set_id} has invalid status "
            f"'{rubric_set.status}'; must be 'published'"
        )

    domains = (
        session.query(RubricDomain)
        .filter_by(rubric_set_id=rubric_set.rubric_set_id)
        .order_by(RubricDomain.display_order.asc(), RubricDomain.code.asc())
        .all()
    )

    all_criteria = (
        session.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id == rubric_set.rubric_set_id)
        .order_by(
            RubricCriterion.display_order.asc(),
            RubricCriterion.criterion_code.asc(),
        )
        .all()
    )

    form_def = orm_to_form_definition(rubric_set, domains, all_criteria)
    report = validate_form_definition(form_def)
    if not report.is_valid:
        error_msgs = "; ".join(f"{i.path}: {i.message}" for i in report.errors)
        raise ValueError(
            "Active form definition failed capability manifest validation: "
            f"{error_msgs}"
        )

    return form_def


def load_active_form_definitions(
    session: Session, scheduled_agent_ids: Sequence[str]
) -> dict[str, FormDefinition]:
    """Bulk load active form definitions for scheduled agents.

    Executes exactly three bounded queries (activation+set, domains, criteria)
    with no locks and no N+1 round trips.

    Raises:
        ValueError: If scheduled_agent_ids is empty, contains duplicates, contains
            unknown agent IDs, has pointer agent mismatches, or has invalid status/form.
        LookupError: If active published rubric sets are missing for any
            scheduled agent.
    """
    if (
        scheduled_agent_ids is None
        or isinstance(scheduled_agent_ids, (str, bytes))
        or not isinstance(scheduled_agent_ids, Sequence)
    ):
        raise ValueError("scheduled_agent_ids must be a non-string sequence")

    agent_tuple = tuple(scheduled_agent_ids)
    if not agent_tuple:
        raise ValueError("scheduled_agent_ids cannot be empty")

    seen_agents: set[str] = set()
    for agent_id in agent_tuple:
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("scheduled_agent_ids contains invalid empty agent ID")
        if len(agent_id) > MAX_CODE_LENGTH:
            raise ValueError(
                "scheduled_agent_ids contains agent ID exceeding maximum code length"
            )
        if agent_id in seen_agents:
            raise ValueError("Duplicate agent ID in scheduled_agent_ids")
        seen_agents.add(agent_id)
        try:
            get_agent_manifest(agent_id)
        except ValueError as exc:
            raise ValueError("Unknown agent ID in scheduled_agent_ids") from exc

    # 1. Single query: activations joined with rubric sets
    activation_rows = (
        session.query(RubricAgentActivation, RubricSet)
        .join(RubricSet, RubricAgentActivation.rubric_set_id == RubricSet.rubric_set_id)
        .filter(RubricAgentActivation.agent_id.in_(agent_tuple))
        .all()
    )

    found_agents = {act.agent_id for act, _ in activation_rows}
    if set(agent_tuple) != found_agents:
        raise LookupError("Missing active published rubric set for scheduled agents")

    for act, r_set in activation_rows:
        if r_set.agent_id != act.agent_id:
            raise ValueError(
                f"Active activation pointer agent mismatch: points to "
                f"'{r_set.agent_id}', expected '{act.agent_id}'"
            )
        if r_set.status != "published":
            raise ValueError(
                f"Active revision {r_set.rubric_set_id} for agent '{act.agent_id}' "
                f"has invalid status '{r_set.status}'; must be 'published'"
            )

    rubric_set_ids = [r_set.rubric_set_id for _, r_set in activation_rows]

    # 2. Single query: all domains for all loaded rubric sets
    domains = (
        session.query(RubricDomain)
        .filter(RubricDomain.rubric_set_id.in_(rubric_set_ids))
        .order_by(RubricDomain.display_order.asc(), RubricDomain.code.asc())
        .all()
    )

    domains_by_set: dict[uuid.UUID, list[RubricDomain]] = {
        rid: [] for rid in rubric_set_ids
    }
    domain_to_set: dict[uuid.UUID, uuid.UUID] = {}
    for dom in domains:
        domains_by_set[dom.rubric_set_id].append(dom)
        domain_to_set[dom.rubric_domain_id] = dom.rubric_set_id

    # 3. Single query: all criteria for all loaded rubric sets
    criteria = (
        session.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id.in_(rubric_set_ids))
        .order_by(
            RubricCriterion.display_order.asc(),
            RubricCriterion.criterion_code.asc(),
        )
        .all()
    )

    criteria_by_set: dict[uuid.UUID, list[RubricCriterion]] = {
        rid: [] for rid in rubric_set_ids
    }
    for crit in criteria:
        set_id = domain_to_set.get(crit.rubric_domain_id)
        if set_id is not None:
            criteria_by_set[set_id].append(crit)

    # Convert to FormDefinition and revalidate with deployed budget
    act_map = {act.agent_id: r_set for act, r_set in activation_rows}
    result: dict[str, FormDefinition] = {}
    for agent_id in agent_tuple:
        r_set = act_map[agent_id]
        form_def = orm_to_form_definition(
            r_set,
            domains_by_set.get(r_set.rubric_set_id, []),
            criteria_by_set.get(r_set.rubric_set_id, []),
        )
        report = validate_form_definition(form_def)
        if not report.is_valid:
            error_msgs = "; ".join(f"{i.path}: {i.message}" for i in report.errors)
            raise ValueError(
                f"Active form definition for agent '{agent_id}' failed "
                f"capability manifest validation: {error_msgs}"
            )
        result[agent_id] = form_def

    return result


def get_form_definition_by_id(
    session: Session, rubric_set_id: uuid.UUID
) -> FormDefinition | None:
    """Load a specific form definition by rubric_set_id."""
    rubric_set = (
        session.query(RubricSet).filter_by(rubric_set_id=rubric_set_id).one_or_none()
    )
    if rubric_set is None:
        return None

    domains = (
        session.query(RubricDomain)
        .filter_by(rubric_set_id=rubric_set.rubric_set_id)
        .order_by(RubricDomain.display_order.asc(), RubricDomain.code.asc())
        .all()
    )

    all_criteria = (
        session.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id == rubric_set.rubric_set_id)
        .order_by(
            RubricCriterion.display_order.asc(),
            RubricCriterion.criterion_code.asc(),
        )
        .all()
    )

    return orm_to_form_definition(rubric_set, domains, all_criteria)


# ---------------------------------------------------------------------------
# Transaction-Safe Shared Locking and Mutation Primitives
# ---------------------------------------------------------------------------


def lock_draft_rubric_set(session: Session, rubric_set_id: uuid.UUID) -> RubricSet:
    """Lock a draft rubric set row exclusively for update.

    Fails if the rubric set does not exist or is published/retired (immutable).
    """
    rubric_set = (
        session.query(RubricSet)
        .filter_by(rubric_set_id=rubric_set_id)
        .with_for_update()
        .one_or_none()
    )
    if rubric_set is None:
        raise LookupError(f"Rubric set {rubric_set_id} not found")
    if rubric_set.status != "draft":
        raise ValueError(
            f"Cannot mutate non-draft rubric set {rubric_set_id}; "
            f"status is '{rubric_set.status}' "
            "(published/retired definitions are immutable)"
        )
    return rubric_set


def lock_activation_and_revisions(
    session: Session,
    agent_id: str,
    revision_ids: Sequence[uuid.UUID],
) -> tuple[RubricAgentActivation | None, list[RubricSet]]:
    """Lock activation row first, followed by revision rows sorted by UUID.

    Automatically includes the current active revision in the lock set.
    """
    activation = (
        session.query(RubricAgentActivation)
        .filter_by(agent_id=agent_id)
        .with_for_update()
        .one_or_none()
    )

    all_ids = set(revision_ids)
    if activation is not None:
        all_ids.add(activation.rubric_set_id)

    sorted_ids = sorted(all_ids)
    revisions: list[RubricSet] = []
    if sorted_ids:
        revisions = (
            session.query(RubricSet)
            .filter(RubricSet.rubric_set_id.in_(sorted_ids))
            .order_by(RubricSet.rubric_set_id.asc())
            .with_for_update()
            .all()
        )

    return activation, revisions


def activate_revision(
    session: Session,
    agent_id: str,
    rubric_set_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    is_system: bool = False,
) -> RubricAgentActivation:
    """Atomically activate a published rubric set for an agent.

    Enforces:
    - Non-null actor_id for normal admin operations
    - Existing activation required for normal admin operations
    - Same-agent target check
    - Revision status must be 'published'
    - Strict FormDefinition parsing and manifest validation
    """
    if actor_id is None and not is_system:
        raise ValueError("actor_id is required for non-system activation")

    activation, revisions = lock_activation_and_revisions(
        session, agent_id, [rubric_set_id]
    )
    if activation is None and not is_system:
        raise ValueError(
            f"Cannot activate: no existing activation pointer found for "
            f"agent '{agent_id}'"
        )

    rubric_set = next((r for r in revisions if r.rubric_set_id == rubric_set_id), None)
    if rubric_set is None:
        raise LookupError(f"Rubric set {rubric_set_id} not found")

    if rubric_set.agent_id != agent_id:
        raise ValueError(
            f"Agent mismatch: revision {rubric_set_id} belongs to "
            f"'{rubric_set.agent_id}', not '{agent_id}'"
        )

    if rubric_set.status != "published":
        raise ValueError(
            f"Cannot activate revision {rubric_set_id} with status "
            f"'{rubric_set.status}'; must be 'published'"
        )

    # Validate target revision strictly against capability manifest
    form_def = get_form_definition_by_id(session, rubric_set_id)
    if form_def is None:
        raise LookupError(f"Failed to load form definition for {rubric_set_id}")

    report = validate_form_definition(form_def)
    if not report.is_valid:
        error_msgs = "; ".join(f"{i.path}: {i.message}" for i in report.errors)
        raise RubricValidationError(
            f"Cannot activate invalid revision: {error_msgs}", report=report
        )

    now = datetime.now(UTC)
    if activation is None:
        activation = RubricAgentActivation(
            agent_id=agent_id,
            rubric_set_id=rubric_set_id,
            updated_by=actor_id,
            updated_at=now,
        )
        session.add(activation)
    else:
        activation.rubric_set_id = rubric_set_id
        activation.updated_by = actor_id
        activation.updated_at = now

    session.flush()
    return activation


def retire_revision(
    session: Session,
    agent_id: str,
    rubric_set_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    is_system: bool = False,
) -> RubricSet:
    """Retire a published rubric set that is not currently active.

    Enforces:
    - Non-null actor_id for normal admin operations
    - Same-agent target check
    - Target must be 'published'
    - Target must NOT be currently active
    """
    if actor_id is None and not is_system:
        raise ValueError("actor_id is required for non-system retirement")

    activation, revisions = lock_activation_and_revisions(
        session, agent_id, [rubric_set_id]
    )
    rubric_set = next((r for r in revisions if r.rubric_set_id == rubric_set_id), None)
    if rubric_set is None:
        raise LookupError(f"Rubric set {rubric_set_id} not found")

    if rubric_set.agent_id != agent_id:
        raise ValueError(
            f"Agent mismatch: revision {rubric_set_id} belongs to "
            f"'{rubric_set.agent_id}', not '{agent_id}'"
        )

    if rubric_set.status != "published":
        raise ValueError(
            f"Cannot retire revision {rubric_set_id} with status "
            f"'{rubric_set.status}'; must be 'published'"
        )

    if activation is not None and activation.rubric_set_id == rubric_set_id:
        raise ValueError(
            f"Cannot retire active revision {rubric_set_id}; activate another "
            "published revision first"
        )

    now = datetime.now(UTC)
    rubric_set.status = "retired"
    rubric_set.retired_at = now
    rubric_set.retired_by = actor_id
    session.flush()
    return rubric_set


def create_draft_from_active(
    session: Session,
    agent_id: str,
    *,
    actor_id: uuid.UUID | None = None,
    is_system: bool = False,
) -> RubricSet:
    """Clone the active published revision into a single editable draft."""
    if actor_id is None and not is_system:
        raise ValueError("actor_id is required for non-system draft creation")

    activation, revisions = lock_activation_and_revisions(session, agent_id, [])
    if activation is None:
        raise LookupError(f"No active rubric revision found for agent '{agent_id}'")

    active_set = next(
        (r for r in revisions if r.rubric_set_id == activation.rubric_set_id), None
    )
    if active_set is None:
        raise LookupError(f"Active rubric set {activation.rubric_set_id} not found")

    if active_set.agent_id != agent_id:
        raise ValueError(
            f"Active rubric set agent mismatch: points to '{active_set.agent_id}', "
            f"expected '{agent_id}'"
        )

    if active_set.status != "published":
        raise ValueError(
            f"Cannot create draft from active revision {active_set.rubric_set_id} "
            f"with status '{active_set.status}'; must be 'published'"
        )

    # Check partial unique index constraint (at most one draft per agent)
    existing_draft = (
        session.query(RubricSet)
        .filter_by(agent_id=agent_id, status="draft")
        .one_or_none()
    )
    if existing_draft is not None:
        raise ValueError(
            f"A draft already exists for agent '{agent_id}' "
            f"({existing_draft.rubric_set_id})"
        )

    active_form_def = get_form_definition_by_id(session, active_set.rubric_set_id)
    if active_form_def is None:
        raise LookupError(
            "Failed to load form definition for active rubric set "
            f"{active_set.rubric_set_id}"
        )
    report = validate_form_definition(active_form_def)
    if not report.is_valid:
        error_msgs = "; ".join(f"{i.path}: {i.message}" for i in report.errors)
        raise ValueError(
            f"Cannot create draft from invalid active revision: {error_msgs}"
        )

    max_ver = (
        session.query(func.max(RubricSet.version_number))
        .filter_by(agent_id=agent_id)
        .scalar()
        or 1
    )

    now = datetime.now(UTC)
    draft_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id=agent_id,
        name=active_set.name,
        version_number=max_ver + 1,
        status="draft",
        adapter_key=active_set.adapter_key,
        adapter_version=active_set.adapter_version,
        created_by=actor_id,
        created_at=now,
    )
    session.add(draft_set)
    session.flush()

    active_domains = (
        session.query(RubricDomain)
        .filter_by(rubric_set_id=active_set.rubric_set_id)
        .order_by(RubricDomain.display_order.asc())
        .all()
    )
    for dom in active_domains:
        new_dom = RubricDomain(
            rubric_domain_id=uuid.uuid4(),
            rubric_set_id=draft_set.rubric_set_id,
            code=dom.code,
            title=dom.title,
            display_order=dom.display_order,
        )
        session.add(new_dom)
        session.flush()

        criteria = (
            session.query(RubricCriterion)
            .filter_by(rubric_domain_id=dom.rubric_domain_id)
            .order_by(RubricCriterion.display_order.asc())
            .all()
        )
        for crit in criteria:
            new_crit = RubricCriterion(
                rubric_criterion_id=uuid.uuid4(),
                rubric_domain_id=new_dom.rubric_domain_id,
                criterion_code=crit.criterion_code,
                title=crit.title,
                description=crit.description,
                scoring_rule=crit.scoring_rule,
                scoring_strategy=crit.scoring_strategy,
                strategy_config=copy.deepcopy(crit.strategy_config),
                display_order=crit.display_order,
            )
            session.add(new_crit)

    session.flush()
    return draft_set


def publish_draft_revision(
    session: Session,
    rubric_set_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    is_system: bool = False,
    activate: bool = False,
) -> tuple[RubricSet, RubricAgentActivation | None]:
    """Validate, lock, and publish a draft revision."""
    if actor_id is None and not is_system:
        raise ValueError("actor_id is required for non-system publication")

    if activate:
        target_info = (
            session.query(RubricSet.agent_id, RubricSet.status)
            .filter_by(rubric_set_id=rubric_set_id)
            .one_or_none()
        )
        if target_info is None:
            raise LookupError(f"Rubric set {rubric_set_id} not found")
        if target_info.status != "draft":
            raise ValueError(
                f"Cannot publish non-draft rubric set {rubric_set_id}; "
                f"status is '{target_info.status}'"
            )

        activation, revisions = lock_activation_and_revisions(
            session, target_info.agent_id, [rubric_set_id]
        )
        locked_set = next(
            (r for r in revisions if r.rubric_set_id == rubric_set_id), None
        )
        if locked_set is None:
            raise LookupError(f"Rubric set {rubric_set_id} not found")
        if locked_set.status != "draft":
            raise ValueError(
                f"Cannot publish non-draft rubric set {rubric_set_id}; "
                f"status is '{locked_set.status}'"
            )

        if activation is None and not is_system:
            raise ValueError(
                "Cannot activate: no existing activation pointer found for "
                f"agent '{locked_set.agent_id}'"
            )
    else:
        locked_set = lock_draft_rubric_set(session, rubric_set_id)
        activation = None

    form_def = get_form_definition_by_id(session, locked_set.rubric_set_id)
    if form_def is None:
        raise LookupError(
            f"Failed to load form definition for {locked_set.rubric_set_id}"
        )

    report = validate_form_definition(form_def)
    if not report.is_valid:
        error_msgs = "; ".join(f"{i.path}: {i.message}" for i in report.errors)
        raise RubricValidationError(
            f"Draft validation failed against manifest: {error_msgs}",
            report=report,
        )

    now = datetime.now(UTC)
    locked_set.status = "published"
    locked_set.published_at = now
    locked_set.published_by = actor_id
    session.flush()

    if activate:
        if activation is None:
            activation = RubricAgentActivation(
                agent_id=locked_set.agent_id,
                rubric_set_id=locked_set.rubric_set_id,
                updated_by=actor_id,
                updated_at=now,
            )
            session.add(activation)
        else:
            activation.rubric_set_id = locked_set.rubric_set_id
            activation.updated_by = actor_id
            activation.updated_at = now
        session.flush()

    return locked_set, activation


def delete_draft_revision(session: Session, rubric_set_id: uuid.UUID) -> None:
    """Delete a draft revision and its child domains and criteria."""
    locked_set = lock_draft_rubric_set(session, rubric_set_id)

    domains = (
        session.query(RubricDomain)
        .filter_by(rubric_set_id=locked_set.rubric_set_id)
        .all()
    )
    for dom in domains:
        session.query(RubricCriterion).filter_by(
            rubric_domain_id=dom.rubric_domain_id
        ).delete()
    session.query(RubricDomain).filter_by(
        rubric_set_id=locked_set.rubric_set_id
    ).delete()
    session.query(RubricSet).filter_by(rubric_set_id=locked_set.rubric_set_id).delete()
    session.flush()


def lock_and_load_requested_active_forms(
    session: Session, agent_rubric_bindings: Mapping[str, uuid.UUID]
) -> dict[str, FormDefinition]:
    """Lock activation and revision rows in deterministic order.

    Locks:
    1. ALL activation rows in canonical agent_id alphabetical order (`agent_id ASC`)
    2. ALL affected RubricSet rows in global `rubric_set_id ASC` order

    Verifies:
    - Bounded, unique, supported agent IDs
    - Each requested revision equals the current active revision for that agent
    - Same-agent target check
    - Published status on all locked revisions
    - Exact FormDefinition manifest/budget validation

    Executes bounded bulk queries for domains and criteria, does NOT commit or flush,
    and returns FormDefinitions keyed by agent_id in requested order.
    """
    if agent_rubric_bindings is None or not isinstance(agent_rubric_bindings, Mapping):
        raise ValueError(
            "agent_rubric_bindings must be a mapping of agent_id to rubric_set_id"
        )

    if not agent_rubric_bindings:
        raise ValueError("agent_rubric_bindings cannot be empty")

    for agent_id, rubric_set_id in agent_rubric_bindings.items():
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("agent_rubric_bindings contains invalid empty agent ID")
        if len(agent_id) > MAX_CODE_LENGTH:
            raise ValueError(
                "agent_rubric_bindings contains agent ID exceeding maximum code length"
            )
        try:
            get_agent_manifest(agent_id)
        except ValueError as exc:
            raise ValueError("Unknown agent ID in agent_rubric_bindings") from exc
        if not isinstance(rubric_set_id, uuid.UUID):
            raise ValueError(
                f"rubric_set_id for agent '{agent_id}' must be a valid UUID"
            )

    sorted_agents = sorted(agent_rubric_bindings.keys())

    # 1. Lock ALL activation rows in canonical agent_id order first
    activations = (
        session.query(RubricAgentActivation)
        .filter(RubricAgentActivation.agent_id.in_(sorted_agents))
        .order_by(RubricAgentActivation.agent_id.asc())
        .with_for_update()
        .all()
    )

    found_agents = {act.agent_id for act in activations}
    if set(sorted_agents) != found_agents:
        raise LookupError("Missing active published rubric set for requested agents")

    act_map = {act.agent_id: act for act in activations}
    for agent_id in sorted_agents:
        expected_set_id = agent_rubric_bindings[agent_id]
        act = act_map[agent_id]
        if act.rubric_set_id != expected_set_id:
            raise ValueError(
                f"Requested revision {expected_set_id} for agent '{agent_id}' "
                f"is not the current active revision ({act.rubric_set_id})"
            )

    # 2. Lock ALL affected RubricSet rows in global rubric_set_id order
    sorted_set_ids = sorted({agent_rubric_bindings[aid] for aid in sorted_agents})
    rubric_sets = (
        session.query(RubricSet)
        .filter(RubricSet.rubric_set_id.in_(sorted_set_ids))
        .order_by(RubricSet.rubric_set_id.asc())
        .with_for_update()
        .all()
    )

    found_set_ids = {r.rubric_set_id for r in rubric_sets}
    if set(sorted_set_ids) != found_set_ids:
        raise LookupError("One or more requested rubric sets not found")

    set_map = {r.rubric_set_id: r for r in rubric_sets}
    for agent_id in sorted_agents:
        req_set_id = agent_rubric_bindings[agent_id]
        r_set = set_map[req_set_id]
        if r_set.agent_id != agent_id:
            raise ValueError(
                f"Agent mismatch: revision {req_set_id} belongs to "
                f"'{r_set.agent_id}', expected '{agent_id}'"
            )
        if r_set.status != "published":
            raise ValueError(
                f"Active revision {req_set_id} for agent '{agent_id}' "
                f"has invalid status '{r_set.status}'; must be 'published'"
            )

    # 3. Bounded bulk queries for domains and criteria across all sets
    domains = (
        session.query(RubricDomain)
        .filter(RubricDomain.rubric_set_id.in_(sorted_set_ids))
        .order_by(RubricDomain.display_order.asc(), RubricDomain.code.asc())
        .all()
    )

    domains_by_set: dict[uuid.UUID, list[RubricDomain]] = {
        rid: [] for rid in sorted_set_ids
    }
    domain_to_set: dict[uuid.UUID, uuid.UUID] = {}
    for dom in domains:
        domains_by_set[dom.rubric_set_id].append(dom)
        domain_to_set[dom.rubric_domain_id] = dom.rubric_set_id

    criteria = (
        session.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id.in_(sorted_set_ids))
        .order_by(
            RubricCriterion.display_order.asc(),
            RubricCriterion.criterion_code.asc(),
        )
        .all()
    )

    criteria_by_set: dict[uuid.UUID, list[RubricCriterion]] = {
        rid: [] for rid in sorted_set_ids
    }
    for crit in criteria:
        set_id = domain_to_set.get(crit.rubric_domain_id)
        if set_id is not None:
            criteria_by_set[set_id].append(crit)

    # Convert to FormDefinition and revalidate with deployed budget
    result: dict[str, FormDefinition] = {}
    for agent_id in agent_rubric_bindings.keys():
        req_set_id = agent_rubric_bindings[agent_id]
        r_set = set_map[req_set_id]
        form_def = orm_to_form_definition(
            r_set,
            domains_by_set.get(req_set_id, []),
            criteria_by_set.get(req_set_id, []),
        )
        report = validate_form_definition(form_def)
        if not report.is_valid:
            error_msgs = "; ".join(f"{i.path}: {i.message}" for i in report.errors)
            raise ValueError(
                f"Active form definition for agent '{agent_id}' failed "
                f"capability manifest validation: {error_msgs}"
            )
        result[agent_id] = form_def

    return result


__all__ = [
    "activate_revision",
    "create_draft_from_active",
    "delete_draft_revision",
    "get_active_form_definition",
    "get_form_definition_by_id",
    "load_active_form_definitions",
    "lock_activation_and_revisions",
    "lock_and_load_requested_active_forms",
    "lock_draft_rubric_set",
    "orm_to_form_definition",
    "publish_draft_revision",
    "retire_revision",
    "validate_form_definition",
]
