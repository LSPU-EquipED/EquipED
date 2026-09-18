"""Frozen training job package creation and zip serialization."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from server.modules.training_data.exporter import export_dpo_package
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class FrozenJobPackage:
    pairs_content: str
    provenance_content: str
    manifest_json: dict


def freeze_job_dataset(session: Session, agent_id: str) -> FrozenJobPackage:
    """Run export_dpo_package() to a scratch dir, read its output back as
    content, then delete the scratch dir. export_dpo_package() itself is
    not modified -- this only reads what it already writes."""
    scratch_root = tempfile.mkdtemp(prefix=".dpo_job_freeze_")
    scratch_dir = Path(scratch_root) / "package"
    try:
        export_dpo_package(session, agent_id, scratch_dir)
        pairs_content = (scratch_dir / "pairs.jsonl").read_text(encoding="utf-8")
        provenance_content = (scratch_dir / "provenance.jsonl").read_text(
            encoding="utf-8"
        )
        manifest_json = (scratch_dir / "manifest.json").read_text(encoding="utf-8")
        return FrozenJobPackage(
            pairs_content=pairs_content,
            provenance_content=provenance_content,
            manifest_json=json.loads(manifest_json),
        )
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)


def serialize_job_package_zip(
    pairs_content: str,
    provenance_content: str,
    manifest_json: dict,
) -> bytes:
    """Serialize frozen package components into in-memory zip bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pairs.jsonl", pairs_content)
        zf.writestr("provenance.jsonl", provenance_content)
        zf.writestr("manifest.json", json.dumps(manifest_json, indent=2))
    return buffer.getvalue()


__all__ = [
    "FrozenJobPackage",
    "freeze_job_dataset",
    "serialize_job_package_zip",
]
