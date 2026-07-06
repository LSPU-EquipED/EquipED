"""Module-local exceptions for documents workflows."""


class DocumentsError(Exception):
    """Base error for documents module operations."""


class UnsupportedFileTypeError(DocumentsError):
    """Raised when an uploaded file is not a supported PDF."""


class PasswordProtectedPDFError(DocumentsError):
    """Raised when a PDF is encrypted and cannot be processed."""


class ExtractionFailedError(DocumentsError):
    """Raised when text extraction or OCR fails."""


class DocumentNotFoundError(DocumentsError):
    """Raised when a document id does not exist."""


class ForbiddenUploadError(DocumentsError):
    """Raised when a user attempts to upload a document type they are not authorized for."""


class ReferenceDeleteConflictError(DocumentsError):
    """Raised when a reference document cannot be deleted because it is referenced by evaluation jobs."""


class ReferenceRebuildError(DocumentsError):
    """Raised when a reference document cannot be rebuilt due to missing chunks or unsupported type."""


class ReferenceDeleteInvalidTypeError(DocumentsError):
    """Raised when attempting to delete a non-reference document type.
    Only syllabus and curriculum documents can be deleted through this endpoint.
    """


__all__ = [
    "DocumentsError",
    "UnsupportedFileTypeError",
    "PasswordProtectedPDFError",
    "ExtractionFailedError",
    "DocumentNotFoundError",
    "ForbiddenUploadError",
    "ReferenceDeleteConflictError",
    "ReferenceRebuildError",
    "ReferenceDeleteInvalidTypeError",
]
