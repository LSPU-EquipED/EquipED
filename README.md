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

Development currently uses local frontend/backend processes, configured document
storage and local Chroma state, and a shared Neon PostgreSQL database for team work.
Neon is temporary development infrastructure only.

Use the project's least-privilege runtime connection with required TLS. The
Windows PostgreSQL database is retained as a point-in-time fallback, not a live
replica; see [migration verification and fallback operations](infra/postgres/README.md).

The production target is an institution-controlled LSPU server with local
PostgreSQL, uploads, and ChromaDB. Policy evidence delivery to an LLM is
disabled by default and must remain local/residency-gated when enabled.

## Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node 20, Corepack, and pnpm 9.12.0
- [Caddy](https://caddyserver.com/) for the optional unified `localhost:3000` origin; without it, use the Faculty Vite proxy at `localhost:5173`
- Docker Compose only when using optional container services (such as ChromaDB via `pnpm infra:chroma`)
- Tesseract with `eng` and `fil` language packs to process scanned PDFs
  (required in production; optional for text-only development)

## Quick start

From the repository root, for a new checkout only (do not overwrite an existing `.env`):

```bash
cp .env.example .env
uv sync --project apps/server
pnpm install
```

On Windows PowerShell, replace `cp .env.example .env` with:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Configure `.env` with the development database URL, Gmail SMTP account, and
existing inference connection before running the app. Use the privately shared
Neon runtime URL (`equiped_app`, pooled endpoint, `sslmode=require`); do not
substitute a Neon API key or the migration-owner URL. Other developer laptops
need internet access, not Tailscale or an always-on Windows PC, to reach Neon.
The inference connection is independent of the database; preserve its approved
endpoint, model, and adapter configuration. Add OCR settings only when scanned
PDF support is required. Do not commit credentials or print connection URLs.

Document binaries and reference vectors are separate from PostgreSQL. Configure
the existing approved R2 bucket privately to read shared documents; a new local
`uploads/` directory does not contain the migrated files. Chroma uses local
persistence unless `CHROMA_HOST` is configured. Preserve existing vector data;
do not treat an empty Chroma store as a completed database migration.

### Database migrations

`equiped_app` intentionally cannot run schema migrations. Temporarily supply
the separate Neon owner URL through the **direct** endpoint while running
`pnpm server:migrate`; restore the runtime URL before starting the backend.
Keep both URLs private. An exported `DATABASE_URL` overrides the `.env` value,
so clear any temporary owner override afterwards. The old Windows
`equiped_owner` credentials do not apply to the new Neon project.

Registration and account-status emails use Gmail SMTP. Set `SMTP_USERNAME` and
`EMAIL_FROM` to the sender account, then place a Google App Password—not the
Gmail account password—in `SMTP_PASSWORD`. The application defaults already use
`smtp.gmail.com:587` with STARTTLS.

### Starting Development

Run the application processes locally; Docker PostgreSQL is not needed for the
shared Neon development database.

**Recommended: one terminal for application processes**

```bash
pnpm dev:all
```

This starts Faculty, Admin, FastAPI, and the optional Caddy runner. It does not
start Chroma. Without Caddy installed, use `http://localhost:5173` instead of
port 3000. Set `APP_PUBLIC_URL` to the chosen origin.

**Alternatively: separate terminals**
```bash
# Terminal 1: Start FastAPI backend
pnpm server:dev

# Terminal 2: Start Frontends (Faculty Vite and Admin Vite)
pnpm dev

# Terminal 3: Optional unified localhost:3000 proxy (requires Caddy)
pnpm dev:proxy
```

**Optional Docker Compose workflows (not the shared development topology)**

The explicit development/production Compose files remain available. The dev
file starts another PostgreSQL container and configures the backend to use Chroma
over HTTP. It is not a drop-in alternative to the native/shared Neon workflow:
container-local `localhost` is not the Windows host, additional application
settings need forwarding, and the bundled Chroma image (0.5.0) differs from the
locked client (1.5.9). These configuration issues were not repaired by the
database migration. Do not run the full stack to initialize or restore team data.

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
cd apps && uv run --project server uvicorn server.main:app --reload --host 127.0.0.1 --port 8000
```

> Note: Running `uv run --project apps/server` directly from the repository root
> does **not** preserve `apps/` as the package import root for absolute `server.*`
> imports. Backend commands must be executed via root `pnpm server:*` scripts or
> with `cd apps && uv run --project server ...`.

## Common commands

| Task | Command |
| --- | --- |
| Start application dev services (Faculty, Admin, Server, Caddy) | `pnpm dev:all` |
| Start both frontend dev servers only | `pnpm dev` |
| Start Caddy dev reverse proxy | `pnpm dev:proxy` |
| Start Faculty dev server | `pnpm dev:faculty` |
| Start Admin dev server | `pnpm dev:admin` |
| Start local ChromaDB container | `pnpm infra:chroma` |
| Start the backend alone | `pnpm server:dev` |
| Run backend tests | `pnpm server:test` (or `cd apps && uv run --project server pytest`) |
| Lint backend | `pnpm server:lint` (or `cd apps && uv run --project server ruff check server`) |
| Format backend | `pnpm server:format` |
| Run migrations with a temporary direct Neon owner URL | `pnpm server:migrate` |
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

The configured R2 backend stores document binaries in the approved private
bucket; local paths may also be used for cached/downloaded artifacts. The shared
relational database is Neon, not a repository-local SQLite file. PC fallback
dumps do not protect new Neon writes or replace R2/Chroma backups.

Docker is optional for local infrastructure and smoke testing; it is not the
canonical full-stack development workflow. To run the optional Chroma service:

```bash
docker compose -f docker-compose.dev.yml up --build chroma
```

The dev Compose file defines `db`, `chroma`, `server`, `faculty`, `admin`, and
`caddy`; there is no `server-smoke` service. Use host-native application processes
for the shared development workflow. Do not assume the Chroma service is
compatible with the installed client without resolving the version mismatch.
Refer to `docker-compose.dev.yml` for development infrastructure ports and environment overrides.

## Repository guide

```text
apps/server/     FastAPI modular monolith
apps/faculty/    Faculty portal React Vite app (port 5173)
apps/admin/      Admin portal React Vite app (port 5174, base /)
libs/            Shared packages (types, api-client, ui, auth, evaluation-harness)
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
- `libs/` — shared TypeScript packages and the pure Python evaluation harness
- `libs/evaluation-harness/equiped_harness/evaluation.py` — `EvaluationRequest` and `evaluate(request, client, ExecutionConfig)` for all four specialist pipelines; `apps/server/modules/evaluations/harness/` prepares evidence and supplies transport/config. See the [harness guide](libs/evaluation-harness/README.md).

Run independent harness tests with `pnpm harness:test`. The server UV lock installs
the local package; Docker copies it before frozen dependency installation. Use UV
0.11.25 or newer (native build backend `uv_build>=0.11.25,<0.12`).
Admin model validation only updates shared-contract imports in this extraction;
its workflow, API, and persisted schema are unchanged.

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
