"""HTTP endpoints for document upload and metadata retrieval."""

from __future__ import annotations

from typing import Any, Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from server.core.database import get_db_session
from server.core.exceptions import CoreError

from .exceptions import (
    DocumentNotFoundError,
    ExtractionFailedError,
    PasswordProtectedPDFError,
    UnsupportedFileTypeError,
)
from .schemas import DocumentListResponse, DocumentResponse, DocumentUploadResponse
from .service import create_document, get_document, list_documents

router = APIRouter(prefix="/documents", tags=["documents"])


def get_optional_db_session() -> Iterator[Any | None]:
    """Provide DB session when configured; fallback to in-memory mode."""

    try:
        yield from get_db_session()
    except CoreError:
        yield None


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: UploadFile = File(...),
    source_type: str = Form(...),
    title: str = Form(...),
    program: str | None = Form(default=None),
    db: Any | None = Depends(get_optional_db_session),
) -> DocumentUploadResponse:
    try:
        return create_document(
            file=file,
            source_type=source_type,
            title=title,
            program=program,
            db=db,
        )
    except (UnsupportedFileTypeError, PasswordProtectedPDFError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ExtractionFailedError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_by_id(
    document_id: UUID,
    db: Any | None = Depends(get_optional_db_session),
) -> DocumentResponse:
    try:
        return get_document(document_id=document_id, db=db)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("", response_model=DocumentListResponse)
def list_documents_endpoint(
    source_type: str | None = Query(default=None),
    program: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Any | None = Depends(get_optional_db_session),
) -> DocumentListResponse:
    return list_documents(
        source_type=source_type,
        program=program,
        page=page,
        page_size=page_size,
        db=db,
    )


__all__ = ["router"]
