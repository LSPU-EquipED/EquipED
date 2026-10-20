from equiped_harness.itso.history_contracts import (
    SourceSpan,
    build_source_snapshot,
    text_hash,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from server.modules.evaluations.itso.assessment_service import _project_source_quotes
from server.modules.evaluations.itso.router import router


def test_public_assessment_quote_is_exact_frozen_source_excerpt():
    text = "Header\nExact source wording.\nFooter"
    start = text.index("Exact source wording.")
    source = build_source_snapshot("document-id", text, ((1, 0, len(text)),), "test.v1")
    span = SourceSpan(
        source_id="document-id",
        start_offset=start,
        end_offset=start + len("Exact source wording."),
        page_number=1,
        text_hash=text_hash("Exact source wording."),
    )
    projected = {
        "criteria": [{"evidence": [{"source_spans": [span.model_dump(mode="json")]}]}]
    }

    result = _project_source_quotes(projected, source)

    assert result["criteria"][0]["evidence"][0]["source_spans"][0]["quote"] == (
        "Exact source wording."
    )
    assert "quote" not in span.model_dump(mode="json")


def test_retired_governance_and_preparation_paths_are_not_routed():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)

    document_id = "00000000-0000-0000-0000-000000000001"
    evaluation_id = "00000000-0000-0000-0000-000000000001"
    paths = (
        ("GET", "/api/v1/evaluations/itso/policies"),
        ("POST", "/api/v1/evaluations/itso/policies"),
        ("POST", "/api/v1/evaluations/itso/preflight"),
        ("POST", f"/api/v1/documents/{document_id}/source-preparation"),
        ("GET", f"/api/v1/documents/{document_id}/itso/attachments"),
        (
            "POST",
            f"/api/v1/evaluations/{evaluation_id}/itso/facts/fact/decision",
        ),
    )
    for method, path in paths:
        response = client.request(method, path, json={})
        assert response.status_code == 404, (method, path, response.text)
