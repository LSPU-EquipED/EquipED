"""Import or restore an agent's training source without deleting historical data."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from server.core.config import get_settings
from server.core.database import get_session_factory
from server.modules.auth.service import require_approved_admin
from server.modules.training_data.agents import VALID_AGENT_IDS
from server.modules.training_data.contracts import FrozenJobPackage
from server.modules.training_data.exceptions import InvalidTrainingSourceError
from server.modules.training_data.models import DpoTrainingJob
from server.modules.training_data.sources import (
    get_active_training_package,
    register_training_source,
    set_active_training_source,
    validate_training_package,
)


def target_fingerprint(database_url: str) -> str:
    """Identify the target without printing credentials; disallow routing overrides."""
    url = make_url(database_url)
    if set(url.query) & {"host", "hostaddr", "port", "dbname", "database", "service"}:
        raise ValueError("Database routing overrides are not supported")
    port = url.port or (5432 if url.get_backend_name() == "postgresql" else None)
    target = f"{(url.host or '').lower()}:{port}/{url.database or ''}"
    return hashlib.sha256(target.encode()).hexdigest()


def load_package(directory: Path) -> FrozenJobPackage:
    """Preserve exact UTF-8 bytes, including JSONL line endings, for checksum checks."""
    return FrozenJobPackage(
        (directory / "pairs.jsonl").read_bytes().decode("utf-8"),
        (directory / "provenance.jsonl").read_bytes().decode("utf-8"),
        json.loads((directory / "manifest.json").read_bytes()),
    )


def change_source(
    session: Session,
    agent_id: str,
    admin_id: uuid.UUID,
    package: FrozenJobPackage | None,
    *,
    apply: bool,
) -> dict:
    """Use a dedicated session and commit only on explicitly requested apply."""
    require_approved_admin(session, admin_id)
    if package is None:
        if apply:
            set_active_training_source(session, agent_id, None)
            session.commit()
        return {
            "agent_id": agent_id,
            "action": "feedback_restored" if apply else "preview_restore",
        }
    validate_training_package(package, agent_id)
    receipt = {
        "agent_id": agent_id,
        "pair_count": package.manifest_json["pair_count"],
        "pairs_sha256": package.manifest_json["pairs_sha256"],
        "action": "preview_import",
    }
    if not apply:
        return receipt
    try:
        active = get_active_training_package(session, agent_id)
    except InvalidTrainingSourceError:
        # A validated replacement must be able to repair an invalid active package.
        active = None
    if active == package:
        job_id = session.scalar(
            select(DpoTrainingJob.job_id).where(
                DpoTrainingJob.agent_id == agent_id,
                DpoTrainingJob.is_active_training_source.is_(True),
            )
        )
        receipt.update(action="already_active", source_job_id=str(job_id))
        return receipt
    result = register_training_source(session, agent_id, admin_id, package)
    receipt.update(action="activated", source_job_id=str(result.job.job_id))
    session.commit()
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, choices=sorted(VALID_AGENT_IDS))
    parser.add_argument("--admin-id", required=True, type=uuid.UUID)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--package-dir", type=Path)
    mode.add_argument("--restore-feedback", action="store_true")
    parser.add_argument(
        "--apply", action="store_true", help="Default is a read-only preview."
    )
    parser.add_argument("--confirm-target", help="Fingerprint printed by the preview.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    load_dotenv(root / "apps/.env")
    load_dotenv(root / ".env")
    settings = get_settings()
    if not settings.database_url:
        parser.error("DATABASE_URL is not configured")
    fingerprint = target_fingerprint(settings.database_url)
    if args.apply and args.confirm_target != fingerprint:
        parser.error("Apply requires --confirm-target with the preview's fingerprint")
    package = load_package(args.package_dir) if args.package_dir else None
    with get_session_factory()() as session:
        try:
            receipt = change_source(
                session, args.agent, args.admin_id, package, apply=args.apply
            )
        except Exception:
            session.rollback()
            # Never print SQL parameters or source content from database exceptions.
            parser.exit(1, "Source change failed; transaction rolled back.\n")
    receipt["target_fingerprint"] = fingerprint
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
