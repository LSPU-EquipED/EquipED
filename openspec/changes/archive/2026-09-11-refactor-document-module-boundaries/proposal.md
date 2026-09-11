## Why

The documents module concentrates upload admission, artifact I/O, ingestion orchestration, persistence, embedding, and failure recovery in an 889-line service while several source-specific packages contain only shallow one-caller files.

## What Changes

- Preserve document APIs, schemas, database models, lifecycle states, ownership rules, and processing behavior.
- Reduce service.py to the stable public application surface.
- Extract upload admission, processing lifecycle, repository, storage, and embedding responsibilities into cohesive module-local services.
- Flatten shallow SLM, syllabus, curriculum, and policy package structure where nesting does not hide meaningful complexity.
- Migrate callers to intentional document service interfaces and remove obsolete paths.

## Capabilities

### New Capabilities

- document-module-boundaries: Defines cohesive internal ownership for the existing document lifecycle without changing product behavior.

### Modified Capabilities

None.

## Impact

Backend-only structural refactor under server/modules/documents and its import callsites. No API, persistence schema, source-type, OCR, chunk, embedding, or evaluation contract changes.
