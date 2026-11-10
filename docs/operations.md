# Operations and deployment

## Deployment configuration

EquipED's production target is institution-controlled infrastructure. Keep
PostgreSQL, uploaded documents, and reference vectors in approved storage
locations. Use least-privilege application credentials, TLS for database and
service connections, private document storage, and HTTPS for browser access.
Model and email services must use approved endpoints and credentials; do not
enable external processing of institutional data without explicit authorization.

Set production configuration through the deployment's secret/configuration
manager, not a committed `.env`. At minimum, configure:

- `APP_ENV=production`, a PostgreSQL `DATABASE_URL` for the runtime role, and a
  separate migration-owner URL used only during upgrades.
- `APP_PUBLIC_URL` with the public HTTPS origin and `SESSION_COOKIE_SECURE=true`.
- A non-console `EMAIL_PROVIDER` with its required credentials. SMTP must use
  STARTTLS.
- The approved model endpoint and model name. Keep `LLM_ALLOWED_ENDPOINTS`
  empty outside development.
- Private document storage settings and Chroma configuration appropriate to
  the approved deployment. Chroma Cloud requires explicit authorization.

Run schema upgrades with the owner role, then start the application with the
runtime role. The backend runs as one Uvicorn worker in the production image;
keep the single-process execution contract. The application returns advisory
evaluation results, with human review remaining authoritative.

## Compose deployment limits

The repository includes `docker-compose.prod.yml` as a deployment starting
point, not a complete secure production deployment. It exposes the web service
on port 80, runs PostgreSQL 15 and Chroma 0.5.0 in named volumes, and starts one
backend worker. Before use, resolve these configuration gaps:

- Compose defaults PostgreSQL to user/password `postgres` and does not publish
  the `APP_ENV`, `APP_PUBLIC_URL`, `SESSION_COOKIE_SECURE`, email, model, or
  document-storage settings required by the application. Production settings
  must be supplied to the server container; the defaults are insufficient for
  a valid production startup.
- The bundled Chroma version may not match the client dependency. Verify a
  compatible server/client pair before connecting it to institutional vectors.
- The web container serves HTTP on port 80. Terminate TLS at an institutionally
  managed ingress and restrict direct access to the application network.
- The Compose file has persistent volumes, but no backup, restore, monitoring,
  upgrade, or disaster-recovery automation. Establish and verify these
  procedures for PostgreSQL, uploaded files, and Chroma independently.

Commands are available for local inspection/building:

```sh
pnpm docker:prod:build
pnpm docker:prod
pnpm docker:prod:down
```

Do not treat these commands as a production cutover checklist. Validate
deployment configuration and backups in the institution's environment before
accepting real data.

## Data and recovery

PostgreSQL, source-document binaries, and vector data are separate stores.
A database backup alone does not restore uploaded files or Chroma collections.
Back up each configured store with access controls and retention appropriate to
institutional policy. Test restore procedures against isolated destinations
before using recovered data.

When moving vector data, use a migration procedure that preserves IDs, stored
text, metadata, and embedding configuration; pause writes and verify retrieval
against the destination before switching application configuration. Keep
secrets and reports containing operational metadata private.

## Health checks and logs

- `GET /health` reports process liveness.
- `GET /ready` checks configured runtime dependencies and can return `503` if
  a required dependency is unavailable.
- The FastAPI documentation endpoint is `/docs`; restrict it according to the
  deployment's access policy.

Monitor application and infrastructure logs without recording credentials,
connection strings, document contents, or other sensitive data. Investigate
failed evaluation jobs as failures; only explicitly supported intentional
partial workflows may complete partially.

## References

- [Development setup](setup.md)
- [Product overview](../PRODUCT.md) and [requirements](../PRD.md)
- [Architecture](../ARCHITECTURE.md) and [design system](../DESIGN.md)
- [Evaluation guide](evaluation.md)
- [Training guide](training.md)
