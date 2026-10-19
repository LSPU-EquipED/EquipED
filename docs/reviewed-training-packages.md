# Reviewed training packages

This is an implemented option within the existing Admin training workflow.
An active approved administrator selects a reviewed package locally; readiness
and new notebook jobs then copy its exact contents. No new table is required.

Apply migration `20261019_0001` before starting the updated backend. It adds
the active-source flag and index where absent, or adopts the earlier schema
without replacing existing job snapshots. It follows the current migration
chain rather than reusing the older, conflicting revision ID.

The import package directory must contain `pairs.jsonl`, `provenance.jsonl`
and `manifest.json`. Preserve their exact UTF-8 bytes. The importer verifies
hashes, sizes, pair identities, agent identity and provenance. These checks
do not establish that the proposed labels are correct; review happens first.

From the repository root, with `apps` on the Python import path:

```powershell
apps/server/.venv/Scripts/python.exe -m server.scripts.import_training_source --agent gad --admin-id ADMIN_UUID --package-dir PACKAGE_DIRECTORY
```

The default is a preview. Apply using the same arguments plus `--apply`
and `--confirm-target TARGET_FINGERPRINT` from that preview. The fingerprint
identifies the database without exposing credentials. A repeated import of
the same active package does not create another source.

Restart the backend, open Admin Training Data, select GAD, and check the
pair count before selecting Start Training Run and Download Notebook. Old
notebooks retain their own frozen data and links; download a new notebook
for the new run. No token-bearing links should be committed or shared.

To restore the normal feedback exporter, use `--restore-feedback` instead of
`--package-dir`, preview first, then apply with the confirmed target. This
changes source selection without deleting feedback or historical packages.
Invalid active packages return an explicit error rather than exporting
different feedback silently.

For the GAD-02 pilot, only GAD-02 has reviewed synthetic target edits. Other
criterion sections retain genuine Base outputs as stability controls, not
expert reference labels. Keep matched lesson variants together when assessing
internal splits; use the six reserved topic-held-out SLMs for external testing.
