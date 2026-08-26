## Context

`features/admin/` began as one feature with a flat `pages/`, `components/`,
`hooks/`, `api/`, and `utils/` layout. Model Validation and Reference Library
have since grown into independent workflows, but their route pages still own
their queries, mutations, mutable form state, dialog state, presentation
sections, and helpers. This produces 1,600+ and 800+ line page files without
changing the fact that both workflows remain Admin-only.

The client is feature-driven: each capability must be self-contained, no Admin
subfeature may import another Admin subfeature, and `shared/` is reserved for
proven reuse by two or more top-level features.

## Goals / Non-Goals

**Goals:**

- Establish `model-validation/` and `reference-library/` as vertical Admin
  subfeatures, each owning its page, components, hooks, API code, types, and
  utilities.
- Reduce route pages to orchestration that composes cohesive sections and
  feature-local hooks.
- Preserve every query key, polling interval, mutation callback, route, payload,
  rendered UI, and interaction behavior.
- Keep the router dependent on a narrow Admin public surface instead of internal
  page paths.

**Non-Goals:**

- Rebuilding visuals, changing accessibility behavior, adding dependencies, or
  changing backend contracts.
- Migrating smaller Admin capabilities in this change.
- Creating generic data tables, dialogs, hooks, or a new global shared layer.
- Making Model Validation and Reference Library import one another.

## Decisions

### Use vertical Admin subfeatures

The target structure is:

```text
features/admin/
├── index.ts
├── model-validation/
│   ├── pages/ModelValidationPage.tsx
│   ├── components/
│   ├── hooks/
│   ├── api/
│   ├── types.ts
│   └── utils/
└── reference-library/
    ├── pages/ReferenceLibraryPage.tsx
    ├── components/
    ├── hooks/
    ├── api/
    ├── types.ts
    └── utils/
```

`features/admin/index.ts` directly and explicitly exports all eight
route-facing Admin page components. Only `app/router.tsx` imports from this
index. It is not a wildcard barrel for internal components, hooks, types, API
code, or utility modules, and the refactor SHALL NOT introduce lazy route
loading or Suspense behavior.

### Keep ownership local; preserve genuine cross-feature services

Model Validation owns `ModelValidation*` and `AdminEvaluationResponse` types
and its validation creation, history, metric, and criterion-catalog API calls.
Reference Library owns its list, preview URL, delete, rebuild, and
library-specific DTO/mapper API code. The existing document workflow API,
including SLM upload, document polling, and curriculum suggestions, remains in
its established document feature because it is genuinely cross-workflow.

`AdminUploadInput` and `uploadReferenceDocument` remain in the legacy Admin
files because the unmigrated Admin Ingest page owns their policy-area upload
payload. It SHALL NOT import Reference Library implementation code. Shared
document primitives (`ReferenceSourceType`, `PolicyArea`, labels, and document
processing status) remain in their existing shared document-type owner because
both Admin Ingest and Reference Library consume them. The legacy Admin API and
types retain only smaller, unmigrated capabilities; moved methods and
feature-private types are removed rather than duplicated.

### Extract cohesive sections, not atomized markup

Model Validation sections are: form preparation/score entry, performance
metrics including the confusion matrix, and validation history/detail. Its
query, mutation, and score-entry state move into feature-local hooks. Small
presentational elements remain next to the section that owns them unless used by
multiple sections.

Reference Library retains separate Reference and Policy tabs because their data
columns and lifecycle semantics differ. It may share a feature-local delete and
rebuild state helper, but it SHALL NOT use a generic configurable table
abstraction.

### Co-locate feature-private utilities and tests

Model Validation's confusion-matrix helper and existing unit tests move to
`model-validation/utils/` and `model-validation/utils/__tests__/`. Other
feature-private helpers move similarly. This follows the existing client test
layout and prevents Admin-wide utility dumping grounds.

### Migrate in bounded, behavior-preserving slices

First establish the Model Validation subfeature, then Reference Library, then
replace all Admin router imports with explicit `features/admin/index.ts` exports
and remove old empty directories. Each subfeature move must be complete before
the next one; there is no prolonged dual implementation or compatibility shim.

### Preserve query and mutation topology

Extraction must preserve a single observer for each existing Model Validation
query, its exact keys, enabled predicates, polling intervals, conditional detail
mounting, and form-reset ordering. Reference Library must retain conditional tab
mounting so inactive policy/reference tabs do not fetch or retain mutation state.
Its reference and policy mutations remain separate, use their existing awaited
`onSettled` invalidation, and keep delete dialogs open after failures. The
existing `activeMutationId` behavior is outside this refactor and SHALL remain
unchanged.

## Risks / Trade-offs

- **Moved hooks alter query/mutation lifecycle behavior** → Preserve query keys,
  enabled predicates, polling, and callbacks verbatim; test and build after each
  bounded subfeature migration.
- **Large prop surfaces recreate the page monolith in a component** → Pass
  cohesive view-model objects from hooks and retain state with its owning
  section; do not pass unrelated page state through every component.
- **Premature generic abstractions hide domain differences** → Keep tables,
  dialogs, and action controls subfeature-local.
- **Import drift breaks routes** → Export only route pages through Admin's root
  index and validate all existing Admin routes after the move.
- **A move accidentally changes visual behavior** → Treat this as structural
  only; preserve markup/classes and use a manual Admin smoke pass after build.

## Migration Plan

1. Move Model Validation types, API calls, utilities/tests, hooks, and cohesive
   sections into its subfeature; leave its page as orchestration.
2. Move Reference Library types, API calls, utilities, action state, tabs, and
   row/dialog sections into its subfeature; keep its two domain-specific tabs.
3. Add root Admin route exports, update router imports, and remove obsolete
   moved files/exports only after all internal imports resolve.
4. Run client typecheck, lint, tests, production build, network/polling checks,
   and manual Admin route smoke checks. Roll back by reverting the atomic
   refactor change; no data migration is involved.
