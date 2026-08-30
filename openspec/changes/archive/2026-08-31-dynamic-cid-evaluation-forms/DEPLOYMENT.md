# Dynamic CID Evaluation Forms Deployment

## Scope

This release introduces versioned CID evaluation forms, immutable per-evaluation form snapshots, criterion-agnostic managed prompts, strict legacy-result labeling, admin lifecycle APIs, and the corresponding admin and faculty interfaces.

## Prerequisites

- Back up the target PostgreSQL database.
- Pause evaluation admission and execution for the migration window.
- Confirm the target is at Alembic revision `20260829_0003` or later.
- Verify the active SME, GAD, ITSO, and Coordinator rubric revisions pass adapter capability validation.
- Verify active GAD and ITSO managed prompts contain no fixed numeric criterion identifiers.

## Migration Order

From `server/`, run `uv run alembic upgrade head` only after explicit administrator approval. Alembic applies:

1. `20260829_0004` — form lifecycle, activation pointers, typed strategies, immutable snapshots, and result bindings.
2. `20260829_0005` — criterion-agnostic GAD and ITSO managed prompts.
3. `20260829_0006` — explicit pre-snapshot legacy marker for coherent historical terminal evaluations.

Shared development database execution remains an approval-gated deployment checkpoint and is not part of implementation verification.

## Post-migration Checks

- `uv run alembic current` reports `20260829_0006`.
- Exactly one same-agent activation pointer exists for each agent and targets a published revision.
- Only coherent historical terminal evaluations are marked as pre-snapshot legacy.
- Admin revision listing, draft validation, and Model Validation criteria catalog load successfully.
- A new partial evaluation binds SME, GAD, and ITSO snapshots; a new full evaluation additionally binds Coordinator.

## Rollback

Revisions `0004` through `0006` intentionally refuse downgrade because reversing them would discard immutable provenance and cannot safely reconstruct prior activation or prompt state. Restore the pre-migration backup and deploy the matching earlier application version instead.
