## Context

The current evaluation setup requires a ready curriculum reference before a fresh evaluation can start. That is correct for full curriculum-grounded review, but it blocks evaluation entirely when program detection is missing or the selected program has no uploaded/embedding-ready CHED curriculum. SME, GAD, and ITSO can still produce useful advisory review without curriculum grounding, but the UI currently has no honest path for that degraded case.

The system already treats synthesis as partial when an agent fails or is missing, normalizing successful agent weights. This change uses that existing partial-output contract deliberately for a no-curriculum mode instead of relying on accidental failures.

## Goals / Non-Goals

**Goals:**
- Replace hard “reference detected” blocking with an explicit curriculum decision.
- Allow faculty to continue with an honest partial evaluation when no ready curriculum exists.
- Preserve full evaluation quality when an embedding-ready curriculum is available.
- Avoid pretending Coordinator/curriculum-grounded scoring occurred when no curriculum is attached.
- Keep ownership and shared-reference validation unchanged for SLMs and available references.

**Non-Goals:**
- No automatic GE/minor course-to-program inference.
- No syllabus picker or syllabus requirement.
- No external curriculum lookup.
- No Celery/Redis job model change.
- No new scoring/rubric model for Coordinator beyond skipping/limiting it when curriculum is absent.

## Decisions

### Explicit partial mode instead of implicit missing curriculum

Evaluation submission without `curriculum_id` will require explicit intent, for example a `partial_without_curriculum` boolean or equivalent enum. This prevents accidental full evaluations without curriculum because of a frontend bug or missing field.

Alternative considered: make `curriculum_id` simply optional. Rejected because it weakens the full-evaluation contract and makes missing-reference bugs hard to distinguish from deliberate partial runs.

### Coordinator is not run as a normal full domain without curriculum

When partial/no-curriculum mode is selected, the pipeline must not present a normal Coordinator result as curriculum-grounded. Coordinator will be skipped entirely by constructing the Supervisor without `ProgramCoordinator`. Synthesis will normalize weights over available successful domains using the existing partial behavior.

Alternative considered: run Coordinator using only SLM text or run-and-mark-limited. Rejected for this phase because the user-facing meaning of Coordinator review is curriculum alignment; running it without curriculum risks misleading users and wastes an LLM call.

### Deliberate partial completes successfully

No-curriculum partial is a user-selected degraded mode, not an unexpected pipeline failure. The evaluation job should finish as `COMPLETED` with partial result metadata and a missing-curriculum reason. Accidental partials caused by agent errors may still use the existing failure semantics.

### UI shows a decision point, not a dead end

When no ready curriculum exists for the selected program, the setup screen will show three clear choices: upload/rebuild curriculum, change program, or continue partial. The partial action must use copy that sets expectations before submission.

### Existing evaluation reuse remains unchanged

If an evaluation already exists for the SLM, the page may reuse it as today. The new partial decision only applies before creating a fresh evaluation.

## Risks / Trade-offs

- **Risk: Users treat partial results as complete.** → Mitigation: mark partial/no-curriculum status in setup, result header, score dashboard, and export/report surfaces.
- **Risk: Weight normalization makes partial scores look comparable to full scores.** → Mitigation: keep `is_partial`/partial status visible and include a missing-curriculum explanation.
- **Risk: Faculty overuse partial mode instead of uploading curriculum.** → Mitigation: make Upload Curriculum/Change Program primary actions and Partial a secondary/degraded path.
- **Risk: Backend accepts unintended no-curriculum jobs.** → Mitigation: require explicit partial intent when `curriculum_id` is absent.
