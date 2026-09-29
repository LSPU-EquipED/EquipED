"""Publish, swap and unpublish the adapter an agent uses for main scoring."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from server.modules.training_data.exceptions import (
    AdapterAgentMismatchError,
    AdapterNotFoundError,
)
from server.modules.training_data.models import (
    AgentAdapterPublication,
    TrainedAdapter,
)
from sqlalchemy.orm import Session


def get_publication(session: Session, agent_id: str) -> AgentAdapterPublication | None:
    return session.get(AgentAdapterPublication, agent_id)


def publish_adapter(
    session: Session,
    agent_id: str,
    adapter_id: uuid.UUID,
    *,
    published_by: uuid.UUID,
) -> AgentAdapterPublication:
    """Upsert the agent's publication row (atomic swap)."""
    adapter = session.get(TrainedAdapter, adapter_id)
    if adapter is None:
        raise AdapterNotFoundError("adapter not found")
    if adapter.agent_id != agent_id:
        raise AdapterAgentMismatchError("adapter belongs to a different agent")
    row = session.get(AgentAdapterPublication, agent_id)
    if row is None:
        row = AgentAdapterPublication(
            agent_id=agent_id, adapter_id=adapter_id, published_by=published_by
        )
        session.add(row)
    else:
        row.adapter_id = adapter_id
        row.published_by = published_by
        row.published_at = datetime.now(UTC)
    session.commit()
    return row


def unpublish_adapter(session: Session, agent_id: str) -> bool:
    row = session.get(AgentAdapterPublication, agent_id)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True
