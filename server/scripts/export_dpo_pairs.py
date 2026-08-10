"""Export DPO training pairs from ITSO reviewer EDIT feedback.

Reads PreferenceLog EDIT rows for agent_name="itso", pairs each with the
prompt snapshot and original score/justification captured on AgentResult /
CriterionScore at scoring time, and yields one dict per pair:

    {"prompt": <str>, "chosen": <json str>, "rejected": <json str>}

Rows whose AgentResult has no prompt_text (e.g. persisted before this
feature shipped) are logged and skipped, never silently dropped.

Training itself is out of scope here — this script only produces the
JSONL a separate, manually-run LoRA DPO training script consumes. See
docs/superpowers/specs/2026-08-10-dpo-itso-scoring-design.md.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentResult, CriterionScore

logger = logging.getLogger(__name__)


def export_dpo_pairs(db: Any) -> Iterator[dict[str, str]]:
    """Yield one DPO pair dict per usable EDIT row, latest edit per grain."""

    edit_rows = (
        db.query(PreferenceLog)
        .filter(PreferenceLog.agent_name == "itso", PreferenceLog.action == "EDIT")
        .order_by(PreferenceLog.created_at.desc())
        .all()
    )

    seen: set[tuple[Any, str]] = set()
    for log in edit_rows:
        grain = (log.evaluation_id, log.criterion_id)
        if grain in seen:
            continue
        seen.add(grain)

        agent_result = (
            db.query(AgentResult)
            .filter(
                AgentResult.evaluation_id == log.evaluation_id,
                AgentResult.agent_name == "itso",
            )
            .first()
        )
        if agent_result is None or not agent_result.prompt_text:
            logger.warning(
                "Skipping preference log %s: no prompt_text snapshot for "
                "evaluation %s (agent_result missing or predates prompt "
                "snapshotting).",
                log.log_id,
                log.evaluation_id,
            )
            continue

        original_score = (
            db.query(CriterionScore)
            .filter(
                CriterionScore.agent_result_id == agent_result.agent_result_id,
                CriterionScore.criterion_id == log.criterion_id,
            )
            .first()
        )
        if original_score is None:
            logger.warning(
                "Skipping preference log %s: no original CriterionScore row "
                "for criterion %s.",
                log.log_id,
                log.criterion_id,
            )
            continue

        if not log.edited_json:
            logger.warning(
                "Skipping preference log %s: EDIT action with empty edited_json.",
                log.log_id,
            )
            continue

        edited_score = log.edited_json.get("score")
        edited_justification = str(
            log.edited_json.get("justification") or ""
        ).strip()
        original_justification = (original_score.justification or "").strip()
        if (
            edited_score == original_score.score
            and edited_justification == original_justification
        ):
            logger.warning(
                "Skipping preference log %s: EDIT action did not change "
                "score or justification from the original (degenerate "
                "chosen == rejected pair).",
                log.log_id,
            )
            continue

        yield {
            "prompt": agent_result.prompt_text,
            "chosen": json.dumps(log.edited_json, ensure_ascii=False),
            "rejected": json.dumps(
                {
                    "score": original_score.score,
                    "justification": original_score.justification,
                },
                ensure_ascii=False,
            ),
        }


def main() -> None:
    import argparse

    from server.core.database import get_session_factory

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", help="Path to write the JSONL export to, e.g. itso_dpo_pairs.jsonl"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    session = get_session_factory()()
    try:
        count = 0
        with open(args.output, "w", encoding="utf-8") as f:
            for pair in export_dpo_pairs(session):
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                count += 1
        logger.info("Wrote %d DPO pairs to %s", count, args.output)
    finally:
        session.close()


if __name__ == "__main__":
    main()
