"""Export DPO training pairs from SME reviewer EDIT feedback.

SME scores via 3 grouped LLM calls (see
``server/modules/agents/sme/groups.py``), so -- unlike ITSO's single-call
export -- pairs are keyed per (evaluation, group), not per evaluation. A
group with no corrected criteria yields no row: no real SME call ever spans
all 10 criteria at once, so a synthetic "all criteria in one prompt" pair
would train on a shape the model never sees at inference time.

See docs/superpowers/specs/2026-08-13-sme-dpo-scoring-design.md and
server/scripts/export_dpo_pairs.py (the ITSO equivalent this mirrors).
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Iterator
from typing import Any

from server.core.database import get_session_factory
from server.modules.feedback.dpo import DpoPair, export_sme_dpo_pairs

logger = logging.getLogger(__name__)


def export_pairs(db: Any) -> Iterator[DpoPair]:
    """Delegate to feedback module SME DPO pair projection."""
    return export_sme_dpo_pairs(db)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", help="Path to write the JSONL export to, e.g. sme_dpo_pairs.jsonl"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    session = get_session_factory()()
    try:
        count = 0
        evaluations: set[Any] = set()
        reviewers: set[Any] = set()
        with open(args.output, "w", encoding="utf-8") as f:
            for pair in export_pairs(session):
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
            "Wrote %d SME DPO pairs across %d evaluations, %d reviewers to %s",
            count,
            len(evaluations),
            len(reviewers),
            args.output,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
