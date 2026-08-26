## Context

The rebased client branch introduces jsPDF scorecard exports from the same evaluation data shown in the application. The initial implementation conflates the canonical 1–4 agent scale with 0–100 monitoring values, assumes a complete curriculum-grounded result, and uses jsPDF's Latin-only built-in font. Evaluation reports are advisory, ownership-scoped artifacts and must remain faithful to persisted status and score semantics.

## Goals / Non-Goals

**Goals:**
- Generate a downloadable per-agent or consolidated PDF from already-authorized result data.
- Reuse existing score-formatting and adjectival-rating helpers; never infer a new aggregate from mismatched units.
- Make partial, failed, skipped, and unavailable content explicit in the report.
- Produce readable Unicode/Filipino text and tolerate a missing optional logo.
- Keep narrative evidence bounded and free of internal chunk identifiers.

**Non-Goals:**
- Server-side report generation, report persistence, signatures, reviewer finalization, or a new API.
- Replacing the interactive scorecard or asserting institutional facts absent from the evaluation/document.
- Changing evaluation scoring, synthesis, permissions, or the Layer 4 boundary.

## Decisions

### Client-only export from the current result payload
The export component receives the same typed result model rendered by the scorecard. This preserves current ownership enforcement in existing result APIs and avoids sending evaluation content to a new service. Browser-print HTML was considered, but a generated PDF provides a consistent download artifact and does not depend on a user choosing a browser print target.

### Canonical-score presentation and explicit scale labels
Agent criterion/subtotal values are rendered on the canonical 1–4 scale and use the existing score/adjectival helpers. A monitoring-matrix percentage, if present, is rendered only as a separately labelled percentage. The PDF never averages heterogeneous fields or invents a complete aggregate from partial results.

### Honest report-state model
Report header and agent sections derive their state from persisted evaluation status, `is_partial`, `partial_reason`, and individual agent status. Skipped and failed agents have explanatory sections rather than scorecards. Missing course, program, academic-year, reviewer, or curriculum values are omitted or labelled unavailable; values are never hard-coded.

### Bundled Unicode font and graceful assets
The report registers a bundled Unicode-capable Noto Sans font with jsPDF before text rendering. This is preferred to Helvetica because institutional Filipino names and punctuation must not be corrupted. The optional LSPU logo is loaded defensively; a load failure produces a text-only header rather than aborting export.

### Shared export sanitization and bounded layout
Export-specific helpers sanitize text, remove raw `chunk_id` tokens, normalize whitespace, enforce narrative/evidence length limits, and paginate deterministically. Unit tests exercise helpers and report data assembly; browser smoke cases cover the generated download and visual state.

## Risks / Trade-offs

- [Bundled font increases client bundle size] → Include one regular-weight subset only and lazy-load export code.
- [Client PDFs can vary slightly by browser] → Test semantic content and page generation; retain manual visual smoke checks.
- [Long justifications can overflow pages] → Bound exported narrative and paginate tables/sections.
- [Partial reports might be mistaken for final approval] → Display a prominent advisory/partial state and never include approval language.

## Migration Plan

1. Retain current HTML export only until the corrected PDF path passes tests and manual smoke checks.
2. Enable corrected PDF export for terminal results only; retain the existing terminal-state gating.
3. Roll back by restoring the prior export action; no data migration is required.

## Open Questions

- None. The report will use the existing LSPU branding tokens and a bundled Unicode font asset.
