
## Local Docker Scaffold

This repo includes a scaffold-only Docker Compose setup for local infrastructure and placeholder app containers.

```bash
docker compose up --build
```

```bash
docker compose down -v
```

Notes:
- Containers currently echo a scaffold message and sleep; no real app process is started yet.
- Postgres is exposed on `5432`, FastAPI on `8000`, Vite on `5173`, and ChromaDB on `8001` (mapped to container `8000`).

## API Contract (Scaffold)

See `docs/API.md` for the minimal Phase 1 API contract.

## Local Dev (Scaffold)

Server (Python 3.12):

```bash
uv pip install -r pyproject.toml  # or `uv sync` when lockfile exists
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

Client (Node 20 + pnpm):

```bash
pnpm install
pnpm dev
```

Notes:
- Lockfiles are not generated yet; install steps will be finalized once P0 wiring completes.
