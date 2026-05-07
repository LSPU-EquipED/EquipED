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


__all__ = [
    "DocumentsError",
    "UnsupportedFileTypeError",
    "PasswordProtectedPDFError",
    "ExtractionFailedError",
    "DocumentNotFoundError",
]
