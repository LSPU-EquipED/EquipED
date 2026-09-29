from __future__ import annotations

import uuid

import pytest
from server.modules.training_data.models import AgentAdapterPublication
from sqlalchemy.exc import IntegrityError


def test_one_publication_row_per_agent(db_session, admin_user):
    from server.tests.training_data.conftest import make_adapter

    first = make_adapter(db_session, "sme", 1)
    second = make_adapter(db_session, "sme", 2)
    db_session.add(
        AgentAdapterPublication(
            agent_id="sme", adapter_id=first.adapter_id, published_by=admin_user.user_id
        )
    )
    db_session.commit()
    db_session.add(
        AgentAdapterPublication(
            agent_id="sme",
            adapter_id=second.adapter_id,
            published_by=admin_user.user_id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert uuid.UUID(str(first.adapter_id))
