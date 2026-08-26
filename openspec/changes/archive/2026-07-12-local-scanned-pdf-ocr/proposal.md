## Why

EquipED currently relies on embedded PDF text. Image-based or mixed scanned PDFs can therefore lose educational content during preprocessing, making uploaded SLMs and institutional references incomplete or unusable. The system needs reliable local OCR that preserves LSPU data residency and fails safely instead of silently accepting documents with unreadable pages.

## What Changes

- Add a local scanned-PDF OCR capability backed by a provisioned Tesseract runtime and explicitly configured language data.
- Detect pages that lack meaningful selectable text and OCR them locally before metadata detection, chunking, and reference embedding.
- Reject uploads when any required OCR page cannot be read; do not mark partially extracted documents as processed or embed incomplete reference content.
- Add readiness diagnostics, deployment configuration, resource limits, and user-safe upload errors for unavailable OCR or unsupported scanned content.
- Add OCR regression tests covering image-only, mixed, empty, and failed OCR pages.

## Capabilities

### New Capabilities
- `local-scanned-pdf-ocr`: Local, privacy-preserving OCR for scanned and mixed PDF pages with safe failure behavior.

### Modified Capabilities
- `custom-semantic-document-chunking`: Require text extraction to preserve page completeness before metadata detection and chunking.

## Impact

- Affects `server/modules/documents/ingestion.py`, document upload/preprocessing error handling, server configuration, supported deployment image/provisioning, and document tests.
- Requires the local Tesseract executable and required language data in production; no cloud OCR service or external document sharing is introduced.
- Adds no public API endpoint, but failed uploads can report a new safe OCR-unavailable or unreadable-page reason.
