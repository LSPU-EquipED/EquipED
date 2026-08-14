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

import json
import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from server.modules.agents.sme.groups import CODE_TO_GROUP, GROUP_CODES
from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentResult, CriterionScore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmeDpoPair:
    group: str
    prompt: str
    chosen: str
    rejected: str
    evaluation_id: Any
    document_id: Any
    reviewer_ids: frozenset[Any]


def _is_real_change(
    edited_json: dict[str, Any] | None, original_score: CriterionScore
) -> bool:
    if not edited_json:
        return False
    edited_score = edited_json.get("score")
    edited_justification = str(edited_json.get("justification") or "").strip()
    original_justification = (original_score.justification or "").strip()
    return not (
        edited_score == original_score.score
        and edited_justification == original_justification
    )


def export_sme_dpo_pairs(db: Any) -> Iterator[SmeDpoPair]:
    """Yield one SmeDpoPair per (evaluation, group) with >=1 real correction."""

    edit_rows = (
        db.query(PreferenceLog)
        .filter(PreferenceLog.agent_name == "sme", PreferenceLog.action == "EDIT")
        .order_by(PreferenceLog.created_at.desc())
        .all()
    )

    latest_edit: dict[tuple[Any, str], PreferenceLog] = {}
    for log in edit_rows:
        grain = (log.evaluation_id, log.criterion_id)
        latest_edit.setdefault(grain, log)

    edits_by_evaluation: dict[Any, dict[str, PreferenceLog]] = defaultdict(dict)
    for (evaluation_id, criterion_id), log in latest_edit.items():
        edits_by_evaluation[evaluation_id][criterion_id] = log

    for evaluation_id, criterion_edits in edits_by_evaluation.items():
        agent_result = (
            db.query(AgentResult)
            .filter(
                AgentResult.evaluation_id == evaluation_id,
                AgentResult.agent_name == "sme",
            )
            .first()
        )
        if agent_result is None or not agent_result.group_prompts:
            logger.warning(
                "Skipping evaluation %s: no group_prompts snapshot (agent_result "
                "missing or predates group-prompt snapshotting).",
                evaluation_id,
            )
            continue

        original_scores = {
            score.criterion_id: score
            for score in (
                db.query(CriterionScore)
                .filter(CriterionScore.agent_result_id == agent_result.agent_result_id)
                .all()
            )
        }
        if not original_scores:
            logger.warning(
                "Skipping evaluation %s: no CriterionScore rows for its SME "
                "agent_result.",
                evaluation_id,
            )
            continue

        edits_by_group: dict[str, dict[str, PreferenceLog]] = defaultdict(dict)
        for criterion_id, log in criterion_edits.items():
            group = CODE_TO_GROUP.get(criterion_id)
            if group is None:
                logger.warning(
                    "Preference log %s: criterion_id %s is not a registered "
                    "SME code; ignored.",
                    log.log_id,
                    criterion_id,
                )
                continue
            edits_by_group[group][criterion_id] = log

        for group, group_edits in edits_by_group.items():
            group_prompt = agent_result.group_prompts.get(group)
            if not group_prompt:
                logger.warning(
                    "Skipping evaluation %s group %s: no prompt snapshot for "
                    "this group (it may have fallen back to per-criterion "
                    "scoring for this evaluation).",
                    evaluation_id,
                    group,
                )
                continue

            group_codes = GROUP_CODES[group]
            if any(code not in original_scores for code in group_codes):
                logger.warning(
                    "Skipping evaluation %s group %s: missing CriterionScore "
                    "row(s) for this group's codes.",
                    evaluation_id,
                    group,
                )
                continue

            chosen_map: dict[str, dict[str, Any]] = {}
            rejected_map: dict[str, dict[str, Any]] = {}
            reviewer_ids: set[Any] = set()

            for code in group_codes:
                score_row = original_scores[code]
                original_entry = {
                    "score": score_row.score,
                    "justification": score_row.justification,
                }
                rejected_map[code] = original_entry
                log = group_edits.get(code)
                if log is None or not _is_real_change(log.edited_json, score_row):
                    chosen_map[code] = original_entry
                    continue
                chosen_map[code] = {
                    "score": log.edited_json.get("score"),
                    "justification": log.edited_json.get("justification"),
                }
                reviewer_ids.add(log.user_id)

            if chosen_map == rejected_map:
                logger.warning(
                    "Skipping evaluation %s group %s: no criterion had a "
                    "real correction survive.",
                    evaluation_id,
                    group,
                )
                continue

            yield SmeDpoPair(
                group=group,
                prompt=group_prompt,
                chosen=json.dumps({"criterion_scores": chosen_map}, ensure_ascii=False),
                rejected=json.dumps(
                    {"criterion_scores": rejected_map}, ensure_ascii=False
                ),
                evaluation_id=evaluation_id,
                document_id=agent_result.document_id,
                reviewer_ids=frozenset(reviewer_ids),
            )


def main() -> None:
    import argparse

    from server.core.database import get_session_factory

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
            for pair in export_sme_dpo_pairs(session):
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
