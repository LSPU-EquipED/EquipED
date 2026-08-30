"""Tests for admin dynamic CID evaluation forms lifecycle and authoring API.

Covers:
- RBAC: 401 unauthenticated, 403 non-admin (faculty) across endpoints
- Actor IDs: non-null admin user_id recorded on create/publish/activate/retire
- Draft lifecycle: one-draft conflict, create from active, delete draft
- Manifest validation: draft validation & structured 422 detail on failure
- CRUD operations: schema bounds & display_order rejection
- Criterion PATCH: omitted vs explicit null/blank scoring_rule
- Immutability: 409 conflict when mutating published or retired revisions
- Bulk reordering: complete-tree validation, zero-partial-write matrix
- Publication & Activation: atomic publish+activate, rollback, retirement
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from server.modules.rubrics import service as rubric_service
from server.modules.rubrics.models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.tests.admin.conftest import _auth
from server.tests.rubrics.test_rubrics import _seed_from_json

# ---------------------------------------------------------------------------
# RBAC Tests (401 / 403)
# ---------------------------------------------------------------------------


def test_admin_rubrics_api_rbac_guards(
    client: TestClient, auth_cookies_faculty, db_session
) -> None:
    _seed_from_json(db_session)
    active_sme = (
        db_session.query(RubricSet)
        .filter_by(agent_id="sme", status="published")
        .first()
    )
    sme_id = str(active_sme.rubric_set_id)

    endpoints = [
        ("GET", "/api/v1/admin/rubrics", None),
        ("GET", "/api/v1/admin/rubrics/revisions", None),
        ("GET", f"/api/v1/admin/rubrics/{sme_id}", None),
        ("POST", "/api/v1/admin/rubrics/agents/sme/draft", None),
        ("DELETE", f"/api/v1/admin/rubrics/{sme_id}/draft", None),
        ("POST", f"/api/v1/admin/rubrics/{sme_id}/validate", None),
        ("POST", f"/api/v1/admin/rubrics/{sme_id}/publish", {}),
        ("POST", f"/api/v1/admin/rubrics/{sme_id}/activate", None),
        ("POST", f"/api/v1/admin/rubrics/{sme_id}/retire", None),
        ("POST", f"/api/v1/admin/rubrics/{sme_id}/reorder", {"domains": []}),
        (
            "POST",
            f"/api/v1/admin/rubrics/{sme_id}/domains",
            {"code": "DOM", "title": "Title"},
        ),
        (
            "POST",
            f"/api/v1/admin/rubrics/criteria/{sme_id}/move",
            {"destination_domain_id": sme_id},
        ),
    ]

    for method, path, payload in endpoints:
        # Unauthenticated -> 401
        client.cookies.clear()
        if method == "GET":
            res_unauth = client.get(path)
        elif method == "POST":
            res_unauth = client.post(path, json=payload or {})
        else:
            res_unauth = client.delete(path)
        assert res_unauth.status_code == 401, (
            f"{method} {path} expected 401, got {res_unauth.status_code}"
        )

        # Faculty -> 403
        _auth(client, auth_cookies_faculty)
        if method == "GET":
            res_fac = client.get(path)
        elif method == "POST":
            res_fac = client.post(path, json=payload or {})
        else:
            res_fac = client.delete(path)
        assert res_fac.status_code == 403, (
            f"{method} {path} expected 403, got {res_fac.status_code}"
        )


# ---------------------------------------------------------------------------
# Revisions and Single Revision Retrieval
# ---------------------------------------------------------------------------


def test_list_revisions_and_get_by_id(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    response = client.get("/api/v1/admin/rubrics/revisions")
    assert response.status_code == 200
    data = response.json()
    assert "revisions" in data
    assert "active_pointers" in data
    assert len(data["revisions"]) >= 4

    active_pointers = data["active_pointers"]
    assert set(active_pointers.keys()) == {"sme", "coordinator", "gad", "itso"}

    # Fetch specific revision by ID
    sme_set_id = active_pointers["sme"]
    res_single = client.get(f"/api/v1/admin/rubrics/{sme_set_id}")
    assert res_single.status_code == 200
    single_data = res_single.json()
    assert single_data["rubric_set_id"] == sme_set_id
    assert single_data["agent_id"] == "sme"
    assert single_data["is_active"] is True
    assert len(single_data["domains"]) > 0


def test_get_nonexistent_revision_returns_404(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    missing_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/admin/rubrics/{missing_id}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Draft Creation and Single-Draft Conflict
# ---------------------------------------------------------------------------


def test_create_draft_from_active_records_actor_id(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    response = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    assert response.status_code == 201
    draft_data = response.json()
    assert draft_data["agent_id"] == "sme"
    assert draft_data["status"] == "draft"
    assert draft_data["version_number"] == 2
    assert draft_data["created_by"] == str(admin_user.user_id)
    assert len(draft_data["domains"]) == 2

    # Second draft for same agent fails with 409 Conflict
    res_conflict = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    assert res_conflict.status_code == 409


def test_create_draft_for_unknown_agent_returns_404(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    response = client.post("/api/v1/admin/rubrics/agents/nonexistent_agent/draft")
    assert response.status_code == 404


def test_delete_draft_success_and_immutability_guard(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    # 1. Create draft
    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_id = create_res.json()["rubric_set_id"]

    # 2. Delete draft via canonical endpoint
    del_res = client.delete(f"/api/v1/admin/rubrics/{draft_id}/draft")
    assert del_res.status_code == 204

    # Verify draft is gone
    get_res = client.get(f"/api/v1/admin/rubrics/{draft_id}")
    assert get_res.status_code == 404

    # 3. Attempt to delete published rubric set -> 409 Conflict
    published_sme = (
        db_session.query(RubricSet)
        .filter_by(agent_id="sme", status="published")
        .first()
    )
    del_pub = client.delete(
        f"/api/v1/admin/rubrics/{published_sme.rubric_set_id}/draft"
    )
    assert del_pub.status_code == 409


# ---------------------------------------------------------------------------
# Domain and Criterion CRUD: Deterministic Appending & Order Field Rejection
# ---------------------------------------------------------------------------


def test_domain_crud_appends_order_and_rejects_order_field(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_id = create_res.json()["rubric_set_id"]

    # Add domain without display_order (appends deterministically)
    add_dom_res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/domains",
        json={"code": "NEWDOM", "title": "New Domain Title"},
    )
    assert add_dom_res.status_code == 201
    domain_data = add_dom_res.json()
    domain_id = domain_data["rubric_domain_id"]
    assert domain_data["code"] == "NEWDOM"
    assert domain_data["title"] == "New Domain Title"
    assert domain_data["display_order"] == 3  # OP was 1, A was 2, new is 3

    # Attempt to pass display_order in create -> 422 (reorder is sole ordering mutation)
    bad_create = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/domains",
        json={"code": "ORDERED", "title": "Ordered", "display_order": 1},
    )
    assert bad_create.status_code == 422

    # Attempt to pass display_order in update -> 422
    bad_update_order = client.patch(
        f"/api/v1/admin/rubrics/domains/{domain_id}",
        json={"title": "Updated", "display_order": 1},
    )
    assert bad_update_order.status_code == 422

    # Duplicate domain code in draft -> 409
    dup_dom_res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/domains",
        json={"code": "NEWDOM", "title": "Duplicate Domain"},
    )
    assert dup_dom_res.status_code == 409

    # Valid update domain
    update_dom_res = client.patch(
        f"/api/v1/admin/rubrics/domains/{domain_id}",
        json={"title": "Updated Domain Title"},
    )
    assert update_dom_res.status_code == 200
    assert update_dom_res.json()["title"] == "Updated Domain Title"

    # Delete domain
    del_dom_res = client.delete(f"/api/v1/admin/rubrics/domains/{domain_id}")
    assert del_dom_res.status_code == 204


def test_criterion_crud_appends_order_and_rejects_order_field(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_data = create_res.json()
    domain_id = draft_data["domains"][0]["rubric_domain_id"]
    existing_count = len(draft_data["domains"][0]["criteria"])

    # Add criterion with typed strategy_config (appends deterministically)
    new_crit_payload = {
        "criterion_code": "SME-NEW-01",
        "title": "New Criterion Title",
        "description": "New criterion description.",
        "scoring_rule": "4+ elements -> 4",
        "strategy_config": {
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 4,
            "threshold_3": 2,
            "threshold_2": 1,
        },
    }
    add_crit_res = client.post(
        f"/api/v1/admin/rubrics/domains/{domain_id}/criteria",
        json=new_crit_payload,
    )
    assert add_crit_res.status_code == 201
    crit_data = add_crit_res.json()
    crit_id = crit_data["rubric_criterion_id"]
    assert crit_data["criterion_code"] == "SME-NEW-01"
    assert crit_data["scoring_strategy"] == "count_band"
    assert crit_data["strategy_config"]["mode"] == "minimum_count"
    assert crit_data["display_order"] == existing_count + 1

    # Attempt to pass display_order in create -> 422
    bad_create_crit = client.post(
        f"/api/v1/admin/rubrics/domains/{domain_id}/criteria",
        json={**new_crit_payload, "criterion_code": "SME-ORDER", "display_order": 1},
    )
    assert bad_create_crit.status_code == 422

    # Attempt to pass display_order in update -> 422
    bad_update_crit_order = client.patch(
        f"/api/v1/admin/rubrics/criteria/{crit_id}",
        json={"description": "Updated", "display_order": 1},
    )
    assert bad_update_crit_order.status_code == 422

    # Mass assignment rejection: client passing scoring_strategy directly
    bad_crit_payload = {
        **new_crit_payload,
        "criterion_code": "SME-NEW-02",
        "scoring_strategy": "count_band",
    }
    bad_add_res = client.post(
        f"/api/v1/admin/rubrics/domains/{domain_id}/criteria",
        json=bad_crit_payload,
    )
    assert bad_add_res.status_code == 422

    # Duplicate criterion code (case-insensitive) -> 409
    dup_crit_payload = {
        **new_crit_payload,
        "criterion_code": "sme-new-01",
    }
    dup_add_res = client.post(
        f"/api/v1/admin/rubrics/domains/{domain_id}/criteria",
        json=dup_crit_payload,
    )
    assert dup_add_res.status_code == 409


def test_create_criterion_domain_removed_while_waiting_returns_404_without_insert(
    client: TestClient, auth_cookies_admin, db_session, monkeypatch
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)
    draft = client.post("/api/v1/admin/rubrics/agents/sme/draft").json()
    draft_id = uuid.UUID(draft["rubric_set_id"])
    domain_res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/domains",
        json={"code": "RACE", "title": "Race domain"},
    )
    domain_id = uuid.UUID(domain_res.json()["rubric_domain_id"])
    original_lock = rubric_service._lock_parent_draft_rubric_set

    def _remove_domain_then_lock(db, rubric_set_id):
        db.query(RubricDomain).filter_by(rubric_domain_id=domain_id).delete()
        db.flush()
        return original_lock(db, rubric_set_id)

    monkeypatch.setattr(
        rubric_service, "_lock_parent_draft_rubric_set", _remove_domain_then_lock
    )
    before_count = db_session.query(RubricCriterion).count()
    response = client.post(
        f"/api/v1/admin/rubrics/domains/{domain_id}/criteria",
        json={
            "criterion_code": "RACE-01",
            "title": "Race criterion",
            "description": "Must not be inserted from a stale parent read.",
            "scoring_rule": None,
            "strategy_config": {
                "strategy": "count_band",
                "mode": "minimum_count",
                "threshold_4": 4,
                "threshold_3": 2,
                "threshold_2": 1,
            },
        },
    )

    assert response.status_code == 404
    assert db_session.query(RubricCriterion).count() == before_count
    assert (
        db_session.query(RubricDomain)
        .filter_by(rubric_domain_id=domain_id, rubric_set_id=draft_id)
        .one_or_none()
        is not None
    )


def test_move_criterion_between_domains_normalizes_orders_and_preserves_uuid(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)
    draft = client.post("/api/v1/admin/rubrics/agents/sme/draft").json()
    source, destination = draft["domains"]
    criterion_id = source["criteria"][0]["rubric_criterion_id"]

    response = client.post(
        f"/api/v1/admin/rubrics/criteria/{criterion_id}/move",
        json={"destination_domain_id": destination["rubric_domain_id"]},
    )

    assert response.status_code == 200
    assert response.json()["rubric_criterion_id"] == criterion_id
    assert response.json()["rubric_domain_id"] == destination["rubric_domain_id"]
    db_session.expire_all()
    for domain_id in (
        uuid.UUID(source["rubric_domain_id"]),
        uuid.UUID(destination["rubric_domain_id"]),
    ):
        orders = [
            row.display_order
            for row in db_session.query(RubricCriterion)
            .filter_by(rubric_domain_id=domain_id)
            .order_by(RubricCriterion.display_order)
            .all()
        ]
        assert orders == list(range(1, len(orders) + 1))


def test_move_criterion_rejects_foreign_non_draft_missing_and_invalid_payload(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)
    draft = client.post("/api/v1/admin/rubrics/agents/sme/draft").json()
    draft_criterion_id = draft["domains"][0]["criteria"][0]["rubric_criterion_id"]
    published = (
        db_session.query(RubricSet).filter_by(agent_id="gad", status="published").one()
    )
    published_domains = (
        db_session.query(RubricDomain)
        .filter_by(rubric_set_id=published.rubric_set_id)
        .order_by(RubricDomain.display_order)
        .all()
    )

    foreign = client.post(
        f"/api/v1/admin/rubrics/criteria/{draft_criterion_id}/move",
        json={"destination_domain_id": str(published_domains[0].rubric_domain_id)},
    )
    assert foreign.status_code == 409

    published_criterion = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_domain_id=published_domains[0].rubric_domain_id)
        .first()
    )
    immutable = client.post(
        f"/api/v1/admin/rubrics/criteria/{published_criterion.rubric_criterion_id}/move",
        json={"destination_domain_id": str(published_domains[-1].rubric_domain_id)},
    )
    assert immutable.status_code == 409

    missing = client.post(
        f"/api/v1/admin/rubrics/criteria/{uuid.uuid4()}/move",
        json={"destination_domain_id": draft["domains"][1]["rubric_domain_id"]},
    )
    assert missing.status_code == 404

    invalid = client.post(
        f"/api/v1/admin/rubrics/criteria/{draft_criterion_id}/move",
        json={
            "destination_domain_id": draft["domains"][1]["rubric_domain_id"],
            "display_order": 1,
        },
    )
    assert invalid.status_code == 422


# ---------------------------------------------------------------------------
# Criterion PATCH: Omitted vs Explicit Null / Blank scoring_rule
# ---------------------------------------------------------------------------


def test_patch_criterion_scoring_rule_omitted_vs_null_vs_blank(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_data = create_res.json()
    first_crit = draft_data["domains"][0]["criteria"][0]
    crit_id = first_crit["rubric_criterion_id"]
    original_rule = first_crit["scoring_rule"]
    assert original_rule is not None and len(original_rule) > 0

    # 1. Omitted scoring_rule in body: leaves scoring_rule unchanged
    res_omitted = client.patch(
        f"/api/v1/admin/rubrics/criteria/{crit_id}",
        json={"description": "Updated description without touching scoring rule."},
    )
    assert res_omitted.status_code == 200
    assert (
        res_omitted.json()["description"]
        == "Updated description without touching scoring rule."
    )
    assert res_omitted.json()["scoring_rule"] == original_rule

    # Verify directly in DB
    refreshed_db = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=uuid.UUID(crit_id))
        .one()
    )
    assert refreshed_db.scoring_rule == original_rule

    # 2. Explicit null scoring_rule: clears to NULL
    res_null = client.patch(
        f"/api/v1/admin/rubrics/criteria/{crit_id}",
        json={"scoring_rule": None},
    )
    assert res_null.status_code == 200
    assert res_null.json()["scoring_rule"] is None

    db_session.expire_all()
    refreshed_db_null = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=uuid.UUID(crit_id))
        .one()
    )
    assert refreshed_db_null.scoring_rule is None

    # 3. Explicit update to a new rule
    res_new_rule = client.patch(
        f"/api/v1/admin/rubrics/criteria/{crit_id}",
        json={"scoring_rule": "Band 1-4 new rule"},
    )
    assert res_new_rule.status_code == 200
    assert res_new_rule.json()["scoring_rule"] == "Band 1-4 new rule"

    # 4. Explicit blank whitespace scoring_rule: clears to NULL
    res_blank = client.patch(
        f"/api/v1/admin/rubrics/criteria/{crit_id}",
        json={"scoring_rule": "   "},
    )
    assert res_blank.status_code == 200
    assert res_blank.json()["scoring_rule"] is None


def test_patch_domain_validation_matrix(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_data = create_res.json()
    domain_id = draft_data["domains"][0]["rubric_domain_id"]

    # 1. Empty body -> 422
    res_empty = client.patch(
        f"/api/v1/admin/rubrics/domains/{domain_id}",
        json={},
    )
    assert res_empty.status_code == 422

    # 2. Explicit null for non-clearable fields -> 422
    res_null_code = client.patch(
        f"/api/v1/admin/rubrics/domains/{domain_id}",
        json={"code": None},
    )
    assert res_null_code.status_code == 422

    res_null_title = client.patch(
        f"/api/v1/admin/rubrics/domains/{domain_id}",
        json={"title": None},
    )
    assert res_null_title.status_code == 422

    # 3. Unknown field (extra='forbid') -> 422
    res_unknown = client.patch(
        f"/api/v1/admin/rubrics/domains/{domain_id}",
        json={"title": "Valid Title", "unexpected_field": "disallowed"},
    )
    assert res_unknown.status_code == 422


def test_patch_criterion_validation_matrix(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_data = create_res.json()
    crit_id = draft_data["domains"][0]["criteria"][0]["rubric_criterion_id"]

    # 1. Empty body -> 422
    res_empty = client.patch(
        f"/api/v1/admin/rubrics/criteria/{crit_id}",
        json={},
    )
    assert res_empty.status_code == 422

    # 2. Explicit null for non-clearable fields -> 422
    non_clearable_nulls = [
        {"criterion_code": None},
        {"title": None},
        {"description": None},
        {"strategy_config": None},
    ]
    for payload in non_clearable_nulls:
        res_null = client.patch(
            f"/api/v1/admin/rubrics/criteria/{crit_id}",
            json=payload,
        )
        assert res_null.status_code == 422, (
            f"Expected 422 for payload {payload}, got {res_null.status_code}"
        )

    # 3. Unknown field (extra='forbid') -> 422
    res_unknown = client.patch(
        f"/api/v1/admin/rubrics/criteria/{crit_id}",
        json={"title": "Valid Title", "unknown_field": "bar"},
    )
    assert res_unknown.status_code == 422

    # 4. Strict strategy DTO rejection (invalid strategy payload) -> 422
    res_invalid_strategy = client.patch(
        f"/api/v1/admin/rubrics/criteria/{crit_id}",
        json={
            "strategy_config": {
                "strategy": "count_band",
                "mode": "minimum_count",
                "threshold_4": "not_an_int",
                "threshold_3": 2,
                "threshold_2": 1,
            }
        },
    )
    assert res_invalid_strategy.status_code == 422

    # 5. Valid strategy update -> 200
    res_valid_strategy = client.patch(
        f"/api/v1/admin/rubrics/criteria/{crit_id}",
        json={
            "strategy_config": {
                "strategy": "count_band",
                "mode": "minimum_count",
                "threshold_4": 5,
                "threshold_3": 3,
                "threshold_2": 1,
            }
        },
    )
    assert res_valid_strategy.status_code == 200
    assert res_valid_strategy.json()["scoring_strategy"] == "count_band"
    assert res_valid_strategy.json()["strategy_config"] == {
        "strategy": "count_band",
        "mode": "minimum_count",
        "threshold_4": 5,
        "threshold_3": 3,
        "threshold_2": 1,
    }


# ---------------------------------------------------------------------------
# Bulk Reorder and Zero-Partial-Write Negative Matrix
# ---------------------------------------------------------------------------


def test_reorder_rubric_tree_success(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_data = create_res.json()
    draft_id = draft_data["rubric_set_id"]

    dom1 = draft_data["domains"][0]
    dom2 = draft_data["domains"][1]

    # Swap domains and reverse criteria within dom1
    reversed_crit_ids_dom1 = list(
        reversed([c["rubric_criterion_id"] for c in dom1["criteria"]])
    )
    dom2_crit_ids = [c["rubric_criterion_id"] for c in dom2["criteria"]]

    reorder_payload = {
        "domains": [
            {
                "rubric_domain_id": dom2["rubric_domain_id"],
                "criterion_ids": dom2_crit_ids,
            },
            {
                "rubric_domain_id": dom1["rubric_domain_id"],
                "criterion_ids": reversed_crit_ids_dom1,
            },
        ]
    }

    reorder_res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/reorder",
        json=reorder_payload,
    )
    assert reorder_res.status_code == 200
    reordered = reorder_res.json()
    assert reordered["domains"][0]["rubric_domain_id"] == dom2["rubric_domain_id"]
    assert reordered["domains"][1]["rubric_domain_id"] == dom1["rubric_domain_id"]

    dom1_reordered_crits = [
        c["rubric_criterion_id"] for c in reordered["domains"][1]["criteria"]
    ]
    assert dom1_reordered_crits == reversed_crit_ids_dom1


def test_reorder_negative_matrix_zero_partial_writes(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_data = create_res.json()
    draft_id = draft_data["rubric_set_id"]

    dom1 = draft_data["domains"][0]
    dom2 = draft_data["domains"][1]
    dom1_crit_ids = [c["rubric_criterion_id"] for c in dom1["criteria"]]
    dom2_crit_ids = [c["rubric_criterion_id"] for c in dom2["criteria"]]

    original_order_dom1 = list(dom1_crit_ids)

    # 1. Missing domain
    res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/reorder",
        json={
            "domains": [
                {
                    "rubric_domain_id": dom1["rubric_domain_id"],
                    "criterion_ids": dom1_crit_ids,
                }
            ]
        },
    )
    assert res.status_code == 422

    # 2. Foreign domain ID
    res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/reorder",
        json={
            "domains": [
                {
                    "rubric_domain_id": dom1["rubric_domain_id"],
                    "criterion_ids": dom1_crit_ids,
                },
                {
                    "rubric_domain_id": str(uuid.uuid4()),
                    "criterion_ids": dom2_crit_ids,
                },
            ]
        },
    )
    assert res.status_code == 422

    # 3. Duplicate domain ID
    res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/reorder",
        json={
            "domains": [
                {
                    "rubric_domain_id": dom1["rubric_domain_id"],
                    "criterion_ids": dom1_crit_ids,
                },
                {
                    "rubric_domain_id": dom1["rubric_domain_id"],
                    "criterion_ids": dom1_crit_ids,
                },
            ]
        },
    )
    assert res.status_code == 422

    # 4. Missing criterion in domain
    res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/reorder",
        json={
            "domains": [
                {
                    "rubric_domain_id": dom1["rubric_domain_id"],
                    "criterion_ids": dom1_crit_ids[:-1],
                },
                {
                    "rubric_domain_id": dom2["rubric_domain_id"],
                    "criterion_ids": dom2_crit_ids,
                },
            ]
        },
    )
    assert res.status_code == 422

    # 5. Foreign criterion ID
    res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/reorder",
        json={
            "domains": [
                {
                    "rubric_domain_id": dom1["rubric_domain_id"],
                    "criterion_ids": dom1_crit_ids + [str(uuid.uuid4())],
                },
                {
                    "rubric_domain_id": dom2["rubric_domain_id"],
                    "criterion_ids": dom2_crit_ids,
                },
            ]
        },
    )
    assert res.status_code == 422

    # 6. Duplicate criterion ID in domain
    res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/reorder",
        json={
            "domains": [
                {
                    "rubric_domain_id": dom1["rubric_domain_id"],
                    "criterion_ids": [dom1_crit_ids[0]] + dom1_crit_ids,
                },
                {
                    "rubric_domain_id": dom2["rubric_domain_id"],
                    "criterion_ids": dom2_crit_ids,
                },
            ]
        },
    )
    assert res.status_code == 422

    # 7. Cross-domain criterion reparenting (moving crit from dom1 to dom2)
    res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/reorder",
        json={
            "domains": [
                {
                    "rubric_domain_id": dom1["rubric_domain_id"],
                    "criterion_ids": dom1_crit_ids[1:],
                },
                {
                    "rubric_domain_id": dom2["rubric_domain_id"],
                    "criterion_ids": [dom1_crit_ids[0]] + dom2_crit_ids,
                },
            ]
        },
    )
    assert res.status_code == 422

    # 8. Reorder on published revision -> 409 Conflict
    published_sme = (
        db_session.query(RubricSet)
        .filter_by(agent_id="sme", status="published")
        .first()
    )
    res_pub = client.post(
        f"/api/v1/admin/rubrics/{published_sme.rubric_set_id}/reorder",
        json={
            "domains": [
                {
                    "rubric_domain_id": dom1["rubric_domain_id"],
                    "criterion_ids": dom1_crit_ids,
                },
                {
                    "rubric_domain_id": dom2["rubric_domain_id"],
                    "criterion_ids": dom2_crit_ids,
                },
            ]
        },
    )
    assert res_pub.status_code == 409

    # Verify zero partial writes on draft
    refreshed_draft = client.get(f"/api/v1/admin/rubrics/{draft_id}").json()
    refreshed_dom1_crits = [
        c["rubric_criterion_id"] for c in refreshed_draft["domains"][0]["criteria"]
    ]
    assert refreshed_dom1_crits == original_order_dom1


# ---------------------------------------------------------------------------
# Validation, Publish, Activate, and Retire Lifecycle
# ---------------------------------------------------------------------------


def test_validate_draft_endpoint(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_id = create_res.json()["rubric_set_id"]

    val_res = client.post(f"/api/v1/admin/rubrics/{draft_id}/validate")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["is_valid"] is True
    assert val_data["criteria_count"] == 10
    assert val_data["estimated_prompt_chars"] > 0
    assert val_data["issues"] == []


def test_publish_and_activate_atomic(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    # 1. Create draft
    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_id = create_res.json()["rubric_set_id"]

    # 2. Publish with atomic activation (activate=True)
    pub_res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/publish",
        json={"activate": True},
    )
    assert pub_res.status_code == 200
    pub_data = pub_res.json()
    assert pub_data["status"] == "published"
    assert pub_data["published_by"] == str(admin_user.user_id)
    assert pub_data["published_at"] is not None
    assert pub_data["is_active"] is True

    # Check activation pointer points to the newly published revision
    act = db_session.query(RubricAgentActivation).filter_by(agent_id="sme").one()
    assert str(act.rubric_set_id) == draft_id
    assert act.updated_by == admin_user.user_id


def test_publish_invalid_draft_fails_with_structured_422(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_id = create_res.json()["rubric_set_id"]

    draft = (
        db_session.query(RubricSet).filter_by(rubric_set_id=uuid.UUID(draft_id)).one()
    )
    draft.adapter_version = 999
    db_session.commit()

    # Attempt to publish invalid draft -> structured 422
    pub_res = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/publish",
        json={"activate": True},
    )
    assert pub_res.status_code == 422
    err_detail = pub_res.json()["detail"]
    assert err_detail["is_valid"] is False
    issue = next(
        issue
        for issue in err_detail["issues"]
        if issue["code"] == "ADAPTER_VERSION_MISMATCH"
    )
    assert issue["path"] == "adapter_version"
    assert issue["severity"] == "error"
    assert issue["message"]
    assert err_detail["criteria_count"] == 10
    assert err_detail["estimated_prompt_chars"] > 0

    # Status remains draft
    refreshed = (
        db_session.query(RubricSet).filter_by(rubric_set_id=uuid.UUID(draft_id)).one()
    )
    assert refreshed.status == "draft"


def test_activate_invalid_published_revision_preserves_structured_422_report(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)
    old_activation_id = (
        db_session.query(RubricAgentActivation)
        .filter_by(agent_id="sme")
        .one()
        .rubric_set_id
    )
    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    revision_id = uuid.UUID(create_res.json()["rubric_set_id"])
    revision = db_session.query(RubricSet).filter_by(rubric_set_id=revision_id).one()
    revision.status = "published"
    revision.adapter_version = 999
    db_session.commit()

    response = client.post(f"/api/v1/admin/rubrics/{revision_id}/activate")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["is_valid"] is False
    issue = next(
        issue
        for issue in detail["issues"]
        if issue["code"] == "ADAPTER_VERSION_MISMATCH"
    )
    assert issue["path"] == "adapter_version"
    assert issue["severity"] == "error"
    assert issue["message"]
    assert detail["criteria_count"] == 10
    assert detail["estimated_prompt_chars"] > 0
    db_session.expire_all()
    activation = db_session.query(RubricAgentActivation).filter_by(agent_id="sme").one()
    assert activation.rubric_set_id == old_activation_id


def test_activate_older_revision_and_retirement_guards(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    # 1. Note Rev 1 for SME
    rev1 = db_session.query(RubricSet).filter_by(agent_id="sme", version_number=1).one()
    rev1_id = str(rev1.rubric_set_id)

    # 2. Create Rev 2 draft and publish+activate it
    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    rev2_id = create_res.json()["rubric_set_id"]
    client.post(f"/api/v1/admin/rubrics/{rev2_id}/publish", json={"activate": True})

    # Verify Rev 2 is active
    act = db_session.query(RubricAgentActivation).filter_by(agent_id="sme").one()
    assert str(act.rubric_set_id) == rev2_id

    # 3. Attempt to retire active Rev 2 -> 409 Conflict
    retire_active_res = client.post(f"/api/v1/admin/rubrics/{rev2_id}/retire")
    assert retire_active_res.status_code == 409

    # 4. Retire non-active Rev 1 -> 200 OK
    retire_rev1_res = client.post(f"/api/v1/admin/rubrics/{rev1_id}/retire")
    assert retire_rev1_res.status_code == 200
    assert retire_rev1_res.json()["status"] == "retired"
    assert retire_rev1_res.json()["retired_by"] == str(admin_user.user_id)

    # 5. Attempt to activate retired Rev 1 -> 409 Conflict
    act_retired_res = client.post(f"/api/v1/admin/rubrics/{rev1_id}/activate")
    assert act_retired_res.status_code == 409


def test_publish_request_strict_boolean_rejection(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _seed_from_json(db_session)
    _auth(client, auth_cookies_admin)

    create_res = client.post("/api/v1/admin/rubrics/agents/sme/draft")
    draft_id = create_res.json()["rubric_set_id"]

    # String instead of strict bool -> 422
    res_str = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/publish",
        json={"activate": "true"},
    )
    assert res_str.status_code == 422

    # Integer instead of strict bool -> 422
    res_int = client.post(
        f"/api/v1/admin/rubrics/{draft_id}/publish",
        json={"activate": 1},
    )
    assert res_int.status_code == 422
