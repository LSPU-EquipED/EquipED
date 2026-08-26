## 1. Export Contract and Data Model

- [x] 1.1 Define typed PDF report view models that preserve canonical score units, evaluation state, and unavailable metadata.
- [x] 1.2 Refactor score/adjectival formatting so PDF and interactive scorecards use the same canonical rules.
- [x] 1.3 Add export sanitization and bounded narrative/evidence helpers, including raw chunk-token removal.

## 2. Truthful Report Rendering

- [x] 2.1 Correct per-agent and consolidated report calculations so 1–4 scores and 0–100 monitoring percentages are never combined.
- [x] 2.2 Render complete, deliberate partial, failure, skipped-agent, and unavailable-data states honestly.
- [x] 2.3 Replace hard-coded institutional/reviewer/course values with persisted metadata or explicit unavailable labels.

## 3. PDF Resilience and Branding

- [x] 3.1 Register a bundled Unicode-capable report font and use it for all generated text.
- [x] 3.2 Make optional logo loading non-fatal and retain a readable text-only header fallback.
- [x] 3.3 Ensure tables and narrative sections paginate safely in per-agent and consolidated reports.

## 4. Tests and Validation

- [x] 4.1 Add unit tests for report models, canonical score formatting, partial/skipped state, metadata omission, and narrative sanitization.
- [x] 4.2 Add PDF-generation tests for Unicode text and missing-logo fallback.
- [x] 4.3 Run typecheck, lint, production build, and focused export tests.
- [x] 4.4 Manually smoke-test complete, deliberate partial, failed-agent, and Unicode/Filipino export downloads.
