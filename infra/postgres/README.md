# PostgreSQL backup and recovery

EquipED uses the PostgreSQL database selected by `DATABASE_URL`. Use a
least-privilege application role for runtime access and a separate owner role
for migrations. Never commit connection URLs, passwords, or database dumps.
See [operations](../../docs/operations.md) for the complete storage boundary.

## Windows backup utility

`Backup-EquipED.ps1` backs up the **local** `equiped` database on
`127.0.0.1:5432` as `equiped_backup`. It does not back up a remotely configured
application database. Create the backup directory and a protected `pgpass.conf`
there, and provision a backup role with access to the required tables and
sequences. Restrict both credentials and backups to authorized operators.

Supply paths explicitly instead of relying on the script's machine-specific
defaults:

```powershell
& ./infra/postgres/Backup-EquipED.ps1 `
  -BackupDirectory 'C:\EquipED\backups' `
  -PostgresBin 'C:\Program Files\PostgreSQL\18\bin' `
  -RetentionDays 14
```

The utility locks against overlapping runs, creates a custom-format dump, checks
its archive index, and reads/decompresses its data blocks before promoting it.
It writes a SHA-256 sidecar, archive index, and success/failure status. Retention
prunes matching completed archives only after a successful backup. Scheduling
and an approved separate backup copy must be configured by the operator.

Archive checks are not a restore rehearsal. PostgreSQL dumps do not include
uploaded documents, R2 objects, Chroma vectors, or cluster-role provisioning.
Back up each configured store separately.

## Restore rehearsal

1. Verify the selected archive's checksum and archive index.
2. Provision an isolated, empty destination database and the required roles.
3. Restore with the PostgreSQL tools appropriate to the archive version, using
   `--no-owner --no-privileges --exit-on-error --single-transaction` and the
   intended owner role.
4. Verify table contents, schema revision, constraints, immutable snapshots,
   active rubrics, and sequence state.
5. Restore or connect the corresponding document and vector stores, then verify
   application access and retrieval in the isolated environment.

Plan cutover and rollback separately. A point-in-time backup does not contain
later writes. Use the configured database provider's backup procedures for a
remote PostgreSQL deployment; this local utility does not provide that coverage.
