# Database metadata and migrations

`metadata.py` imports the domain-owned SQLAlchemy models and exposes their shared
metadata for Alembic. Runtime engines and sessions live in `server.core.database`;
active revisions live in `apps/server/alembic/versions/`, not this directory.

Development uses the shared Neon database configured by DATABASE_URL. Backends
use the least-privilege `equiped_app` role through the pooled endpoint with TLS.
Migrations use a separate owner connection through the direct endpoint:

```bash
pnpm server:migrate
```

Supply the owner URL privately for this command only; restore the runtime URL
and clear any temporary exported DATABASE_URL before starting the backend.
Do not run migrations with `equiped_app`, use the old Windows owner password for
Neon, or commit connection credentials.

See the root `.env.example` and
[migration verification and PC fallback operations](../../../infra/postgres/README.md).
