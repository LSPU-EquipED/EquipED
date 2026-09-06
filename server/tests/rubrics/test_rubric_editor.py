"""Tests for admin rubric editor: read tree, draft edits, RBAC, 409/422 guards."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from server.modules.rubrics.exceptions import RubricConflictError, RubricNotFoundError
from server.modules.rubrics.models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.modules.rubrics.service import (
    get_rubric_sets_for_editor,
    update_criterion,
    update_domain,
)
from server.tests.rubrics.conftest import _auth
from server.tests.rubrics.test_rubrics import _seed_from_json


def _criterion(
    db_session, agent_id: str, code: str, *, status: str | None = None
) -> RubricCriterion:
    """Fetch one criterion by agent + code (optionally scoped to a set status)."""
    query = (
        db_session.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .join(RubricSet, RubricDomain.rubric_set_id == RubricSet.rubric_set_id)
        .filter(RubricSet.agent_id == agent_id, RubricCriterion.criterion_code == code)
    )
    if status is not None:
        query = query.filter(RubricSet.status == status)
    return query.one()


def _create_draft_tree(
    db_session,
    agent_id: str = "sme",
    *,
    domain_code: str = "DRAFT_DOM",
    criterion_code: str = "DRAFT-01",
) -> tuple[RubricSet, RubricDomain, RubricCriterion]:
    """Create an isolated draft rubric set tree for mutation testing."""
    now = datetime.now(UTC)
    draft_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id=agent_id,
        name=f"{agent_id.upper()} Draft Rubric",
        version_number=99,
        status="draft",
        adapter_key=agent_id,
        adapter_version=1,
        created_at=now,
    )
    db_session.add(draft_set)
    db_session.flush()

    draft_domain = RubricDomain(
        rubric_domain_id=uuid.uuid4(),
        rubric_set_id=draft_set.rubric_set_id,
        code=domain_code,
        title="Draft Domain Title",
        display_order=1,
    )
    db_session.add(draft_domain)
    db_session.flush()

    draft_criterion = RubricCriterion(
        rubric_criterion_id=uuid.uuid4(),
        rubric_domain_id=draft_domain.rubric_domain_id,
        criterion_code=criterion_code,
        title="Draft Criterion Title",
        description="Draft initial description",
        scoring_rule="Draft scoring rule",
        scoring_strategy="count_band",
        strategy_config={
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 4,
            "threshold_3": 2,
            "threshold_2": 1,
        },
        display_order=1,
    )
    db_session.add(draft_criterion)
    db_session.flush()
    db_session.commit()
    return draft_set, draft_domain, draft_criterion


# --- service layer -------------------------------------------------------------


def test_get_rubric_sets_for_editor_returns_nested_active_sets(db_session) -> None:
    _seed_from_json(db_session)

    sets = get_rubric_sets_for_editor(db=db_session)

    by_agent = {s["agent_id"]: s for s in sets}
    assert set(by_agent) == {"sme", "coordinator", "gad", "itso"}
    # Editor presents agents in evaluation order, not alphabetically.
    assert [s["agent_id"] for s in sets] == ["sme", "coordinator", "gad", "itso"]

    sme = by_agent["sme"]
    assert sme["name"] == "SME Rubric v1"
    assert sme["version_number"] == 1
    assert sme["status"] == "published"
    assert [d["code"] for d in sme["domains"]] == ["OP", "A"]

    op = sme["domains"][0]
    assert op["title"] == "Organization & Presentation"
    assert [c["criterion_code"] for c in op["criteria"]] == [
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
    ]
    first = op["criteria"][0]
    assert first["title"] == "Topic Coherence"
    assert first["description"] == "Topics are coherent from Unit to Chapter."
    assert "rubric_criterion_id" in first
    assert "scoring_rule" in first


def test_get_rubric_sets_for_editor_fails_closed_without_activation(
    db_session,
) -> None:
    """When activations are absent, returns [] without guessing published."""
    _seed_from_json(db_session)

    db_session.query(RubricAgentActivation).delete()
    db_session.commit()

    sets = get_rubric_sets_for_editor(db=db_session)
    assert sets == []


def test_get_rubric_sets_for_editor_query_count_bounded(db_session) -> None:
    """Loading rubric sets for editor issues bounded queries (<= 4)."""
    _seed_from_json(db_session)

    from sqlalchemy import event

    query_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    conn = db_session.connection()
    event.listens_for(conn, "before_cursor_execute")(_count_queries)
    try:
        get_rubric_sets_for_editor(db=db_session)
    finally:
        event.remove(conn, "before_cursor_execute", _count_queries)

    assert query_count <= 4, f"expected <= 4 queries, got {query_count}"


def test_update_criterion_persists_description_and_scoring_rule_on_draft(
    db_session,
) -> None:
    _seed_from_json(db_session)
    draft_set, _, draft_criterion = _create_draft_tree(db_session)
    assert draft_set.status == "draft"

    update_criterion(
        db_session,
        draft_criterion.rubric_criterion_id,
        description="Topics flow coherently across chapters.",
        scoring_rule="EDITED: 0 issues -> 4, else lower.",
    )
    db_session.commit()

    refreshed = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=draft_criterion.rubric_criterion_id)
        .one()
    )
    assert refreshed.description == "Topics flow coherently across chapters."
    assert refreshed.scoring_rule == "EDITED: 0 issues -> 4, else lower."
    assert refreshed.criterion_code == "DRAFT-01"
    assert refreshed.title == "Draft Criterion Title"


def test_update_criterion_blank_scoring_rule_clears_to_null_on_draft(
    db_session,
) -> None:
    _seed_from_json(db_session)
    draft_set, _, draft_criterion = _create_draft_tree(db_session)
    assert draft_set.status == "draft"

    update_criterion(
        db_session,
        draft_criterion.rubric_criterion_id,
        description="still here",
        scoring_rule="   ",
    )
    db_session.commit()

    refreshed = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=draft_criterion.rubric_criterion_id)
        .one()
    )
    assert refreshed.scoring_rule is None


def test_update_criterion_on_published_set_raises_rubric_conflict_error(
    db_session,
) -> None:
    _seed_from_json(db_session)
    criterion = _criterion(db_session, "sme", "OP-01")
    old_desc = criterion.description

    with pytest.raises(RubricConflictError):
        update_criterion(
            db_session,
            criterion.rubric_criterion_id,
            description="Mutated description",
            scoring_rule="Mutated rule",
        )
    db_session.rollback()

    refreshed = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=criterion.rubric_criterion_id)
        .one()
    )
    assert refreshed.description == old_desc


def test_update_criterion_on_retired_set_raises_rubric_conflict_error(
    db_session,
) -> None:
    _seed_from_json(db_session)
    # Coordinator v1 is retired
    retired_criterion = _criterion(db_session, "coordinator", "OP-01", status="retired")
    old_desc = retired_criterion.description

    with pytest.raises(RubricConflictError):
        update_criterion(
            db_session,
            retired_criterion.rubric_criterion_id,
            description="Mutated retired description",
            scoring_rule=None,
        )
    db_session.rollback()

    refreshed = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=retired_criterion.rubric_criterion_id)
        .one()
    )
    assert refreshed.description == old_desc


def test_update_criterion_missing_id_raises_lookup_error(db_session) -> None:
    _seed_from_json(db_session)
    with pytest.raises((LookupError, RubricNotFoundError)):
        update_criterion(db_session, uuid.uuid4(), description="y", scoring_rule=None)


def test_update_domain_persists_on_draft(db_session) -> None:
    _seed_from_json(db_session)
    draft_set, draft_domain, _ = _create_draft_tree(db_session)
    assert draft_set.status == "draft"

    update_domain(db_session, draft_domain.rubric_domain_id, title="Organization")
    db_session.commit()

    refreshed = (
        db_session.query(RubricDomain)
        .filter_by(rubric_domain_id=draft_domain.rubric_domain_id)
        .one()
    )
    assert refreshed.title == "Organization"


def test_update_domain_on_published_raises_rubric_conflict_error(
    db_session,
) -> None:
    _seed_from_json(db_session)
    domain = (
        db_session.query(RubricDomain)
        .filter_by(code="OP")
        .filter(RubricDomain.title == "Organization & Presentation")
        .first()
    )
    old_title = domain.title

    with pytest.raises(RubricConflictError):
        update_domain(db_session, domain.rubric_domain_id, title="Mutated Title")
    db_session.rollback()

    refreshed = (
        db_session.query(RubricDomain)
        .filter_by(rubric_domain_id=domain.rubric_domain_id)
        .one()
    )
    assert refreshed.title == old_title


def test_update_domain_on_retired_raises_rubric_conflict_error(
    db_session,
) -> None:
    _seed_from_json(db_session)
    retired_set = (
        db_session.query(RubricSet)
        .filter_by(agent_id="coordinator", version_number=1)
        .one()
    )
    retired_domain = (
        db_session.query(RubricDomain)
        .filter_by(rubric_set_id=retired_set.rubric_set_id)
        .first()
    )
    old_title = retired_domain.title

    with pytest.raises(RubricConflictError):
        update_domain(
            db_session, retired_domain.rubric_domain_id, title="Mutated Retired Title"
        )
    db_session.rollback()

    refreshed = (
        db_session.query(RubricDomain)
        .filter_by(rubric_domain_id=retired_domain.rubric_domain_id)
        .one()
    )
    assert refreshed.title == old_title


# --- router: access control ---------------------------------------------------


def test_rubrics_get_access_control(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)

    response = client.get("/api/v1/admin/rubrics")
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.get("/api/v1/admin/rubrics")
    assert response.status_code == 403

    _auth(client, auth_cookies_admin)
    response = client.get("/api/v1/admin/rubrics")
    assert response.status_code == 200
    agents = {s["agent_id"] for s in response.json()["rubric_sets"]}
    assert agents == {"sme", "coordinator", "gad", "itso"}


def test_rubrics_patch_criterion_access_control(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, _, draft_criterion = _create_draft_tree(db_session)
    criterion_id = str(draft_criterion.rubric_criterion_id)
    payload = {
        "description": "Lessons are interactive.",
        "scoring_rule": "count interactive elements",
    }

    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{criterion_id}", json=payload
    )
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{criterion_id}", json=payload
    )
    assert response.status_code == 403

    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{criterion_id}", json=payload
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Lessons are interactive."


def test_rubrics_patch_domain_access_control(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, draft_domain, _ = _create_draft_tree(db_session)
    domain_id = str(draft_domain.rubric_domain_id)
    payload = {"title": "New Domain Title"}

    response = client.patch(f"/api/v1/admin/rubrics/domains/{domain_id}", json=payload)
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.patch(f"/api/v1/admin/rubrics/domains/{domain_id}", json=payload)
    assert response.status_code == 403

    _auth(client, auth_cookies_admin)
    response = client.patch(f"/api/v1/admin/rubrics/domains/{domain_id}", json=payload)
    assert response.status_code == 200
    assert response.json()["title"] == "New Domain Title"


# --- router: behaviour & 409 immutability ------------------------------------


def test_patch_draft_criterion_success(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, _, draft_criterion = _create_draft_tree(db_session)
    criterion_id = str(draft_criterion.rubric_criterion_id)

    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{criterion_id}",
        json={
            "description": "Topics flow coherently across chapters.",
            "scoring_rule": "NEW RULE: 6+ types -> 4",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Topics flow coherently across chapters."
    assert data["scoring_rule"] == "NEW RULE: 6+ types -> 4"


def test_patch_published_criterion_returns_409_and_leaves_db_unchanged(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    criterion = _criterion(db_session, "sme", "OP-01")
    old_desc = criterion.description
    old_rule = criterion.scoring_rule

    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{criterion.rubric_criterion_id}",
        json={
            "description": "Direct mutation of published definition.",
            "scoring_rule": "Direct mutation rule.",
        },
    )
    assert response.status_code == 409

    refreshed = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=criterion.rubric_criterion_id)
        .one()
    )
    assert refreshed.description == old_desc
    assert refreshed.scoring_rule == old_rule


def test_patch_retired_criterion_returns_409_and_leaves_db_unchanged(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    retired_criterion = _criterion(db_session, "coordinator", "OP-01", status="retired")
    old_desc = retired_criterion.description

    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{retired_criterion.rubric_criterion_id}",
        json={
            "description": "Direct mutation of retired definition.",
            "scoring_rule": None,
        },
    )
    assert response.status_code == 409

    refreshed = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=retired_criterion.rubric_criterion_id)
        .one()
    )
    assert refreshed.description == old_desc


def test_patch_draft_domain_title_success(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, draft_domain, _ = _create_draft_tree(db_session)

    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/domains/{draft_domain.rubric_domain_id}",
        json={"title": "Inclusivity & Awareness"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Inclusivity & Awareness"


def test_patch_published_domain_returns_409_and_leaves_db_unchanged(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    domain = db_session.query(RubricDomain).filter_by(code="GAD").one()
    old_title = domain.title

    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/domains/{domain.rubric_domain_id}",
        json={"title": "Direct published domain change"},
    )
    assert response.status_code == 409

    refreshed = (
        db_session.query(RubricDomain)
        .filter_by(rubric_domain_id=domain.rubric_domain_id)
        .one()
    )
    assert refreshed.title == old_title


def test_patch_retired_domain_returns_409_and_leaves_db_unchanged(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    retired_set = (
        db_session.query(RubricSet)
        .filter_by(agent_id="coordinator", version_number=1)
        .one()
    )
    retired_domain = (
        db_session.query(RubricDomain)
        .filter_by(rubric_set_id=retired_set.rubric_set_id)
        .first()
    )
    old_title = retired_domain.title

    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/domains/{retired_domain.rubric_domain_id}",
        json={"title": "Direct retired domain change"},
    )
    assert response.status_code == 409

    refreshed = (
        db_session.query(RubricDomain)
        .filter_by(rubric_domain_id=retired_domain.rubric_domain_id)
        .one()
    )
    assert refreshed.title == old_title


def test_patch_criterion_unknown_id_returns_404(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{uuid.uuid4()}",
        json={"description": "y", "scoring_rule": None},
    )
    assert response.status_code == 404


def test_patch_domain_unknown_id_returns_404(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/domains/{uuid.uuid4()}",
        json={"title": "Missing"},
    )
    assert response.status_code == 404


# --- router: strict schema validation (422) -----------------------------------


def test_patch_criterion_blank_description_rejected(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, _, draft_criterion = _create_draft_tree(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{draft_criterion.rubric_criterion_id}",
        json={"description": "   ", "scoring_rule": None},
    )
    assert response.status_code == 422


def test_patch_criterion_oversized_description_rejected(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, _, draft_criterion = _create_draft_tree(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{draft_criterion.rubric_criterion_id}",
        json={"description": "x" * 4001, "scoring_rule": None},
    )
    assert response.status_code == 422


def test_patch_criterion_oversized_scoring_rule_rejected(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, _, draft_criterion = _create_draft_tree(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{draft_criterion.rubric_criterion_id}",
        json={"description": "Valid", "scoring_rule": "s" * 4001},
    )
    assert response.status_code == 422


def test_patch_criterion_unknown_fields_rejected(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, _, draft_criterion = _create_draft_tree(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{draft_criterion.rubric_criterion_id}",
        json={
            "description": "Valid description",
            "extra_field": "disallowed",
        },
    )
    assert response.status_code == 422


def test_patch_criterion_strategy_fields_rejected_in_legacy_patch(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, _, draft_criterion = _create_draft_tree(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{draft_criterion.rubric_criterion_id}",
        json={
            "description": "Valid description",
            "scoring_strategy": "count_band",
            "strategy_config": {"strategy": "count_band"},
        },
    )
    assert response.status_code == 422


def test_patch_domain_blank_title_rejected(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, draft_domain, _ = _create_draft_tree(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/domains/{draft_domain.rubric_domain_id}",
        json={"title": "   "},
    )
    assert response.status_code == 422


def test_patch_domain_oversized_title_rejected(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, draft_domain, _ = _create_draft_tree(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/domains/{draft_domain.rubric_domain_id}",
        json={"title": "d" * 201},
    )
    assert response.status_code == 422


def test_patch_domain_unknown_fields_rejected(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _, draft_domain, _ = _create_draft_tree(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/domains/{draft_domain.rubric_domain_id}",
        json={"title": "Valid Title", "extra_prop": "bad"},
    )
    assert response.status_code == 422
