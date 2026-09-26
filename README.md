# EquipED

EquipED is an advisory, multi-agent evaluation system for Self-Paced Learning
Modules (SLMs) at **Laguna State Polytechnic University – Santa Cruz Campus,
College of Computer Studies**.

It helps faculty and CID staff review SLMs against institutional rubrics while
keeping human review authoritative. Current academic scope is limited to
**BSInfoTech** and **BSCS**.

## What it does

- Accepts faculty-owned SLM PDF uploads and extracts selectable or scanned text.
- Runs one selected specialist (SME, Program Coordinator, GAD, or ITSO) per
  faculty evaluation. Completed specialist results progressively fill the
  monitoring matrix; its composite score appears after all four domains complete.
- Uses LSPU CCS curriculum, syllabus, rubric, and approved policy documents as
  local reference evidence. SLMs are direct evaluation input and are never
  embedded into ChromaDB.
- Requires a faculty-confirmed program for submission. Coordinator evaluations
  additionally require a ready curriculum; other specialist jobs complete
  independently. The old partial-without-curriculum mode is not used for
  faculty submissions; it remains for historical jobs and Admin model-validation
  benchmarks.
- Provides Admin workflows for reference/policy ingestion, user management,
  prompt history, preference logs, monitoring, and model validation.
- Exports truthful client-side PDF scorecards.

Generated results are advisory only and do not replace institutional review or
approval.

## Data and deployment model

Development currently uses local frontend/backend processes, local uploads and
Chroma state, and may use a shared Neon PostgreSQL database for team work.
Neon is temporary development infrastructure only.

The production target is an institution-controlled LSPU server with local
PostgreSQL, uploads, and ChromaDB. Policy evidence delivery to an LLM is
disabled by default and must remain local/residency-gated when enabled.

## Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node 20, Corepack, and pnpm 9.12.0
- [Caddy](https://caddyserver.com/) (required for unified single-origin reverse proxy `pnpm dev` or `pnpm dev:proxy`)
- Docker Compose only when using optional container services (such as ChromaDB via `pnpm infra:chroma`)
- Tesseract with `eng` and `fil` language packs to process scanned PDFs
  (required in production; optional for text-only development)

## Quick start

From the repository root:

```bash
cp .env.example .env
uv sync --project apps/server
pnpm install
```

Configure `.env` with the development database URL, Gmail SMTP account, and
local model endpoint before running the app. Add OCR settings only when scanned
PDF support is required. Do not commit credentials.

Registration and account-status emails use Gmail SMTP. Set `SMTP_USERNAME` and
`EMAIL_FROM` to the sender account, then place a Google App Password—not the
Gmail account password—in `SMTP_PASSWORD`. The application defaults already use
`smtp.gmail.com:587` with STARTTLS.

### Starting Development

You can run the development environment in two ways:

**Option 1: Two-Terminal Host Workflow (Standard Workflow)**
```bash
# Terminal 1: Start FastAPI backend
make server

# Terminal 2: Start Frontends (Faculty Vite and Admin Vite)
pnpm dev
```

**Option 2: Docker Compose Workflows (All-in-One)**

EquipED maintains separate Docker Compose configurations for Development and Production:

```bash
# Development (with hot-reloading, preserving local ./uploads and ./chroma_data)
pnpm docker:dev        # or: docker compose -f docker-compose.dev.yml up
pnpm docker:dev:build  # rebuild dev containers
pnpm docker:dev:down   # stop dev containers

# Production (Caddy reverse proxy + static SPAs + production FastAPI single worker)
pnpm docker:prod       # or: docker compose -f docker-compose.prod.yml up
pnpm docker:prod:build # rebuild production containers
pnpm docker:prod:down  # stop production containers
```

The unified development origin is available at <http://localhost:3000> (or <http://localhost:5173> when running without Caddy):
- Faculty Portal: <http://localhost:3000/>
- Admin Workstations: <http://localhost:3000/admin>
- Monitoring Matrix: <http://localhost:3000/matrix>
- Evaluation Map: <http://localhost:3000/evaluation-map>
- API: <http://localhost:3000/api/v1/...> (proxied to port 8000)
- FastAPI Docs: <http://localhost:8000/docs> (direct backend endpoint)

### Route Ownership & Port Allocations

| Service | Port / Address | Route Ownership / Role |
| --- | --- | --- |
| **Caddy Dev Ingress** | `:3000` (default) | Single-origin ingress (`http://localhost:3000`). Handles `/api/*` -> FastAPI, `/admin-assets/*`, `/admin/*`, `/matrix/*`, `/evaluation-map/*` -> Admin Vite, and all other paths -> Faculty Vite. |
| **FastAPI Monolith** | `127.0.0.1:8000` | Backend API routes (`/api/*`, `/health`, `/ready`, `/docs`). |
| **Faculty Vite** | `127.0.0.1:5173` | Faculty dashboard, document intake, evaluations history, and public auth. |
| **Admin Vite** | `127.0.0.1:5174` | Admin workstations (`/admin/*`), Monitoring Matrix (`/matrix/*`), Evaluation Map (`/evaluation-map/*`). Component-debug endpoint only; canonical navigation origin is Caddy `:3000` or Faculty proxy `:5173`. |
| **ChromaDB** | Host port `8001` | Local vector store (started separately via `pnpm infra:chroma` or Docker Compose). |

### Fallback Commands & Individual Dev Servers

If `caddy` is not installed on your host, you can run individual services independently:

```bash
# Start backend
pnpm server:dev

# Start Faculty portal (with Vite internal dev proxy)
pnpm dev:faculty  # http://localhost:5173

# Start Admin portal
pnpm dev:admin    # http://localhost:5174

# Run Caddy dev proxy alone (when Caddy is installed)
pnpm dev:proxy

# Start vector store container independently
pnpm infra:chroma
```

When running without Caddy, open the faculty portal at <http://localhost:5173> and the admin portal at <http://localhost:5173/admin> (proxied to admin Vite on port 5174 via Vite's dev proxy). Direct access to port 5174 is intended solely as a component-debug endpoint, not a canonical navigation origin; cross-app relative redirects and session flows rely on the canonical dev origin provided by Caddy (`:3000`) or the Faculty proxy (`:5173`). The direct FastAPI documentation is available at <http://localhost:8000/docs>.

### How backend commands run

The FastAPI application is imported as `server.main:app`, and backend modules
use absolute `server.*` imports. Always standardize on running backend commands
from `apps/` (or via root package scripts) so `apps/` is the Python package import root:

```bash
pnpm server:dev
# or directly:
cd apps && uv run --project server uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

> Note: Running `uv run --project apps/server` directly from the repository root
> does **not** preserve `apps/` as the package import root for absolute `server.*`
> imports. Backend commands must be executed via root `pnpm server:*` scripts or
> with `cd apps && uv run --project server ...`.

## Common commands

| Task | Command |
| --- | --- |
| Start all dev services (Faculty, Admin, Server, Caddy) | `pnpm dev` |
| Start Caddy dev reverse proxy | `pnpm dev:proxy` |
| Start Faculty dev server | `pnpm dev:faculty` |
| Start Admin dev server | `pnpm dev:admin` |
| Start local ChromaDB container | `pnpm infra:chroma` |
| Start the backend alone | `make server` (or `pnpm server:dev`) |
| Run backend tests | `pnpm server:test` (or `cd apps && uv run --project server pytest`) |
| Lint backend | `pnpm server:lint` (or `cd apps && uv run --project server ruff check server`) |
| Format backend | `pnpm server:format` |
| Run migrations | `pnpm server:migrate` |
| Run all frontend/lib tests | `pnpm test` |
| Run Caddy contract test | `pnpm test:caddy` |
| Lint all workspace packages | `pnpm lint` |
| Build all frontend apps | `pnpm build` |
| Typecheck entire workspace | `pnpm typecheck` |
| Check API liveness | `curl http://localhost:8000/health` |
| Check runtime readiness | `curl http://localhost:8000/ready` |

`/health` is a liveness check. `/ready` verifies configured runtime
dependencies; it can return `503` when a required dependency is unavailable.

## Local storage and optional Docker services

By default, local runtime data is anchored at the repository root:

- `uploads/` — uploaded PDF files
- `chroma_data/` — local Chroma persistence
- `equiped_dev.db` — local development database, when used

Docker is optional for local infrastructure and smoke testing; it is not the
canonical full-stack development workflow. To run the optional Chroma service:

```bash
docker compose up --build chroma
```

The Compose file also provides optional `db`, `server`, and `server-smoke`
services. Frontend container packaging remains deferred; run apps locally with `pnpm dev`.
Refer to `docker-compose.yml` for infrastructure ports and environment overrides.

## Repository guide

```text
apps/server/     FastAPI modular monolith
apps/faculty/    Faculty portal React Vite app (port 5173)
apps/admin/      Admin portal React Vite app (port 5174, base /)
libs/            Extracted shared workspace packages (types, api-client, ui, auth)
openspec/specs/  Historical specification references
docs/            Product and architecture reference material
uploads/         Local uploaded documents
chroma_data/     Local vector-store data
```

Key entry points:

- `apps/server/main.py` — FastAPI application
- `apps/faculty/src/main.tsx` — Faculty app bootstrap
- `apps/faculty/src/app/router.tsx` — Faculty route tree
- `apps/admin/src/main.tsx` — Admin app bootstrap
- `apps/admin/src/app/router.tsx` — Admin route tree
- `libs/` — workspace packages (@equiped/types, @equiped/api-client, @equiped/ui, @equiped/auth)

## Documentation and authority model

- [Product requirements](PRD.md)
- [Architecture overview](ARCHITECTURE.md)
- [Historical OpenSpec material](openspec/specs/)
- [Live API documentation](http://localhost:8000/docs)

Executable behavior is authoritative through current code, API and schema
contracts, migrations, and tests. `PRODUCT.md` and `PRD.md` govern product intent,
roles, scope, and constraints; `ARCHITECTURE.md` governs system structure, and
`DESIGN.md` governs design-system and UX direction.

OpenSpec material is retained for historical reference only. It is not an
implementation contract, required workflow, or source of current authority.
