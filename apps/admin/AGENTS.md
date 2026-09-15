## Scope

- Applies to administrator portal frontend code and assets under `apps/admin/`.
- Inherits repository root rules; current code, tests, and API contracts define executable frontend behavior.

## Frontend Boundaries

- Features (`src/features/*`) are self-contained: each feature owns its components, hooks, API calls, types, utilities, and tests.
- Admin owns administrator workstation features: home/dashboard, user-management, reference-ingestion, reference-library, agent-prompt, preference-log, rubric-editor, model-validation, monitoring-matrix, and evaluation-map.
- Never import across features (`features/A` must not import from `features/B`).
- Shared domain contracts, HTTP clients, UI primitives, and session management live in workspace libraries (`@equiped/types`, `@equiped/api-client`, `@equiped/ui`, `@equiped/auth`).
- `src/app/` is the composition root for router configuration, global providers, session management, and layout shell. `app` may import entry points from features.
- Features may import from `app` only for type-only routing contracts.

## Product And Access Enforcement

- UI navigation and route visibility derive from the hydrated session, but backend authorization remains authoritative.
- Admin portal strictly requires `admin` role authorization. Non-admin users are redirected via document navigation to `/dashboard`.
- Admin operational capabilities (user approvals/suspensions, rubric publishing/reordering/reverting, reference ingestion/rebuilding, model validation) must enforce strict human verification and auditability.
- No public login or registration forms are mounted in admin; authentication rehydrates from the shared session cookie and unauthenticated access redirects via document navigation to `/login`.

## Design

- Follow guidance in `PRODUCT.md` and `DESIGN.md`.
- Use institutional design tokens, typography rules, and flat elevation principles defined in the design system.
- Maintain WCAG 2.1 AA compliance for color contrast, keyboard navigation, visible focus indicators, and reduced motion preferences.
- Do not import external UI template kits or introduce redundant local UI primitives without demonstrated reuse.

## Tests And Verification

- Frontend commands run from workspace root (`pnpm test`, `pnpm build`, `pnpm lint`) or scoped (`pnpm --dir apps/admin <command>`).
- Colocate tests near behavior using adjacent `*.test.ts(x)` files or local `__tests__/` directories.
- Run targeted `pnpm test` paths during development iteration.
- Run `pnpm lint` and `pnpm build` before completing work when TypeScript contracts, routing, providers, or production UI components change.
