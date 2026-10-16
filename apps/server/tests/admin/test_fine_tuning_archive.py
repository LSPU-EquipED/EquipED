"""Archived research remains independent of the validation database."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from server.modules.admin.fine_tuning_archive import load_fine_tuning_archive
from server.modules.admin.router import router
from server.modules.auth.dependencies import require_admin


def test_archive_preserves_matching_references_and_real_metrics():
    archive = load_fine_tuning_archive()
    v7 = archive.experiments[0]
    assert v7.adapter_label == "sme-v7"
    criteria = [c for run in v7.runs for c in run.criteria]
    assert len(criteria) == 30
    assert sum(abs(c.base.score - c.expected) for c in criteria) == 16
    assert sum(abs(c.adapter.score - c.expected) for c in criteria) == 12
    assert sum(c.base.score == c.expected for c in criteria) == 15
    assert sum(c.adapter.score == c.expected for c in criteria) == 18
    v13 = next(e for e in archive.experiments if e.adapter_label == "sme-v13")
    target = [c for r in v13.runs for c in r.criteria if c.id == "OP-05"]
    assert len(target) == 6
    assert sum(abs(c.base.score - c.expected) for c in target) == 8
    assert sum(abs(c.adapter.score - c.expected) for c in target) == 8


@pytest.mark.parametrize("allowed", [False, True])
def test_archive_route_requires_admin_and_does_not_load_validation_rows(allowed):
    app = FastAPI()
    app.include_router(router)

    def admin_gate():
        if not allowed:
            raise HTTPException(403, "Admin required")
        return object()

    app.dependency_overrides[require_admin] = admin_gate
    with TestClient(app) as client:
        response = client.get("/admin/model-validations/fine-tuning-results")
    assert response.status_code == (200 if allowed else 403)
    if allowed:
        assert len(response.json()["experiments"]) == 3
