"""Read-only ownership and integrity checks for historical source artifacts."""

import hashlib
import json
from uuid import uuid4

import pytest
from equiped_harness.agents.itso.compatibility.contracts import build_source_snapshot

from server.modules.auth.models import User, UserRole
from server.modules.documents.models import Document, UserDocument
from server.modules.documents.source_artifact_service import load_owned_source_snapshot
from server.modules.documents.source_artifacts import DocumentSourceSnapshot


@pytest.fixture()
def owned_document(db_session, seeded_user):
    document = Document(
        title="Synthetic source",
        source_type="slm",
        file_path="synthetic.pdf",
        uploaded_by=seeded_user.user_id,
        processing_status="PROCESSED",
    )
    db_session.add(document)
    db_session.flush()
    text = "Synthetic\n\n[1] Test reference (2024)"
    source = build_source_snapshot(
        str(document.document_id),
        text,
        ((1, 0, 9), (2, 11, len(text))),
        "synthetic.v1",
        raw_pdf_hash="a" * 64,
    )
    page_map = [page.model_dump(mode="json") for page in source.pages]
    references = [item.model_dump(mode="json") for item in source.references]
    inventory_version = source.inventory_version
    uncertainties = list(source.inventory_uncertainties)
    inventory_hash = hashlib.sha256(
        json.dumps(
            {
                "pages": page_map,
                "references": references,
                "inventory_version": inventory_version,
                "inventory_complete": source.inventory_complete,
                "inventory_uncertainties": uncertainties,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    snapshot = DocumentSourceSnapshot(
        document_id=document.document_id,
        owner_id=seeded_user.user_id,
        source_hash="a" * 64,
        canonical_hash=source.source_hash,
        extractor_version=source.extractor_version,
        canonicalization_version="coordinator.strip-join.v1",
        canonical_text=text,
        page_map=page_map,
        reference_inventory=references,
        inventory_hash=inventory_hash,
        inventory_version=inventory_version,
        inventory_complete=source.inventory_complete,
        inventory_uncertainties=uncertainties,
    )
    db_session.add(snapshot)
    db_session.commit()
    return document, snapshot


def test_owned_snapshot_frozen_replay_and_fresh_session(db_session, owned_document):
    document, row = owned_document
    from sqlalchemy.orm import Session

    with Session(db_session.get_bind()) as fresh:
        artifact = load_owned_source_snapshot(
            fresh,
            snapshot_id=row.snapshot_id,
            document_id=document.document_id,
            owner_id=document.uploaded_by,
        )
        assert artifact.canonical_text == row.canonical_text
        assert artifact.raw_pdf_hash == "a" * 64
        assert not artifact.inventory_complete
        assert len(artifact.pages) == 2
        with pytest.raises(LookupError):
            load_owned_source_snapshot(
                fresh,
                snapshot_id=row.snapshot_id,
                document_id=document.document_id,
                owner_id=uuid4(),
            )


def test_linked_user_can_read_uploader_owned_snapshot(db_session, owned_document):
    document, row = owned_document
    linked = User(
        name="Linked faculty",
        email="linked-source@example.invalid",
        password_hash="test-only",
        role=UserRole.FACULTY,
    )
    db_session.add(linked)
    db_session.flush()
    db_session.add(
        UserDocument(user_id=linked.user_id, document_id=document.document_id)
    )
    db_session.flush()
    artifact = load_owned_source_snapshot(
        db_session,
        snapshot_id=row.snapshot_id,
        document_id=document.document_id,
        owner_id=linked.user_id,
    )
    assert artifact.canonical_text == row.canonical_text
    with pytest.raises(LookupError):
        load_owned_source_snapshot(
            db_session,
            snapshot_id=row.snapshot_id,
            document_id=document.document_id,
            owner_id=uuid4(),
        )


def test_historical_source_payload_tampering_is_rejected(db_session, owned_document):
    document, row = owned_document
    row.page_map[0]["text_hash"] = "0" * 64
    db_session.flush()
    with pytest.raises(ValueError, match="inventory hash"):
        load_owned_source_snapshot(
            db_session,
            snapshot_id=row.snapshot_id,
            document_id=document.document_id,
            owner_id=document.uploaded_by,
        )
