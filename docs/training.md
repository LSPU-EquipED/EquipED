# Training workflow

EquipED training produces advisory adapters for evaluation agents. Human
review remains authoritative; a trained adapter is not evidence that its
outputs are correct or suitable for publication.

## Prepare reviewed data

In Admin Training Data, inspect the available feedback and provenance before
starting a training run. Where a reviewed package is used, follow
[Reviewed training packages](reviewed-training-packages.md). Package integrity
checks verify bytes and identities, not label correctness. Keep synthetic
examples explicitly identified as synthetic; they are useful for controlled
experiments, not expert reference labels.

## Train and export

Before using Colab, configure `PUBLIC_BASE_URL` on the backend to an authorized,
externally reachable HTTPS origin. Colab must reach the generated dataset and
upload endpoints; a localhost URL from the development proxy will not work.
Authorize the training data transfer under institutional policy and keep notebook
links private. Download a fresh notebook after changing this setting.

Download the notebook from Admin Training Data and use its frozen snapshot. The Colab templates in `colab/` are supporting
artifacts; follow the notebook's current validation and split summary. Review
pair counts, dropped examples, provenance, and held-out availability before
training. If the run has no internal held-out set, use separately reserved
evaluation data. A held-out split is not independent if related documents or
near duplicates cross the split.

Training produces an adapter archive. The adapter must be converted to a GGUF
LoRA and uploaded to EquipED before the model host can load it. Uploading or
loading does not publish it.

## Evaluate and publish

Use [adapter evaluation](../training/evaluating-an-adapter.md) to compare the
served base model with the adapter on held-out corrected cases. This comparison
is advisory and has limited scope: corrected cases do not show effects on
approved cases, and synthetic target edits only test whether the taught change
appears. Check output validity and control behavior as well as target movement.

Have the host owner load the adapter at scale 0.0 and confirm it is available.
Then use Model Validation to compare Base and the selected adapter for one
agent at a time. Review the results before an authorized administrator
publishes or unpublishes a version in Admin Training Data. If a published
adapter is unavailable, evaluation may fall back to the base model; inspect
the recorded adapter resolution.

## Operational boundaries

- Training runs in the isolated training environment, not in the FastAPI
  server process.
- Notebooks use frozen training snapshots; existing jobs are not changed when
  a source package changes.
- Host sync downloads verified GGUF files and writes launch flags. It does not
  restart the model server, delete old files, or publish adapters.
- Keep host keys, API keys, and token-bearing download links private. Do not
  put secrets or real private data in examples, notebooks, or reports.

See [host sync setup](host-sync-setup.md),
[serving adapters](../training/serving-lora-adapter.md), and
[evaluation details](../training/evaluating-an-adapter.md) for operator steps.
