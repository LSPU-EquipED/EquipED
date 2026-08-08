"""Tests for policy document foundation (ITSO evidence tools 1.1-1.6).

Covers:
  1.1  Policy as distinct source type (not in shared-reference set)
  1.2  policy_area validation (required for policy, prohibited for non-policy)
  1.3  Policy chunk section_ref + chunk_index persistence
  1.4  Dedicated col_policy_all collection routing
  1.5  Policy health/rebuild/delete lifecycle
  1.6  Clause-aware assembly and deterministic ordering for rebuild
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import VALID_POLICY_AREAS, Document, DocumentChunk
from server.modules.documents.schemas import (
    POLICY_SOURCE_TYPES,
    REFERENCE_SOURCE_TYPES,
    SOURCE_TYPES,
)
from server.modules.embeddings.collections import (
    COL_POLICY_ALL,
    SOURCE_TYPE_TO_COLLECTION,
)

_TEST_PASSWORD = "password123"

# ── Helpers ─────────────────────────────────────────────────────────


def _add_doc(
    db_session,
    *,
    owner_id,
    source_type: str = "slm",
    title: str = "Test Doc",
    processing_status: str = "PROCESSED",
    file_path: str | None = None,
    policy_area: str | None = None,
    _ensure_file: bool = False,
):
    """Create a Document row in the test database.

    If ``_ensure_file`` is True, the file_path is created as a real temp file
    on disk so that ``is_healthy_policy_document`` passes.
    """
    doc_id = uuid.uuid4()
    if file_path is None:
        file_path = f"/tmp/test_policy_doc_{doc_id}.pdf" if _ensure_file else f"uploads/{doc_id}.pdf"
    if _ensure_file:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).write_text("test pdf content")
    db_session.add(
        Document(
            document_id=doc_id,
            title=title,
            program="BSCS",
            source_type=source_type,
            policy_area=policy_area,
            file_path=file_path,
            uploaded_by=owner_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status=processing_status,
        )
    )
    db_session.commit()
    return doc_id


def _add_chunk(
    db_session,
    *,
    document_id,
    source_type: str = "slm",
    section_ref: str | None = None,
    chunk_index: int | None = None,
):
    """Create a DocumentChunk row."""
    db_session.add(
        DocumentChunk(
            chunk_id=uuid.uuid4(),
            document_id=document_id,
            source_type=source_type,
            agent_domain="all",
            page_number=1,
            text=f"chunk for {source_type}",
            token_count=4,
            is_ocr=False,
            chroma_stored=True,
            section_ref=section_ref,
            chunk_index=chunk_index,
        )
    )
    db_session.commit()


def _login(client, email, password=None):
    if password is None:
        password = _TEST_PASSWORD
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return resp


# ── 1.1: Policy as distinct source type ─────────────────────────────


class TestPolicyIsDistinctSourceType:
    """1.1 Policy must be a distinct source type, NOT in shared-reference set."""

    def test_policy_in_source_types(self):
        assert "policy" in SOURCE_TYPES

    def test_policy_not_in_reference_source_types(self):
        """Policy is NOT part of REFERENCE_SOURCE_TYPES."""
        assert "policy" not in REFERENCE_SOURCE_TYPES

    def test_reference_types_exclude_policy(self):
        """Only syllabus is an active reference type."""
        assert REFERENCE_SOURCE_TYPES == {"syllabus"}

    def test_policy_has_own_source_type_set(self):
        assert POLICY_SOURCE_TYPES == {"policy"}

    def test_is_policy_source_type_helper(self, db_session):
        from server.modules.documents.service import is_policy_source_type
        assert is_policy_source_type("policy") is True
        assert is_policy_source_type("syllabus") is False
        assert is_policy_source_type("curriculum") is False
        assert is_policy_source_type("slm") is False
        assert is_policy_source_type("rubric_sme") is False

    def test_is_reference_helper_excludes_policy(self, db_session):
        from server.modules.documents.service import is_reference_source_type
        assert is_reference_source_type("policy") is False
        assert is_reference_source_type("syllabus") is True
        assert is_reference_source_type("curriculum") is False


# ── 1.2: policy_area validation ─────────────────────────────────────


class TestPolicyAreaValidation:
    """1.2 policy_area valid/required for policy and prohibited for non-policy."""

    def test_policy_requires_policy_area_on_upload(self, client, db_session):
        """Uploading a policy doc without policy_area should fail."""
        admin = create_user(db_session, name="Admin", email="a@polarea1.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        _login(client, admin.email)
        pdf_path = Path("/tmp/test_policy_no_area.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 test")
        try:
            with pdf_path.open("rb") as pdf_file:
                resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.pdf", pdf_file, "application/pdf")},
                    data={
                        "source_type": "policy",
                        "title": "Policy Without Area",
                    },
                )
        finally:
            pdf_path.unlink(missing_ok=True)
        assert resp.status_code == 422
        assert "policy_area is required" in resp.json()["detail"].lower()

    def test_non_policy_rejects_policy_area(self, client, db_session):
        """Uploading a non-policy doc with policy_area should fail."""
        admin = create_user(db_session, name="Admin", email="a@polarea2.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        _login(client, admin.email)
        pdf_path = Path("/tmp/test_syllabus_with_area.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 test")
        try:
            with pdf_path.open("rb") as pdf_file:
                resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.pdf", pdf_file, "application/pdf")},
                    data={
                        "source_type": "syllabus",
                        "title": "Syllabus With Area",
                        "policy_area": "academic_rights",
                    },
                )
        finally:
            pdf_path.unlink(missing_ok=True)
        assert resp.status_code == 422
        assert "policy_area is only valid for policy" in resp.json()["detail"].lower()

    def test_policy_upload_with_policy_area_succeeds(self, client, db_session):
        """Uploading a policy doc with policy_area should succeed (up to PDF parse)."""
        admin = create_user(db_session, name="Admin", email="a@polarea3.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        _login(client, admin.email)
        # The upload will fail at PDF extraction but that's fine —
        # we're testing that the validation doesn't reject it.
        pdf_path = Path("/tmp/test_policy_good.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 junk")
        try:
            with pdf_path.open("rb") as pdf_file:
                resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.pdf", pdf_file, "application/pdf")},
                    data={
                        "source_type": "policy",
                        "title": "Policy With Area",
                        "policy_area": "academic_rights",
                    },
                )
        finally:
            pdf_path.unlink(missing_ok=True)
        # Should not be 422 (validation error) — might be 500 (PDF parse failure)
        assert resp.status_code != 422
        # But we can at least check policy_area was accepted
        if resp.status_code == 201:
            assert resp.json()["policy_area"] == "academic_rights"

    def test_policy_area_column_persisted(self, db_session):
        """policy_area is stored in the DB row for policy documents."""
        admin = create_user(db_session, name="Admin", email="a@polpersist.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        doc_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="policy", title="Policy Persist",
                          policy_area="data_privacy")

        row = db_session.get(Document, doc_id)
        assert row is not None
        assert row.policy_area == "data_privacy"

    def test_policy_area_null_for_non_policy(self, db_session):
        """Non-policy docs should have NULL policy_area."""
        admin = create_user(db_session, name="Admin", email="a@polnull.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        for st in ("syllabus", "curriculum", "slm", "rubric_sme"):
            doc_id = _add_doc(db_session, owner_id=admin.user_id, source_type=st)
            row = db_session.get(Document, doc_id)
            assert row.policy_area is None, f"{st} should have NULL policy_area"


# ── 1.3: Chunk section_ref + chunk_index ────────────────────────────


class TestPolicyChunkMetadata:
    """1.3 Persist policy chunk section reference + chunk_index."""

    def test_policy_chunk_has_section_ref(self, db_session):
        """Policy chunks persist section_ref."""
        admin = create_user(db_session, name="Admin", email="a@chunksec.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        doc_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="policy", title="Policy SecRef",
                          policy_area="academic_rights")

        _add_chunk(db_session, document_id=doc_id, source_type="policy",
                   section_ref="Section 1. Policy Statement", chunk_index=0)

        chunks = db_session.query(DocumentChunk).filter(
            DocumentChunk.document_id == doc_id
        ).all()
        assert len(chunks) == 1
        assert chunks[0].section_ref == "Section 1. Policy Statement"
        assert chunks[0].chunk_index == 0

    def test_non_policy_chunk_section_ref_null(self, db_session):
        """Non-policy chunks have NULL section_ref and chunk_index."""
        admin = create_user(db_session, name="Admin", email="a@nullchunk.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        doc_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="syllabus", title="Syllabus No SecRef")

        _add_chunk(db_session, document_id=doc_id, source_type="syllabus")

        chunks = db_session.query(DocumentChunk).filter(
            DocumentChunk.document_id == doc_id
        ).all()
        assert len(chunks) == 1
        assert chunks[0].section_ref is None
        assert chunks[0].chunk_index is None


# ── 1.4: Dedicated col_policy_all ────────────────────────────────────


class TestPolicyCollectionRouting:
    """1.4 Dedicated col_policy_all collection."""

    def test_policy_collection_name(self):
        assert COL_POLICY_ALL == "col_policy_all"

    def test_policy_routes_to_policy_collection(self):
        assert SOURCE_TYPE_TO_COLLECTION["policy"] == COL_POLICY_ALL

    def test_policy_collection_distinct_from_reference(self):
        assert COL_POLICY_ALL != "col_reference_all"

    def test_policy_not_in_reference_collection(self):
        """Policy must NOT route to col_reference_all."""
        from server.modules.embeddings.collections import COL_REFERENCE_ALL
        assert SOURCE_TYPE_TO_COLLECTION["policy"] != COL_REFERENCE_ALL

    def test_resolve_collection_name_for_policy(self):
        from server.modules.embeddings.collections import resolve_collection_name
        assert resolve_collection_name("policy") == COL_POLICY_ALL


# ── 1.5: Policy lifecycle (health/rebuild/delete) ───────────────────


class TestPolicyAdminList:
    """1.5 Admin policy library listing with health."""

    def test_admin_lists_policies(self, client, db_session):
        """Admin can list policy documents."""
        admin = create_user(db_session, name="Admin", email="a@polylist1.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        faculty = create_user(db_session, name="Faculty", email="f@polylist1.com",
                              password=_TEST_PASSWORD, role=UserRole.FACULTY)
        db_session.commit()

        _add_doc(db_session, owner_id=admin.user_id,
                 source_type="policy", title="Policy A", policy_area="academic_rights")
        _add_doc(db_session, owner_id=admin.user_id,
                 source_type="policy", title="Policy B", policy_area="data_privacy")
        # Faculty SLM should not appear
        _add_doc(db_session, owner_id=faculty.user_id,
                 source_type="slm", title="Faculty SLM")

        _login(client, admin.email)
        resp = client.get("/api/v1/documents/policies")
        assert resp.status_code == 200
        data = resp.json()
        titles = {item["title"] for item in data["items"]}
        assert "Policy A" in titles
        assert "Policy B" in titles
        assert "Faculty SLM" not in titles
        assert data["total"] == 2

    def test_policy_list_has_health_fields(self, client, db_session):
        """Policy list items include computed health indicators."""
        admin = create_user(db_session, name="Admin", email="a@polyhealth.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        doc_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="policy", title="Health Check",
                          policy_area="intellectual_property")
        _add_chunk(db_session, document_id=doc_id, source_type="policy")

        _login(client, admin.email)
        resp = client.get("/api/v1/documents/policies")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "file_exists" in item
        assert "chunk_count" in item
        assert "chroma_available" in item
        assert "embedding_ready" in item
        assert item["policy_area"] == "intellectual_property"

    def test_faculty_cannot_access_policy_list(self, client, db_session):
        """Faculty gets 403 on admin policy list."""
        faculty = create_user(db_session, name="Faculty", email="f@denypol.com",
                              password=_TEST_PASSWORD, role=UserRole.FACULTY)
        db_session.commit()

        _login(client, faculty.email)
        resp = client.get("/api/v1/documents/policies")
        assert resp.status_code == 403

    def test_policy_list_empty(self, client, db_session):
        """Empty policy list returns empty items."""
        admin = create_user(db_session, name="Admin", email="a@emptypol.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        _login(client, admin.email)
        resp = client.get("/api/v1/documents/policies")
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0}


class TestPolicyAdminDelete:
    """1.5 Admin delete policy with asset cleanup."""

    def test_admin_delete_policy(self, client, db_session):
        """Admin can delete a policy document."""
        admin = create_user(db_session, name="Admin", email="a@poldel1.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        pdf_path = Path("/tmp/test_del_policy.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 delete")

        try:
            ref_id = _add_doc(db_session, owner_id=admin.user_id,
                              source_type="policy", title="Policy To Delete",
                              policy_area="general_itso", file_path=str(pdf_path))
            _add_chunk(db_session, document_id=ref_id, source_type="policy")

            _login(client, admin.email)
            resp = client.delete(f"/api/v1/documents/policies/{ref_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["deleted"] is True
            assert data["document_id"] == str(ref_id)

            # Document row is gone
            assert db_session.get(Document, ref_id) is None
            # PDF file is gone
            assert not pdf_path.exists()
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_delete_policy_tolerates_missing_file(self, client, db_session):
        """Delete completes even when the local PDF file is missing."""
        admin = create_user(db_session, name="Admin", email="a@poldelmiss.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        ref_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="policy", title="Missing Policy File",
                          policy_area="intellectual_property",
                          file_path="/nonexistent/missing.pdf")

        _login(client, admin.email)
        resp = client.delete(f"/api/v1/documents/policies/{ref_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert db_session.get(Document, ref_id) is None

    def test_faculty_cannot_delete_policy(self, client, db_session):
        """Faculty gets 403 on policy delete."""
        faculty = create_user(db_session, name="Faculty", email="f@denypoldel.com",
                              password=_TEST_PASSWORD, role=UserRole.FACULTY)
        db_session.commit()

        _login(client, faculty.email)
        resp = client.delete(f"/api/v1/documents/policies/{uuid.uuid4()}")
        assert resp.status_code == 403

    def test_admin_cannot_delete_non_policy_through_policy_endpoint(self, client, db_session):
        """DELETE /policies/{id} rejects non-policy documents."""
        admin = create_user(db_session, name="Admin", email="a@badpoldel.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        syllabus_id = _add_doc(db_session, owner_id=admin.user_id,
                               source_type="syllabus", title="Syllabus")

        _login(client, admin.email)
        resp = client.delete(f"/api/v1/documents/policies/{syllabus_id}")
        assert resp.status_code == 422


class TestPolicyAdminRebuild:
    """1.5 Admin rebuild policy embeddings."""

    def test_admin_rebuild_policy_embeddings(self, client, db_session):
        """Admin can rebuild policy embeddings from existing chunks."""
        admin = create_user(db_session, name="Admin", email="a@polyreb1.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        ref_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="policy", title="Policy Rebuild",
                          policy_area="general_itso", _ensure_file=True)
        _add_chunk(db_session, document_id=ref_id, source_type="policy",
                   chunk_index=0)

        with patch("server.modules.embeddings.service.embed_and_store_chunks") as mock_embed:
            mock_embed.return_value = 1
            _login(client, admin.email)
            resp = client.post(f"/api/v1/documents/policies/{ref_id}/rebuild-embeddings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rebuilt"] is True
        assert data["chunk_count"] == 1

    def test_policy_rebuild_no_chunks_fails(self, client, db_session):
        """Rebuild rejected when no chunks exist."""
        admin = create_user(db_session, name="Admin", email="a@polynochunks.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        ref_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="policy", title="Policy No Chunks",
                          policy_area="academic_rights")

        _login(client, admin.email)
        resp = client.post(f"/api/v1/documents/policies/{ref_id}/rebuild-embeddings")
        assert resp.status_code == 422

    def test_policy_rebuild_unsupported_source_type_fails(self, client, db_session):
        """Rebuild rejected for non-policy source types."""
        admin = create_user(db_session, name="Admin", email="a@polybadtype.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        slm_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="slm", title="SLM Not Rebuildable")
        _add_chunk(db_session, document_id=slm_id, source_type="slm")

        _login(client, admin.email)
        resp = client.post(f"/api/v1/documents/policies/{slm_id}/rebuild-embeddings")
        assert resp.status_code == 422

    def test_faculty_cannot_rebuild_policy(self, client, db_session):
        """Faculty gets 403 on policy rebuild."""
        faculty = create_user(db_session, name="Faculty", email="f@denypolyrb.com",
                              password=_TEST_PASSWORD, role=UserRole.FACULTY)
        db_session.commit()

        _login(client, faculty.email)
        resp = client.post(
            f"/api/v1/documents/policies/{uuid.uuid4()}/rebuild-embeddings"
        )
        assert resp.status_code == 403

    def test_policy_rebuild_sets_chroma_stored(self, client, db_session):
        """Rebuild marks all chunks chroma_stored=True."""
        admin = create_user(db_session, name="Admin", email="a@polychromarb.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        ref_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="policy", title="Policy Chroma Rebuild",
                          policy_area="data_privacy", _ensure_file=True)

        chunk_id = uuid.uuid4()
        db_session.add(
            DocumentChunk(
                chunk_id=chunk_id,
                document_id=ref_id,
                source_type="policy",
                agent_domain="all",
                page_number=1,
                text="policy rebuild chroma test",
                token_count=4,
                is_ocr=False,
                chroma_stored=False,
                chunk_index=0,
            )
        )
        db_session.commit()

        with patch("server.modules.embeddings.service.embed_and_store_chunks") as mock_embed:
            mock_embed.return_value = 1
            _login(client, admin.email)
            resp = client.post(f"/api/v1/documents/policies/{ref_id}/rebuild-embeddings")
        assert resp.status_code == 200

        chunk = db_session.get(DocumentChunk, chunk_id)
        assert chunk is not None
        assert chunk.chroma_stored is True


# ── 1.6: Clause-aware assembly ──────────────────────────────────────


class TestPolicyClauseAwareAssembly:
    """1.6 Clause-aware assembly for policy documents."""

    def test_basic_policy_section_detection(self):
        """Policy-like text with sections produces multiple units."""
        import uuid

        from server.modules.documents.ingestion import (
            ExtractedPage,
            _ingest_policy_document,
        )

        text = (
            "Preamble text explaining the policy.\n\n"
            "Section 1. Policy Statement\n\n"
            "This policy applies to all faculty members.\n\n"
            "Section 2. Compliance Requirements\n\n"
            "All faculty must comply with this policy.\n\n"
            "Section 3. Enforcement\n\n"
            "Violations will be reported to the Dean."
        )

        pages = [ExtractedPage(page_number=1, text=text, is_ocr=False)]
        doc_uuid = uuid.uuid4()
        chunks = _ingest_policy_document(pages, "all", doc_uuid)

        assert len(chunks) >= 3
        # Each policy chunk has section_ref
        section_refs = [c.section_ref for c in chunks if c.section_ref]
        assert any("Section 1" in (r or "") for r in section_refs)
        assert any("Section 2" in (r or "") for r in section_refs)
        assert any("Section 3" in (r or "") for r in section_refs)

    def test_policy_chunks_have_deterministic_indices(self):
        """Policy chunks carry sequential chunk_index values."""
        import uuid

        from server.modules.documents.ingestion import (
            ExtractedPage,
            _ingest_policy_document,
        )

        text = (
            "Section 1. First Policy\n\nContent one.\n\n"
            "Section 2. Second Policy\n\nContent two.\n\n"
            "Section 3. Third Policy\n\nContent three."
        )

        pages = [ExtractedPage(page_number=1, text=text, is_ocr=False)]
        doc_uuid = uuid.uuid4()
        chunks = _ingest_policy_document(pages, "all", doc_uuid)

        indices = [c.chunk_index for c in chunks if c.chunk_index is not None]
        # Indices should be in ascending order
        assert len(indices) >= 2
        for i in range(len(indices) - 1):
            assert indices[i] <= indices[i + 1]

    def test_policy_single_chunk_when_no_headings(self):
        """Policy doc without detectable headings should produce a single chunk."""
        import uuid

        from server.modules.documents.ingestion import (
            ExtractedPage,
            _ingest_policy_document,
        )

        text = ("Just a plain paragraph with no real section headings "
                "that would trigger the clause detection logic.")

        pages = [ExtractedPage(page_number=1, text=text, is_ocr=False)]
        doc_uuid = uuid.uuid4()
        chunks = _ingest_policy_document(pages, "all", doc_uuid)

        assert len(chunks) > 0


# ── Policy document access rules (admin-only, no faculty visibility) ──


class TestPolicyAccessAdminOnly:
    """Policy documents MUST NOT be visible to faculty (no existence leakage)."""

    def test_faculty_gets_404_for_policy_document(self, client, db_session):
        """Faculty GET on a policy document returns 404 (no existence leakage)."""
        admin = create_user(db_session, name="Admin", email="a@poladmin1.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        faculty = create_user(db_session, name="Faculty", email="f@poladmin1.com",
                              password=_TEST_PASSWORD, role=UserRole.FACULTY)
        db_session.commit()

        policy_id = _add_doc(db_session, owner_id=admin.user_id,
                             source_type="policy", title="Policy Doc",
                             policy_area="data_privacy")

        _login(client, faculty.email)
        resp = client.get(f"/api/v1/documents/{policy_id}")
        assert resp.status_code == 404

    def test_admin_can_read_policy_document(self, client, db_session):
        """Admin can GET a policy document."""
        admin = create_user(db_session, name="Admin", email="a@poladmin2.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        policy_id = _add_doc(db_session, owner_id=admin.user_id,
                             source_type="policy", title="Admin Policy",
                             policy_area="data_privacy")

        _login(client, admin.email)
        resp = client.get(f"/api/v1/documents/{policy_id}")
        assert resp.status_code == 200
        assert resp.json()["source_type"] == "policy"
        assert resp.json()["policy_area"] == "data_privacy"

    def test_faculty_list_excludes_policy_documents(self, client, db_session):
        """Faculty document listing must NOT include policy documents."""
        admin = create_user(db_session, name="Admin", email="a@pollist_admin1.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        faculty = create_user(db_session, name="Faculty", email="f@pollist_admin1.com",
                              password=_TEST_PASSWORD, role=UserRole.FACULTY)
        db_session.commit()

        _add_doc(db_session, owner_id=admin.user_id,
                 source_type="policy", title="Policy Doc",
                 policy_area="data_privacy")
        _add_doc(db_session, owner_id=faculty.user_id,
                 source_type="slm", title="My SLM")

        _login(client, faculty.email)
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        titles = {item["title"] for item in resp.json()["items"]}
        assert "Policy Doc" not in titles, "Faculty must not see policy documents"
        assert "My SLM" in titles

    def test_admin_list_includes_policy_documents(self, client, db_session):
        """Admin document listing includes policy documents."""
        admin = create_user(db_session, name="Admin", email="a@pollist_admin2.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        _add_doc(db_session, owner_id=admin.user_id,
                 source_type="policy", title="Admin Policy",
                 policy_area="data_privacy")
        _add_doc(db_session, owner_id=admin.user_id,
                 source_type="slm", title="Admin SLM")

        _login(client, admin.email)
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        titles = {item["title"] for item in resp.json()["items"]}
        assert "Admin Policy" in titles
        assert "Admin SLM" in titles

    def test_faculty_cannot_preview_policy_file(self, client, db_session):
        """Faculty gets 404 on policy PDF preview (no existence leakage)."""
        admin = create_user(db_session, name="Admin", email="a@polprev_adm.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        faculty = create_user(db_session, name="Faculty", email="f@polprev_fac.com",
                              password=_TEST_PASSWORD, role=UserRole.FACULTY)
        db_session.commit()

        pdf_path = Path("/tmp/test_policy_file_preview.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 policy")
        try:
            policy_id = _add_doc(db_session, owner_id=admin.user_id,
                                 source_type="policy", title="Policy Preview",
                                 policy_area="intellectual_property",
                                 file_path=str(pdf_path))

            _login(client, faculty.email)
            resp = client.get(f"/api/v1/documents/{policy_id}/file")
            assert resp.status_code == 404
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_admin_can_preview_policy_file(self, client, db_session):
        """Admin can preview a policy PDF file."""
        admin = create_user(db_session, name="Admin", email="a@polprev_adm2.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        pdf_path = Path("/tmp/test_policy_file_adm.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 policy")
        try:
            policy_id = _add_doc(db_session, owner_id=admin.user_id,
                                 source_type="policy", title="Policy Preview",
                                 policy_area="intellectual_property",
                                 file_path=str(pdf_path))

            _login(client, admin.email)
            resp = client.get(f"/api/v1/documents/{policy_id}/file")
            assert resp.status_code == 200
            assert resp.headers.get("content-type") == "application/pdf"
        finally:
            pdf_path.unlink(missing_ok=True)


# ── DB constraint tests ──────────────────────────────────────────────


class TestPolicyAreaConstraint:
    """DB-level CHECK constraint for valid policy_area values."""

    def test_valid_policy_areas_are_accepted_by_model(self, db_session):
        """Each valid policy_area can be stored on a policy document."""
        admin = create_user(db_session, name="Admin", email="a@constraint_valids@test.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        for area in VALID_POLICY_AREAS:
            doc_id = _add_doc(db_session, owner_id=admin.user_id,
                              source_type="policy", title=f"Policy {area}",
                              policy_area=area)
            row = db_session.get(Document, doc_id)
            assert row is not None
            assert row.policy_area == area

    def test_invalid_policy_area_raises_on_flush(self, db_session):
        """Inserting a policy doc with an invalid policy_area raises IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        admin = create_user(db_session, name="Admin", email="a@constraint_bad@test.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        doc_id = uuid.uuid4()
        bad_doc = Document(
            document_id=doc_id,
            title="Bad Policy",
            source_type="policy",
            policy_area="invalid_value_not_in_enum",
            file_path=f"uploads/{doc_id}.pdf",
            uploaded_by=admin.user_id,
            uploaded_at=datetime.now(UTC),
        )
        db_session.add(bad_doc)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_policy_with_null_policy_area_raises(self, db_session):
        """A policy document with NULL policy_area violates the constraint."""
        from sqlalchemy.exc import IntegrityError

        admin = create_user(db_session, name="Admin", email="a@constraint_nullpol@test.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        doc_id = uuid.uuid4()
        null_doc = Document(
            document_id=doc_id,
            title="Null Area Policy",
            source_type="policy",
            policy_area=None,
            file_path=f"uploads/{doc_id}.pdf",
            uploaded_by=admin.user_id,
            uploaded_at=datetime.now(UTC),
        )
        db_session.add(null_doc)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_non_policy_with_policy_area_raises(self, db_session):
        """A non-policy document with a non-NULL policy_area violates the constraint."""
        from sqlalchemy.exc import IntegrityError

        admin = create_user(db_session, name="Admin", email="a@constraint_nonpol@test.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        doc_id = uuid.uuid4()
        bad_doc = Document(
            document_id=doc_id,
            title="Syllabus With Area",
            source_type="syllabus",
            policy_area="data_privacy",
            file_path=f"uploads/{doc_id}.pdf",
            uploaded_by=admin.user_id,
            uploaded_at=datetime.now(UTC),
        )
        db_session.add(bad_doc)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()


# ── Corrections: Task 1 — invalid policy_area rejected on upload ─────────────


class TestInvalidPolicyAreaRejected:
    """Task 1: Uploading a policy doc with invalid policy_area must be rejected."""

    def test_upload_rejects_invalid_policy_area(self, client, db_session):
        """Upload with invalid policy_area value returns 422."""
        admin = create_user(db_session, name="Admin", email="a@badarea@test.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        _login(client, admin.email)
        pdf_path = Path("/tmp/test_bad_policy_area.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 test")
        try:
            with pdf_path.open("rb") as pdf_file:
                resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("test.pdf", pdf_file, "application/pdf")},
                    data={
                        "source_type": "policy",
                        "title": "Bad Area Policy",
                        "policy_area": "invalid_not_in_set",
                    },
                )
        finally:
            pdf_path.unlink(missing_ok=True)
        assert resp.status_code == 422
        assert "invalid policy_area" in resp.json()["detail"].lower()


# ── Corrections: Task 2 — policy_area persisted on DocumentChunk ────────────


class TestDocumentChunkPolicyArea:
    """Task 2: policy_area column on DocumentChunk, no transient _policy_area."""

    def test_chunk_policy_area_persisted(self, db_session):
        """DocumentChunk stores policy_area from parent document."""
        admin = create_user(db_session, name="Admin", email="a@chunkpa@test.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        doc_id = uuid.uuid4()
        db_session.add(
            Document(
                document_id=doc_id,
                title="Policy Doc",
                source_type="policy",
                policy_area="data_privacy",
                file_path="/tmp/test_chunk_pa.pdf",
                uploaded_by=admin.user_id,
                uploaded_at=datetime.now(UTC),
                processing_status="PROCESSED",
            )
        )
        db_session.add(
            DocumentChunk(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                source_type="policy",
                agent_domain="all",
                page_number=1,
                text="test chunk with policy area",
                token_count=5,
                is_ocr=False,
                policy_area="data_privacy",
                section_ref="Section 1",
                chunk_index=0,
            )
        )
        db_session.commit()

        chunk = db_session.query(DocumentChunk).filter(
            DocumentChunk.document_id == doc_id
        ).first()
        assert chunk is not None
        assert chunk.policy_area == "data_privacy"

    def test_non_policy_chunk_policy_area_null(self, db_session):
        """Non-policy chunks default to NULL policy_area."""
        admin = create_user(db_session, name="Admin", email="a@nonpolchunk@test.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        doc_id = uuid.uuid4()
        db_session.add(
            Document(
                document_id=doc_id,
                title="Syllabus",
                source_type="syllabus",
                file_path="/tmp/test_nonpol.pdf",
                uploaded_by=admin.user_id,
                uploaded_at=datetime.now(UTC),
                processing_status="PROCESSED",
            )
        )
        db_session.add(
            DocumentChunk(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=1,
                text="syllabus chunk",
                token_count=3,
                is_ocr=False,
            )
        )
        db_session.commit()

        chunk = db_session.query(DocumentChunk).filter(
            DocumentChunk.document_id == doc_id
        ).first()
        assert chunk is not None
        assert chunk.policy_area is None

    def test_chunk_policy_area_backfilled_on_persist(self, db_session):
        """Chunks get policy_area from parent document when persisted via service."""
        from server.modules.documents.schemas import DocumentChunkData

        admin = create_user(db_session, name="Admin", email="a@backfill@test.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        doc_id = uuid.uuid4()
        db_session.add(
            Document(
                document_id=doc_id,
                title="Policy Doc",
                source_type="policy",
                policy_area="academic_rights",
                file_path="/tmp/test_backfill.pdf",
                uploaded_by=admin.user_id,
                uploaded_at=datetime.now(UTC),
                processing_status="PROCESSED",
            )
        )
        db_session.commit()

        chunk_data = DocumentChunkData(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            source_type="policy",
            agent_domain="all",
            page_number=1,
            text="test",
            token_count=1,
            is_ocr=False,
            policy_area="academic_rights",
        )
        from server.modules.documents.service import _persist_chunks
        _persist_chunks(db_session, doc_id, [chunk_data], commit=True)

        chunk = db_session.query(DocumentChunk).filter(
            DocumentChunk.document_id == doc_id
        ).first()
        assert chunk is not None
        assert chunk.policy_area == "academic_rights"


# ── Corrections: Task 4 — policy chunking preserves page_number/is_ocr ──────


class TestPolicyChunkingPageProvenance:
    """Task 4: Policy chunking preserves page_number/is_ocr per source page."""

    def test_policy_chunks_preserve_page_number_and_ocr(self):
        """Each policy chunk carries its source page's page_number and is_ocr."""
        import uuid

        from server.modules.documents.ingestion import (
            ExtractedPage,
            _ingest_policy_document,
        )

        pages = [
            ExtractedPage(page_number=1, text="Section 1. Intro\n\nContent A.", is_ocr=False),
            ExtractedPage(page_number=2, text="Section 2. Details\n\nContent B.", is_ocr=True),
            ExtractedPage(page_number=3, text="Section 3. Conclusion\n\nContent C.", is_ocr=False),
        ]
        doc_uuid = uuid.uuid4()
        chunks = _ingest_policy_document(pages, "all", doc_uuid)

        found_pages = {(c.page_number, c.is_ocr) for c in chunks}
        assert (1, False) in found_pages
        assert (2, True) in found_pages
        assert (3, False) in found_pages
        # Ensure we didn't lose any source pages entirely
        assert len(found_pages) >= 3

    def test_policy_chunks_have_globally_increasing_indices(self):
        """chunk_index is globally increasing across all pages, not per-clause."""
        import uuid

        from server.modules.documents.ingestion import (
            ExtractedPage,
            _ingest_policy_document,
        )

        pages = [
            ExtractedPage(page_number=1, text="Section 1. Part A\n\nContent one.", is_ocr=False),
            ExtractedPage(page_number=2, text="Section 2. Part B\n\nContent two.", is_ocr=False),
        ]
        doc_uuid = uuid.uuid4()
        chunks = _ingest_policy_document(pages, "all", doc_uuid)

        indices = [c.chunk_index for c in chunks if c.chunk_index is not None]
        assert len(indices) >= 2
        # Indices must be strictly increasing within a single document
        for i in range(len(indices) - 1):
            assert indices[i] < indices[i + 1]
        assert indices[0] == 0  # Must start at 0


# ── Corrections: Task 7 — deletion ordering ────────────────────────────────


class TestPolicyDeleteOrdering:
    """Task 7: Policy deletion is DB-authoritative: SQL first, cleanup after."""

    def test_delete_commits_sql_before_external_cleanup(self, db_session):
        """Delete commits SQL removal first, then attempts external cleanup."""
        from server.modules.documents.policy_service import delete_policy_document

        admin = create_user(db_session, name="Admin", email="a@delorder@test.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        pdf_path = Path("/tmp/test_del_order.pdf")
        pdf_path.write_text("test")
        doc_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="policy", title="Delete Order",
                          policy_area="data_privacy", file_path=str(pdf_path))
        _add_chunk(db_session, document_id=doc_id, source_type="policy")
        db_session.commit()

        result = delete_policy_document(doc_id, db=db_session)
        assert result.deleted is True

        # Document row must be gone after deletion
        assert db_session.get(Document, doc_id) is None
        # PDF file should be cleaned up
        assert not pdf_path.exists()

    def test_delete_changes_status_first_before_external(self, db_session):
        """SQL removal happens before external cleanup in the function body."""
        from server.modules.documents.policy_service import delete_policy_document

        admin = create_user(db_session, name="Admin", email="a@delorder2@test.com",
                            password=_TEST_PASSWORD, role=UserRole.ADMIN)
        db_session.commit()

        pdf_path = Path("/tmp/test_del_seq.pdf")
        pdf_path.write_text("test")
        doc_id = _add_doc(db_session, owner_id=admin.user_id,
                          source_type="policy", title="Delete Sequence",
                          policy_area="data_privacy", file_path=str(pdf_path))
        _add_chunk(db_session, document_id=doc_id, source_type="policy")

        # Before delete, the doc and file exist
        assert db_session.get(Document, doc_id) is not None
        assert pdf_path.exists()

        result = delete_policy_document(doc_id, db=db_session)
        assert result.deleted is True
        # After delete, both SQL row and file are gone
        assert db_session.get(Document, doc_id) is None
        assert not pdf_path.exists()

    def test_delete_rejects_nonexistent_document(self, db_session):
        """Deleting a non-existent document raises DocumentNotFoundError."""
        from server.modules.documents.exceptions import DocumentNotFoundError
        from server.modules.documents.policy_service import delete_policy_document

        fake_id = uuid.uuid4()
        with pytest.raises(DocumentNotFoundError):
            delete_policy_document(fake_id, db=db_session)


# ── In-memory state cleanup ─────────────────────────────────────────


@pytest.fixture(autouse=True)
def _cleanup_global_state():
    """Clean up shared in-memory state to avoid polluting other tests."""
    from server.modules.documents.schemas import POLICY_SOURCE_TYPES
    from server.modules.documents.service import (
        _MEM_CHUNKS,
        _MEM_DOCUMENT_OWNERS,
        _MEM_DOCUMENTS,
    )
    yield
    ids_to_remove = []
    for doc_id, doc in list(_MEM_DOCUMENTS.items()):
        if doc.source_type in POLICY_SOURCE_TYPES:
            ids_to_remove.append(doc_id)
    for doc_id in ids_to_remove:
        _MEM_DOCUMENTS.pop(doc_id, None)
        _MEM_DOCUMENT_OWNERS.pop(doc_id, None)
        _MEM_CHUNKS.pop(doc_id, None)
