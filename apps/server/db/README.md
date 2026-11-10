# Database metadata and migrations

`metadata.py` imports domain-owned SQLAlchemy models and exposes shared metadata
for Alembic. Runtime engines and sessions live in `server.core.database`.
Active revisions live in `apps/server/alembic/versions/`.

From the repository root, apply migrations with:

```sh
pnpm server:migrate
```

Supply the deployment's migration-owner `DATABASE_URL` privately for this command.
Restore the least-privilege runtime connection afterwards and clear temporary
exported overrides. Managed PostgreSQL deployments may require a direct endpoint
for migrations and a pooled endpoint for application traffic. Keep TLS and role
permissions consistent with deployment policy.

See [operations](../../../docs/operations.md) and
[PostgreSQL backup guidance](../../../infra/postgres/README.md).
