## 1. Refactor Guardrails

- [x] 1.1 Record the existing Admin route imports and concrete Model Validation query keys/enabled predicates/polling/reset order, plus Reference Library conditional-tab, mutation, invalidation, and delete-dialog behavior as baselines.
- [x] 1.2 Establish the `features/admin/model-validation/` and `features/admin/reference-library/` subfeature directories without creating cross-subfeature imports or global shared abstractions.

## 2. Model Validation Subfeature

- [x] 2.1 Move `ModelValidation*`/`AdminEvaluationResponse` types and validation-specific API methods into `model-validation/types.ts` and `model-validation/api/`; retain document workflow APIs and Admin Ingest policy-area upload ownership outside the subfeature.
- [x] 2.2 Move the confusion-matrix utility and its tests into `model-validation/utils/` and `model-validation/utils/__tests__/`.
- [x] 2.3 Extract Model Validation query, mutation, and score-entry state into feature-local hooks while preserving query keys, enabled predicates, polling, mutation callbacks, and partial-evaluation acknowledgement behavior.
- [x] 2.4 Extract cohesive Model Validation form, metrics/confusion-matrix, and history/detail components without visual or interaction changes.
- [x] 2.5 Reduce `model-validation/pages/ModelValidationPage.tsx` to route orchestration over its feature-local hooks and section components.

## 3. Reference Library Subfeature

- [x] 3.1 Move Reference Library/policy-specific API methods, DTOs, and mappers into the Reference Library subfeature without duplicating ownership; retain shared document primitives for Admin Ingest and Reference Library.
- [x] 3.2 Move Reference Library feature-private date/status/type helpers into `reference-library/utils/`.
- [x] 3.3 Extract feature-local reference/policy tab state, delete confirmation, and rebuild actions without generic table abstractions.
- [x] 3.4 Extract cohesive Reference Library tab, row-action, and delete-confirmation components while preserving reference and policy lifecycle behavior.
- [x] 3.5 Reduce `reference-library/pages/ReferenceLibraryPage.tsx` to route orchestration over its feature-local tabs and hooks.

## 4. Public Boundary and Cleanup

- [x] 4.1 Add direct, explicit `features/admin/index.ts` exports for all eight Admin route pages without wildcard exports or lazy-loading behavior.
- [x] 4.2 Update only application-router Admin page imports to use the Admin public surface and preserve all existing Admin URLs, guards, and static route declarations.
- [x] 4.3 Remove obsolete moved files and Admin API/type exports only after all consumers resolve; leave unmigrated Admin capabilities and the Admin Ingest policy-area upload path in their current locations.
- [x] 4.4 Verify Model Validation and Reference Library do not import implementation code from one another, no Admin internal imports use `admin/index.ts`, no moved methods remain in legacy Admin API files, and no new `shared/` dependency was created.

## 5. Verification

- [x] 5.1 Run baseline and final Model Validation utility tests plus the full client unit test suite; add dependency-free API/pure-state tests where extraction creates a testable seam.
- [x] 5.2 Run client typecheck, lint, and production build.
- [x] 5.3 Capture baseline/final screenshots and manually smoke `/admin`, `/admin/users`, `/admin/ingest`, `/admin/references`, prompts, preferences, rubrics, and Model Validation—including deep-link/refresh, faculty denial, submission/partial acknowledgement/history, and preview/rebuild/delete flows.
- [x] 5.4 Verify the refactor changed no API payload, query key, polling interval, query observer count, backend contract, visible styling, or interaction behavior; verify policy/detail requests remain conditionally mounted.
