## 1. Regression Coverage

- [x] 1.1 Add direct A-01 normalization tests for the four observed aliases, canonical-prefix compatibility, case/whitespace handling, and unknown/combined-label negative controls.
- [x] 1.2 Add A-01 score-boundary and empty-evidence tests proving approved higher-order aliases are retained without promoting unknown labels.
- [x] 1.3 Add A-04 scoring tests for high-confidence copyright, fair-use disclaimer, reproduction-prohibition, and Section-plus-RA boilerplate.
- [x] 1.4 Add A-04 regression tests preserving genuine praise, legal-themed answer keys, rubrics, remediation, and mixed praise-plus-boilerplate evidence.
- [x] 1.5 Add prompt-content tests for explicit canonical-category output and minimal evidence quotes in both grouped and per-criterion paths.
- [x] 1.6 Add a mixed boilerplate-and-non-listed learner-praise regression test.

## 2. Deterministic Scoring Corrections

- [x] 2.1 Update A-01 extraction prompts to require the canonical category name rather than an example action verb.
- [x] 2.2 Implement four observed exact-token Bloom aliases while preserving existing canonical-prefix compatibility and no fuzzy promotion.
- [x] 2.3 Update A-04 extraction prompts to exclude boilerplate and request minimal direct feedback evidence.
- [x] 2.4 Implement the type-specific, high-confidence A-04 boilerplate guard after normalization and before count-band scoring.
- [x] 2.5 Preserve the current A-05 objective hierarchy and score-band behavior without modification.

## 3. Validation

- [x] 3.1 Run the targeted SME criterion, basket, engine, prompt, and Coordinator full-independent regression tests.
- [x] 3.2 Verify frozen facts show only intended A-01 increases and A-04 decreases, with `OP-01`, `OP-02`, and `OP-03` unchanged.
- [ ] 3.3 Run the manual local calibration gate with at least two de-identified, human-reviewed SLMs; record local identifiers, model/prompt configuration, code revision, intended changes, and unrelated score bands without committing source text. *(Pending: the database has 55 historical human-validated cases, but zero original PDFs are locally available as of 2026-07-30; re-upload two reviewed SLMs before rerunning this gate.)*
- [x] 3.4 Verify no API, data model, migration, dependency, basket-membership, or A-05 behavior changed, and document Coordinator's transitive A-01/A-04 impact.
