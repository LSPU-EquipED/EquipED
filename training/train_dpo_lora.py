"""Standalone DPO/LoRA fine-tuning script for EquipED agent adapters.

Deliberately standalone -- NOT part of the apps/server/ FastAPI project. This
script is meant to be copied to (or run from) a separate GPU training
environment; see training/requirements.txt for its own, isolated
dependency set. It has no import dependency on anything under apps/server/.

Input: a JSONL file of DPO pairs, one object per line with keys
"prompt", "chosen", "rejected" -- exactly what
apps/server/scripts/export_score_level_dpo_pairs.py and
apps/server/scripts/export_item_level_dpo_pairs.py already produce.

Output: a LoRA adapter directory (not a merged model) that can be loaded
alongside the frozen base model at inference time.

IMPORTANT, unresolved before any real (non-smoke-test) training run:
this script fine-tunes a fine-tunable/unquantized base checkpoint (e.g.
a HuggingFace transformers checkpoint), NOT the quantized
"equiped-gemma3-4b-qat-q4" artifact the server serves for inference.
Confirm the correct unquantized source checkpoint for that model before
pointing --base-model at anything you intend to actually deploy from.

Usage (on the training machine, inside a venv with requirements.txt
installed):

    python train_dpo_lora.py \
        --base-model <hf-checkpoint-or-local-path> \
        --data score_level_dpo_pairs.jsonl \
        --output-dir ./adapters/sme-v1 \
        --max-steps 5   # small smoke-test run; drop for a real run and
                         # use --num-train-epochs instead

Smoke-test note: with only a handful of real pairs (as of this writing),
this run only proves the pipeline's mechanics -- model loads, LoRA
attaches, DPOTrainer runs, an adapter saves and reloads. It says nothing
about training quality; see docs discussion on required volume before
treating any resulting adapter as more than a wiring check.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-model",
        required=True,
        help=(
            "HuggingFace model id or local path to a fine-tunable "
            "(unquantized) checkpoint. NOT the qat-q4 serving artifact."
        ),
    )
    parser.add_argument(
        "--data",
        required=True,
        type=Path,
        help="Path to a JSONL file of {prompt, chosen, rejected} pairs.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to save the resulting LoRA adapter to.",
    )
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument(
        "--target-modules",
        default="all-linear",
        help="LoRA target modules; 'all-linear' works for most decoder models.",
    )
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--beta", type=float, default=0.1, help="DPO beta (KL penalty).")
    parser.add_argument("--per-device-train-batch-size", type=int, default=1)
    parser.add_argument(
        "--num-train-epochs",
        type=float,
        default=None,
        help="Full-data training epochs. Mutually exclusive with --max-steps.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Cap total training steps -- use for a quick smoke test.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.num_train_epochs is None and args.max_steps is None:
        parser.error("Specify either --num-train-epochs or --max-steps.")
    return args


def _validate_jsonl(path: Path) -> int:
    """Fail fast with a clear error if the export file is malformed, rather
    than letting a cryptic error surface deep inside the trainer."""
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    required_keys = {"prompt", "chosen", "rejected"}
    count = 0
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON") from exc
            missing = required_keys - obj.keys()
            if missing:
                raise ValueError(
                    f"{path}:{line_no}: missing required key(s) {sorted(missing)}"
                )
            count += 1

    if count == 0:
        raise ValueError(
            f"{path} contains no pairs -- nothing to train on. "
            "Run the export script(s) first and confirm they produced output."
        )
    return count


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()

    pair_count = _validate_jsonl(args.data)
    logger.info("Loaded %d DPO pair(s) from %s", pair_count, args.data)
    if pair_count < 20:
        logger.warning(
            "Only %d pair(s) found -- this is a wiring/smoke test, not a "
            "meaningful training run. See project notes on required volume "
            "before treating the resulting adapter as production-worthy.",
            pair_count,
        )

    try:
        from datasets import load_dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import DPOConfig, DPOTrainer
    except ImportError as exc:
        logger.error(
            "Missing a required package (%s). Install training/requirements.txt "
            "in this environment first: pip install -r requirements.txt",
            exc,
        )
        sys.exit(1)

    dataset = load_dataset("json", data_files=str(args.data), split="train")

    logger.info("Loading tokenizer and base model: %s", args.base_model)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(args.base_model)

    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=args.target_modules,
    )

    training_kwargs: dict[str, object] = dict(
        output_dir=str(args.output_dir),
        per_device_train_batch_size=args.per_device_train_batch_size,
        learning_rate=args.learning_rate,
        beta=args.beta,
        seed=args.seed,
        logging_steps=1,
        save_strategy="no",
        report_to=[],
    )
    if args.max_steps is not None:
        training_kwargs["max_steps"] = args.max_steps
    else:
        training_kwargs["num_train_epochs"] = args.num_train_epochs

    training_args = DPOConfig(**training_kwargs)

    # NOTE: trl's DPOTrainer constructor signature has changed across
    # versions (e.g. the tokenizer/processing_class kwarg name). If this
    # raises a TypeError on your installed trl version, check
    # `DPOTrainer.__init__`'s signature and adjust the kwarg name below --
    # the rest of this script (data validation, LoRA config, save/reload)
    # is version-independent.
    trainer = DPOTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    logger.info("Starting DPO training...")
    trainer.train()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(args.output_dir))
    logger.info("Saved LoRA adapter to %s", args.output_dir)

    # Reload check: confirms the saved adapter is actually loadable, not
    # just that save_model() didn't raise.
    from peft import PeftModel

    logger.info("Verifying the saved adapter reloads cleanly...")
    base_for_reload = AutoModelForCausalLM.from_pretrained(args.base_model)
    PeftModel.from_pretrained(base_for_reload, str(args.output_dir))
    logger.info("Adapter reload check passed.")


if __name__ == "__main__":
    main()
