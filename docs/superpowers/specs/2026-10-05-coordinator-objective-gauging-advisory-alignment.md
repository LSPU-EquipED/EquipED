# Coordinator v3: Objective Gauging and advisory Curriculum Alignment

**Status:** Finalized specification; implementation is opt-in through adapter v3. Local verification is recorded below. The default Coordinator contract remains v2; no live rubric has been created, published, or activated.

## Boundary and ownership

Coordinator owns source inventory, evidence validation, and deterministic coverage scoring. The immutable rubric snapshot selects the harness version. Its official form remains exactly OP-01–05/A-01–05; A-05 uses `objective_gauging`. C-01 is a harness-owned supplemental definition, not an eleventh rubric row. Its fixed definition and bands are governed by adapter v3, so changing them requires another version.

Shared agent contracts own the typed output. Synthesis validates and persists it using existing advisory JSON storage, without a database schema migration. Faculty and Admin render the supplement separately using a shared presentation component. No new service framework, queue, or concurrency boundary is introduced; pure inventory data is immutable and existing durable admission/recovery remains authoritative.

## Source inventory and supported format

A ready authoritative curriculum remains mandatory. Before any scoring call, derive the inventory from canonical direct SLM text, never vector storage or model-returned objectives.

Supported headings are Objectives, Learning Objectives, Course Objectives, Lesson Objectives, Learning Outcomes, and Intended Learning Outcomes, case-insensitive, with optional Markdown/lettered prefixes and a trailing colon. Entries must be numbered consecutively from 1, or bulleted with `-`, `*`, or `•`. Each section uses one consistent indentation and list style. Multiline continuations must be indented. Multiple independently delimited objective sections are supported. Source spans are preserved verbatim and receive canonical `OBJ-0001` onward IDs.

Recognized section headings (including Content, Discussion, References, Assessment, Quiz, and numbered Lesson/Unit/Module headings) terminate objective sections. Unknown explicit headings within an objective section, nested/mixed lists, skipped numbers, duplicates, missing sections, empty sections, and unsupported continuations fail closed. Objectives nested directly in assessment material are ambiguous and fail rather than silently joining the inventory. This is deliberately bounded parsing, not a universal guarantee for PDF layouts. Upstream canonical extraction must be complete; the harness also rejects the runtime gap marker and sources beyond 200,000 characters.

Assessment support must come from explicitly headed assessment/activity/exercise sections. An absent assessment section gives no supported matches; it does not remove objectives. Every objective, every extracted assessment section, and the full supplied curriculum context reach the joint scoring prompt without downsampling. Unrelated SLM text need not be duplicated into that call. Prompt overflow fails explicitly; diagnostic repair retains the complete context. The other nine criteria retain their existing envelope behavior.

## Evidence, scoring, and failure semantics

The model judges semantic relationships, but cannot determine the denominator or numeric scores. It must return exactly one row per frozen objective ID for both dimensions. Missing/unknown/duplicate IDs or malformed/truncated responses receive one bounded repair, then fail the run if unresolved.

- **A-05 Objective Gauging:** actual SLM assessment tasks measure the objective's stated learning performance. Objective self-quotations cannot establish assessment support.
- **C-01 Curriculum Alignment:** supporting excerpts must occur in the supplied authoritative curriculum, never merely in the SLM. Mere topical similarity is insufficient according to the evaluator instructions.

The harness validates exact excerpt provenance. Unsupported positive claims become unmatched, with rejection recorded; the objective stays in the denominator. A-05 and C-01 justifications explicitly list supported and unmatched objective IDs; the supplemental evidence view shows each ID and its full source objective. Semantic correctness remains advisory and requires human review even when quotations are valid.

Both dimensions use deterministic coverage bands: 4 at ≥80%, 3 at ≥50%, 2 at ≥20%, otherwise 1. Missing assessments yield unmatched coverage. An invalid/ambiguous/empty inventory is a failed evaluation, not an invented zero-objective score. V3 requires both results to succeed; an unresolved supplemental extraction failure does not become partial success.

## Result and storage contract

Only the ten official scores appear in `criterion_scores` and their arithmetic mean. C-01 cannot affect official flags, the Coordinator subtotal, document composite, PDF average, score distribution, or reviewer correction arrays.

Existing `AgentResult.advisory_outputs` JSON stores the separate payload:

```json
{
  "contract": "coordinator_alignment.v1",
  "criterion_id": "C-01",
  "criterion_title": "Curriculum Alignment",
  "advisory_only": true,
  "score": 1,
  "justification": "Curriculum alignment: 0/1 objectives supported.",
  "objective_matches": [
    {
      "objective_id": "OBJ-0001",
      "objective_text": "A verbatim SLM objective.",
      "matched": false,
      "excerpt": "",
      "rejected": false
    }
  ]
}
```

Result integrity requires this payload on successful v3 Coordinator results, rejects it for other agents/old versions, checks canonical objective identities, evidence disposition and derived C-01 score, and cross-checks both dimensions against the saved objective measurement. Existing official subtotal validation remains unchanged. Replay repeats these checks. Legacy GAD/ITSO warning serialization retains its exact shape.

The additive public field is `domain_scores.coordinator.advisory_outputs`; matrix domain data and Admin's Coordinator pillar carry the same payload. Historical results omit it or return null; they are never relabelled. The supplement shows matched and unmatched objectives and clearly states exclusion from official totals and the PDF.

The joint generation is captured as `coordinator_objective_coverage.v1`, version 1, with official `criterion_ids: ["A-05"]`. It is not mislabeled as `criterion_measurements.v1` or projected through its DPO rules. Existing training exports explicitly skip unsupported contracts. A DPO projector for this new contract is deferred; the other nine criteria retain their supported capture contracts.

## Compatibility and cutover

Keep v1/v2 manifests, snapshots, hashes, saved result meaning, default manifest, seeds, and institutional PDF assets unchanged. The rubric editor selects A-05 strategy requirements using the revision's adapter version, so opening a v3 criterion cannot silently rewrite it to curriculum alignment.

Activation is a separate human-approved operation: prepare a new v3 draft with the original ten institutional descriptions (especially A-05 “Objectives are gauged effectively.”), validate/publish it, coordinate model-validation contract handling with its owner, and verify real inference before activating it. Do not reactivate the incompatible retired revision, modify historical scores, or downgrade migrations. Model-validation implementation remains untouched. The historical runtime path is retained intentionally, not a removable shim, while old jobs need recovery.

## Acceptance verification

Focused tests cover supported source formats and exact spans, ambiguous inventories, denominator preservation, evidence-source rejection, bands, bounded repair and overflow, fake-LLM v3 execution, official mean, persistence/replay tampering, public result and Admin pillar presentation, legacy contracts, shared supplement rendering, version-aware rubric editing, and the unchanged single-page ten-row PDF. Browser/pixel/zoom checks and loaded-adapter/live inference remain separate release checks, not claims made by unit tests.

Local verification: 98 Coordinator/persistence regression tests and 51 affected UI/editor/PDF tests passed. Workspace typecheck, Faculty/Admin lint and production builds, scoped backend Ruff checks/formatting, and `git diff --check` passed. Persistence tests use isolated in-memory SQLite, not the live application database. The broader rubric/snapshot/synthesis compatibility check passed 266 cases; its one legacy error-message regression was corrected and passed in the final targeted check. Real institutional SLM-format samples, PostgreSQL deployment, loaded-adapter inference, and browser/pixel/zoom verification remain unverified. No rubric publication or activation occurred.
