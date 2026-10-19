"""Frozen training job package creation and zip serialization."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from server.modules.training_data.agents import validate_agent_id
from server.modules.training_data.contracts import DpoPackageManifest, FrozenJobPackage
from server.modules.training_data.exporter import export_dpo_package
from server.modules.training_data.sources import get_active_training_package
from sqlalchemy.orm import Session


def freeze_job_dataset(session: Session, agent_id: str) -> FrozenJobPackage:
    """Copy the active source, or freeze a fresh export of eligible feedback."""
    validate_agent_id(agent_id)
    active = get_active_training_package(session, agent_id)
    if active is not None:
        return active
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


def preview_dataset_manifest(session: Session, agent_id: str) -> DpoPackageManifest:
    """Dry-run the exporter: same manifest a job would freeze, nothing written."""
    validate_agent_id(agent_id)
    # output_dir is never touched when dry_run is True.
    active = get_active_training_package(session, agent_id)
    if active is not None:
        return DpoPackageManifest.model_validate(active.manifest_json)
    return export_dpo_package(session, agent_id, Path("."), dry_run=True)


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
    "preview_dataset_manifest",
    "serialize_job_package_zip",
]
