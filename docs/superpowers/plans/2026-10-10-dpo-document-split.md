# DPO document split implementation plan

> **For agentic workers:** Use superpowers:executing-plans for inline implementation. Track the steps below.

**Goal:** Make future notebook-held-out results independent of training documents and preserve accurate artifact membership after length filtering.

**Architecture:** Keep helpers in the existing notebook cells. Split frozen pair/provenance records by document, validate overlap before model loading, filter records and datasets together, and package additive split metadata.

**Tech stack:** Python notebook, pytest CPU-only cell execution, existing artifact reader.

**Spec:** `docs/superpowers/specs/2026-10-10-dpo-document-split-design.md`

## Constraints and execution

- Seed 42, held-out percentage 20, minimum 20 pairs; fewer than two documents means an explicit training-only run.
- Preserve chat rows, original pair text, source_job_manifest, cell count/order and historical archive readability.
- No database/API/UI changes, GPU training or host calls.
- User requested implementation and a new branch on 2026-10-10; implement inline on `feat/dpo-document-split` in the current checkout, retaining existing untracked work.

## Review focus

- Missing document identity must fail even below the split threshold.
- Unequal document sizes must not cause pair-level rebalancing.
- Duplicate prompts crossing document IDs must stop without exposing source text.
- Length filtering must not leave stale saved held-out rows or a stale file from a previous cell run.
- Historical archives must remain readable alongside additive document metadata.

## Task 1: Split and integrity checks

Files: notebook dataset cell; new `apps/server/tests/training_data/test_notebook_document_split.py`; existing notebook contract fixtures.

- [x] Write and run failing tests for repeated evaluations/documents, deterministic assignment and row order, unequal groups, missing identity, empty/small/single-document datasets, cross-side exact prompts and within-side repeats.
- [x] Implement `split_by_document(items, percent, seed)`, `check_split_overlap(train, heldout)`, `build_split_metadata(assigned_train, assigned_heldout, train, heldout, reason)`, and `build_heldout_rows(items)` in the dataset cell. Metadata includes version/method/seed/fraction/minimum/reason, assigned document IDs, retained IDs/counts, dropped IDs with assignment and overlap/repetition counts.
- [x] Run the new split tests and existing notebook contract tests; update fixtures to carry document IDs and new manifest fields.

## Task 2: Final membership and artifacts

Files: notebook length/manifest/summary cells; notebook planning and document-split tests; `training/tests/test_evaluate_adapter.py`.

- [x] Write and run failing tests for partial/all held-out drops, no training survivors, final row/count/hash alignment, and stale held-out file removal.
- [x] Apply retained indices to provenance records and datasets; rebuild raw held-out rows and metadata. Add document_count and dataset_split to manifest; remove an old held-out file when no rows remain.
- [x] Verify archive reader accepts both grouping methods, including document_id on rows.

## Task 3: Documentation and verification

Files: notebook markdown, `training/evaluating-an-adapter.md`, evaluator missing-heldout explanation.

- [x] Document document grouping, duplicate limits, training-only outcomes and historical evaluation-level archives.
- [x] Run notebook tests and evaluator tests with `apps/server/.venv/Scripts/python.exe -m pytest` from the appropriate project directory. Run Ruff on changed Python files and inspect the notebook diff/cell layout.
- [x] Obtain a fresh whole-change review and resolve material findings. Scope the implementation commit to the notebook, tests, evaluator message and documentation.

## Execution ledger

- Baseline: initial sandbox run had pytest temporary-directory permission errors; rerun with approved escalation. No product failures observed in initial 58 contract tests.
- Ruling: proceed inline after user's explicit instruction to implement; the requested new branch supplies separation without relocating their existing local environment or artifacts.
- Baseline complete: 170 focused tests passed. New regression suite initially had 14 expected failures and 1 existing behavior pass; after implementation, all 118 focused notebook tests passed.
- Full affected verification: all test_notebook*.py suites, test_dpo_colab_contract.py and training/tests passed (395 tests; expected duplicate-ZIP warning). Ruff lint and formatting checks passed for all five changed Python files.
- Notebook structure check: 19 cells, original cell types/order, CRLF and no trailing newline preserved; only cells 3, 5, 6, 9 and 10 changed.
- Local preview on the audited v10 frozen source: 29 training pairs / 6 documents and 3 held-out pairs / 2 documents; zero document or exact-prompt overlap. No model training was run.
- Independent review resolved: cumulative dropped counts now survive length-cell reruns; notebook introduction names document_id; documentation explicitly preserves the existing 20% drop safety limit before any training-only fallback. Added regression coverage, including real planner boundary cases.
- Final verification after review fixes: 399 tests passed with the expected duplicate-ZIP warning. Ruff lint/format, notebook structure/serialization and git diff whitespace checks passed. Colab GPU training and hosted inference remain untested locally.
