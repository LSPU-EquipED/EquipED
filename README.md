# EquipED

EquipED is an advisory, multi-agent evaluation system for Self-Paced Learning
Modules (SLMs) at **Laguna State Polytechnic University – Santa Cruz Campus,
College of Computer Studies**.

It helps faculty and CID staff review SLMs against institutional rubrics while
keeping human review authoritative. Current academic scope is limited to
**BSInfoTech** and **BSCS**.

## What it does

- Accepts faculty-owned SLM PDF uploads and extracts selectable or scanned text.
- Runs SME, Program Coordinator, GAD, and ITSO evaluation perspectives in
  parallel, then produces a consolidated scorecard and monitoring-matrix entry.
- Uses LSPU CCS curriculum, syllabus, rubric, and approved policy documents as
  local reference evidence. SLMs are direct evaluation input and are never
  embedded into ChromaDB.
- Requires a faculty-confirmed program and curriculum for a full evaluation. A
  clearly labelled partial evaluation can continue without a curriculum; the
  Coordinator is skipped and the result is marked partial.
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
- Docker Compose only when using optional container services
- Tesseract with `eng` and `fil` language packs to process scanned PDFs
  (required in production; optional for text-only development)

## Quick start

From the repository root:

```bash
cp .env.example .env
uv sync --project server

cd client
pnpm install
cd ..
```

Configure `.env` with the development database URL, Gmail SMTP account, and
local model endpoint before running the app. Add OCR settings only when scanned
PDF support is required. Do not commit credentials.

Registration and account-status emails use Gmail SMTP. Set `SMTP_USERNAME` and
`EMAIL_FROM` to the sender account, then place a Google App Password—not the
Gmail account password—in `SMTP_PASSWORD`. The application defaults already use
`smtp.gmail.com:587` with STARTTLS.

Start the backend:

```bash
make server
```

Start the client in another terminal:

```bash
cd client
pnpm dev
```

Open the client at <http://localhost:5173>. The live FastAPI documentation is
available at <http://localhost:8000/docs>.

### Why `make server` runs from the repository root

The FastAPI application is imported as `server.main:app`, and backend modules
use absolute `server.*` imports. The root Make target selects
`server/pyproject.toml` while keeping the repository root on Python's import
path:

```bash
uv run --project server uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

## Common commands

| Task | Command |
| --- | --- |
| Start the backend | `make server` |
| Run backend tests | `uv run --project server pytest server/tests` |
| Lint backend | `uv run --project server ruff check server` |
| Start the client | `cd client && pnpm dev` |
| Run client tests | `cd client && pnpm test` |
| Lint client | `cd client && pnpm lint` |
| Build client | `cd client && pnpm build` |
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

The Compose file also provides optional `db`, `server`, `server-smoke`,
`client`, and `client-smoke` services. Refer to `docker-compose.yml` for their
ports and environment overrides.

## Repository guide

```text
server/          FastAPI modular monolith
client/          React feature-driven application
openspec/specs/  Canonical implementation contracts
docs/            Product and architecture reference material
uploads/         Local uploaded documents
chroma_data/     Local vector-store data
```

Key entry points:

- `server/main.py` — FastAPI application
- `client/src/main.tsx` — client bootstrap
- `client/src/app/router.tsx` — route tree
- `client/src/features/` — feature-owned UI, APIs, hooks, and types

## Documentation and contracts

- [Product requirements](docs/PRD.md)
- [Architecture overview](docs/ARCHITECTURE.md)
- [Canonical OpenSpec contracts](openspec/specs/)
- [Live API documentation](http://localhost:8000/docs)

OpenSpec contracts define accepted implementation behavior. The PRD provides
product scope and supporting context; it does not override an OpenSpec contract.
