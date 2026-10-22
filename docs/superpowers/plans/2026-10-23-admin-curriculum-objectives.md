# Admin-managed curriculum objectives

Status: Implemented. Migration `20261023_0001` is applied to the configured database. Initial verification: 261 backend tests and 34 Admin tests passed; the original 12 objectives and 356 mappings retained their values. Management response contracts were also validated against the migrated database.

Subsequent user-authorized changes enabled BSCS standalone alignment with same-program validation and imported CS01–CS10 plus five verified course rows (50 mappings). Other rows from the supplied matrix remain pending verification. BSCS enablement passed 266 backend and 41 frontend tests plus both production builds. The Agent Prompts admin frontend was subsequently removed; 27 routing/navigation tests and the updated admin build passed. The baseline and proposal below record the original plan rather than current program restrictions.

## Intended outcome

Administrators can add and edit curriculum objectives from the Admin portal instead of editing database rows or seed JSON. Administrators can also assign objectives to existing courses with an expected Introductory, Enabling, or Demonstrative level. Faculty alignment uses the saved course mappings on subsequent checks. Existing results retain their original descriptions, levels, and evidence.

This remains structured relational reference data. It does not require PDF ingestion, OCR, embeddings, another model call, or changes to the evaluation harness.

## Baseline before implementation

- [Objective and mapping models](../../../apps/server/modules/curriculum/models.py) already separate an objective's identity, code, description, and program from the course-to-objective I/E/D mapping. Code is unique within a program; course/objective pairs are unique.
- [Catalog endpoints](../../../apps/server/modules/curriculum/router.py) currently provide authenticated reads for courses and roadmaps; there are no objective-management endpoints.
- [Alignment admission](../../../apps/server/modules/alignment/curriculum/admission.py) explicitly supports BSInfoTech, including the legacy BSIT alias. The shared application program catalog also includes BSCS. These are different scopes and must remain explicit in the editor.
- [Saved alignment results](../../../apps/server/modules/alignment/curriculum/results.py) already snapshot each successful result's code, description, expected level, and evidence. They must not be reconstructed from subsequently edited objectives.
- The [seed script](../../../apps/server/scripts/seed_curriculum_map.py) currently overwrites seed-defined descriptions and levels and removes certain mappings during convergence. That behavior conflicts with making saved admin edits authoritative and must be reconciled before rollout.

## Proposed Admin experience

Add a **Curriculum Objectives** workspace under **Knowledge Base**, using the existing compact table and modal conventions.

The objective catalog provides code/description search, a program filter, mapping counts, an Add Objective action, and an Edit action per row. Show an explicit unmapped state for newly added objectives; adding a catalog entry alone does not include it in any course's alignment.

| Field | Proposed behavior |
| --- | --- |
| Objective ID | Server-generated UUID; immutable and omitted from the normal edit form. |
| Code | Required, trimmed and normalized to uppercase, at most 50 characters; unique per normalized program. Do not hardcode the existing IT01–IT12 range. |
| Description | Required, trimmed multiline text; bounded to 4,000 characters for new writes, with existing longer values checked before applying that limit. |
| Program | Required dropdown with exactly **BSCS** and **BSInfoTech**, with no free-text or custom options. Require an explicit selection when adding an objective and preselect the saved value when editing. Normalize legacy BSIT values to BSInfoTech for display. A mapped objective cannot move to another program while incompatible course mappings exist. |

Include a **Course Mappings** view in the same feature: select an existing course, list objectives from its program, and choose **I**, **E**, **D**, or **Not mapped**. Explain the three levels beside the editor. A blank choice removes that mapping; it does not store a null level.

An explicit Save action applies validated changes to future checks. Show the affected mapping count when editing an objective, preserve entered values on validation failures, and refresh the list after a successful save. Forms must support keyboard use, visible focus, labelled controls, and inline errors.

## Scope recommendation

Include objective creation/editing and mappings to existing courses in the first release. A new objective otherwise has no effect on the alignment workflow.

Do not include permanent deletion, bulk imports, course creation, roadmap editing, rubric editing, or a draft/publish workflow in this increment. Archive/delete can be designed separately if needed.

The catalog supports both **BSCS** and **BSInfoTech**, as selected by the user. Keep existing alignment program gates and label BSCS entries as unavailable for standalone alignment until that program's authoritative course map and admission support are intentionally enabled. Do not imply that changing the Program field enables another program's alignment.

## Implementation sequence

1. **Define contracts and migration.** Extend the curriculum-owned schemas with validated create/edit and mapping inputs and typed list responses. Add objective edit-version metadata and course-mapping edit-version metadata for optimistic concurrency. Add a curriculum-owned append-only change history containing actor, timestamp, operation, and before/after values. Preserve existing UUIDs, codes, and mapping rows during migration. Check existing case/alias collisions before enforcing normalized uniqueness; report conflicts rather than silently merging records.

2. **Implement domain operations.** Keep objective catalog management and mapping operations in the existing curriculum module, with thin authenticated routers delegating to its service interface. Guard every management read/write with `require_admin`. Validate lengths, canonical programs, duplicate codes, mapping levels, and course/program compatibility on the server. Use database constraints as the final concurrency guard; return actionable conflict errors rather than leaking database details. Save data changes, version increments, and audit history in one transaction. Reject stale form versions instead of silently overwriting another admin's changes.

3. **Protect admin edits from seeds.** Preserve existing convergence behavior for untouched seed-managed rows, but stop a normal seed run from overwriting admin-modified objectives or mappings. Retain a durable ownership marker for a course's edited mapping set so removed seed mappings are not recreated. Code changes must not cause an ordinary seed run to silently recreate an old objective. An explicit administrative reset can be a separate operation; an implicit reset is outside this scope.

4. **Build the Admin feature.** Add a self-contained `curriculum-objectives` feature with its own API adapter, query/mutation hooks, objective form, catalog table, and course mapping editor. Add the navigation item and protected route through the Admin composition root. Reuse shared program types and existing UI primitives; do not import another feature's internals. Keep validation feedback and unsaved-change handling local to the feature.

5. **Integrate with alignment history.** Future runs continue loading mappings through the curriculum service. Capture the objective identity/edit version and mapping version used for a new check in its provenance, including failed checks, without rewriting historical records. Ensure edits made while a model call runs cannot change the snapshot that the check evaluates or displays. Existing successful result snapshots remain authoritative for historical reads.

6. **Update authoritative documentation.** Record the new admin capability and seed ownership rules in PRODUCT.md and PRD.md, add the Admin workspace to the relevant architecture description, and describe the editor behavior in DESIGN.md. Explicitly preserve current program scope, human authority, and local data handling.

## Verification and acceptance

- Unauthenticated callers cannot access management operations; faculty cannot create, edit, or remap objectives.
- An administrator can create IT13, edit its description, assign it to a matching existing course at level E, and see it included in the next alignment check.
- The editor rejects blank fields, duplicate normalized codes within a program, invalid levels, incompatible program moves, and stale edits. Invalid mapping submissions leave the entire previous mapping set intact.
- The Program dropdown offers only BSCS and BSInfoTech, requires a selection, and preselects an existing objective's saved program on edit. New management writes accept only those two canonical values; unknown or custom program values are rejected by the server. Legacy BSIT records display as BSInfoTech.
- An existing objective can be renamed without changing its UUID or losing compatible course mappings.
- Editing an objective leaves previously saved alignment descriptions, expected levels, and evidence unchanged. A concurrent check retains the exact reference snapshot it started with.
- A normal seed rerun preserves admin descriptions, code changes, mapping changes, and deliberate mapping removals while retaining convergence for untouched seed-managed data.
- Backend tests cover authorization, constraints, alias normalization, transaction rollback, concurrency conflicts, migration preservation, history, seed protection, and alignment integration. Admin component/API tests cover add/edit, mapping saves, failed saves, and stale-edit feedback.
- Run scoped server tests and lint/format checks, then Admin tests, lint, and production build. Manually verify keyboard access, long descriptions, empty/unmapped states, and layout at desktop/mobile widths.

## Settled implementation choices

The program choices are settled: **BSCS** and **BSInfoTech** in a required dropdown. Enabling BSCS standalone alignment remains a separate behavior change.

The workspace is a separate Curriculum Objectives entry under Knowledge Base.

Implementation follows the backend contracts and seed protection first, then the objective editor and mappings together, followed by alignment provenance and verification. Existing institutional objective values are preserved by the schema migration; adding or modifying those values remains an explicit administrator action in the editor.
