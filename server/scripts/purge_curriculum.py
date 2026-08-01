"""Purge retired curriculum reference documents.

Dry-run by default; pass ``--execute`` to apply. Emits a content-free JSON
manifest (document ids and counts only) to stdout and optionally to a file.

Usage:
    python -m server.scripts.purge_curriculum           # dry-run plan
    python -m server.scripts.purge_curriculum --execute # apply the purge
    python -m server.scripts.purge_curriculum --manifest out.json --execute

Exit codes:
    0  success (plan produced, or purge applied)
    1  purge blocked by safety checks, or external cleanup failed
    2  a required dependency is unreachable or unconfigured
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from server.core.database import get_session_factory
from server.db.metadata import import_model_modules
from server.modules.admin.curriculum_purge import (
    PurgeBlockedError,
    PurgeExecutionError,
    PurgeUnreachableError,
    execute_curriculum_purge,
    plan_curriculum_purge,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="purge_curriculum",
        description=(
            "Purge retired curriculum reference documents (dry-run by default)."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Apply the purge. Without this flag the command only plans "
            "(dry run) and changes nothing."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Also write the JSON manifest to this file.",
    )
    parser.add_argument(
        "--upload-root",
        type=Path,
        default=None,
        help="Override the upload root directory (defaults to <repo>/uploads).",
    )
    return parser


def _emit_manifest(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    payload = json.dumps(manifest, indent=2, default=str) + "\n"
    if args.manifest is not None:
        try:
            args.manifest.write_text(payload, encoding="utf-8")
        except OSError as exc:
            print(
                f"failed to write manifest to {args.manifest}: {exc}",
                file=sys.stderr,
            )
            return 1
    print(payload)
    return 0


def _emit_error(message: str, *, code: int) -> int:
    print(message, file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Register ALL ORM model metadata (including auth `users`, which the
    # purge's Document/Evaluation tables reference) before any session work.
    # Without this, a standalone process reaches the commit with an
    # incomplete metadata graph and fails with NoReferencedTableError.
    import_model_modules()

    try:
        session = get_session_factory()()
    except Exception as exc:
        return _emit_error(
            f"purge aborted: database unreachable "
            f"({type(exc).__name__}: {exc})",
            code=2,
        )

    try:
        if args.execute:
            manifest = execute_curriculum_purge(
                session, upload_root=args.upload_root
            )
        else:
            manifest = plan_curriculum_purge(session, upload_root=args.upload_root)
    except PurgeUnreachableError as exc:
        return _emit_error(f"purge aborted: {exc}", code=2)
    except (PurgeBlockedError, PurgeExecutionError) as exc:
        return _emit_error(f"purge failed: {exc}", code=1)
    finally:
        session.close()

    return _emit_manifest(args, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
