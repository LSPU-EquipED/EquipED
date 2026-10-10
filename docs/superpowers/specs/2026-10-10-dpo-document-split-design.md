# DPO document-level split and dataset integrity

Date: 2026-10-10. Status: approved for implementation by the user on 2026-10-10.
Classification: architectural follow-up to the DPO deployment-readiness discussion, scoped to the existing notebook and its artifact contracts.

## Intended outcome

The current experiment teaches selected SME criteria a synthetic +1 score adjustment. Its purpose is to demonstrate learning and transfer to unseen SLMs, not agreement with institutional reviewers. Future adapters need an internal held-out set that contains documents absent from their training set. Preserve human publication decisions and existing privacy/residency boundaries.

User-approved scope: document-level splitting, overlap checks, split metadata, tests and documentation. Exported provenance already includes document_id. No database migration, HTTP API or Admin UI change is needed. Existing adapters, including v10, remain historical artifacts with their original split semantics.

## Evidence and boundaries

The v10 audit found 32 pairs from 21 evaluations and 8 documents. Its evaluation-level split held out 7 pairs from 5 evaluations; all 5 held-out documents also occur in training, with 6 distinct prompt strings shared across the split. The separate house-rule reference evaluations were not in the frozen source. Those reserved SLMs remain the route for assessing v10's generalization.

The tracked notebook splits in its dataset cell, filters datasets for length in its model cell, and packages raw held-out rows later. Length filtering currently selects evaluation dataset rows without always selecting the corresponding saved held-out rows. This change must align them rather than record misleading counts or membership.

Root product documentation does not mandate an evaluation-level training split. Historical plans and artifacts do describe that split; retain their historical meaning and document the new behavior prospectively.

## Document-level assignment

Replace the evaluation grouping helper with split_by_document. Validate that every provenance record has a nonempty string document_id before assignment; missing identity is an error, not a reason to fall back to evaluation-level splitting.

Retain the existing seed (42), held-out percentage (20), and minimum pair threshold (20). Sort unique document IDs by SHA-256 of '<seed>:<document_id>', with document ID as a deterministic tie-breaker. Hold out ceil(20% of document groups), bounded to at least one and fewer than all documents when splitting is eligible. Preserve source row order within each set. Percentages refer to document groups; unequal group sizes mean pair percentages can differ.

Every evaluation and envelope belonging to a document receives the same assignment. The split changes which examples enter training; it does not modify prompt, chosen, rejected, scores, explanations, chat formatting, or the synthetic rule.

If there are fewer than 20 pairs or fewer than two documents, retain all pairs for training and explicitly report why no internal held-out set exists. This permits intentional smoke runs without claiming unseen-document evaluation. An empty training dataset is an error.

## Overlap checks

Check document membership and exact prompt identity across the assigned training and held-out sets before model loading. Document overlap is always an error. If identical prompt strings occur across different document IDs on opposite sides, stop with a bounded diagnostic listing pair/document IDs and counts, without printing source text. This prevents exact prompt leakage from being passed off as an independent test.

Repeated prompts within one side are permitted and counted; do not deduplicate or alter examples automatically. Checking near-duplicate text, document revisions or uploaded file hashes is deferred; document IDs and exact prompt comparisons cannot guarantee independence of revised or re-uploaded SLMs.

## Length filtering and final membership

Apply the length planner's retained indices to train_items and heldout_items as well as their datasets. Rebuild heldout_rows from the retained heldout_items, preserving source pair IDs, evaluation IDs and raw strings, and adding document_id for traceability. Keep dropped pair IDs and their original assignment in metadata. Do not move dropped examples to the other side or rerun the split after filtering.

If no training pairs remain, fail before training. Preserve the existing length planner's 20% maximum drop fraction: exceeding that limit stops the run, even when only held-out pairs would be dropped. Within that limit, if all held-out pairs are dropped, proceed as an explicitly reported training-only run, set eval_dataset to None, save no heldout_pairs.jsonl, and retain the reason and original assignment in split metadata. The heldout manifest remains null, as today. Recompute final overlap checks and counts on retained rows.

## Artifact contract

Set HELDOUT_METHOD to group_by_document_id. Keep the existing heldout manifest fields (method, seed, fraction, pair_count, evaluation_count, sha256) and add document_count. Keep existing raw held-out row fields; document_id is additive. The evaluation tool accepts extra row fields and does not dispatch on split method, so old archives remain readable.

Add a versioned dataset_split object to training_manifest.json, independent of whether a held-out file exists. It records:

- version, method, seed, requested held-out fraction and minimum pair threshold;
- an optional no-held-out reason (below_minimum_pairs, single_document, or all_heldout_dropped_for_length);
- assigned train and held-out document IDs before filtering;
- retained train and held-out pair IDs, document IDs, evaluation counts and pair counts;
- dropped pair IDs with their original train/held-out assignment;
- document overlap and distinct exact-prompt overlap counts, which must both be zero for an emitted split;
- repeated exact-prompt counts within each final side, defined as rows minus unique prompt strings.

IDs and counts are sufficient; do not duplicate prompt or response text into the manifest. Preserve source_job_manifest exactly because backend upload validation checks it against the frozen job. No export-schema change is needed; training artifact metadata remains additive. No backfill or reinterpretation of historical archives.

The notebook prints document, evaluation and pair counts for each side and describes evaluation results as an in-run check on held-out documents. It must not imply that high DPO reward accuracy proves generated score shifts or authorizes deployment.

## Files and compatibility

Primary implementation: docs/colab/dpo_training_template.ipynb. Preserve notebook cell count and established cell ordering; add helpers to existing cells. Preserve the repository's notebook encoding/newline convention and keep changes limited to affected cell sources.

Verification: existing CPU-only notebook contract/planning tests plus focused split tests under apps/server/tests/training_data/. Extend training/tests/test_evaluate_adapter.py for an archive containing the new method and additive metadata. A narrowly scoped wording update to the evaluator's no-held-out error may be needed to describe both historical evaluation grouping and new document grouping accurately.

Documentation: update training/evaluating-an-adapter.md to explain document grouping, training-only cases, old archive semantics, and the difference between internal held-out data and separately reserved house-rule reference SLMs. Update relevant notebook markdown. Untracked experiment notebook copies are outside the implementation scope.

## Verification criteria

CPU-only checks establish:

1. Repeated evaluations/envelopes of one document stay together; document groups and exact prompts never cross a successful split.
2. Assignment is deterministic for the same IDs and seed regardless of input order; each set preserves its input row order.
3. Single-document and below-threshold runs have explicit training-only outcomes; missing document identity fails.
4. Unequal group sizes retain all rows without inventing pair-level balancing.
5. Exact cross-side prompt duplicates fail; within-side duplicates are reported without removal.
6. Length filtering keeps datasets, saved held-out rows and metadata aligned, including all-held-out-dropped and no-training-pairs edge cases.
7. Packaged held-out contents, hash and counts match final membership; source_job_manifest stays unchanged.
8. The evaluation reader still accepts historical archives and reads the new document-split archive.

Run narrow notebook and evaluator test suites and formatting/lint checks for changed Python tests. No GPU, host restart, external training or production database writes are required for this implementation. A later real Colab run confirms printed counts and emitted metadata; served-model comparisons remain necessary to demonstrate behavioral learning.

## Deferred work

Automatic deduplication, near-duplicate document families, reviewer-disagreement resolution, correction-reasoning changes, experiment publication restrictions, training recovery, and new Admin screens require separate designs. This change improves measurement integrity and does not guarantee better training results.
