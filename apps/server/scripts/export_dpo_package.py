"""CLI script to export a unified DPO training package."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from server.core.database import get_session_factory
from server.modules.training_data.exporter import export_dpo_package

logger = logging.getLogger(__name__)


def _parse_datetime(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a unified DPO training package for an agent."
    )
    parser.add_argument(
        "--agent",
        required=True,
        choices=["sme", "coordinator", "gad", "itso"],
        help="Target agent to export DPO pairs for.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory for exported package.",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=None,
        help="Filter generation rows by model_name.",
    )
    parser.add_argument(
        "--since",
        type=_parse_datetime,
        default=None,
        help="Filter generation rows created at or after this ISO datetime.",
    )
    parser.add_argument(
        "--until",
        type=_parse_datetime,
        default=None,
        help="Filter generation rows created at or before this ISO datetime.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate export without writing package files to disk.",
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    session = get_session_factory()()
    try:
        manifest = export_dpo_package(
            session=session,
            agent_id=args.agent,
            output_dir=args.output,
            model_name=args.model_name,
            since=args.since,
            until=args.until,
            dry_run=args.dry_run,
        )
        print(json.dumps(manifest.model_dump(mode="json"), indent=2))
        logger.info(
            "DPO package export complete: %d pairs, %d evaluations, %d reviewers%s",
            manifest.pair_count,
            manifest.evaluation_count,
            manifest.reviewer_count,
            " (dry-run)" if args.dry_run else f" written to {args.output}",
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
