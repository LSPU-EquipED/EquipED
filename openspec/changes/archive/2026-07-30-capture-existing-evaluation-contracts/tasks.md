## 1. Curriculum Extraction Contract Capture

- [x] 1.1 Cross-check the curriculum extraction contract against `curriculum_extraction.py`, `ingestion.py`, and the existing curriculum extraction tests.
- [x] 1.2 Verify the new `curriculum-reference-extraction` delta is ready for canonical synchronization during archive.
- [x] 1.3 Confirm the contract preserves single-course fallback order, canonical program mapping, BSIS exclusion, and page-level multi-program chunking without changing code.

## 2. SME Engine Scoring Contract Capture

- [x] 2.1 Cross-check the SME engine-scoring contract against the registry, scoring bands, slicing logic, engine path, and existing SME tests.
- [x] 2.2 Verify the new `sme-engine-scoring` delta is ready for canonical synchronization during archive.
- [x] 2.3 Confirm the six-basket split, score bands, grounding rules, temperature requirement, fallback behavior, and known limitations match current behavior without changing code.

## 3. Reference Library Contract Link

- [x] 3.1 Verify the `reference-library` delta delegates curriculum chunk semantics to the curriculum extraction contract.
- [x] 3.2 Confirm reference lifecycle, access, health, preview, deletion, and rebuild requirements remain unchanged.

## 4. Documentation Validation and Historical Preservation

- [x] 4.1 Validate the OpenSpec change and all affected canonical specs.
- [x] 4.2 Verify no application code, API contract, data model, migration, or dependency changed.
- [x] 4.3 Retain `curriculum-map-extraction-summary.md`, `sme-scoring-basis.md`, and `sme-scoring-progress.md` until the synced specs are reviewed and accepted.
