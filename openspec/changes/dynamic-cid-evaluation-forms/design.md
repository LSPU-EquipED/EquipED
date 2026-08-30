## Context

See `proposal.md` for motivation and scope.

EquipED evaluates Student Learning Materials (SLMs) against Curriculum Instruction Development (CID) forms across Subject Matter Expert (SME), Program Coordinator, Gender and Development (GAD), and Information Technology Standards and Outcomes (ITSO) domains. Currently, rubric definitions use static database rows in `rubric_sets`, `rubric_domains`, and `rubric_criteria`, but workers query the database during execution or rely on ungrounded fallbacks. In addition, Program Coordinator evaluations implicitly inherit Subject Matter Expert scores through legacy reconciliation (`server/modules/agents/coordinator/reconciliation.py`) rather than operating against an independent evaluation form and result contract.

This design reuses and extends the existing rubric tables in `server/modules/rubrics`, adds independent atomic activation via `rubric_agent_activations`, introduces orchestrator-level pre-dispatch evaluation snapshots (`evaluation_form_snapshots`), and supports registered typed scoring strategies.

## Goals / Non-Goals

**Goals:**
- Pure DB-free form contract layer: immutable `FormDefinition`, `DomainDefinition`, `CriterionDefinition`, strict strategy config discriminated union, measurement input shapes, `ValidationReport`, canonical ordering/bounds, four immutable capability manifests (`SME_MANIFEST_V1`, `GAD_MANIFEST_V1`, `ITSO_MANIFEST_V1`, `COORDINATOR_MANIFEST_V1`), and pure `validate_form(form, manifest)`. No plugin inheritance or class-based adapter registries.
- Reuse existing `rubric_sets`, `rubric_domains`, and `rubric_criteria` entities in `server/modules/rubrics` by adding only necessary publication, retirement, and audit metadata.
- Track lifecycle via `rubric_sets.status` with single source of truth: `draft | published | retired` enforced by DB CHECK constraint. The lifecycle API remains a thin service façade around existing `server/modules/rubrics` repository methods and shared locking primitives without introducing a generic workflow engine.
- Support atomic per-agent independent activation via `rubric_agent_activations(agent_id PK, rubric_set_id FK, updated_by, updated_at)` with composite FK ensuring same-agent targets. `updated_by` is nullable only for migration/system seed rows; every normal admin activation requires a non-null authenticated admin actor.
- Provide draft editing (at most one editable draft per agent via partial unique index), atomic ordering-only bulk reordering (submitting a complete ordered tree that retains every criterion under its existing domain with no reparenting, and rejects missing, duplicate, or foreign IDs atomically; add/remove/move structural operations remain explicit mutation endpoints), validation against agent capability manifests, publication, retirement (for non-active published sets), and activation rollback (activating an older still-published compatible revision).
- Enforce shared locking protocol: lock parent `rubric_sets` row (`FOR UPDATE`) on draft child mutations/reorders/publication; lock `rubric_agent_activations` then affected `rubric_sets` rows in deterministic `rubric_set_id` sort order on activation/retirement/combined publish+activate.
- Decouple Coordinator into an independent form/result contract: delete `server/modules/agents/coordinator/reconciliation.py` and remove `EvaluationOrchestrator._reconcile_coordinator_result`. Retain Coordinator Version 1 as retired legacy metadata, and create and activate a new published Coordinator Revision 2 matching executable A-05 curriculum alignment behavior.
- Pre-compute and persist complete structured form snapshots in standard `evaluation_form_snapshots` with `UNIQUE(evaluation_id, agent_id)` on the main thread in a single transaction coordinated with the job lock and transition into `EVALUATING` (or precreated during benchmark submission). Incomplete or mismatched snapshot sets fail closed. Pass recursively immutable frozen DTOs into workers and eliminate all worker-side database queries.
- Snapshot canonical hash & bounds: deterministic UTF-8 JSON SHA-256 hash over `evaluation_id`, `agent_id`, `rubric_set_id`/revision identity, `adapter_key`, `adapter_version`, and ordered domain/criterion definitions with sorted keys. Duplicated columns (`evaluation_id`, `agent_id`, `rubric_set_id`, `adapter_key`, `adapter_version`, `snapshot_hash`) must equal payload values at creation, dispatch, recovery, and persistence. Strategy configs strictly bound nesting depth, array lengths, string lengths, total serialized size per config/request/revision/snapshot, and finite numbers. Verified at draft save, locked publication, activation, creation, dispatch, recovery, and persistence.
- Support registered typed scoring strategies (`llm_rubric_guidance`, `count_band`, `ratio_band`, `curriculum_alignment`) with strict JSON schema validation, unknown field prohibition, and prompt injection delimiting.
- Support genuinely new SME, GAD, and ITSO criterion codes through the bounded measurement shape selected by the criterion's registered strategy. Snapshot title, description, scoring rule, guidance, thresholds, domains, and order define the criterion; runtime code SHALL NOT require a per-code plugin. A new measurement shape or Coordinator expansion requires a new adapter version.
- Remove GAD broad `except Exception` swallowing and misleading autouse test fixtures. GAD-01/03/04/05 use `count_band`, while GAD-02 uses `ratio_band`.
- Scope boundaries: `server/modules/rubrics` owns definitions, lifecycle, immutable DTO construction, and schema validation; agent implementations own extraction, prompt assembly, grounding, and execution.
- Authenticated owner-scoped faculty evaluation API responses use a single explicit allowlisted snapshot presentation DTO returning form identity, version, canonical hash, adapter identity, ordered domain/criterion UUID/code/title/description/order, and scorecard presentation fields, while strictly excluding strategy_config, scoring_rule/guidance, raw prompt/response data, and unrestricted provenance.
- Preserve legacy evaluations with explicit forward migration legacy marker; only rows explicitly marked as pre-snapshot legacy display `Legacy — form snapshot unavailable`, while mixed or new missing bindings fail closed.

**Non-Goals:**
- No parallel `cid_forms` module; keep backend in `server/modules/rubrics` and frontend in `client/src/features/admin/rubric-editor`.
- No general survey builder, formula language, user code execution, or plugin architecture.
- No file import/export converters in initial release (manual builder only).
- No unretire operation, separate activation-history table, generic audit log platform, or two-person approval workflow.
- No modifications to applied migrations. Downgrade is unconditionally irreversible.
- No changes to institutional criterion scale (1–4) or terminal Layer 4 synthesis weights.

## Decisions

### 1. Pure Form Contract & Execution Support Matrix
- **Decision**: Define pure Pydantic models in `server/modules/rubrics/contracts.py`:
  - `FormDefinition`, `DomainDefinition`, `CriterionDefinition`, `ValidationReport`.
  - Strategy configurations as a discriminated union:
    - `LlmRubricGuidanceConfig`: bounded prompt guidance and optional level descriptors for scores 1..4; the institutional score range remains fixed even when descriptors are omitted.
    - `CountBandConfig`: mode `minimum_count | maximum_count` with monotonic thresholds for scores 4, 3, and 2 and score 1 as the bounded fallback.
    - `RatioBandConfig`: mode `coverage_percentage | absolute_difference`, monotonic ratio/difference bands, and optional short-sample threshold & issue-count override (`ShortSampleConfig`).
    - `CurriculumAlignmentConfig`: Coordinator-only grounded alignment scoring.
  - Four immutable manifests in `server/modules/rubrics/manifests.py`:
    - `SME_MANIFEST_V1`: strategies (`llm_rubric_guidance`, `count_band`, `ratio_band`), criteria count 1..20, measurement input shapes (score/evidence, instance list using `minimum_count`, qualifying/total units), and `sme_total_prompt_budget_chars` cap.
    - `GAD_MANIFEST_V1`: strategies (`count_band`, `ratio_band`), criteria count 1..10, measurement input shapes (adverse-instance lists using `maximum_count`, female/male counts via `absolute_difference` mode with <=2, <=5, <=10 mapping to scores 4, 3, 2, 1), and `agent_total_prompt_budget_chars` cap. Revision 1 maximum-count thresholds are 0/1/3 for GAD-01 and 0/2/5 for GAD-03/04/05.
    - `ITSO_MANIFEST_V1`: strategy `llm_rubric_guidance`, criteria count 1..10, measurement input shape (score/evidence/chunks), and `agent_total_prompt_budget_chars` cap.
    - `COORDINATOR_MANIFEST_V1`: strategy `curriculum_alignment`, criteria count exactly 1 (A-05 alignment).
  - SME, GAD, and ITSO adapter v1 accept new criterion codes only when their configured strategy maps to one of the manifest's existing measurement shapes. Criterion codes are globally unique case-insensitively within a form. Strategy-selected bounded schemas—not code-specific plugins—drive extraction for both seeded and newly authored criteria.
  - Pure validation function `validate_form(form: FormDefinition, manifest: AgentCapabilityManifest) -> ValidationReport`.
- **Rationale**: Clean separation of pure business logic from database and transport, enabling exhaustive offline testing and preventing runtime plugin complexity.

### 2. Data Model Extension & Lifecycle Concurrency
- **Decision**: Extend existing tables:
  - `rubric_sets`: use existing `status` with allowed values `draft | published | retired` (DB CHECK constraint); add `published_at` (datetime), `published_by` (UUID nullable for migration rows, non-null for normal admin ops), `created_by` (UUID nullable for migration rows, non-null for normal admin ops), `retired_at` (datetime), `retired_by` (UUID nullable), `adapter_key` (str), `adapter_version` (int). Add `UNIQUE(agent_id, rubric_set_id)`.
  - Partial unique index `uq_rubric_sets_one_draft_per_agent` on `(agent_id)` WHERE `status = 'draft'`.
  - `rubric_criteria`: add `scoring_strategy` (str), `strategy_config` (jsonb/dict).
  - New table `rubric_agent_activations`: `agent_id` (PK, str), `rubric_set_id` (UUID, not null), `updated_by` (UUID nullable for migration/system seed rows, non-null for admin ops), `updated_at` (datetime). Composite FK `FOREIGN KEY (agent_id, rubric_set_id) REFERENCES rubric_sets(agent_id, rubric_set_id)`.
  - New table `evaluation_form_snapshots`: `snapshot_id` (UUID PK), `evaluation_id` (FK, UUID), `agent_id` (str), `rubric_set_id` (FK, UUID), `snapshot_payload` (jsonb/dict), `snapshot_hash` (str SHA-256), `adapter_key` (str), `adapter_version` (int), `created_at` (datetime), `UNIQUE(evaluation_id, agent_id)`. Snapshot rows are immutable and ineligible for update/delete.
  - `agent_results`: add nullable `form_snapshot_id` (FK to evaluation_form_snapshots).
  - Explicit legacy marker: `evaluation_jobs.is_pre_snapshot_legacy BOOLEAN NOT NULL DEFAULT FALSE`. Forward migration backfills `is_pre_snapshot_legacy = TRUE` ONLY for coherent historical evaluation jobs that have persisted `AgentResult` rows, zero `evaluation_form_snapshots`, and where all `AgentResult.form_snapshot_id` values are NULL. Nonterminal or queued jobs and mixed bindings are not marked; all new evaluation jobs default to `FALSE`. Downgrade refuses under existing irreversible migration policy. Only rows with `is_pre_snapshot_legacy = TRUE` display `Legacy — form snapshot unavailable`, while any unlinked or missing snapshot on non-legacy rows fails closed. No heuristic date or reconstruction logic is used.
- **Concurrency & Shared Locking Protocol**:
  - Draft child mutations, reorders, and publications lock parent `rubric_sets` row (`FOR UPDATE`) before checking status or modifying children.
  - Activation, retirement, and combined publish+activate lock `rubric_agent_activations` row first, followed by all affected `rubric_sets` revision rows in deterministic `rubric_set_id` sort order. Publishing revalidates the locked draft before committing.

### 3. Lifecycle, Retirement & Rollback
- **Decision**: Lifecycle operations are exposed via a thin service façade in `server/modules/rubrics/service.py` wrapping repository queries and row locking primitives without a generic workflow engine. Draft editing occurs only on the single draft per agent. Deleting a draft deletes only its child domains and criteria. Published revisions are immutable; attempting to edit a published revision returns HTTP 409 Conflict.
- **Bulk Reordering**: `POST /api/v1/admin/rubrics/{rubric_set_id}/reorder` is strictly ordering-only. It accepts a complete ordered tree of domain and criterion IDs. It validates under parent row lock that all submitted IDs belong to the draft, contain no duplicates, leave no domain or criterion omitted, and retain every criterion under its existing domain; criterion reparenting across domains is forbidden and rejected atomically. Structural mutations (adding, deleting, or explicitly moving criteria between domains) remain explicit dedicated mutation endpoints.
- **Retirement & Active Revision Semantics**: Admins may retire a non-active published revision (`published -> retired`). An active revision cannot be retired until another compatible revision is activated. Retired revisions cannot be activated, drafted from, or edited. Retirement affects future selection only: an in-flight evaluation or benchmark bound to an immutable snapshot whose source revision is later retired continues execution without change.
- **Rollback**: Performed by updating `rubric_agent_activations` to point to a previously published, non-retired compatible revision.

### 4. Two Explicit Snapshot Creation Paths, In-Memory Snapshots & Recovery
- **Decision**: Snapshot creation has two explicit creation paths:
  1. **Path 1 (Standard Evaluations)**: On evaluation preparation (after determining scheduled agents from full/partial intent and reference readiness), the main supervisor thread resolves current active revisions from `rubric_agent_activations`, builds canonical frozen DTOs (`EvaluationFormSnapshotDTO`), computes a canonical UTF-8 JSON SHA-256 hash (with sorted keys covering `evaluation_id`, `agent_id`, `rubric_set_id`, `adapter_key`, `adapter_version`), and inserts all snapshots into `evaluation_form_snapshots` in a single transaction coordinated with the job row lock and transition into `EVALUATING`.
  2. **Path 2 (Model Validation Submission)**: The benchmark submission endpoint verifies echoed active published revisions and exact criterion UUID sets under activation-first and deterministic revision locks (`rubric_agent_activations` followed by `rubric_sets` revisions in sorted order), creates the `EvaluationJob`, and atomically precreates standard `evaluation_form_snapshots` alongside the job and benchmark expectation rows in the same transaction.
- **Preparation & Recovery on Precreated Snapshots**: When an evaluation job already has precreated standard snapshots persisted at submission time, later preparation when transitioning into `EVALUATING` and subsequent recovery reuse those existing snapshots, verify hashes and schema bounds, and NEVER reread `rubric_agent_activations`. Later activation or retirement cannot alter an accepted benchmark. Incomplete, partial, duplicate, wrong-agent, hash-mismatched, or column-mismatched snapshot sets fail closed. Workers receive frozen DTOs with zero ORM sessions or DB queries.
- **Dynamic Order & Score Matching**: Dynamic domain and criterion order is reconstructed directly from verified immutable snapshot payloads. Persisted `CriterionScore.criterion_id` values match exact snapshot `criterion_code` values; missing, duplicate, or extra criterion scores fail closed. Rubric criterion UUIDs remain immutable snapshot metadata; no second score identity column is introduced.
- **Recovery**: Reuses existing `evaluation_form_snapshots` bound to the evaluation job, verifies canonical hashes and column equality, and rejects incomplete snapshot sets without re-resolving active pointers.

### 5. Registered Typed Scoring Strategies & Security
- **Decision**: Registered strategies execute via pure calculator functions:
  - `llm_rubric_guidance`: Bounded validated LLM-assigned 1–4 score with prompt guidance and level descriptors. Prompts structurally delimit untrusted text and prohibit instruction execution.
  - `count_band`: Deterministic instance counting with explicit `minimum_count` mode when more qualifying instances are better (for example SME 4+/2+/1+/0) or `maximum_count` mode when fewer adverse instances are better (GAD).
  - `ratio_band`: Deterministic ratio calculation (`coverage_percentage` or `absolute_difference`) with optional short-sample issue-count override for OP-01.
  - `curriculum_alignment`: Coordinator-only grounded alignment scoring.
- **Security Constraints**: Strict schemas with unknown fields forbidden, bounded nesting depth, bounded array lengths, bounded string lengths, bounded total serialized size per config/request/revision/snapshot, finite numbers, and monotonic bands covering scores 1–4. Strategy configs cannot contain model, URL, tool, or template controls. Revalidated at draft save, locked publication, activation, and snapshot load.

### 6. Coordinator Decoupling & Teardown
- **Decision**: Delete `server/modules/agents/coordinator/reconciliation.py` and remove `EvaluationOrchestrator._reconcile_coordinator_result`. Coordinator outputs are persisted directly. Existing Coordinator Version 1 (ten unexecuted rows) is preserved as retired legacy metadata. The forward migration creates and activates a new published Coordinator Revision 2 containing only the executable A-05 curriculum alignment criterion. Synthesis calculates Coordinator contribution directly from its returned criterion count/form without altering agent-level synthesis weights.
- **Implementation Dependency**: The minimum Coordinator merge teardown lands after snapshot resolution but before strict snapshot-bound result persistence. This prevents the legacy ten-criterion merged Coordinator result from violating Revision 2's single A-05 snapshot contract; no temporary Coordinator exception is permitted.

### 7. API, Admin UI, Model Validation & Faculty Presentation Boundary
- **Decision**: Retain `/api/v1/admin/rubrics` and extend `client/src/features/admin/rubric-editor`. Implement atomic bulk reorder endpoint `POST /api/v1/admin/rubrics/{rubric_set_id}/reorder` accepting a complete ordered tree that is ordering-only (strictly retaining criteria under their existing parent domains with no reparenting) and atomically rejecting missing/duplicate/foreign IDs under parent lock.
- **Model Validation Catalog**: Model validation preparation catalog returns exact active `rubric_set_id`, revision version, and rubric criterion UUID, code, title, domain, and display order.
- **Model Validation Submission & Standard Snapshots**: Submission echoes `rubric_set_id` and rubric criterion UUIDs alongside expected scores (1–4). Under activation-first shared locks (`rubric_agent_activations` then `rubric_sets` revisions in sorted order), submission verifies that echoed revisions match current active published compatible revisions with exact criterion UUID sets. It creates the standard `EvaluationJob` and persists standard `evaluation_form_snapshots` for those exact revisions in the same transaction. Later evaluation preparation and recovery reuse these precreated snapshots and never reread `rubric_agent_activations`, guaranteeing that later activation or retirement cannot alter an accepted benchmark. Partial mode binds SME/GAD/ITSO and requires no curriculum; full mode requires explicit curriculum input and binds SME/GAD/ITSO/Coordinator. No separate benchmark binding table or format is introduced.
- **Faculty Presentation DTO**: Authenticated owner-scoped faculty evaluation endpoints serve a single explicit allowlisted snapshot presentation DTO containing:
  - Snapshot & Form identity: `form_snapshot_id`, `rubric_set_id`, form `version`
  - Revision & Adapter identity: `snapshot_hash`, `adapter_key`, `adapter_version`
  - Ordered domain/criterion definitions: criterion UUID, criterion code, criterion title, criterion description, domain name, domain order, criterion order
  - Existing scorecard presentation fields: criterion score, justification, evidence, ungrounded flags
  - Strictly excluded: `strategy_config`, `scoring_rule`/guidance, raw prompt/response and group response data, and unrestricted internal provenance.
- **Legacy Evaluations**: Only historical evaluation rows with `evaluation_jobs.is_pre_snapshot_legacy = TRUE` display `Legacy — form snapshot unavailable` in API/UI metadata; mixed or new unlinked evaluation results fail closed.

### 8. Prompt Management Decoupling & Framing Contract
- **Decision**: Active GAD and ITSO managed prompts serve solely as criterion-agnostic framing; fixed criterion identifiers in managed prompts fail closed, and all per-criterion authority, descriptions, guidance, and validation schemas derive exclusively from the bound form snapshot. Forward-only migration 0005 preserves already-generic admin prompt definitions and unconditionally refuses downgrade.

### 9. Cross-Cutting Local LLM Prerequisite & Response Bounds
- **Decision**: Local LLM execution enforces fixed byte-capped response reads alongside configuration maxima (32768 output tokens, 3600 second timeout) without adding a new configuration knob.

## Risks / Trade-offs

- **[Risk] Migration Execution on Shared Neon DB**
  → *Mitigation*: Forward migrations are verified on local temporary PostgreSQL databases first; shared Neon execution is a separate post-implementation deployment checkpoint requiring explicit manual administrator approval.
- **[Risk] Prompt Context Overflow from Dynamic Forms**
  → *Mitigation*: Capability manifests enforce strict character and criteria count limits during draft validation and publication gates.
- **[Risk] Broken Worker Independence**
  → *Mitigation*: Workers receive only frozen Pydantic DTOs; unit and integration tests assert no database session is opened in worker threads.

## Migration Plan

1. **Forward Database Migration**:
   - Migrate existing `rubric_sets.status='active'` rows to `published`.
   - Add DB CHECK constraint for `status IN ('draft', 'published', 'retired')`.
   - Add partial unique index on `(agent_id)` WHERE `status = 'draft'`.
   - Add unique `(agent_id, rubric_set_id)` and new audit/adapter columns.
   - Create `rubric_agent_activations` with composite FK, and insert initial activation rows for SME, GAD, and ITSO Revision 1 (with null `updated_by` for migration seed).
   - Create `evaluation_form_snapshots` with `UNIQUE(evaluation_id, agent_id)`.
   - Add nullable `agent_results.form_snapshot_id`.
   - Add column `evaluation_jobs.is_pre_snapshot_legacy BOOLEAN NOT NULL DEFAULT FALSE`. Backfill `is_pre_snapshot_legacy = TRUE` ONLY for coherent historical jobs having persisted `AgentResult` rows, zero `evaluation_form_snapshots`, and where all `AgentResult.form_snapshot_id` values are NULL. Queued, in-flight, or mixed jobs remain `FALSE`.
   - Backfill strategy configurations using exact frozen config schemas: SME OP-01/03/04/A-01/A-05 to `ratio_band` (with OP-01 short-sample config), OP-02/05/A-02/A-03/A-04 to `count_band`; GAD-01/03/04/05 to `count_band`, GAD-02 to `ratio_band` (`absolute_difference` mode); ITSO-01..05 to `llm_rubric_guidance`.
   - Mark Coordinator Version 1 as `retired`, create published Coordinator Revision 2 with A-05 `curriculum_alignment`, and activate it.
   - Forward migration 0005 preserves already-generic admin prompt definitions for GAD and ITSO as criterion-agnostic framing while refusing downgrade.
   - Update bootstrap scripts to refuse destructive overwrites of published revisions.
2. **Backward Compatibility**: Existing evaluation records with `evaluation_jobs.is_pre_snapshot_legacy = TRUE` display `Legacy — form snapshot unavailable`. Mixed or new evaluations without snapshots fail closed.
3. **Migration Downgrade Refusal**: The migration downgrade method is unconditionally irreversible and refuses to drop applied tables/columns; rollback of deployed code in production uses a forward compensating migration. Form activation rollback remains purely an administrative update to `rubric_agent_activations`.
