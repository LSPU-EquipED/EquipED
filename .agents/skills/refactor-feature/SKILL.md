---
name: refactor-feature
description: Implement scoped React feature refactoring and cleanup while preserving the existing design and behavior. Use when asked to improve code quality, split oversized components or God files, separate hooks and utilities, or remove stale code from an existing feature. Intended for applying changes, not a read-only codebase audit or a visual redesign.
---

# Refactor a feature without redesigning it

Improve maintainability within the requested feature. Preserve its rendered interface, workflows, API contracts, and current user edits. Do not promise performance improvements without measurements; reducing duplication and clarifying ownership are useful outcomes in their own right.

## Establish scope and a baseline

- Infer the feature from the active conversation and current route. A request to clean up the page being discussed does not authorize a repository-wide rewrite.
- Read applicable `AGENTS.md` instructions, relevant product and architecture documentation, and `DESIGN.md`. Inspect the current diff before editing: the working tree, including the user's uncommitted design changes, is the baseline.
- Follow the entry page through its components, hooks, utilities, types, API callers, and existing tests. Read relevant schema or migration contracts when the code being changed depends on them.
- Identify mixed responsibilities, duplicated logic, stale interfaces, and unnecessary work. File length is a signal to inspect, not a reason to split a cohesive module.
- Briefly explain the concrete refactoring boundaries before editing. Continue with authorized implementation rather than stopping at an audit or proposal.

## Separate responsibilities where they belong

Keep ownership inside the feature and follow the repository's established folders:

| Responsibility | Destination |
| --- | --- |
| Page composition and workspace selection | `pages/` |
| Cohesive visual sections, repeated rows, input controls | `components/` |
| State transitions, subscriptions, pagination, query orchestration | `hooks/` |
| Pure calculations, transformations, formatting | `utils/` |
| Feature data contracts and domain types | Existing `types.ts` or `types/` |
| HTTP transport and request serialization | `api/` |

- Extract meaningful responsibilities, not arbitrary chunks of JSX. Do not replace one large file with many tiny forwarding components.
- Consolidate truly equivalent controls, such as repeated score inputs, while retaining supported data shapes and fallback paths.
- Give extracted components explicit, narrow props. A typed `Pick` of a feature form state is appropriate when it represents a cohesive section; avoid forwarding the entire state indiscriminately.
- Keep state at the owner that preserves its lifetime. Moving state into a conditionally mounted child can reset selections, drafts, or disclosures. Check component identity and keys when extracting.
- Let hooks own mutable refs and expose registration callbacks when child components need to register inputs. Preserve focus behavior and remove registrations on unmount.
- Keep related transitions together: changing a filter or page size should continue to reset pagination as it did before. Preserve query keys, enabled conditions, polling, mutation invalidation, and error handling.
- Follow EquipED's feature boundaries: no cross-feature imports. Promote code to shared libraries only when actual reuse justifies it. Reuse existing shared primitives instead of inventing replacements.
- Add memoization only for demonstrated repeated work or a meaningful identity requirement. Component extraction alone is not a rendering-performance optimization.

## Preserve the interface and behavior

Keep layout wrappers, classes, tokens, typography, spacing, copy, responsive rules, animations, and loading/error/empty states intact. Preserve labels, IDs, ARIA relationships, keyboard interactions, selection behavior, and collapse state as well as visible appearance.

If extraction exposes an unrelated bug or design concern, report it separately. Do not silently fold a redesign or a changed product rule into a behavior-preserving refactor.

## Remove only verified stale code

- Trace imports and usages before deleting exports or files. Also check routes, lazy imports, registries, configuration, scripts, and tests where applicable; absence of a direct import is not sufficient evidence.
- Remove unused props, derived state, obsolete handlers, redundant imports, stale test mocks, and comments that no longer describe the code.
- Keep valid compatibility paths and API response fields even when the current view does not display them. Do not delete tests simply because their assertions expose a regression.
- Keep constants with their actual owner when they have no broader use. Avoid compatibility re-exports that merely preserve obsolete internal import paths; update known consumers instead.
- Leave unrelated user changes intact. Do not force file deletions to satisfy a cleanup request when no whole files are demonstrably stale.

## Verify the affected behavior

- Run the narrowest relevant tests. For meaningful extractions, cover interactions at the new boundaries: filter/page resets, selected-record review, keyboard navigation, score editing, focus registration, and submission guards as applicable.
- Use existing integration tests to verify that extracted sections still work together. Add tests for uncovered behavior, not assertions that merely repeat implementation details or file structure.
- When preserving markup is important, capture representative rendered states before and after the refactor. Compare DOM structure, text, attributes, and classes; normalize only known nondeterministic values such as generated IDs. Keep temporary capture code and artifacts out of the final source changes.
- DOM comparisons do not establish browser layout correctness. Use available browser verification for responsive or interaction concerns, and state when live visual verification was unavailable.
- Run the scoped lint, type/build checks required by the applicable repository instructions, plus a diff check. Separate pre-existing warnings from failures introduced by the change. Broaden testing only when dependencies or failures justify it.
- Finish with the responsibilities separated, stale code removed, design-preservation evidence, and actual verification results. Mention material limitations without claiming a repository-wide cleanup from a feature-local pass.
