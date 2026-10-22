"""Administrator editing, concurrency, audit and seed-ownership regression tests."""

import uuid
from types import SimpleNamespace

import pytest
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.curriculum.management import (
    CatalogError,
    save_mappings,
    save_objective,
)
from server.modules.curriculum.management_schemas import (
    MappingEdit,
    ObjectiveEdit,
    ObjectiveInput,
)
from server.modules.curriculum.models import (
    Course,
    CurriculumChange,
    CurriculumMapCell,
    CurriculumObjective,
)
from server.scripts.seed_curriculum_map import seed_curriculum_map


def objective(**changes):
    return {
        "code": "IT13",
        "description": "Explain distributed systems.",
        "program": "BSInfoTech",
        **changes,
    }


@pytest.mark.parametrize("role", [None, "faculty"])
def test_management_authorization(client, role):
    if role:
        client.app.dependency_overrides[require_authenticated_user] = lambda: (
            SimpleNamespace(id=uuid.uuid4(), role=role)
        )
    for method, path, payload in [
        ("get", "/objectives", None),
        ("post", "/objectives", objective()),
        ("put", f"/objectives/{uuid.uuid4()}", objective(version=1)),
        ("get", f"/courses/{uuid.uuid4()}/mappings", None),
        ("put", f"/courses/{uuid.uuid4()}/mappings", {"version": 1, "entries": []}),
    ]:
        kwargs = {} if payload is None else {"json": payload}
        assert getattr(client, method)(
            f"/api/v1/curriculum-map/admin{path}", **kwargs
        ).status_code == (403 if role else 401)


def test_admin_api_validates_and_preserves_edit_version(
    client, seeded_user, db_session
):
    client.app.dependency_overrides[require_authenticated_user] = lambda: (
        SimpleNamespace(id=seeded_user.user_id, role="admin")
    )
    root = "/api/v1/curriculum-map/admin/objectives"
    created = client.post(root, json=objective(code=" it13 "))
    assert created.status_code == 201
    row = created.json()
    assert row["code"] == "IT13"
    assert row["mapping_count"] == 0
    edited = client.put(
        f"{root}/{row['objective_id']}",
        json=objective(description="Revised", version=1),
    )
    assert edited.status_code == 200
    assert edited.json()["version"] == 2
    assert (
        client.put(
            f"{root}/{row['objective_id']}", json=objective(version=1)
        ).status_code
        == 409
    )
    assert client.post(root, json=objective(code="it13")).status_code == 409
    for invalid in [
        objective(program="BSIT"),
        objective(program="Custom"),
        objective(description=" "),
        objective(code=" "),
    ]:
        assert client.post(root, json=invalid).status_code == 422
    assert db_session.query(CurriculumChange).count() == 2
    assert client.get(root).json()["items"][0]["description"] == "Revised"


def test_mapping_changes_are_atomic_and_block_incompatible_moves(
    db_session, seeded_user
):
    actor = seeded_user.user_id
    item = save_objective(db_session, actor, ObjectiveInput(**objective()))
    item_id = uuid.UUID(item["objective_id"])
    course = Course(course_code="TEST", course_title="Test", program="BSIT")
    db_session.add(course)
    db_session.commit()
    entry = {"objective_id": item_id, "level": "E"}
    saved = save_mappings(
        db_session, actor, course.course_id, MappingEdit(version=1, entries=[entry])
    )
    assert saved["version"] == 2
    with pytest.raises(CatalogError, match="Reload"):
        save_mappings(
            db_session, actor, course.course_id, MappingEdit(version=1, entries=[])
        )
    with pytest.raises(CatalogError, match="incompatible"):
        save_objective(
            db_session,
            actor,
            ObjectiveEdit(**objective(program="BSCS", version=1)),
            item_id,
        )
    with pytest.raises(CatalogError, match="only once"):
        save_mappings(
            db_session,
            actor,
            course.course_id,
            MappingEdit(version=2, entries=[entry, entry]),
        )
    other = save_objective(
        db_session, actor, ObjectiveInput(**objective(code="CS01", program="BSCS"))
    )
    with pytest.raises(CatalogError, match="program"):
        save_mappings(
            db_session,
            actor,
            course.course_id,
            MappingEdit(
                version=2,
                entries=[{"objective_id": other["objective_id"], "level": "I"}],
            ),
        )
    assert (
        db_session.query(CurriculumMapCell)
        .filter_by(course_id=course.course_id)
        .one()
        .level
        == "E"
    )
    save_mappings(
        db_session, actor, course.course_id, MappingEdit(version=2, entries=[])
    )
    moved = save_objective(
        db_session,
        actor,
        ObjectiveEdit(**objective(program="BSCS", version=1)),
        item_id,
    )
    assert moved["objective_id"] == str(item_id)
    assert moved["program"] == "BSCS"


def test_seed_preserves_admin_rename_description_and_removed_mapping(
    db_session, seeded_user
):
    payload = {
        "program": "BSInfoTech",
        "objectives": [{"code": "IT01", "description": "Original"}],
        "courses": [
            {
                "course_code": "TEST",
                "course_title": "Test",
                "objective_levels": {"IT01": "I"},
            }
        ],
    }
    seed_curriculum_map(db_session, payload)
    row = db_session.query(CurriculumObjective).one()
    original_id = row.objective_id
    course = db_session.query(Course).one()
    save_objective(
        db_session,
        seeded_user.user_id,
        ObjectiveEdit(**objective(code="IT99", description="Admin wording", version=1)),
        row.objective_id,
    )
    save_mappings(
        db_session,
        seeded_user.user_id,
        course.course_id,
        MappingEdit(version=1, entries=[]),
    )
    seed_curriculum_map(db_session, payload)
    assert db_session.query(CurriculumObjective).count() == 1
    row = db_session.get(CurriculumObjective, original_id)
    assert row.code == "IT99"
    assert row.description == "Admin wording"
    assert db_session.query(CurriculumMapCell).count() == 0
