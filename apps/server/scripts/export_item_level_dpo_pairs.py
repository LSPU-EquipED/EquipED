"""Export DPO training pairs from reviewer item-level feedback for a target agent.

Usage (from repo root):

    cd apps && uv run --project server python -m \
        server.scripts.export_item_level_dpo_pairs \
        --agent sme \
        item_level_dpo_pairs.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Iterator
from typing import Any

from server.core.database import get_session_factory
from server.modules.feedback.dpo import DpoPair, export_item_level_dpo_pairs

logger = logging.getLogger(__name__)


def export_pairs(db: Any, agent: str) -> Iterator[DpoPair]:
    """Delegate to the feedback module's item-level DPO pair projection."""
    return export_item_level_dpo_pairs(db, (agent,))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent",
        required=True,
        choices=["sme", "coordinator"],
        help="Target agent to export item-level DPO pairs for (sme or coordinator).",
    )
    parser.add_argument(
        "output",
        help="Path to write the JSONL export to, e.g. item_level_dpo_pairs.jsonl",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    session = get_session_factory()()
    try:
        count = 0
        evaluations: set[Any] = set()
        reviewers: set[Any] = set()
        with open(args.output, "w", encoding="utf-8") as f:
            for pair in export_pairs(session, args.agent):
                f.write(
                    json.dumps(
                        {
                            "prompt": pair.prompt,
                            "chosen": pair.chosen,
                            "rejected": pair.rejected,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                count += 1
                evaluations.add(pair.evaluation_id)
                reviewers.update(pair.reviewer_ids)
        logger.info(
            "Wrote %d item-level DPO pairs for agent '%s' across %d "
            "evaluations, %d reviewers to %s",
            count,
            args.agent,
            len(evaluations),
            len(reviewers),
            args.output,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
