"""HTTP endpoints for document upload and metadata retrieval."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from server.core.database import get_db_session
from server.core.exceptions import CoreError
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.service import AuthenticatedUser

from .exceptions import (
    DocumentNotFoundError,
    ExtractionFailedError,
    PasswordProtectedPDFError,
    UnsupportedFileTypeError,
)
from .schemas import DocumentListResponse, DocumentResponse, DocumentUploadResponse
from .service import create_document, embed_document_chunks, get_document, list_documents

router = APIRouter(prefix="/documents", tags=["documents"])


def get_optional_db_session() -> Iterator[Any | None]:
    """Provide DB session when configured; fallback to in-memory mode."""

    session_generator = get_db_session()
    try:
        session = next(session_generator)
    except CoreError:
        session_generator.close()
        yield None
        return
    try:
        yield session
    finally:
        session_generator.close()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_type: str = Form(...),
    title: str = Form(...),
    course_title: str | None = Form(default=None),
    lesson_title: str | None = Form(default=None),
    program: str | None = Form(default=None),
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any | None = Depends(get_optional_db_session),
) -> DocumentUploadResponse:
    try:
        response = create_document(
            file=file,
            source_type=source_type,
            title=title,
            course_title=course_title,
            lesson_title=lesson_title,
            program=program,
            uploaded_by=_current_user.id,
            db=db,
        )
        if response.processing_status == "PROCESSED":
            background_tasks.add_task(embed_document_chunks, response.document_id)
        return response
    except (UnsupportedFileTypeError, PasswordProtectedPDFError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ExtractionFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_by_id(
    document_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any | None = Depends(get_optional_db_session),
) -> DocumentResponse:
    try:
        return get_document(
            document_id=document_id,
            current_user_id=_current_user.id,
            current_user_role=_current_user.role.value,
            db=db,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("", response_model=DocumentListResponse)
def list_documents_endpoint(
    source_type: str | None = Query(default=None),
    program: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any | None = Depends(get_optional_db_session),
) -> DocumentListResponse:
    return list_documents(
        source_type=source_type,
        program=program,
        page=page,
        page_size=page_size,
        current_user_id=_current_user.id,
        current_user_role=_current_user.role.value,
        db=db,
    )


__all__ = ["router"]
