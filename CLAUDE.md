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

### Client (`client/`, Node 20 + pnpm 9.12.0)

```bash
cd client
pnpm install
pnpm dev        # Vite dev server (http://localhost:5173)
pnpm build      # tsc && vite build
pnpm preview    # serve production build
pnpm lint       # eslint .
pnpm format     # prettier --write .
```

### Server (Python 3.12, run from repo root)

```bash
uv sync --project server
uv run --project server uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
uv run --project server ruff check server     # lint (E, F, I, UP; line-length 88)
uv run --project server pytest                 # tests are currently scaffold-only
```

Notes:
- Run the backend from the **repo root**, not inside `server/` (absolute
  `from server.core...` imports require repo root on `PYTHONPATH`).
- There is no root `pyproject.toml`; always pass `--project server`.
- DB: shared **Neon** PostgreSQL for dev + **local Chroma** per developer.
  See `README.md` for the full topology and Docker/smoke-test workflow.

## Architecture

Two apps in one repo. Backend is a single-process **FastAPI modular
monolith**; frontend is a **feature-driven React + Vite + TS** SPA.

```
server/
  main.py            # FastAPI app entry
  core/              # shared infrastructure ONLY (no business logic)
  modules/           # each owns router / service / models / schemas / exceptions
    auth/  documents/  embeddings/  evaluations/  agents/
    synthesis/  feedback/  admin/  rubrics/
  db/  alembic/      # migrations & config
  tests/             # scaffold
client/src/
  app/               # router.tsx, providers.tsx, layout shell
  features/          # self-contained: auth, dashboard, upload, evaluation,
                     #   history, matrix, admin
  shared/            # only code reused by 2+ features (api, components, hooks, types)
docs/  openspec/     # supporting reference docs & specs (see Working Style)
uploads/  chroma_data/  equiped_dev.db   # local runtime data, anchored to repo root
```

Key entry points: `server/main.py`, `client/src/main.tsx`,
`client/src/app/router.tsx`, `client/src/app/providers.tsx`.

Module boundaries: `server/core/` is infrastructure only. Frontend
`features/*` must stay self-contained and **must not import from one another**;
promote shared code to `shared/` only once 2+ features use it.

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

## Working Style

- This project is in an experimental phase; scope is still evolving.
- AGENTS.md is REFERENCE ONLY — not a fixed spec or roadmap. Do not treat
  it as a waterfall plan.
- Before modifying code, ask 3–5 clarifying questions about intent and scope.
- Propose options instead of committing to one approach.
- Prefer small, reversible changes; confirm before large refactors or new
  dependencies.
- When ambiguous, stop and ask rather than guessing.

> `AGENTS.md`, `openspec/specs/`, `docs/`, `PRODUCT.md`, and `DESIGN.md` are
> useful background context, but they are subordinate to the Working Style
> rules above — consult them for context, don't follow them as a fixed plan.
