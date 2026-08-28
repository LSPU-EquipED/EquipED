"""Tests for the admin-facing rubric editor: read tree, text edits, access control."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.rubrics.models import RubricCriterion, RubricDomain, RubricSet
from server.modules.rubrics.service import (
    get_active_rubric_context,
    get_rubric_sets_for_editor,
    update_criterion_text,
    update_domain_title,
)
from server.tests.rubrics.conftest import _auth
from server.tests.rubrics.test_rubrics import _seed_from_json


def _criterion(db_session, agent_id: str, code: str) -> RubricCriterion:
    """Fetch one criterion by agent + code (the same code exists for several agents)."""
    return (
        db_session.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .join(RubricSet, RubricDomain.rubric_set_id == RubricSet.rubric_set_id)
        .filter(RubricSet.agent_id == agent_id, RubricCriterion.criterion_code == code)
        .one()
    )


# --- service layer -------------------------------------------------------------


def test_get_rubric_sets_for_editor_returns_nested_active_sets(db_session) -> None:
    _seed_from_json(db_session)

    sets = get_rubric_sets_for_editor(db=db_session)

    by_agent = {s["agent_id"]: s for s in sets}
    assert set(by_agent) == {"sme", "coordinator", "gad", "itso"}

    sme = by_agent["sme"]
    assert sme["name"] == "SME Rubric v1"
    assert sme["version_number"] == 1
    assert sme["status"] == "active"
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


def test_update_criterion_text_persists_new_title_and_description(db_session) -> None:
    _seed_from_json(db_session)
    criterion = _criterion(db_session, "sme", "OP-01")

    update_criterion_text(
        db_session,
        criterion.rubric_criterion_id,
        title="Topic Flow",
        description="Topics flow coherently across chapters.",
    )
    db_session.commit()

    refreshed = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=criterion.rubric_criterion_id)
        .one()
    )
    assert refreshed.title == "Topic Flow"
    assert refreshed.description == "Topics flow coherently across chapters."
    # criterion_code is never touched by a text edit.
    assert refreshed.criterion_code == "OP-01"


def test_update_criterion_text_missing_id_raises_lookup_error(db_session) -> None:
    import uuid

    _seed_from_json(db_session)
    with pytest.raises(LookupError):
        update_criterion_text(
            db_session, uuid.uuid4(), title="x", description="y"
        )


def test_update_domain_title_persists(db_session) -> None:
    _seed_from_json(db_session)
    domain = (
        db_session.query(RubricDomain)
        .filter_by(code="OP")
        .filter(RubricDomain.title == "Organization & Presentation")
        .first()
    )

    update_domain_title(db_session, domain.rubric_domain_id, title="Organization")
    db_session.commit()

    refreshed = (
        db_session.query(RubricDomain)
        .filter_by(rubric_domain_id=domain.rubric_domain_id)
        .one()
    )
    assert refreshed.title == "Organization"


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
    criterion_id = str(_criterion(db_session, "sme", "OP-02").rubric_criterion_id)
    payload = {"title": "Interaction", "description": "Lessons are interactive."}

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
    assert response.json()["title"] == "Interaction"


# --- router: behaviour -------------------------------------------------------


def test_patch_criterion_reflects_in_active_rubric_context(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    criterion_id = str(_criterion(db_session, "sme", "OP-01").rubric_criterion_id)

    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{criterion_id}",
        json={
            "title": "Topic Flow",
            "description": "Topics flow coherently across chapters.",
        },
    )
    assert response.status_code == 200

    context = get_active_rubric_context("sme", db=db_session)
    assert (
        "OP-01 | Title: Topic Flow | Description: "
        "Topics flow coherently across chapters." in context
    )


def test_patch_criterion_unknown_id_returns_404(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    import uuid

    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{uuid.uuid4()}",
        json={"title": "x", "description": "y"},
    )
    assert response.status_code == 404


def test_patch_criterion_blank_title_rejected(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    criterion_id = str(_criterion(db_session, "sme", "OP-01").rubric_criterion_id)
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/criteria/{criterion_id}",
        json={"title": "   ", "description": "still here"},
    )
    assert response.status_code == 422


def test_patch_domain_title(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    domain_id = str(
        db_session.query(RubricDomain)
        .filter_by(code="GAD")
        .one()
        .rubric_domain_id
    )
    _auth(client, auth_cookies_admin)
    response = client.patch(
        f"/api/v1/admin/rubrics/domains/{domain_id}",
        json={"title": "Inclusivity"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Inclusivity"
