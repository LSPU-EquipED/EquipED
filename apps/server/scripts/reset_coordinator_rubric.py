"""Offline Coordinator rubric authoring reset; never run automatically.

This script intentionally requires an exact confirmation string. It deletes
only Coordinator authoring rows, preserves snapshots/provenance, and stops
without publishing or activating a replacement.

Usage:
    cd apps && uv run --project server python -m \
        server.scripts.reset_coordinator_rubric --confirm RESET_COORDINATOR_RUBRIC

A blank v1 draft is opt-in and requires a second confirmation string:
    ... --confirm RESET_COORDINATOR_RUBRIC \
        --create-fresh-v1-draft \
        --fresh-draft-confirm CREATE_COORDINATOR_RUBRIC_V1_DRAFT
"""

from __future__ import annotations

import argparse

from server.core.database import get_session_factory
from server.modules.rubrics.reset import (
    FRESH_V1_DRAFT_CONFIRMATION,
    RESET_CONFIRMATION,
    reset_coordinator_rubric,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Explicitly reset Coordinator rubric authoring rows offline."
    )
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--create-fresh-v1-draft", action="store_true")
    parser.add_argument("--fresh-draft-confirm")
    parser.add_argument("--expected-rubric-set-count", type=int)
    parser.add_argument("--expected-snapshot-count", type=int)
    parser.add_argument("--expected-provenance-count", type=int)
    args = parser.parse_args(argv)

    if args.confirm != RESET_CONFIRMATION:
        parser.error(f"--confirm must equal {RESET_CONFIRMATION!r}")
    if args.create_fresh_v1_draft and (
        args.fresh_draft_confirm != FRESH_V1_DRAFT_CONFIRMATION
    ):
        parser.error(
            "--fresh-draft-confirm must equal "
            f"{FRESH_V1_DRAFT_CONFIRMATION!r} when creating a draft"
        )
    if not args.create_fresh_v1_draft and args.fresh_draft_confirm is not None:
        parser.error("--fresh-draft-confirm requires --create-fresh-v1-draft")

    session_factory = get_session_factory()
    with session_factory() as session:
        with session.begin():
            report = reset_coordinator_rubric(
                session,
                confirmation=args.confirm,
                create_fresh_v1_draft=args.create_fresh_v1_draft,
                fresh_draft_confirmation=args.fresh_draft_confirm,
                expected_rubric_set_count=args.expected_rubric_set_count,
                expected_snapshot_count=args.expected_snapshot_count,
                expected_provenance_count=args.expected_provenance_count,
            )

    print(
        "Coordinator rubric authoring reset complete: "
        f"rubric_sets={len(report.coordinator_rubric_set_ids)}, "
        f"domains={report.coordinator_domain_count}, "
        f"criteria={report.coordinator_criterion_count}, "
        f"snapshots_preserved={report.snapshot_count_before}, "
        f"provenance_preserved={report.provenance_count_before}, "
        f"fresh_draft_id={report.fresh_draft_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
