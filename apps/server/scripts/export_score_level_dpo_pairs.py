"""Export DPO training pairs from SME score-level reviewer feedback.

Applies only to llm_rubric_guidance criteria (SME's current scoring
approach), where the LLM outputs the score itself -- a plain score+
justification EDIT is real, valid model output to pair against. See
server/modules/feedback/dpo.py for the item-level exporter this
replaces for SME (its count_band/ratio_band criteria never had a score
in the model's own output to correct).

Usage (from repo root):

    cd apps && uv run --project server python -m \
        server.scripts.export_score_level_dpo_pairs \
        score_level_dpo_pairs.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Iterator
from typing import Any

from server.core.database import get_session_factory
from server.modules.feedback.dpo import DpoPair, export_score_level_dpo_pairs

logger = logging.getLogger(__name__)


def export_pairs(db: Any) -> Iterator[DpoPair]:
    """Delegate to the feedback module's score-level DPO pair projection."""
    return export_score_level_dpo_pairs(db)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        help="Path to write the JSONL export to, e.g. score_level_dpo_pairs.jsonl",
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
            "Wrote %d score-level DPO pairs across %d evaluations, %d reviewers to %s",
            count,
            len(evaluations),
            len(reviewers),
            args.output,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
