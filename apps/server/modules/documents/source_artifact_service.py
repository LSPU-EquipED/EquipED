"""Read-only ownership and integrity seam for immutable ITSO source artifacts."""

from __future__ import annotations

import hashlib
import json
import uuid

from equiped_harness.itso.history_contracts import (
    CanonicalSourceSnapshot,
    ReferenceCandidate,
    SourcePage,
)
from server.modules.documents.models import Document, UserDocument
from server.modules.documents.source_artifacts import DocumentSourceSnapshot
from sqlalchemy import select
from sqlalchemy.orm import Session


def require_owned_source_document(
    db: Session, document_id: uuid.UUID, owner_id: uuid.UUID
) -> Document:
    document = db.scalar(select(Document).where(Document.document_id == document_id))
    if document is not None and document.uploaded_by != owner_id:
        linked_slm = document.source_type == "slm" and db.scalar(
            select(UserDocument.user_document_id).where(
                UserDocument.document_id == document_id,
                UserDocument.user_id == owner_id,
            )
        )
        if not linked_slm:
            document = None
    if document is None:
        raise LookupError("owned document not found")
    return document


def load_owned_source_snapshot(
    db: Session,
    *,
    snapshot_id: uuid.UUID,
    document_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> CanonicalSourceSnapshot:
    """Replay frozen bytes without re-extracting or comparing future OCR code."""
    document = require_owned_source_document(db, document_id, owner_id)
    row = db.scalar(
        select(DocumentSourceSnapshot).where(
            DocumentSourceSnapshot.snapshot_id == snapshot_id,
            DocumentSourceSnapshot.document_id == document_id,
            DocumentSourceSnapshot.owner_id == document.uploaded_by,
        )
    )
    if row is None:
        raise LookupError("owned source snapshot not found")
    actual_inventory_hash = hashlib.sha256(
        json.dumps(
            {
                "pages": row.page_map,
                "references": row.reference_inventory,
                "inventory_version": row.inventory_version,
                "inventory_complete": row.inventory_complete,
                "inventory_uncertainties": row.inventory_uncertainties,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    if actual_inventory_hash != row.inventory_hash:
        raise ValueError("frozen source inventory hash mismatch")
    return CanonicalSourceSnapshot(
        source_id=str(document_id),
        source_hash=row.canonical_hash,
        raw_pdf_hash=row.source_hash,
        canonical_text=row.canonical_text,
        pages=tuple(SourcePage.model_validate(page) for page in row.page_map),
        references=tuple(
            ReferenceCandidate.model_validate(ref) for ref in row.reference_inventory
        ),
        extractor_version=row.extractor_version,
        inventory_complete=row.inventory_complete,
        inventory_version=row.inventory_version,
        inventory_uncertainties=tuple(row.inventory_uncertainties),
    )


__all__ = ["load_owned_source_snapshot", "require_owned_source_document"]
