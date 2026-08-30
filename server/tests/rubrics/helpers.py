"""Shared test-only helpers for seeding and manipulating rubrics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from server.modules.rubrics.models import RubricAgentActivation, RubricSet
from server.scripts.seed_rubrics import seed_coordinator_v2_if_needed, seed_domain

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_JSON = ROOT / "data" / "rubrics" / "rubrics.json"


def seed_all_rubrics(session) -> None:
    """Seed published and active rubric sets from rubrics.json."""
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    for rubric_set_data in payload["rubric_sets"]:
        agent_id = str(rubric_set_data["agent_id"])
        version_number = int(rubric_set_data["version_number"])
        raw_status = str(rubric_set_data.get("status", "draft"))
        status = "published" if raw_status == "active" else raw_status
        if agent_id == "coordinator" and version_number == 1:
            status = "retired"

        now = datetime.now(UTC)
        published_at = now if status == "published" else None
        retired_at = now if status == "retired" else None

        rubric_set = RubricSet(
            rubric_set_id=uuid4(),
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
        session.flush()

        if status == "published":
            activation = (
                session.query(RubricAgentActivation)
                .filter_by(agent_id=agent_id)
                .one_or_none()
            )
            if activation is None:
                session.add(
                    RubricAgentActivation(
                        agent_id=agent_id,
                        rubric_set_id=rubric_set.rubric_set_id,
                        updated_by=None,
                        updated_at=now,
                    )
                )
            else:
                activation.rubric_set_id = rubric_set.rubric_set_id
                activation.updated_at = now

    seed_coordinator_v2_if_needed(session)
    session.flush()


__all__ = [
    "seed_all_rubrics",
]
