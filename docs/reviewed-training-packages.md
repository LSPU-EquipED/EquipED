# Reviewed training packages

An authorized administrator can select a reviewed package as the active
training source for an agent. The importer checks package structure, hashes,
sizes, pair identities, agent identity, and provenance. These checks establish
integrity and consistency; they do not establish that labels are correct.

## Package contents

The package directory contains `pairs.jsonl`, `provenance.jsonl`, and
`manifest.json`. Preserve the package bytes. Review provenance and labels
before importing. Synthetic target edits must remain labeled synthetic;
unmodified model outputs are not expert reference labels.

## Preview and apply

From the repository root, with the server application environment available:

```sh
cd apps
uv run --project server python -m server.scripts.import_training_source \
  --agent <sme|coordinator|gad|itso> --admin-id <ADMIN_UUID> \
  --package-dir <PACKAGE_DIRECTORY>
```

The default is a preview. Review its validation and target fingerprint. To
apply, repeat the command with `--apply --confirm-target <FINGERPRINT>`.
Repeatedly importing the same active package does not create another source.

To restore the feedback exporter as the active source, preview with
`--restore-feedback`, then apply with `--apply --confirm-target
<FINGERPRINT>`. Source selection does not delete feedback or prior training
snapshots. Invalid active packages return an error rather than silently
switching to another source.

After changing the source, create a new training job and download a new
notebook. Existing notebooks retain their frozen training data. Keep
token-bearing download links private.

For split and evaluation guidance, see the [training workflow](training.md)
and [adapter evaluation guide](../training/evaluating-an-adapter.md).
