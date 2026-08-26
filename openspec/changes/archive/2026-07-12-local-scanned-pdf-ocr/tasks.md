## 1. OCR Runtime and Configuration

- [x] 1.1 Define validated OCR settings for executable path, languages, page/raster limits, timeout, and concurrency.
- [x] 1.2 Add local OCR executable and selected language packs to the supported server deployment image or provisioning workflow.
- [x] 1.3 Document OCR environment variables, required `eng+fil` language packs, and text-only development behavior in the deployment example/configuration.
- [x] 1.4 Add OCR startup/readiness diagnostics for executable and configured language packs.

## 2. Safe Page Extraction

- [x] 2.1 Replace sentinel-string OCR outcomes with typed/module-local result or exception handling that distinguishes blank pages, engine unavailability, and page OCR failure.
- [x] 2.2 Implement safe rasterization for OCR candidate pages with configured resource bounds and compatible image mode handling.
- [x] 2.3 Detect OCR-candidate pages without treating weak selectable overlays as complete page text.
- [x] 2.4 Fail document preprocessing when any nonblank OCR-required page is unreadable; prevent chunk persistence and reference embedding.
- [x] 2.5 Preserve blank-page behavior, page numbers, and `is_ocr` provenance for successfully extracted pages.
- [x] 2.6 Add bounded OCR timeout/concurrency behavior and safe error translation for limit exceedance.

## 3. Upload Errors and Operational Behavior

- [x] 3.1 Surface distinct user-safe upload errors for unavailable OCR, missing language packs, unreadable pages, and OCR resource limits.
- [x] 3.2 Ensure internal paths, Tesseract command details, and raw OCR errors remain server logs only.
- [x] 3.3 Ensure failed or interrupted OCR uploads leave no document chunks, Chroma vectors, or untracked upload artifacts through durable pre-write ownership and startup recovery.
- [x] 3.4 Update conflicting TDD OCR guidance to require fail-closed handling for unreadable nonblank pages.

## 4. Tests

- [x] 4.1 Add image-only scanned-PDF ingestion fixture/test with successful local OCR and OCR chunk provenance.
- [x] 4.2 Add mixed selectable/scanned PDF test that requires both extraction paths before success.
- [x] 4.3 Add blank-page test that permits preprocessing without a blank-page chunk.
- [x] 4.4 Add unavailable executable, missing language pack, generic OCR error, timeout, and limit-exceeded tests that reject safely.
- [x] 4.5 Add weak-overlay scanned-page regression test to ensure main image text is not silently skipped.
- [x] 4.6 Add failed/interrupted-upload tests proving no partial chunks, embeddings, or untracked artifacts are persisted across immediate cleanup and restart recovery.

## 5. Validation

- [x] 5.1 Run document ingestion, upload, and reference-library test suites plus lint/format checks.
- [x] 5.2 Verify readiness behavior in OCR-enabled and text-only development profiles.
- [x] 5.3 Manually upload representative text-only, image-only, mixed, and unreadable PDFs and verify truthful UI outcomes.
- [x] 5.4 Run post-implementation architecture/code review and address blocking findings.
