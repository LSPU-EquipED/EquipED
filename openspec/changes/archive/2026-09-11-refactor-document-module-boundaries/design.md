## Context

Document behavior is correct but service.py mixes eight substantial workflows and low-level mechanisms. Explicit submodule imports are retained; no package barrel is introduced.

## Decisions

- service.py remains the stable public facade for create_document, process_document_ingestion, and embed_document_chunks.
- Upload admission owns RBAC, validation, deduplication, durable upload intent, and artifact acceptance.
- Processing owns synchronous and background lifecycle orchestration.
- Repository owns SQL and no-database development persistence.
- Storage owns artifact paths, markers, writes, resolution, and cleanup.
- Ingestion remains a real subsystem; shallow source-specific packages are flattened.
- Background reference ingestion preserves the Neon-safe sequence: short read session, no open session during OCR, fresh write session for finalization.
- Processing remains fail-closed and never publishes partial chunks or vectors.

## Non-Goals

No route, schema, database, source-type, lifecycle, OCR, chunking, embedding, authorization, or evaluation behavior changes. No new framework or generic dependency-injection layer.

## Migration

Extract one responsibility at a time, migrate all imports, delete obsolete modules, then run document tests followed by the full server suite.
