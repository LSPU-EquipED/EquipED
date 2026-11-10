# Development setup

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 20, Corepack, and pnpm 9.12.0
- Tesseract with `eng` and `fil` language data when processing scanned PDFs
- Caddy is optional; it provides a unified local origin on port 3000
- Docker Compose is optional for running the bundled Chroma service

## Install

From the repository root:

```sh
test -e .env || cp .env.example .env
uv sync --project apps/server
pnpm install
```

If `.env` already exists, keep it and edit only the settings needed for your
environment. In PowerShell, copy the template only when creating a new file:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Configure `.env` before starting the server:

- `DATABASE_URL`: PostgreSQL connection for the application. Supply a
  development database and use a least-privilege runtime role. For schema
  upgrades, use a separate migration-owner connection only for the migration
  command, then restore the runtime URL.
- `LLM_PROVIDER`, `LLM_MODEL_NAME`, and `LLM_API_BASE`: the approved model
  service and model. Set `LLM_API_KEY` only if that service requires one.
- `EMAIL_PROVIDER`: configure SMTP credentials if account and status emails
  should be delivered. For Gmail SMTP use a Google App Password.
- `APP_PUBLIC_URL`: use `http://localhost:3000` with Caddy, otherwise the
  Faculty Vite origin `http://localhost:5173`.
- Optional services: set `CHROMA_HOST` and `CHROMA_PORT` for a Chroma server;
  configure R2 values only when using an authorized private document bucket.
  Without R2 configuration, document files use local `uploads/` storage.

For authorized Chroma Cloud storage, configure `CHROMA_API_KEY`,
`CHROMA_TENANT`, and `CHROMA_DATABASE`; the optional host is
`api.trychroma.com`. These settings select managed cloud mode rather than the
local store. Preserve existing vector data when changing stores.

For ITSO evaluation, set `ITSO_VERIFICATION_ENABLED=true` only on a deployment
authorized to search public references. Current search needs no API key and
never uses private body passages as queries.

Keep credentials out of source control. Do not point institutional documents or
vectors at an external service unless that storage and processing path is
explicitly authorized. See [operations](operations.md) for storage and backup
responsibilities.

## Start the application

Recommended local development command:

```sh
pnpm dev:all
```

This starts the Faculty app, Admin app, FastAPI server, and Caddy proxy. Browse
to <http://localhost:3000>; without Caddy, use the Faculty proxy at
<http://localhost:5173>. API documentation is at <http://localhost:8000/docs>.
The separate Compose development topology has different port and proxy
configuration; see its file before using it.

To run processes separately:

```sh
pnpm server:dev
pnpm dev
pnpm dev:proxy # optional; requires Caddy
```

The server's `/health` endpoint is a liveness check. `/ready` checks configured
runtime dependencies and may return `503` when one is unavailable.

## Useful commands

| Purpose | Command |
| --- | --- |
| Run frontend tests | `pnpm test` |
| Run backend and harness tests | `pnpm server:test` |
| Run harness tests only | `pnpm harness:test` |
| Lint workspace | `pnpm lint` |
| Build frontend apps | `pnpm build` |
| Typecheck workspace | `pnpm typecheck` |
| Apply database migrations | `pnpm server:migrate` |
| Start local Chroma Compose service | `pnpm infra:chroma` |

Run backend commands through the root scripts or from `apps/`, where `server.*`
imports resolve correctly. `pnpm server:migrate` uses the configured
`DATABASE_URL`; ensure it points to the migration-owner database role for that
command and restore the application runtime URL afterwards.

## Optional Compose development

The development Compose file can start the database, Chroma, server, frontends,
and Caddy with `pnpm docker:dev`. It is a separate local topology: it creates a
PostgreSQL 15 database, while the host-native workflow uses whichever database
you configured. The server container is wired to Chroma over HTTP and does not
receive all host `.env` settings (including model-service configuration). The
bundled Chroma image is `0.5.0`; confirm compatibility with the installed client
before using it. These defaults are for local development and are not a
production-ready deployment.

See [operations](operations.md) for the production Compose constraints and
operational care of persistent data.
