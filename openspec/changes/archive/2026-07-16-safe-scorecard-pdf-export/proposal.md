## Why

The current PDF export branch provides useful downloadable reports, but it can misstate scores and evaluation completeness, hard-codes institutional facts, and is not robust for Filipino text or partial results. Reports are advisory artifacts, so they must faithfully represent the persisted evaluation rather than infer or embellish it.

## What Changes

- Add a safe, client-side PDF export capability for authorized evaluation results.
- Export score values in their canonical scale and use the existing adjectival-rating helpers rather than recomputing incompatible aggregates.
- Render complete, deliberate partial, accidental failure, skipped-agent, and unavailable-data states honestly.
- Derive report metadata from persisted evaluation/document data; omit unavailable facts rather than hard-coding them.
- Use Unicode-capable PDF text rendering and tolerate unavailable optional assets.
- Bound and sanitize exported narrative evidence, including removal of raw chunk identifiers.
- Add automated and browser smoke coverage for generated report content and representative result states.

## Capabilities

### New Capabilities
- `evaluation-pdf-export`: Generates truthful, resilient, institution-branded PDF reports from authorized evaluation results.

### Modified Capabilities
- None.

## Impact

- Affected client code: evaluation export components, score display helpers, export actions, and UI tests.
- Adds/uses the existing `jspdf` client dependency and a bundled Unicode-capable font asset.
- No backend API, persistence, evaluation logic, authorization, or external-service changes.
