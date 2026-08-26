## Context

Layer-1 ingestion currently extracts embedded text with PyMuPDF and chunks it locally. The repository already declares Python OCR bindings (`Pillow`, `pytesseract`), but the Tesseract executable and its trained language data are not provisioned in the server image or checked at readiness. Current OCR fallback can silently discard unreadable pages from a mixed PDF, which is unsafe for SLM evaluation and reference retrieval.

EquipED is deployed with local data residency on institution-controlled infrastructure. Document text must not be sent to a cloud OCR or vision service.

## Goals / Non-Goals

**Goals:**
- Extract text from pages without meaningful embedded text using an offline local OCR engine.
- Preserve document completeness: a required unreadable page fails preprocessing rather than becoming an invisible omission.
- Provision and validate Tesseract and required language data in supported production deployment.
- Keep the existing page-bounded chunk persistence contract and `is_ocr` provenance flag.
- Give users safe, actionable upload failures without leaking host paths or internal configuration.

**Non-Goals:**
- Cloud OCR, remote vision APIs, or external transmission of PDF content.
- LLM-based OCR, semantic interpretation of page images, handwriting recognition, or table reconstruction.
- A plugin framework or multiple interchangeable OCR providers.
- Retroactive automatic reprocessing of documents already stored.
- Persisting partial documents with a warning status in this change.

## Decisions

### Use local Tesseract as the single OCR engine
Tesseract runs offline and is mature enough for English/Filipino institutional documents. It fits local residency and avoids a second remote dependency. The app uses the existing OCR boundary in document ingestion; `pytesseract` remains a thin Python adapter, while the executable and language data are a production deployment requirement.

**Alternatives considered:** native PDF extraction cannot recognize raster text; cloud OCR conflicts with data residency and availability/cost constraints; a local vision model is larger, slower, and may hallucinate evaluation input.

### OCR only pages without meaningful embedded text
PyMuPDF embedded text remains the first path. Pages below a defined meaningful-text threshold are candidates for OCR. The implementation will preserve the threshold as a documented/configurable extraction heuristic and use scanned/mixed PDF fixtures to protect against weak overlay text.

### Fail closed for unreadable OCR-required pages
If a page requires OCR and cannot be processed because the engine, configured language pack, rasterization, or OCR execution fails, preprocessing fails and creates no chunks or embeddings. This avoids silently evaluating or retrieving from a partial SLM/reference document.

Blank pages are not treated as required content and may remain empty without failing a document; the implementation must distinguish a truly blank page from an OCR-required page with failed OCR.

### Establish durable upload ownership before artifact creation
Database-backed uploads use the existing `Document` row as a write-ahead ownership record: commit a `PENDING` row with deterministic file path before opening the target PDF; finalize document metadata and chunks together when transitioning to `PROCESSED`. Startup recovery treats `PENDING` and failed tracked documents as recoverable incomplete uploads.

No-database development mode uses an atomically-created, fsynced ownership marker under `uploads/.upload-journal/` before opening a PDF. Since no-database metadata is in-memory and disappears at restart, startup recovery removes all marker-owned PDFs. This keeps no-database uploads explicitly ephemeral without adding a dependency or schema migration.

### Tesseract readiness is explicit
Production startup/readiness verifies the executable and every configured language pack. English (`eng`) and Filipino (`fil`) are required production language packs. Development may use a text-only profile, but scanned uploads are rejected clearly in that profile. `TESSERACT_CMD` locates an executable when PATH is insufficient; configured languages default to `eng+fil` and are documented. The executable configuration and language availability are resolved once at startup/readiness rather than on every OCR page.

### Bound OCR resources
OCR rasterization uses a fixed maximum DPI/resolution and page-count/file-size protections already applicable to uploads where possible. Initial defaults are 25 OCR-candidate pages per document, 200 DPI, 8 million pixels per page, 20 seconds per page, one OCR worker, and a 30-second worker-acquisition limit. OCR calls are time-bounded and concurrency-limited to avoid a large scanned PDF exhausting the single-process server. Tesseract execution limits native OpenMP threads to one process thread.

## Risks / Trade-offs

- **OCR recognition is imperfect** → Preserve `is_ocr` provenance, keep human review authoritative, and reject unreadable pages rather than invent text.
- **Tesseract adds host/image provisioning** → Add it to the supported server image/provisioning and readiness diagnostics; do not discover it only during upload.
- **Failing mixed PDFs can reject otherwise useful files** → Prefer correctness and retrievable completeness; users can upload a text-based source or administrators can repair OCR deployment.
- **OCR increases preprocessing latency and memory use** → Execute only on candidate pages and enforce rasterization/time/concurrency bounds.
- **English/Filipino language packs may be absent** → Readiness checks report missing configured packs before users upload files.

## Migration Plan

1. Add the canonical OCR requirements and regression fixtures/tests.
2. Establish durable upload ownership before artifact creation and startup recovery for interrupted uploads.
3. Add safe page-level OCR result/error handling in ingestion, with no partial persistence on failure, and update the conflicting TDD guidance.
4. Provision Tesseract and selected language data in the supported deployment image or host setup; document configuration.
5. Deploy with readiness validation enabled and verify text, scanned, mixed, blank-page, and unavailable-engine uploads.
6. Roll back by disabling OCR execution only in a text-only development profile; production rollback must continue rejecting scanned PDFs rather than silently dropping content.

## Confirmed Defaults

- Production language set: `eng+fil`.
- Limits: 25 OCR-candidate pages per document, 200 DPI, 8 million pixels per page, 20 seconds per page, one concurrent OCR worker, and a 30-second worker-acquisition limit.
