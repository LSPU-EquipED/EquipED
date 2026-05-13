## Scope

- This directory is only responsible for repository documentation.
- Changes here should improve clarity, consistency, and architectural accuracy.

## Documentation Guardrails

- Treat `openspec/specs/` as the canonical implementation contract source.
- Use `docs/TDD.md` and `docs/PRD.md` as supporting reference material.
- Do not present open decisions as settled architecture.
- When reconciling inconsistencies, preserve the canonical structure already established in `openspec/specs/` unless the change is intentional.
- Keep terminology, path names, route names, module names, and lifecycle states consistent with the rest of the repo.

## What Not To Do Here

- Do not add implementation code under `docs/`.
- Do not use docs edits to silently change architecture without making the change explicit.
- Do not loosen privacy/compliance language beyond what the PRD and TDD support.

## Before Editing Docs

- Cross-check `openspec/specs/`, `TDD.md`, `PRD.md`, and the root `../AGENTS.md`.
- If supporting docs differ, prefer `openspec/specs/` for implementation detail and `PRD.md` for scope/constraint wording.
