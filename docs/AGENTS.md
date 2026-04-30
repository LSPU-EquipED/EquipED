## Scope

- This directory is only responsible for repository documentation.
- Changes here should improve clarity, consistency, and architectural accuracy of the specs.

## Documentation Guardrails

- Treat `TDD.md` as the implementation blueprint and `PRD.md` as product scope and constraints.
- Do not present open decisions as settled architecture.
- When reconciling inconsistencies, preserve the canonical structure already established in `TDD.md` unless the change is intentional.
- Keep terminology, path names, route names, module names, and lifecycle states consistent with the rest of the repo.

## What Not To Do Here

- Do not add implementation code under `docs/`.
- Do not use docs edits to silently change architecture without making the change explicit.
- Do not loosen privacy/compliance language beyond what the PRD and TDD support.

## Before Editing Docs

- Cross-check `TDD.md`, `PRD.md`, and the root `../AGENTS.md`.
- If PRD and TDD differ, prefer TDD for implementation detail and PRD for scope/constraint wording.
