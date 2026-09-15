"""Document upload lifecycle and background processing orchestration."""

from __future__ import annotations

import logging
import uuid

from server.core.config import get_settings
from server.core.database import get_session_factory
from server.modules.embeddings.service import (
    embed_and_store_chunks,
)

from . import persistence
from .models import Document

logger = logging.getLogger(__name__)

# Restricted source types that only admins can upload
_ADMIN_ONLY_SOURCE_TYPES = {
    "syllabus",
    "curriculum",
    "policy",
    "rubric_sme",
    "rubric_coord",
    "rubric_gad",
    "rubric_itso",
}


def embed_document_chunks(document_id: uuid.UUID) -> int:
    """Embed a document's chunks and mark them as stored in Chroma."""

    settings = get_settings()
    db = None
    session = None

    if settings.database_configured:
        session = get_session_factory()()
        db = session

    try:
        if db is not None:
            document = db.get(Document, document_id)
            source_type = document.source_type if document is not None else None
        else:
            document = persistence._MEM_DOCUMENTS.get(document_id)
            source_type = document.source_type if document is not None else None

        if source_type == "slm":
            return 0

        chunks = persistence.get_document_chunks(document_id, db=db)
        upserted = embed_and_store_chunks(chunks)
        if db is not None and upserted:
            persistence.mark_chunks_chroma_stored(
                db, [chunk.chunk_id for chunk in chunks]
            )
        elif db is None and upserted:
            for chunk in chunks:
                if isinstance(chunk, dict):
                    chunk["chroma_stored"] = True
        return upserted
    finally:
        if session is not None:
            session.close()


__all__ = ["embed_document_chunks"]
