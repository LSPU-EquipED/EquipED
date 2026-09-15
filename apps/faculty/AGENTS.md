## Scope

- Applies to all frontend code and assets under `client/`.
- Inherits repository root rules and implementation contracts in `openspec/specs/`.

## Frontend Boundaries

- Features (`src/features/*`) are self-contained: each feature owns its components, hooks, API calls, types, utilities, and tests.
- Never import across features (`features/A` must not import from `features/B`).
- `src/shared/` is strictly for shared primitives and utilities with proven reuse across two or more features; do not use `shared/` for single-feature code.
- `src/app/` is the composition root for router configuration, global providers, session management, and layout shell. `app` may import entry points from features.
- Features may import from `app` only for type-only routing contracts.

## Product And Access Enforcement

- UI navigation and route visibility derive from the hydrated session, but backend authorization remains authoritative.
- Document and evaluation management must enforce user ownership boundaries.
- Evaluation setup must present full versus explicit partial evaluation intent clearly before submission.
- Evaluation status rendering must preserve truthfulness across completed, intentional-partial, and failed states; never present a failed evaluation run as partial success.
- Client-side exports must preserve provenance and completeness without leaking internal database IDs or sensitive source details.

## Design

- Follow guidance in `../PRODUCT.md` and `../DESIGN.md`.
- Use institutional design tokens, typography rules, and flat elevation principles defined in the design system.
- Maintain WCAG 2.1 AA compliance for color contrast, keyboard navigation, visible focus indicators, and reduced motion preferences.
- Do not import external UI template kits or introduce redundant local UI primitives without demonstrated reuse.

## Tests And Verification

- Frontend commands run from `client/`; from repository root use `pnpm --dir client <command>`.
- Colocate tests near behavior using adjacent `*.test.ts(x)` files or local `__tests__/` directories.
- Run targeted `pnpm test` paths during development iteration.
- Run `pnpm lint` and `pnpm build` before completing work when TypeScript contracts, routing, providers, or production UI components change.
