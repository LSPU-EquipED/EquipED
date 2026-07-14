"""HTTP endpoints for document upload and metadata retrieval."""

from __future__ import annotations

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
from fastapi.responses import FileResponse
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin, require_authenticated_user
from server.modules.auth.service import AuthenticatedUser

from .exceptions import (
    DocumentNotFoundError,
    ExtractionFailedError,
    ForbiddenUploadError,
    PasswordProtectedPDFError,
    ReferenceDeleteConflictError,
    ReferenceDeleteInvalidTypeError,
    ReferenceRebuildError,
    UnsupportedFileTypeError,
)
from .schemas import (
    CurriculumSuggestionResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    ReferenceDeleteResponse,
    ReferenceLibraryResponse,
    ReferenceRebuildResponse,
)
from .service import (
    create_document,
    delete_reference_document,
    embed_document_chunks,
    get_curriculum_suggestions,
    get_document,
    list_documents,
    list_reference_documents,
    process_document_ingestion,
    rebuild_reference_embeddings,
    stream_document_file,
)

router = APIRouter(prefix="/documents", tags=["documents"])


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
    db: Any = Depends(get_db_session),
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
            user_role=_current_user.role.value,
            db=db,
        )
        if response.processing_status == "PROCESSED":
            background_tasks.add_task(embed_document_chunks, response.document_id)
        elif response.processing_status == "PROCESSING":
            # Reference documents (syllabus/curriculum) defer OCR/extraction to
            # a background task since scanned CMOs can take minutes to process.
            background_tasks.add_task(process_document_ingestion, response.document_id)
        return response
    except ForbiddenUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
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


@router.get("/references", response_model=ReferenceLibraryResponse)
def list_references(
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Any = Depends(get_db_session),
) -> ReferenceLibraryResponse:
    """Admin-only reference library listing of syllabus/curriculum documents."""
    return list_reference_documents(db=db)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_by_id(
    document_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
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
    db: Any = Depends(get_db_session),
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


@router.get("/{document_id}/file")
def get_document_file(
    document_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> FileResponse:
    """Stream a document's PDF file. References shared; SLMs owner-only."""
    try:
        file_path = stream_document_file(
            document_id=document_id,
            current_user_id=_current_user.id,
            db=db,
        )
        return FileResponse(
            path=str(file_path),
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"},
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{document_id}/curriculum-suggestion",
    response_model=CurriculumSuggestionResponse,
)
def get_curriculum_suggestion(
    document_id: UUID,
    program: str = Query(
        ..., min_length=1, description="Confirmed academic program for curriculum matching"
    ),
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> CurriculumSuggestionResponse:
    """Return curriculum suggestions for an SLM document by confirmed program.

    Requires authentication. The SLM document must be owned by the current
    user (SLMs are owner-only; references are shared). The program parameter
    is required and must be non-empty.
    """
    try:
        return get_curriculum_suggestions(
            document_id=document_id,
            program=program,
            current_user_id=_current_user.id,
            current_user_role=_current_user.role.value,
            db=db,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.delete("/{document_id}", response_model=ReferenceDeleteResponse)
def delete_document(
    document_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Any = Depends(get_db_session),
) -> ReferenceDeleteResponse:
    """Admin-only delete of a reference document with full asset cleanup."""
    try:
        return delete_reference_document(
            document_id=document_id,
            db=db,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ReferenceDeleteInvalidTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ReferenceDeleteConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post("/{document_id}/rebuild-embeddings", response_model=ReferenceRebuildResponse)
def rebuild_document_embeddings(
    document_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Any = Depends(get_db_session),
) -> ReferenceRebuildResponse:
    """Admin-only rebuild of Chroma embeddings from stored chunks."""
    try:
        return rebuild_reference_embeddings(
            document_id=document_id,
            db=db,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ReferenceRebuildError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


__all__ = ["router"]
