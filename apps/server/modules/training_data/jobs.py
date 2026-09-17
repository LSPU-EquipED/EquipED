"""apps/server/modules/training_data/jobs.py"""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from server.modules.training_data.exceptions import InvalidAgentIdError
from server.modules.training_data.exporter import export_dpo_package
from server.modules.training_data.models import DpoTrainingJob
from server.modules.training_data.tokens import generate_raw_token, hash_token
from sqlalchemy.orm import Session

VALID_AGENT_IDS: frozenset[str] = frozenset({"sme", "coordinator", "gad", "itso"})

_DOWNLOAD_TOKEN_LIFETIME = timedelta(hours=24)
_UPLOAD_TOKEN_LIFETIME = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class TrainingJobCreated:
    job: DpoTrainingJob
    raw_download_token: str
    raw_upload_token: str


def _freeze_dataset(session: Session, agent_id: str) -> tuple[str, str, dict]:
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
        return pairs_content, provenance_content, json.loads(manifest_json)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)


def create_training_job(
    session: Session, agent_id: str, created_by: uuid.UUID
) -> TrainingJobCreated:
    """Create a training job: freeze the current DPO dataset for agent_id
    and mint a single-use download token plus a single-use upload token,
    both scoped to the new job."""
    if agent_id not in VALID_AGENT_IDS:
        raise InvalidAgentIdError(f"unknown agent_id: {agent_id!r}")

    pairs_content, provenance_content, manifest_json = _freeze_dataset(
        session, agent_id
    )

    raw_download_token = generate_raw_token()
    raw_upload_token = generate_raw_token()
    now = datetime.now(UTC)

    job = DpoTrainingJob(
        job_id=uuid.uuid4(),
        agent_id=agent_id,
        status="pending",
        created_by=created_by,
        pairs_content=pairs_content,
        provenance_content=provenance_content,
        manifest_json=manifest_json,
        download_token_hash=hash_token(raw_download_token),
        download_expires_at=now + _DOWNLOAD_TOKEN_LIFETIME,
        upload_token_hash=hash_token(raw_upload_token),
        upload_expires_at=now + _UPLOAD_TOKEN_LIFETIME,
    )
    session.add(job)
    session.commit()

    return TrainingJobCreated(
        job=job,
        raw_download_token=raw_download_token,
        raw_upload_token=raw_upload_token,
    )


__all__ = ["VALID_AGENT_IDS", "TrainingJobCreated", "create_training_job"]
