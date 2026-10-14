# Coordinator v3: Objective Gauging and advisory Curriculum Alignment

**Status:** Finalized specification; implementation is opt-in through adapter v3. Local verification is recorded below. The default Coordinator contract remains v2; no live rubric has been created, published, or activated.

## Boundary and ownership

Coordinator owns source inventory, evidence validation, and deterministic coverage scoring. The immutable rubric snapshot selects the harness version. Its official form remains exactly OP-01–05/A-01–05; A-05 uses `objective_gauging`. C-01 is a harness-owned supplemental definition, not an eleventh rubric row. Its fixed definition and bands are governed by adapter v3, so changing them requires another version.

Shared agent contracts own the typed output. Synthesis validates and persists it using existing advisory JSON storage, without a database schema migration. Faculty and Admin render the supplement separately using a shared presentation component. No new service framework, queue, or concurrency boundary is introduced; pure inventory data is immutable and existing durable admission/recovery remains authoritative.

## Source inventory and supported format

A ready authoritative curriculum remains mandatory. Before any scoring call, derive the inventory from canonical direct SLM text, never vector storage or model-returned objectives.

Supported headings include Objectives, Learning Objectives, Course Objectives, Lesson Objectives, Learning Outcomes, Intended Learning Outcomes, Lesson Learning Outcomes, and Targets/ Objectives (case-insensitive), with optional Markdown/lettered prefixes and a trailing colon. A heading may wrap over at most three consecutive nonblank lines only when their recognition-space join completes an exact finite known heading; no keyword/hint-based heading join or arbitrary prose skipping is supported. This includes `Intended / Learning / Outcomes` and `Targets/ / Objectives` (slashes here denote line breaks). Incomplete buffered fragments fail. Consecutive recognized objective heading aliases before any entry form one header (blank lines between complete aliases are allowed); this does not permit independent empty objective sections or intervening prose. Entries must be numbered consecutively from 1, or bulleted with `-`, `*`, `•`, or `·`; a marker separated from its entry by a PDF line break is accepted only with matching indentation and plain, unmarked entry text, never another full or split marker or an intervening blank. Each section uses one consistent indentation and list style. Indented continuations remain supported. One exact learner lead-in ("At the end of this/the lesson/module/course, [the] students/learners should/will be able to:" or "After completing ...") is accepted before the first entry of each section and is not inventoried. It may wrap over at most three consecutive lines at word boundaries, but every buffered line must extend a known phrase and the complete phrase must precede the first marker; unknown, incomplete, repeated, misplaced, or blank-separated lead-ins fail.

Unindented continuations require explicit incomplete syntax and a following marker or recognized section heading that bounds the finished entry. Existing lowercase wraps remain supported. The verified final objective additionally needs a title-cased noun-phrase wrap: this is restricted to a previous line ending exactly `in the` and a continuation of exactly three title-cased alphabetic words, space-separated, whose first word is a nominal `-tion` form (no sentence punctuation). A completed clause ending `; and` may finish an entry only at the next explicit list marker, never at a section heading or EOF; the conjunction remains part of its verbatim span. Blank-separated incomplete wraps, unindented wraps at source EOF, other unfinished entries, and completed entries followed by unheaded prose still fail closed. Source spans are never rewritten and receive canonical `OBJ-0001` onward IDs.

Recognized section headings (including Content, Discussion, References, Assessment, Quiz, Student Learning Strategies, Online Activities (optionally labeled Synchronous/ Asynchronous), and numbered Lesson/Unit/Module headings) terminate objective sections. Exact finite section names may use the same bounded heading join, including `Online Activities` followed by `(Synchronous/` and `Asynchronous)`. Student Learning Strategies and Online Activities are terminators, not assessment evidence; assessment support still requires separately headed assessment/activity/exercise material. Unknown explicit headings within an objective section, nested/mixed lists, skipped numbers, duplicates, missing sections, empty sections, arbitrary unnumbered objectives, and ambiguous continuations fail closed. Objectives nested directly in assessment material are ambiguous and fail rather than silently joining the inventory. A sentence-case singular subject `The [main] objective ... has ... to ...` in ordinary discussion is not classified as a heading solely for containing the word objective. This narrow predicate form cannot introduce an unmarked objective; explicit colon/Markdown/uppercase unknown headings still fail, and such a sentence after a finished objective remains unsupported prose.

The actual failed PDF was reproduced locally through unchanged backend `prepare_canonical_source`: canonical SHA256 `c33acec745c0810518ebcf92e93d879570739cc58481a88faa6935a8e86fbaf5`, length 7,225, five complete objectives, three single-line and two two-line entries. PDF geometry and a body-redacted rendering verified all five explicit markers as SymbolMT **U+2022**, not U+F0B7. No PUA support was added. The source has no separately headed assessment section: a fake explicit-client v3 public-evaluate/persistence-integrity smoke therefore retained 0/5 A-05 support (score 1), five advisory rows, ten official rows and their mean; synthetic curriculum claims are development checks, not institutional curriculum validation. An anonymized fixture preserves the real heading breaks, lead-in, glyph, wrap syntax, and terminator without retaining private SLM content. This bounded compatibility still does not support arbitrary PDF layouts. Unicode whitespace (including nonbreaking spaces) is normalized to ASCII spaces only for heading and learner-preface recognition; source text and objective spans remain verbatim. U+00B7 middle dot is accepted only as a leading bullet marker under the same whitespace, indentation, and list-consistency rules as the existing bullets; mid-text dots do not split objectives. Other uncertain glyph substitutions remain unsupported. Upstream canonical extraction must be complete; the harness rejects the runtime gap marker, sources beyond 200,000 characters, more than 100 objectives, and objective text beyond 4,000 characters.

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
