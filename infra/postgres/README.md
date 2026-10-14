# Shared native Windows PostgreSQL

## Verified host setup (2026-10-14)

- Host: `DESKTOP-J752SQK`, Windows 10 Pro, native PostgreSQL 18.6.
- Service: `postgresql-x64-18`, running with Automatic startup.
- Database: `equiped`; port: `5432`; Tailscale IPv4: `100.123.191.41`.
- Listening: `127.0.0.1`, `::1`, and the Tailscale IPv4 only; no wildcard listener.
- Tailscale runs as an Automatic service with unattended mode enabled. AC sleep
  was already disabled. The host's current Tailscale key expires 2027-04-12;
  the Tailnet administrator must manage renewal or disable expiry in the console
  for this trusted host. No auth keys are stored in this repository.
- Windows Firewall allows TCP 5432 only on the Tailscale interface, to the host's
  Tailscale address, from Jeremy's Mac (`100.115.14.4`). No pre-existing
  PostgreSQL/5432 allow rules were found. Localhost connections remain available.
- HBA uses SCRAM for localhost and explicitly authorizes `equiped_app` and
  `equiped_owner` from the Mac's `/32`, only for `equiped`. No remote superuser,
  trust authentication, router forwarding, Docker PostgreSQL, or WARP was added.
- Configs: `F:\Dev\Servers\PostgreSQL\data\postgresql.conf` and `pg_hba.conf`.
  Protected pre-change copies are in the migration directory below.

## Migration evidence

The complete Neon custom-format dump was restored in a single transaction with
`--no-owner --no-privileges --role=equiped_owner`. All **36 tables** match the
dump by count and order-independent SHA256 digest of every COPY row, preserving
account password hashes, snapshot bytes/hashes, historical results, metadata,
and training history. Constraints, indexes, the sequence, and the immutable
snapshot trigger were restored. Verification is against the export's consistent
snapshot, not any later writes to Neon.

| Records | Count |
| --- | ---: |
| Users | 7 |
| Documents / document chunks | 145 / 961 |
| Evaluation jobs / agent results | 214 / 108 |
| Immutable snapshots | 159 |
| Criterion scores / evaluation flags | 800 / 45 |
| Monitoring matrix | 30 |
| Rubric sets / criteria / active selections | 11 / 81 / 4 |
| DPO training jobs / trained adapters | 37 / 13 |

The active Coordinator rubric remains **v5 / adapter v3**, published. Local
owner-role `alembic upgrade head` passed on PostgreSQL 18; the repository and
database head are both `20261010_0002`. No inference configuration, tunnel,
models, prompts, adapters, or application records were changed.

Protected migration files:
`F:\Dev\Backups\EquipED\migration-20261014-162220`.
`record-counts.csv` has counts for every table; `data-verification.json` records
the comparisons. The directory contains sensitive backups and connection files:
never commit, publish, or send it wholesale.

## Roles and developer cutover

- `equiped_owner`: LOGIN, owns database/schema/objects; use only for migrations.
- `equiped_app`: LOGIN, CONNECT, public schema USAGE, table SELECT/INSERT/UPDATE/
  DELETE, sequence USAGE/SELECT. Cannot create schema objects.
- `equiped_backup`: local-only LOGIN, CONNECT, schema USAGE and table/sequence
  SELECT for complete backups.
- All three have no SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, or BYPASSRLS.
  Owner default privileges cover future tables/sequences for runtime and backup.

Developer connection template:

```dotenv
DATABASE_URL="postgresql://equiped_app:<URL_ENCODED_PASSWORD>@100.123.191.41:5432/equiped?sslmode=prefer"
```

The generated URL-safe runtime password and complete connection line are in
`developer-database.env` in the protected migration directory. Retrieve locally
and distribute through a private secret-sharing channel, not chat or git.
`migration-owner.env` contains the separate owner connection; do not use it for
normal backends. Percent-encode any special password characters if replacing
these generated passwords. Tailscale encrypts network traffic; `sslmode=prefer`
allows native PostgreSQL without independently configured TLS. `disable` is
also appropriate only over this private link; `require` needs configured TLS.

The Windows checkout's root `.env` was backed up and only DATABASE_URL was
changed, using `equiped_app` on `127.0.0.1`. All other settings are preserved.
No Mac files or services were modified. On the Mac, copy the runtime connection
line into the existing server/root `.env` in
`/Users/admin/Developer/repos/EquipED`; avoid conflicting values in two files
or an already-exported DATABASE_URL. Run migrations separately using the owner
connection, then run the backend with the runtime connection.

Teammates are **not enrolled or authorized yet**. Each must join this Tailnet
with their own invited account, install Tailscale, and provide their laptop's
IPv4. An administrator must add each verified `/32` to both the Firewall rule's
RemoteAddress list and an HBA rule of this form, preserving existing entries:

```text
host equiped equiped_app,equiped_owner <AUTHORIZED_LAPTOP_IPV4>/32 scram-sha-256
```

Back up HBA before each change and reload PostgreSQL. Do not authorize the whole
`100.64.0.0/10` range or enable unrestricted inbound TCP 5432. After authorization,
teammates use the same runtime URL and their own local frontend/backend.

## Verification boundaries

- Real SQLAlchemy runtime connection passed as `equiped_app`; historical users,
  document metadata, matrix rows, snapshots, and jobs are readable.
- Runtime DML grants, absence of schema CREATE, object ownership, the admission
  unique constraint, and the snapshot immutability trigger were verified.
- All 214 restored evaluation jobs are terminal (184 completed, 30 failed);
  there are no standalone syllabus alignment runs to recover. No evaluation
  execution was started. This does not certify future multi-backend job safety:
  standalone alignment startup recovery is process-local and must not interrupt
  another developer's active alignment. Avoid concurrent alignment workloads
  until a separately tested shared-backend coordination change is made.
- 26 document records explicitly reference R2; other artifact references and
  actual downloads require application/storage verification. A PostgreSQL dump
  does not copy local uploads, R2 objects, or Chroma vectors. Keep the existing
  artifact services/configuration; do not treat this dump as their backup.
- Mac connectivity, web login, `/health`, `/ready`, and browser matrix/document
  workflows were not tested: execution was narrowed to the Windows PC. The
  inference service was not contacted for a readiness probe.
- Neon was not deleted, suspended, or administratively changed. Other checkouts
  still need their runtime URL changed to stop using it. No billing change is
  implied by this database migration.

## Daily backups

- Source script: `infra/postgres/Backup-EquipED.ps1`.
- Operational script: `F:\Dev\Backups\EquipED\daily\Backup-EquipED.ps1`.
- Scheduled task: `EquipED-Daily-PostgreSQL-Backup`, daily **02:00 Windows local
  time**, running as SYSTEM even when logged out; missed runs start when available.
- Retention: **14 days**, pruning only matching completed daily dumps after a
  successful backup. The original migration dump is outside rolling retention.
- Dumps, SHA256 sidecars, archive indexes, and last-run JSON status live in the
  same `daily` directory, outside PostgreSQL's data folder.
- The backup credential file `pgpass.conf` and operational directory are ACL
  restricted to SYSTEM and Administrators. Do not move them into the repository.
- Initial manual and actual scheduled SYSTEM runs passed. Each run validates
  the archive index and reads/decompresses every data block before promotion.
  Scheduled Task `LastTaskResult` was `0`.
- No off-PC copy is configured: no external storage/sync destination was selected
  or authorized. Local dumps do not protect against PC/disk loss. Do not upload
  these institutional records to cloud sync without explicit approval.

For a manual backup, run elevated PowerShell:

```powershell
& 'F:\Dev\Backups\EquipED\daily\Backup-EquipED.ps1'
Get-ScheduledTaskInfo -TaskName 'EquipED-Daily-PostgreSQL-Backup'
```

## Restore without overwriting an existing database

Use an elevated local terminal and interactive PostgreSQL password prompts.
Confirm the owner role exists first. Choose a **new, absent** restore database:

```powershell
$bin = 'F:\Dev\Servers\PostgreSQL\bin'
& "$bin\psql.exe" -X -W -h 127.0.0.1 -U postgres -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE equiped_restore OWNER equiped_owner;'
& "$bin\pg_restore.exe" -W -h 127.0.0.1 -U postgres -d equiped_restore --role=equiped_owner --no-owner --no-privileges --exit-on-error --single-transaction 'F:\Dev\Backups\EquipED\daily\<SELECTED_BACKUP>.dump'
& "$bin\psql.exe" -X -W -h 127.0.0.1 -U postgres -d equiped_restore -c 'SELECT version_num FROM alembic_version;'
```

Verify the SHA256 sidecar first, compare all table counts/data, and check active
rubrics and snapshots before planning any cutover. Dumps intentionally omit
cluster roles and grants; reprovision the least-privilege roles/default grants
on a new cluster. Never use `--clean`, DROP the live database, or overwrite its
data directory as an automatic restore step. The daily archive was integrity-
checked; a separate restore of a daily archive into a new database was not run.
