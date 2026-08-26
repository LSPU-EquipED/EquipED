## 1. Policy document foundation

- [x] 1.1 Add `policy` document source-type validation and a nullable, validated policy-area classification.
- [x] 1.2 Create and apply an Alembic migration for policy classification, persisted policy chunk section/order metadata, and policy/non-policy database constraints.
- [x] 1.3 Route policy documents to a dedicated local `col_policy_all` collection with source-appropriate embedding metadata.
- [x] 1.4 Add clause-oriented policy chunk assembly with bounded policy metadata (area, section reference, page, ordering).
- [x] 1.5 Extend document/reference lifecycle services to compute policy health and clean/rebuild vectors in the policy collection; document that deletion leaves only hash-level historical audit evidence.
- [x] 1.6 Add backend tests for policy validation, collection routing, persisted chunk metadata, health, rebuild, cleanup, and exclusion of orphaned vectors.

## 2. Admin policy management and RBAC

- [x] 2.1 Introduce separate shared-reference, admin-library, and embedding-required source-type sets; restrict policy upload, list, preview, rebuild, and delete actions to admins while preserving shared syllabus/curriculum behavior.
- [x] 2.2 Extend admin reference APIs to list policy documents and their policy-area/health metadata.
- [x] 2.3 Add an admin policy upload flow that requires a recognized policy area and does not expose policy files in faculty document lists.
- [x] 2.4 Update the Reference Library UI with policy type/area, health, preview, rebuild, and delete affordances.
- [x] 2.5 Add API/RBAC and frontend tests for policy management, no-existence-leak faculty denial, and cross-admin lifecycle behavior.

## 3. ITSO policy retrieval and frozen evidence integration

- [x] 3.1 Implement deterministic criterion-targeted policy retrieval with policy-area and SQL healthy-document allowlist filters, general fallback, stable tie sorting, and bounded results.
- [x] 3.2 Build policy retrieval into separate immutable attempt-scoped ITSO prompt evidence snapshot and persisted provenance contract without blocking other agents on unavailable tools.
- [x] 3.3 Extend ITSO prompt assembly with an advisory policy evidence section, code-owned non-punitive guardrails, and policy-delivery residency gating.
- [x] 3.4 Extend recursively bounded allowlisted ITSO provenance serialization and authorized result schemas with opaque policy outcomes and actual prompt-delivery/trim state at successful and failed persistence boundaries.
- [x] 3.5 Add regression tests that confirm no raw SLM/prompt/policy text reaches provenance, unavailable policy retrieval does not fail evaluation, and policy text is blocked for external LLM endpoints.

## 4. Validation and operational readiness

- [x] 4.1 Add deterministic fixture coverage for policy evidence and stable repeated ITSO prompt/provenance assembly.
- [x] 4.2 Run backend test suites, frontend typecheck/build/lint, migration upgrade, and formatting checks; fix failures caused by this change.
- [x] 4.3 Upload a controlled policy fixture and verify admin lifecycle/health plus faculty no-existence-leak denial in a local environment.
- [x] 4.4 Run post-implementation council review and record deferred limits: DOI verification, title/author search, plagiarism determination, policy authoring, and external tools.
