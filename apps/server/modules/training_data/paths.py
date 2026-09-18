"""apps/server/modules/training_data/paths.py"""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
ADAPTER_ROOT = _PROJECT_ROOT / "adapters"

MAX_ADAPTER_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB -- comfortably fits a
# LoRA adapter (typically tens to low hundreds of MB), not full model weights.
ALLOWED_ADAPTER_EXTENSIONS = frozenset({".zip"})


__all__ = [
    "ADAPTER_ROOT",
    "ALLOWED_ADAPTER_EXTENSIONS",
    "MAX_ADAPTER_UPLOAD_BYTES",
]
