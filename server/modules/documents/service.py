"""Public application interface and facade for document upload and processing."""

from __future__ import annotations

from .background import process_document_ingestion
from .embedding import embed_document_chunks
from .ingestion.pipeline import ingest_document
from .metadata import detect_metadata
from .processing import _sanitize_error
from .upload import _validate_upload, create_document

__all__ = [
    "_sanitize_error",
    "detect_metadata",
    "_validate_upload",
    "create_document",
    "embed_document_chunks",
    "ingest_document",
    "process_document_ingestion",
]
