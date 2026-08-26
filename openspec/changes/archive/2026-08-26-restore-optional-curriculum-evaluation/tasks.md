## 1. Curriculum reference lifecycle

- [x] 1.1 Re-enable admin curriculum upload and active reference access while preserving BSCS/BSInfoTech validation, faculty denial, and rubric rejection.
- [x] 1.2 Add deterministic section-aware curriculum text trimming before chunking, including same-page program boundaries and fail-closed unrecognized multi-program indicators; cover single-program, BSCS, BSInfoTech, absent-section, ambiguous-boundary, and OCR-failure scenarios.
- [x] 1.3 Add one documents-owned curriculum-readiness service requiring current admin provenance, curriculum source type, matching canonical program, `PROCESSED`, non-empty chunks, and live local vectors; cover stale Chroma flags and legacy faculty rows.
- [x] 1.4 Restore the ownership-scoped curriculum suggestion endpoint, validating missing/foreign/non-SLM masking before program lookup, and keep generic faculty lists from exposing curriculum discovery.
- [x] 1.5 Extend admin reference listing, preview, rebuild, and deletion coverage; block ordinary deletion on any evaluation reference and preserve SQL state when vector cleanup fails.

## 2. Optional full evaluation admission

- [x] 2.1 Accept exactly two explicit launch combinations: curriculum ID plus `partial_without_curriculum=false`, or no curriculum ID plus `partial_without_curriculum=true`, both with canonical `BSCS`/`BSInfoTech` writes.
- [x] 2.2 Reject omitted/conflicting intent, `BSIT` writes, mismatched program, unready/non-admin curriculum, unsupported program, and missing/foreign/non-SLM requests with ownership masking preserved.
- [x] 2.3 Add full-flow integration coverage proving authoritative curriculum reaches Coordinator and asserting successful full job/matrix `COMPLETED`, failed full job/matrix `FAILED`, retained full intent, and no `COMPLETED_PARTIAL` downgrade.
- [x] 2.4 Preserve partial-flow coverage proving Coordinator is excluded, successful partial jobs end with `COMPLETED_PARTIAL`, and failed/missing partial agents produce job/matrix `FAILED` while retaining partial intent.

## 3. Admin and faculty client flows

- [x] 3.1 Restore Curriculum in Admin Ingestion with a required BSCS/BSInfoTech ProgramSelector and accessible validation/error states.
- [x] 3.2 Restore typed curriculum suggestion API mapping and an ownership-scoped query keyed by document and confirmed program.
- [x] 3.3 Implement an accessible curriculum radio group in Evaluation Setup that requires explicit faculty selection, never auto-selects authority, and shows unavailable entries without allowing selection.
- [x] 3.4 Move evaluation submission into an evaluation-owned API/hook, remove the evaluation-to-upload feature dependency, make partial acknowledgement conditional on the explicit partial option, and preserve upload auto-navigation.
- [x] 3.5 Add client tests for program changes, ready/unavailable suggestions, full submission, partial acknowledgement, conflicting-state prevention, and keyboard/accessibility semantics.

## 4. Verification and review

- [x] 4.1 Run scoped server tests and Ruff for documents, evaluations, Coordinator, synthesis, and monitoring-matrix finalization.
- [x] 4.2 Run client typecheck, focused/full Vitest, and production build.
- [x] 4.3 Validate the OpenSpec change strictly and confirm no database migration or new Alembic head is introduced.
- [x] 4.4 Smoke-test one partial and one full BSCS/BSInfoTech evaluation with truthful terminal status and Coordinator attribution.
- [x] 4.5 Run the three-seat council review, remediate blockers, and obtain a final synthesis verdict.
