# CLAUDE.md

## Overview

EquipED is a multi-agent SLM (Self-Paced Learning Material) evaluation system
for LSPU SCC. Faculty upload SLMs (PDFs); the system runs them through
domain evaluator agents (SME content accuracy, Coordinator curriculum
alignment, GAD gender sensitivity, ITSO IP compliance) against institutional
rubrics and reference documents, then synthesizes scores, compliance flags,
and a monitoring matrix. Output is **advisory only** — human CID reviewers
hold final authority. The project is in an active build phase.

## Key Commands

### Frontend Workspace (Node 20 + pnpm 9.12.0)

```bash
pnpm install
pnpm dev        # Faculty Vite dev server (http://localhost:5173)
pnpm dev:admin  # Admin Vite dev server (http://localhost:5174, proxied under /admin)
pnpm build      # tsc && vite build for all workspace apps
pnpm test       # vitest run across all workspace packages
pnpm lint       # eslint across workspace packages
pnpm typecheck  # typecheck all packages
```

### Backend Workspace (Python 3.12, run via root scripts or `cd apps`)

```bash
uv sync --project apps/server
pnpm server:dev     # or: cd apps && uv run --project server uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
pnpm server:lint    # or: cd apps && uv run --project server ruff check
pnpm server:format  # or: cd apps && uv run --project server ruff format --check
pnpm server:test    # or: cd apps && uv run --project server pytest
pnpm server:migrate # or: cd apps/server && uv run alembic upgrade head
```

Notes:
- Backend modules use absolute `server.*` imports. Always run via root scripts
  or `cd apps && uv run --project server ...` so `apps/` is the Python package import root.
  Running `uv run --project apps/server` from repo root does not add `apps/` to `sys.path`.
- DB: shared **Neon** PostgreSQL for dev + **local Chroma** per developer.
  See `README.md` for the full topology and Docker/smoke-test workflow.

## Architecture

Monorepo with applications in `apps/` and shared TypeScript packages in `libs/`.
Backend is a single-process **FastAPI modular monolith**; frontend consists of
two **feature-driven React + Vite + TS** SPAs (`faculty` and `admin`).

```
apps/
  server/
    main.py            # FastAPI app entry
    core/              # shared infrastructure ONLY (no business logic)
    modules/           # each owns router / service / models / schemas / exceptions
      auth/  documents/  embeddings/  evaluations/  agents/
      synthesis/  feedback/  admin/  rubrics/  curriculum/
      curriculum_alignment/  syllabus_alignment/
    alembic/           # migrations & config
    scripts/           # seed and benchmark scripts
    tests/             # backend test suites
  faculty/             # Faculty portal SPA (port 5173 dev)
    src/
      app/             # router.tsx, providers.tsx, layout shell
      features/        # self-contained: auth, home, documents, evaluation,
                       #   history, curriculum-alignment, syllabus-alignment
  admin/               # CID Admin portal SPA (port 5174 dev)
    src/
      app/             # router.tsx, layout shell
      features/        # self-contained: home, monitoring-matrix, rubric-editor,
                       #   agent-prompt, preference-log, user-management,
                       #   reference-library, reference-ingestion, model-validation,
                       #   evaluation-map
libs/
  types/               # shared TypeScript domain contracts and interfaces
  api-client/          # typed API client and HTTP primitives
  ui/                  # WCAG AA design system primitives, tokens, and components
  auth/                # client session hooks, providers, and RBAC guards
docs/  openspec/       # supporting reference docs & specs (see Authority and Working Style)
uploads/  chroma_data/ # local runtime data, anchored to repo root
```

Key entry points: `apps/server/main.py`, `apps/faculty/src/main.tsx`,
`apps/faculty/src/app/router.tsx`, `apps/admin/src/main.tsx`, `apps/admin/src/app/router.tsx`.

Module boundaries: `apps/server/core/` is infrastructure only. Frontend
`features/*` within each app must stay self-contained and **must not import from sibling features**;
shared code is promoted to `libs/*`. `libs/` packages must never import from `apps/*`.

## Coding Conventions

- **Backend**: ruff-enforced (E, F, I, UP), line length 88, Python 3.12.
  Per-module layout: `router.py`, `service.py`, `models.py`, `schemas.py`,
  `exceptions.py`. Keep business rules in modules, not `core/`.
- **Frontend**: TypeScript, ESLint (incl. react-hooks, react-refresh) +
  Prettier. React 18, TanStack Router + Query, Tailwind v4, lucide-react.
  **No** shadcn/ui or external component kits — components are custom-built.
- Authenticated document workflows are ownership-scoped.
- Only reference docs (syllabus, curriculum) and rubrics go into Chroma; SLMs
  are direct evaluation input and are **not** embedded.

## Authority and Working Style

- **AGENTS.md is governing** repo-wide; executable behavior is authoritative
  through current code, API and schema contracts, migrations, and tests.
  `PRODUCT.md`/`PRD.md` govern product intent, `ARCHITECTURE.md` governs system
  structure, and `DESIGN.md` governs design tokens.
- OpenSpec material is historical reference only. It is not an implementation
  contract, required workflow, or source of current authority.
- Before modifying code, ask 3–5 clarifying questions about intent and scope.
- Propose options instead of committing to one approach.
- Prefer small, reversible changes; confirm before large refactors or new
  dependencies.
- When ambiguous, stop and ask rather than guessing.
- Surfaced conflicts between code, tests, migrations, and product documentation
  must be reconciled explicitly, never chosen silently.
