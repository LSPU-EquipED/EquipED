# Training tools

Training scripts run in a separate environment from the EquipED API server.
See the [workflow guide](../docs/training.md) for preparation, evaluation,
and operational limits.

- `train_dpo_lora.py` trains a LoRA adapter from validated DPO pairs or a
  package. Install this directory's `requirements.txt` in the training
  environment. The base checkpoint must be a compatible fine-tunable model;
  the quantized serving artifact is not a training checkpoint.
- `evaluate_adapter.py` compares a loaded adapter with the base model on
  held-out corrected cases. See [evaluation instructions](evaluating-an-adapter.md).
- `host_sync.py` downloads published and recent GGUF files for the model
  host. See [host sync setup](../docs/host-sync-setup.md).
- `smoke_test_lora_serving.py` checks that the served model returns valid
  replies with an adapter off and on. Passing is a wiring check, not a quality
  claim.
- `serving-lora-adapter.md` explains manual adapter loading and verification.

`sample_pairs.jsonl` is synthetic test data. Do not treat it as expert labels.
