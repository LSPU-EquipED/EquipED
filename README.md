# EquipED

EquipED is a multi-agent SLM evaluation system being developed for LSPU SCC. The current repository is still in an active scaffold/build phase, so this README focuses on the agreed development topology and local setup path.

## Development Topology

The current official development topology is:

- **Frontend:** local on each developer machine
- **Backend:** local on each developer machine
- **Relational DB:** shared Neon PostgreSQL
- **Vector DB:** local Chroma per developer
- **Uploads:** local per developer machine

Neon is a temporary development database host for team collaboration. The long-term production target remains localized LSPU-hosted infrastructure, including PostgreSQL, Chroma, and local file storage.

## Docker in This Phase

Docker is a **local infrastructure helper** in the current phase, not the canonical full-stack runtime.

- `chroma` is the main local service intended for day-to-day development
- `db` remains available as an **optional local PostgreSQL fallback** for validation and future pre-production checks
- `server` and `client` containers are scaffold placeholders only; they do not run the real FastAPI or Vite app yet

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
- Postgres is exposed on `5432`, FastAPI on `8000`, Vite on `5173`, and ChromaDB on `8001` (mapped to container `8000`).
- The Docker app containers currently echo a scaffold message and sleep.

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
5. the app containers become real runtime paths instead of scaffold placeholders

When pre-production starts, validate the app against local PostgreSQL rather than relying only on Neon.

## Reference Corpus Guidance

The team does **not** need a standardized shared Chroma corpus yet.

For now, each developer may use their own local ingestion state while features are still under active construction. If retrieval-heavy collaboration becomes frequent, introduce a small shared reference corpus that every developer ingests locally for consistent testing.
