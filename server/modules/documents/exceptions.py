"""Module-local exceptions for documents workflows."""


class DocumentsError(Exception):
    """Base error for documents module operations."""


class UnsupportedFileTypeError(DocumentsError):
    """Raised when an uploaded file is not a supported PDF."""


class PasswordProtectedPDFError(DocumentsError):
    """Raised when a PDF is encrypted and cannot be processed."""


class ExtractionFailedError(DocumentsError):
    """Raised when text extraction or OCR fails."""


class OcrUnavailableError(ExtractionFailedError):
    """Raised when the OCR engine is not available.

    Or missing required lang packs.
    """


class OcrLimitExceededError(ExtractionFailedError):
    """Raised when OCR resource limits are exceeded.

    Limits include pages, resolution, timeout, concurrency.
    """


class OcrFailedError(ExtractionFailedError):
    """Raised when OCR execution fails or the page is unreadable."""


class DocumentNotFoundError(DocumentsError):
    """Raised when a document id does not exist."""


class ForbiddenUploadError(DocumentsError):
    """Raised when upload is unauthorized.

    Triggered when a user attempts to upload a document type they
    are not authorized for.
    """


class ReferenceDeleteConflictError(DocumentsError):
    """Raised when deletion conflicts.

    Triggered when a reference document cannot be deleted because it
    is referenced by evaluation jobs.
    """


class ReferenceRebuildError(DocumentsError):
    """Raised when rebuilding embeddings fails.

    Triggered when a reference document cannot be rebuilt due to missing
    chunks or unsupported type.
    """


class ReferenceDeleteInvalidTypeError(DocumentsError):
    """Raised when attempting to delete a non-reference document type.
    Only reference documents (syllabus, curriculum) can be deleted
    through this endpoint.
    """


class ReferenceDeleteStorageError(DocumentsError):
    """Raised when external storage cleanup fails during reference deletion."""


__all__ = [
    "DocumentsError",
    "UnsupportedFileTypeError",
    "PasswordProtectedPDFError",
    "ExtractionFailedError",
    "OcrUnavailableError",
    "OcrLimitExceededError",
    "OcrFailedError",
    "DocumentNotFoundError",
    "ForbiddenUploadError",
    "ReferenceDeleteConflictError",
    "ReferenceRebuildError",
    "ReferenceDeleteInvalidTypeError",
    "ReferenceDeleteStorageError",
]
