## ADDED Requirements

### Requirement: Admin subfeatures own their vertical implementation
The client SHALL organize Model Validation and Reference Library as separate
subfeatures under `features/admin/model-validation/` and
`features/admin/reference-library/`. Each subfeature SHALL own its route page,
feature-private components, hooks, API code, types, and utilities.

An Admin subfeature SHALL NOT import implementation code from another Admin
subfeature. It MAY consume an established cross-feature service only when that
service is independently used outside the Admin subfeature boundary.

#### Scenario: Model Validation route is resolved
- **WHEN** the Model Validation route renders
- **THEN** its page, components, hooks, API calls, types, and utilities SHALL
  resolve from the Model Validation subfeature without importing Reference
  Library implementation code

#### Scenario: Reference Library route is resolved
- **WHEN** the Reference Library route renders
- **THEN** its page, components, hooks, API calls, types, and utilities SHALL
  resolve from the Reference Library subfeature without importing Model
  Validation implementation code

### Requirement: Route pages remain feature orchestrators
Each migrated route page SHALL compose feature-local hooks and cohesive section
components rather than directly owning unrelated query, mutation, score-entry,
dialog, helper, and large table/detail implementations. A component or hook
SHALL remain feature-local unless reuse by another top-level feature is proven.

#### Scenario: Model Validation workflow renders
- **WHEN** an administrator opens the Model Validation route
- **THEN** the route page SHALL orchestrate its preparation form, metrics, and
  validation history through feature-local sections and hooks while preserving
  the existing workflow behavior

#### Scenario: Reference Library workflow renders
- **WHEN** an administrator opens the Reference Library route
- **THEN** the route page SHALL orchestrate its reference and policy tabs
  through feature-local sections and hooks while preserving their distinct
  lifecycle behavior

### Requirement: Admin routes retain a narrow public surface
`features/admin/index.ts` SHALL directly and explicitly expose all route-facing
Admin page exports needed by the application router. Only the application router
SHALL import from this public surface. Internal components, hooks, types, API
modules, and utilities SHALL be imported from their owning paths and SHALL NOT
be re-exported through a wildcard Admin barrel. The reorganization SHALL NOT
introduce lazy loading, dynamic route imports, or Suspense behavior.

#### Scenario: Application router imports Admin routes
- **WHEN** the application router resolves an Admin route
- **THEN** it SHALL obtain the route-facing page export through the Admin public
  surface without depending on the page's former flat internal path or changing
  its route declaration

### Requirement: Refactor preserves Admin behavior and contracts
The subfeature reorganization SHALL preserve existing routes, query keys,
polling behavior, API payloads, response handling, mutation callbacks,
authorization behavior, visible UI, and interaction behavior. It SHALL NOT add
dependencies, change backend contracts, alter data models, or redirect the
Admin Ingest policy-area upload through the document workflow API.

#### Scenario: Existing Model Validation interaction completes
- **WHEN** an administrator uploads an SLM, supplies expected scores, confirms
  partial-evaluation intent when required, and starts validation
- **THEN** the refactored feature SHALL submit the same request and retain the
  existing success, progress, and history behavior

#### Scenario: Existing Reference Library interaction completes
- **WHEN** an administrator previews, rebuilds, or deletes a reference or
  policy document
- **THEN** the refactored feature SHALL retain the existing request, result, and
  confirmation behavior

### Requirement: Feature-private utilities and tests are co-located
Feature-private utility code SHALL reside under its owning subfeature's
`utils/` directory. Its unit tests SHALL reside under the corresponding
`utils/__tests__/` directory. The existing Model Validation confusion-matrix
utility and tests SHALL move together.

#### Scenario: Confusion-matrix utility tests run
- **WHEN** the client unit test suite runs
- **THEN** the Model Validation confusion-matrix tests SHALL resolve from the
  Model Validation subfeature utility test location

### Requirement: Refactor preserves query and tab lifecycles
The refactor SHALL preserve one observer for every existing Model Validation
query, including its key, enabled predicate, polling behavior, detail expansion,
and reset ordering. Reference Library SHALL preserve conditional tab mounting,
separate reference/policy mutations, awaited `onSettled` invalidation, and
delete-dialog failure behavior. Existing unrelated defects SHALL NOT be changed
as incidental refactor work.

#### Scenario: Inactive policy tab remains unmounted
- **WHEN** an administrator opens Reference Library with the References tab
  active
- **THEN** the Policy list SHALL NOT fetch until its tab is opened

#### Scenario: Model Validation history expands
- **WHEN** an administrator expands a validation history row
- **THEN** the feature SHALL fetch only that row's detail and linked evaluation
  using the existing conditional query behavior
