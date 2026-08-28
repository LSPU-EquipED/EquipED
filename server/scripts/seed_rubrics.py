"""Seed rubric tables from JSON.

Usage:
    python -m scripts.seed_rubrics --input data/rubrics/rubrics.json

This is initial-seed tooling only. Admins edit criterion / domain *text* in
place through the rubric editor (PATCH /admin/rubrics/...); re-running this
script overwrites those edits with the JSON contents.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from server.core.database import get_session_factory
from server.modules.rubrics.models import RubricCriterion, RubricDomain, RubricSet


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "server" / "data" / "rubrics" / "rubrics.json"


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
        session.commit()
    finally:
        session.close()

    print(f"Seeded {len(rubric_sets)} rubric sets from {args.input}")
    return 0


def seed_rubric_set(session: Any, rubric_set_data: dict[str, Any]) -> None:
    agent_id = str(rubric_set_data["agent_id"])
    version_number = int(rubric_set_data["version_number"])

    existing = (
        session.query(RubricSet)
        .filter_by(agent_id=agent_id, version_number=version_number)
        .one_or_none()
    )
    if existing is not None:
        existing_domains = session.query(RubricDomain).filter_by(rubric_set_id=existing.rubric_set_id).all()
        for domain in existing_domains:
            session.query(RubricCriterion).filter_by(rubric_domain_id=domain.rubric_domain_id).delete()
        session.query(RubricDomain).filter_by(rubric_set_id=existing.rubric_set_id).delete()
        session.query(RubricSet).filter_by(rubric_set_id=existing.rubric_set_id).delete()
        session.flush()

    rubric_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id=agent_id,
        name=str(rubric_set_data["name"]),
        version_number=version_number,
        status=str(rubric_set_data.get("status", "draft")),
    )
    session.add(rubric_set)
    session.flush()

    for domain_data in rubric_set_data.get("domains", []):
        seed_domain(session, rubric_set.rubric_set_id, domain_data)


def seed_domain(session: Any, rubric_set_id: uuid.UUID, domain_data: dict[str, Any]) -> None:
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
        criterion = RubricCriterion(
            rubric_criterion_id=uuid.uuid4(),
            rubric_domain_id=domain.rubric_domain_id,
            criterion_code=str(criterion_data["criterion_code"]),
            title=str(criterion_data["title"]),
            description=str(criterion_data["description"]),
            display_order=int(criterion_data["display_order"]),
        )
        session.add(criterion)


if __name__ == "__main__":
    raise SystemExit(main())
