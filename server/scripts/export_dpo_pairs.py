"""Export DPO training pairs from ITSO reviewer feedback."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Iterator
from typing import Any

from server.core.database import get_session_factory
from server.modules.feedback.dpo import DpoPair, export_itso_dpo_pairs

logger = logging.getLogger(__name__)


def export_dpo_pairs(db: Any) -> Iterator[DpoPair]:
    """Delegate to feedback module DPO pair projection."""
    return export_itso_dpo_pairs(db)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", help="Path to write the JSONL export to, e.g. itso_dpo_pairs.jsonl"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    session = get_session_factory()()
    try:
        count = 0
        evaluations: set[Any] = set()
        documents: set[Any] = set()
        reviewers: set[Any] = set()
        with open(args.output, "w", encoding="utf-8") as f:
            for pair in export_dpo_pairs(session):
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
                documents.add(pair.document_id)
                reviewers.update(pair.reviewer_ids)
        logger.info(
            "Wrote %d DPO pairs across %d evaluations, %d documents, %d "
            "reviewers to %s",
            count,
            len(evaluations),
            len(documents),
            len(reviewers),
            args.output,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
