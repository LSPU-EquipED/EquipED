"""Seed rubric tables from JSON with dynamic CID strategy configs.

Usage:
    python -m server.scripts.seed_rubrics --input server/data/rubrics/rubrics.json

Initial-seed and bootstrap tooling only. Refuses destructive overwrites of
published or retired admin revisions.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from server.core.database import get_session_factory
from server.modules.agents.coordinator.scoring_rules import COORDINATOR_SCORING_RULES
from server.modules.rubrics.contracts import (
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    canonicalize_form,
)
from server.modules.rubrics.manifests import (
    COORDINATOR_MANIFEST_V1,
    GAD_MANIFEST_V1,
    ITSO_MANIFEST_V1,
    SME_MANIFEST_V1,
    AgentCapabilityManifest,
)
from server.modules.rubrics.models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.modules.rubrics.repository import (
    activate_revision,
    get_form_definition_by_id,
    validate_form_definition,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "server" / "data" / "rubrics" / "rubrics.json"

MANIFEST_BY_AGENT: dict[str, AgentCapabilityManifest] = {
    "sme": SME_MANIFEST_V1,
    "gad": GAD_MANIFEST_V1,
    "itso": ITSO_MANIFEST_V1,
    "coordinator": COORDINATOR_MANIFEST_V1,
}

# Frozen default strategy configurations matching contracts
SME_STRATEGY_CONFIGS: dict[str, dict[str, Any]] = {
    "OP-01": {
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
    "OP-02": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 4,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "OP-03": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "OP-04": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "OP-05": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 3,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-01": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "A-02": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 5,
        "threshold_3": 3,
        "threshold_2": 2,
    },
    "A-03": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 4,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-04": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 3,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-05": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
}

# Coordinator v3 mirrors SME's per-criterion count/ratio configs for the nine
# shared OP/A criteria; A-05 is the grounded curriculum_alignment strategy.
_COORDINATOR_STRATEGY_CONFIGS: dict[str, dict[str, Any]] = {
    "OP-01": {
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
    "OP-02": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 4,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "OP-03": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "OP-04": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "OP-05": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 3,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-01": {
        "strategy": "ratio_band",
        "mode": "coverage_percentage",
        "threshold_4": 80.0,
        "threshold_3": 50.0,
        "threshold_2": 20.0,
    },
    "A-02": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 5,
        "threshold_3": 3,
        "threshold_2": 2,
    },
    "A-03": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 4,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-04": {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 3,
        "threshold_3": 2,
        "threshold_2": 1,
    },
    "A-05": {"strategy": "curriculum_alignment"},
}

GAD_STRATEGY_CONFIGS: dict[str, dict[str, Any]] = {
    "GAD-01": {
        "strategy": "count_band",
        "mode": "maximum_count",
        "threshold_4": 0,
        "threshold_3": 1,
        "threshold_2": 3,
    },
    "GAD-02": {
        "strategy": "ratio_band",
        "mode": "absolute_difference",
        "threshold_4": 2.0,
        "threshold_3": 5.0,
        "threshold_2": 10.0,
    },
    "GAD-03": {
        "strategy": "count_band",
        "mode": "maximum_count",
        "threshold_4": 0,
        "threshold_3": 2,
        "threshold_2": 5,
    },
    "GAD-04": {
        "strategy": "count_band",
        "mode": "maximum_count",
        "threshold_4": 0,
        "threshold_3": 2,
        "threshold_2": 5,
    },
    "GAD-05": {
        "strategy": "count_band",
        "mode": "maximum_count",
        "threshold_4": 0,
        "threshold_3": 2,
        "threshold_2": 5,
    },
}


def _resolve_criterion_strategy(
    agent_id: str,
    criterion_code: str,
    description: str,
    criterion_data: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve and validate scoring_strategy and strategy_config for a criterion."""
    has_strat = "scoring_strategy" in criterion_data
    has_cfg = "strategy_config" in criterion_data
    if has_strat != has_cfg:
        raise ValueError(
            f"Criterion {criterion_code} must provide both scoring_strategy "
            "and strategy_config or neither"
        )

    if has_strat and has_cfg:
        strat = criterion_data["scoring_strategy"]
        cfg = criterion_data["strategy_config"]
        if not isinstance(strat, str) or not strat.strip():
            raise ValueError(
                f"Criterion {criterion_code} scoring_strategy must be non-empty string"
            )
        if not isinstance(cfg, dict):
            raise ValueError(f"Criterion {criterion_code} strategy_config must be dict")
        if cfg.get("strategy") != strat:
            raise ValueError(
                f"Criterion {criterion_code} scoring_strategy '{strat}' does not match "
                f"strategy_config.strategy '{cfg.get('strategy')}'"
            )
        return strat, cfg

    if agent_id == "sme":
        cfg = SME_STRATEGY_CONFIGS.get(criterion_code)
        if cfg:
            return cfg["strategy"], cfg
    elif agent_id == "gad":
        cfg = GAD_STRATEGY_CONFIGS.get(criterion_code)
        if cfg:
            return cfg["strategy"], cfg
    elif agent_id == "itso":
        guidance = description or criterion_code
        cfg = {"strategy": "llm_rubric_guidance", "guidance": guidance}
        return "llm_rubric_guidance", cfg
    elif agent_id == "coordinator":
        cfg = _COORDINATOR_STRATEGY_CONFIGS.get(criterion_code)
        if cfg:
            return cfg["strategy"], cfg

    return None, None


RUBRIC_SET_ALLOWED_KEYS = {
    "agent_id",
    "name",
    "version_number",
    "status",
    "description",
    "domains",
    "adapter_key",
    "adapter_version",
}
RUBRIC_SET_REQUIRED_KEYS = {"agent_id", "name", "version_number", "domains"}

DOMAIN_ALLOWED_KEYS = {"code", "title", "display_order", "criteria"}
DOMAIN_REQUIRED_KEYS = {"code", "title", "display_order", "criteria"}

CRITERION_ALLOWED_KEYS = {
    "criterion_code",
    "title",
    "description",
    "scoring_rule",
    "display_order",
    "scoring_strategy",
    "strategy_config",
}
CRITERION_REQUIRED_KEYS = {"criterion_code", "title", "description", "display_order"}

ALLOWED_STATUSES = {"active", "draft", "published", "retired"}


def _prevalidate_seed_payload(rubric_set_data: Any) -> None:
    """Strictly validate the raw seed JSON structure, types, and allowed keys."""
    if not isinstance(rubric_set_data, dict):
        raise ValueError("Rubric set payload must be a dict")

    unknown_keys = set(rubric_set_data.keys()) - RUBRIC_SET_ALLOWED_KEYS
    if unknown_keys:
        raise ValueError(
            f"Unknown fields in rubric set payload: {sorted(unknown_keys)}"
        )

    missing_keys = RUBRIC_SET_REQUIRED_KEYS - set(rubric_set_data.keys())
    if missing_keys:
        raise ValueError(
            f"Missing required fields in rubric set payload: {sorted(missing_keys)}"
        )

    agent_id = rubric_set_data["agent_id"]
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise ValueError("Rubric set 'agent_id' must be a non-empty string")

    name = rubric_set_data["name"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Rubric set 'name' must be a non-empty string")

    version_number = rubric_set_data["version_number"]
    if isinstance(version_number, bool) or not isinstance(version_number, int):
        raise ValueError("Rubric set 'version_number' must be an integer")
    if version_number <= 0:
        raise ValueError(f"Invalid version_number '{version_number}'")

    if "status" in rubric_set_data:
        status = rubric_set_data["status"]
        if not isinstance(status, str) or status not in ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'; must be one of {sorted(ALLOWED_STATUSES)}"
            )

    if "adapter_key" in rubric_set_data:
        adapter_key = rubric_set_data["adapter_key"]
        if not isinstance(adapter_key, str) or not adapter_key.strip():
            raise ValueError("Rubric set 'adapter_key' must be a non-empty string")

    if "adapter_version" in rubric_set_data:
        adapter_version = rubric_set_data["adapter_version"]
        if isinstance(adapter_version, bool) or not isinstance(adapter_version, int):
            raise ValueError("Rubric set 'adapter_version' must be an integer")
        if adapter_version <= 0:
            raise ValueError("Rubric set 'adapter_version' must be positive")

    domains = rubric_set_data["domains"]
    if not isinstance(domains, list) or not domains:
        raise ValueError("Rubric set 'domains' must be a non-empty list")

    for d_idx, dom_data in enumerate(domains):
        if not isinstance(dom_data, dict):
            raise ValueError(f"Domain at index {d_idx} must be a dict")

        dom_unknown = set(dom_data.keys()) - DOMAIN_ALLOWED_KEYS
        if dom_unknown:
            raise ValueError(
                f"Unknown fields in domain at index {d_idx}: {sorted(dom_unknown)}"
            )

        dom_missing = DOMAIN_REQUIRED_KEYS - set(dom_data.keys())
        if dom_missing:
            raise ValueError(
                f"Missing required fields in domain at index {d_idx}: "
                f"{sorted(dom_missing)}"
            )

        code = dom_data["code"]
        if not isinstance(code, str) or not code.strip():
            raise ValueError(f"Domain at index {d_idx} 'code' must be non-empty string")

        title = dom_data["title"]
        if not isinstance(title, str) or not title.strip():
            raise ValueError(
                f"Domain at index {d_idx} 'title' must be non-empty string"
            )

        order = dom_data["display_order"]
        if isinstance(order, bool) or not isinstance(order, int) or order < 0:
            raise ValueError(
                f"Domain at index {d_idx} 'display_order' must be a non-negative int"
            )

        criteria = dom_data["criteria"]
        if not isinstance(criteria, list) or not criteria:
            raise ValueError(f"Domain '{code}' 'criteria' must be a non-empty list")

        for c_idx, crit_data in enumerate(criteria):
            if not isinstance(crit_data, dict):
                raise ValueError(
                    f"Criterion at index {c_idx} in domain '{code}' must be a dict"
                )

            crit_unknown = set(crit_data.keys()) - CRITERION_ALLOWED_KEYS
            if crit_unknown:
                raise ValueError(
                    f"Unknown fields in criterion at index {c_idx} in domain '{code}': "
                    f"{sorted(crit_unknown)}"
                )

            crit_missing = CRITERION_REQUIRED_KEYS - set(crit_data.keys())
            if crit_missing:
                raise ValueError(
                    f"Missing required fields in criterion at index {c_idx} in "
                    f"domain '{code}': {sorted(crit_missing)}"
                )

            c_code = crit_data["criterion_code"]
            if not isinstance(c_code, str) or not c_code.strip():
                raise ValueError(
                    f"Criterion at index {c_idx} in domain '{code}' 'criterion_code' "
                    "must be non-empty string"
                )

            c_title = crit_data["title"]
            if not isinstance(c_title, str) or not c_title.strip():
                raise ValueError(
                    f"Criterion '{c_code}' 'title' must be non-empty string"
                )

            c_desc = crit_data["description"]
            if not isinstance(c_desc, str) or not c_desc.strip():
                raise ValueError(
                    f"Criterion '{c_code}' 'description' must be non-empty string"
                )

            c_order = crit_data["display_order"]
            if isinstance(c_order, bool) or not isinstance(c_order, int) or c_order < 0:
                raise ValueError(
                    f"Criterion '{c_code}' 'display_order' must be non-negative int"
                )

            if "scoring_rule" in crit_data and crit_data["scoring_rule"] is not None:
                if not isinstance(crit_data["scoring_rule"], str):
                    raise ValueError(
                        f"Criterion '{c_code}' 'scoring_rule' must be a string"
                    )


def _build_in_memory_form_definition(
    rubric_set_data: dict[str, Any],
) -> FormDefinition:
    """Build a FormDefinition from raw JSON dictionary with synthetic UUIDs."""
    agent_id = str(rubric_set_data.get("agent_id", ""))
    version_number = int(rubric_set_data.get("version_number", 0))
    name = str(rubric_set_data.get("name", ""))
    adapter_key = str(rubric_set_data.get("adapter_key", agent_id))
    adapter_version = int(rubric_set_data.get("adapter_version", 1))

    domain_defs: list[DomainDefinition] = []
    for dom_data in rubric_set_data.get("domains", []):
        crit_defs: list[CriterionDefinition] = []
        for crit_data in dom_data.get("criteria", []):
            code = str(crit_data.get("criterion_code", ""))
            desc = str(crit_data.get("description", ""))
            strat, cfg = _resolve_criterion_strategy(agent_id, code, desc, crit_data)
            if strat is None or cfg is None:
                if agent_id == "coordinator" and version_number == 1:
                    cfg = {
                        "strategy": "llm_rubric_guidance",
                        "guidance": desc or code,
                    }
                else:
                    raise ValueError(
                        f"Criterion {code} missing strategy/config and "
                        "cannot be resolved"
                    )
            crit_def = CriterionDefinition(
                rubric_criterion_id=uuid.uuid4(),
                criterion_code=code,
                title=str(crit_data.get("title", "")),
                description=desc,
                scoring_rule=crit_data.get("scoring_rule"),
                display_order=int(crit_data.get("display_order", 0)),
                strategy_config=cfg,
            )
            crit_defs.append(crit_def)

        domain_def = DomainDefinition(
            rubric_domain_id=uuid.uuid4(),
            code=str(dom_data.get("code", "")),
            title=str(dom_data.get("title", "")),
            display_order=int(dom_data.get("display_order", 0)),
            criteria=tuple(crit_defs),
        )
        domain_defs.append(domain_def)

    raw_form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id=agent_id,
        name=name,
        version_number=version_number,
        adapter_key=adapter_key,
        adapter_version=adapter_version,
        domains=tuple(domain_defs),
    )
    return canonicalize_form(raw_form)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed rubric tables from JSON.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    rubric_sets = payload.get("rubric_sets", [])
    if not isinstance(rubric_sets, list):
        raise SystemExit("Invalid JSON: rubric_sets must be a list")

    session = get_session_factory()()
    try:
        for rubric_set_data in rubric_sets:
            seed_rubric_set(session, rubric_set_data)
        seed_coordinator_v3_if_needed(session)
        session.commit()
    finally:
        session.close()

    print(f"Seeded rubric sets from {args.input}")
    return 0


def seed_rubric_set(session: Any, rubric_set_data: dict[str, Any]) -> RubricSet:
    _prevalidate_seed_payload(rubric_set_data)

    agent_id = str(rubric_set_data["agent_id"])
    version_number = int(rubric_set_data["version_number"])

    raw_status = str(rubric_set_data.get("status", "draft"))
    # Normalize legacy active to published
    if raw_status == "active":
        status = "published"
    else:
        status = raw_status

    # Coordinator v1 is retired legacy metadata
    if agent_id == "coordinator" and version_number == 1:
        status = "retired"

    # Pre-validate payload strictly against FormDefinition contracts and budget
    # BEFORE any DB mutation. Exempt only legacy Coordinator v1 from manifest.
    in_memory_form = _build_in_memory_form_definition(rubric_set_data)
    if not (agent_id == "coordinator" and version_number == 1):
        report = validate_form_definition(in_memory_form)
        if not report.is_valid:
            error_msgs = "; ".join(f"{i.path}: {i.message}" for i in report.errors)
            raise ValueError(f"Seeded form failed manifest validation: {error_msgs}")

    existing = (
        session.query(RubricSet)
        .filter_by(agent_id=agent_id, version_number=version_number)
        .one_or_none()
    )
    if existing is not None:
        raise RuntimeError(
            f"Refusing to delete/overwrite {existing.status} rubric set "
            f"for agent '{agent_id}' version {version_number}"
        )

    now = datetime.now(UTC)
    published_at = now if status == "published" else None
    retired_at = now if status == "retired" else None

    rubric_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id=agent_id,
        name=str(rubric_set_data["name"]),
        version_number=version_number,
        status=status,
        adapter_key=str(rubric_set_data.get("adapter_key", agent_id)),
        adapter_version=int(rubric_set_data.get("adapter_version", 1)),
        published_at=published_at,
        published_by=None,
        created_by=None,
        retired_at=retired_at,
        retired_by=None,
        created_at=now,
    )
    session.add(rubric_set)
    session.flush()

    for domain_data in rubric_set_data.get("domains", []):
        seed_domain(session, rubric_set.rubric_set_id, agent_id, domain_data)

    if status == "published":
        activate_revision(
            session,
            agent_id,
            rubric_set.rubric_set_id,
            actor_id=None,
            is_system=True,
        )

    session.flush()
    return rubric_set


def seed_domain(
    session: Any,
    rubric_set_id: uuid.UUID,
    agent_id: str,
    domain_data: dict[str, Any],
) -> RubricDomain:
    domain = RubricDomain(
        rubric_domain_id=uuid.uuid4(),
        rubric_set_id=rubric_set_id,
        code=str(domain_data["code"]),
        title=str(domain_data["title"]),
        display_order=int(domain_data["display_order"]),
    )
    session.add(domain)
    session.flush()

    for criterion_data in domain_data.get("criteria", []):
        code = str(criterion_data["criterion_code"])
        desc = str(criterion_data["description"])
        strat, cfg = _resolve_criterion_strategy(agent_id, code, desc, criterion_data)

        criterion = RubricCriterion(
            rubric_criterion_id=uuid.uuid4(),
            rubric_domain_id=domain.rubric_domain_id,
            criterion_code=code,
            title=str(criterion_data["title"]),
            description=desc,
            scoring_rule=criterion_data.get("scoring_rule"),
            scoring_strategy=strat,
            strategy_config=cfg,
            display_order=int(criterion_data["display_order"]),
        )
        session.add(criterion)

    session.flush()
    return domain


# Canonical Coordinator Rubric v3 form: OP domain then A domain, five criteria
# each. Titles/descriptions mirror the retired coordinator v1 metadata, except
# A-05 which becomes the grounded curriculum-alignment criterion.
_COORDINATOR_V3_DOMAINS: list[dict[str, Any]] = [
    {
        "code": "OP",
        "title": "Organization & Presentation",
        "display_order": 1,
        "criteria": [
            {
                "criterion_code": "OP-01",
                "title": "Topic Coherence",
                "description": "Topics are coherent from Unit to Chapter.",
                "display_order": 1,
            },
            {
                "criterion_code": "OP-02",
                "title": "Interactivity",
                "description": (
                    "Material is interactive in each lesson which makes "
                    "life-long learning easier."
                ),
                "display_order": 2,
            },
            {
                "criterion_code": "OP-03",
                "title": "Clear Directions",
                "description": (
                    "Directions are clear and complete enough for students "
                    "to perform required tasks."
                ),
                "display_order": 3,
            },
            {
                "criterion_code": "OP-04",
                "title": "Accurate Sections",
                "description": (
                    "Paragraphs and sections have clear and accurate "
                    "information."
                ),
                "display_order": 4,
            },
            {
                "criterion_code": "OP-05",
                "title": "Enhancement Activities",
                "description": "Enhancement activities for students are provided.",
                "display_order": 5,
            },
        ],
    },
    {
        "code": "A",
        "title": "Assessment",
        "display_order": 2,
        "criteria": [
            {
                "criterion_code": "A-01",
                "title": "Learner Transformation",
                "description": "Students are engaged in transforming what they learn.",
                "display_order": 1,
            },
            {
                "criterion_code": "A-02",
                "title": "Varied Assessment Tools",
                "description": (
                    "Teachers can easily assess students' progress by using "
                    "varied assessment tools."
                ),
                "display_order": 2,
            },
            {
                "criterion_code": "A-03",
                "title": "Progress Monitoring",
                "description": (
                    "The material keeps an on-going record of students' "
                    "progress and allows the teacher to monitor student "
                    "performance."
                ),
                "display_order": 3,
            },
            {
                "criterion_code": "A-04",
                "title": "Prescriptive Feedback",
                "description": (
                    "Positive, meaningful feedback, and prescriptive guides "
                    "for interventions are provided."
                ),
                "display_order": 4,
            },
            {
                "criterion_code": "A-05",
                "title": "Curriculum Alignment",
                "description": (
                    "Evaluate alignment between the student learning "
                    "material's stated objectives and the confirmed course "
                    "curriculum/syllabus topics."
                ),
                "display_order": 5,
            },
        ],
    },
]


def _validate_coordinator_revision(session: Any, rubric_set_id: uuid.UUID) -> None:
    """Load and manifest-validate a persisted coordinator revision, or raise."""
    form_def = get_form_definition_by_id(session, rubric_set_id)
    if form_def is None:
        raise LookupError(f"Failed to load form definition for {rubric_set_id}")
    report = validate_form_definition(form_def)
    if not report.is_valid:
        error_msgs = "; ".join(f"{i.path}: {i.message}" for i in report.errors)
        raise ValueError(
            f"Coordinator revision {rubric_set_id} failed manifest "
            f"validation: {error_msgs}"
        )


def build_coordinator_v3_rubric_set(
    session: Any,
    *,
    version_number: int,
    name: str,
    status: str = "published",
) -> RubricSet:
    """Persist a published Coordinator rubric set with the canonical 10 criteria.

    Shared by the v3 seed create-path and by tests that need a second valid
    Coordinator revision. Does not touch activation.
    """
    now = datetime.now(UTC)
    rubric_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="coordinator",
        name=name,
        version_number=version_number,
        status=status,
        adapter_key="coordinator",
        adapter_version=2,
        published_at=now if status == "published" else None,
        published_by=None,
        created_by=None,
        created_at=now,
    )
    session.add(rubric_set)
    session.flush()

    for domain_spec in _COORDINATOR_V3_DOMAINS:
        domain = RubricDomain(
            rubric_domain_id=uuid.uuid4(),
            rubric_set_id=rubric_set.rubric_set_id,
            code=str(domain_spec["code"]),
            title=str(domain_spec["title"]),
            display_order=int(domain_spec["display_order"]),
        )
        session.add(domain)
        session.flush()

        for crit_spec in domain_spec["criteria"]:
            code = str(crit_spec["criterion_code"])
            desc = str(crit_spec["description"])
            strat, cfg = _resolve_criterion_strategy("coordinator", code, desc, {})
            if strat is None or cfg is None:
                raise ValueError(
                    f"Coordinator criterion {code} could not resolve a "
                    "scoring strategy"
                )
            session.add(
                RubricCriterion(
                    rubric_criterion_id=uuid.uuid4(),
                    rubric_domain_id=domain.rubric_domain_id,
                    criterion_code=code,
                    title=str(crit_spec["title"]),
                    description=desc,
                    scoring_rule=COORDINATOR_SCORING_RULES.get(code),
                    scoring_strategy=strat,
                    strategy_config=cfg,
                    display_order=int(crit_spec["display_order"]),
                )
            )
        session.flush()

    return rubric_set


def seed_coordinator_v3_if_needed(session: Any) -> RubricSet | None:
    """Create and activate Coordinator Revision 3 (10 criteria) if not present."""
    existing_v3 = (
        session.query(RubricSet)
        .filter_by(agent_id="coordinator", version_number=3)
        .one_or_none()
    )
    if existing_v3 is not None:
        if existing_v3.status != "published":
            raise ValueError(
                f"Existing Coordinator v3 has invalid status "
                f"'{existing_v3.status}'; must be 'published'"
            )
        _validate_coordinator_revision(session, existing_v3.rubric_set_id)

        activation = (
            session.query(RubricAgentActivation)
            .filter_by(agent_id="coordinator")
            .one_or_none()
        )
        if activation is None:
            activate_revision(
                session,
                "coordinator",
                existing_v3.rubric_set_id,
                actor_id=None,
                is_system=True,
            )
            session.flush()
        elif activation.rubric_set_id == existing_v3.rubric_set_id:
            pass
        else:
            active_target = (
                session.query(RubricSet)
                .filter_by(rubric_set_id=activation.rubric_set_id)
                .one_or_none()
            )
            if active_target is None:
                raise ValueError(
                    "Coordinator activation points to non-existent rubric set "
                    f"{activation.rubric_set_id}"
                )
            if active_target.agent_id != "coordinator":
                raise ValueError(
                    "Coordinator activation points to rubric set for agent "
                    f"'{active_target.agent_id}'"
                )
            if active_target.status != "published":
                raise ValueError(
                    f"Coordinator activation points to revision "
                    f"{active_target.rubric_set_id} with invalid status "
                    f"'{active_target.status}'"
                )
            _validate_coordinator_revision(session, active_target.rubric_set_id)
            # preserve admin choice, do not override
        return existing_v3

    v3_set = build_coordinator_v3_rubric_set(
        session,
        version_number=3,
        name="Coordinator Rubric v3",
    )
    _validate_coordinator_revision(session, v3_set.rubric_set_id)

    activate_revision(
        session,
        "coordinator",
        v3_set.rubric_set_id,
        actor_id=None,
        is_system=True,
    )

    session.flush()
    return v3_set


if __name__ == "__main__":
    raise SystemExit(main())
