## Scope

- Applies to faculty portal frontend code and assets under `apps/faculty/`.
- Inherits repository root rules; current code, tests, and API contracts define executable frontend behavior.

## Frontend Boundaries

- Features (`src/features/*`) are self-contained: each feature owns its components, hooks, API calls, types, utilities, and tests.
- Faculty owns non-admin features: home, documents, evaluation, history, curriculum-alignment, syllabus-alignment, plus public login/registration page composition.
- Never import across features (`features/A` must not import from `features/B`).
- Shared domain contracts, HTTP clients, UI primitives, and session management live in workspace libraries (`@equiped/types`, `@equiped/api-client`, `@equiped/ui`, `@equiped/auth`).
- `src/app/` is the composition root for router configuration, global providers, session management, and layout shell. `app` may import entry points from features.
- Features may import from `app` only for type-only routing contracts.

## Product And Access Enforcement

- UI navigation and route visibility derive from the hydrated session, but backend authorization remains authoritative.
- Document and evaluation management must enforce user ownership boundaries.
- Evaluation setup must present full versus explicit partial evaluation intent clearly before submission.
- Evaluation status rendering must preserve truthfulness across completed, intentional-partial, and failed states; never present a failed evaluation run as partial success.
- Client-side exports must preserve provenance and completeness without leaking internal database IDs or sensitive source details.

## Design

- Follow guidance in `PRODUCT.md` and `DESIGN.md`.
- Use institutional design tokens, typography rules, and flat elevation principles defined in the design system.
- Maintain WCAG 2.1 AA compliance for color contrast, keyboard navigation, visible focus indicators, and reduced motion preferences.
- Do not import external UI template kits or introduce redundant local UI primitives without demonstrated reuse.

## Tests And Verification

- Frontend commands run from workspace root (`pnpm test`, `pnpm build`, `pnpm lint`) or scoped (`pnpm --dir apps/faculty <command>`).
- Colocate tests near behavior using adjacent `*.test.ts(x)` files or local `__tests__/` directories.
- Run targeted `pnpm test` paths during development iteration.
- Run `pnpm lint` and `pnpm build` before completing work when TypeScript contracts, routing, providers, or production UI components change.
