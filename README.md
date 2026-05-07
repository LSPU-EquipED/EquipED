# EquipED

EquipED is a multi-agent SLM evaluation system being developed for LSPU SCC. The current repository is still in an active build phase, so this README focuses on the agreed development topology and the current local/Docker workflow.

## Development Topology

The current official development topology is:

- **Frontend:** local on each developer machine
- **Backend:** local on each developer machine
- **Relational DB:** shared Neon PostgreSQL
- **Vector DB:** local Chroma per developer
- **Uploads:** local per developer machine

Neon is a temporary development database host for team collaboration. The long-term production target remains localized LSPU-hosted infrastructure, including PostgreSQL, Chroma, and local file storage.

## Docker in This Phase

Docker is a **local infrastructure and smoke-test helper** in the current phase, not the canonical full-stack runtime.

- `chroma` is the main local service intended for day-to-day development
- `db` remains available as an **optional local PostgreSQL fallback** for validation and future pre-production checks
- `server` and `server-smoke` are optional backend container flows for local runtime and smoke testing
- `client` and `client-smoke` are optional frontend container flows for local runtime and smoke testing
- running backend and frontend separately is the preferred Docker workflow for now

```bash
docker compose up --build chroma
```

You can verify Chroma is running with:

```bash
docker compose ps
curl http://localhost:8001/api/v1/heartbeat
```

```bash
docker compose down -v
```

Notes:
- Do **not** treat `docker compose up` by itself as the official way to run the full stack.
- Postgres is exposed on `5433`, FastAPI on `8000`, backend smoke on `8002`, Vite on `5173`, built client preview on `4173`, and ChromaDB on `8001` (mapped to container `8000`).
- `server` and `server-smoke` target the real FastAPI app and use `/health` as the first-pass smoke signal.
- `server` boot has been validated after adding the missing `python-multipart` dependency to the backend runtime.

### Optional Backend Container Commands

Run the backend locally in Docker:

```bash
docker compose up --build server
```

Run the backend smoke path:

```bash
docker compose up --build server-smoke
```

Notes:
- `server` uses the `dev` target from `server/Dockerfile` and serves FastAPI on `http://localhost:8000`
- `server-smoke` uses the `smoke` target from `server/Dockerfile` and exposes the same app on `http://localhost:8002`
- first-pass backend smoke validation is `GET /health`, not full `/ready`
- compose defaults `DATABASE_URL` to the local `db` service, but you can override it with a Neon URL in your shell or root `.env`
- backend container flows always point Chroma at the compose `chroma` service rather than host `localhost`
- local fallback Postgres is reachable from the host on `localhost:5433`

### Optional Client Container Commands

Run the client locally in Docker:

```bash
docker compose up --build client
```

Run the built client preview for smoke testing:

```bash
docker compose up --build client-smoke
```

Notes:
- `client` uses the `dev` target from `client/Dockerfile` and serves Vite on `http://localhost:5173`
- `client-smoke` uses the `smoke` target from `client/Dockerfile` and serves the built app on `http://localhost:4173`
- the `client` service mounts `./client` into the container so local edits are reflected in the running dev server

### Recommended Docker Usage Right Now

Use Docker services independently while feature work is still evolving:

```bash
docker compose up --build chroma
docker compose up --build server
docker compose up --build server-smoke
docker compose up --build client
docker compose up --build client-smoke
```

Avoid treating `db + chroma + server + client` as a fully supported full-stack Docker mode yet. It can be attempted, but it is not the documented primary workflow at this stage.

## API Contract (Scaffold)

See `docs/API.md` for the minimal Phase 1 API contract.

## Local Dev

### Server (Python 3.12)

```bash
cd server
uv sync
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

Notes:
- `server/.python-version` pins the intended local Python version to `3.12.10`
- `uv.lock` already exists, so `uv sync` is the preferred backend install path

### Client (Node 20 + pnpm 9.12.0)

```bash
cd client
pnpm install
pnpm dev
```

Notes:
- `client/package.json` declares `packageManager: pnpm@9.12.0`
- `client/Dockerfile` uses Node 20, which is the intended local runtime target as well

Before starting local app processes:

- point `DATABASE_URL` to the shared Neon development database
- start or connect to your **local** Chroma instance
- keep in mind that uploads and Chroma state are local to your own machine

Recommended start order:

1. start local Chroma
2. configure `.env`
3. run the backend locally
4. run the frontend locally

## Shared Relational State vs Local Retrieval State

Neon gives the team a shared relational source of truth for records such as users, sessions, document metadata, and other PostgreSQL-backed state.

Chroma is different: each developer runs their own local vector store. That means a document row existing in the shared database does **not** guarantee that another developer can retrieve or evaluate against that same document on their machine.

Practical rule:

- use shared Neon rows for collaboration and integration
- treat Chroma-backed retrieval and evaluation as reliable only for documents ingested into your own local Chroma instance

## Revisit Conditions

Revisit this topology when any of the following becomes true:

1. multiple developers need to evaluate the exact same document corpus consistently
2. real institutional/private documents are used regularly in development
3. retrieval quality becomes central to daily cross-machine testing
4. pre-production/localization work begins on LSPU-hosted infrastructure
5. the app containers need to become the primary, reliable full-stack runtime path rather than optional helper flows

When pre-production starts, validate the app against local PostgreSQL rather than relying only on Neon.

## Reference Corpus Guidance

The team does **not** need a standardized shared Chroma corpus yet.

For now, each developer may use their own local ingestion state while features are still under active construction. If retrieval-heavy collaboration becomes frequent, introduce a small shared reference corpus that every developer ingests locally for consistent testing.
