from __future__ import annotations

import uuid

import pytest
from server.modules.training_data.exceptions import (
    AdapterAgentMismatchError,
    AdapterNotFoundError,
)
from server.modules.training_data.publication import (
    get_publication,
    publish_adapter,
    unpublish_adapter,
)
from server.tests.training_data.conftest import make_adapter


def test_publish_then_swap_then_unpublish(db_session, admin_user):
    v1 = make_adapter(db_session, "sme", 1)
    v2 = make_adapter(db_session, "sme", 2)
    publish_adapter(db_session, "sme", v1.adapter_id, published_by=admin_user.user_id)
    assert get_publication(db_session, "sme").adapter_id == v1.adapter_id
    publish_adapter(db_session, "sme", v2.adapter_id, published_by=admin_user.user_id)
    assert get_publication(db_session, "sme").adapter_id == v2.adapter_id
    assert unpublish_adapter(db_session, "sme") is True
    assert get_publication(db_session, "sme") is None
    assert unpublish_adapter(db_session, "sme") is False


def test_publish_refuses_other_agents_adapter_and_keeps_existing(
    db_session, admin_user
):
    sme1 = make_adapter(db_session, "sme", 1)
    gad1 = make_adapter(db_session, "gad", 1)
    publish_adapter(db_session, "sme", sme1.adapter_id, published_by=admin_user.user_id)
    with pytest.raises(AdapterAgentMismatchError):
        publish_adapter(
            db_session, "sme", gad1.adapter_id, published_by=admin_user.user_id
        )
    assert get_publication(db_session, "sme").adapter_id == sme1.adapter_id


def test_publish_unknown_adapter(db_session, admin_user):
    with pytest.raises(AdapterNotFoundError):
        publish_adapter(
            db_session, "sme", uuid.uuid4(), published_by=admin_user.user_id
        )
