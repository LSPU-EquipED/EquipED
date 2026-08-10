"""Export DPO training pairs from ITSO reviewer EDIT feedback.

Reads PreferenceLog EDIT rows for agent_name="itso", merges each with the
prompt snapshot and every criterion's original score/justification
captured on AgentResult / CriterionScore at scoring time, and yields one
DpoPair per evaluation:

    prompt: the exact prompt ITSO received (shared across all its criteria)
    chosen: the reviewer-corrected {criterion_id: {score, justification}}
        for every criterion -- corrected where a reviewer edited, the
        AI's original everywhere else
    rejected: the AI's original {criterion_id: {score, justification}}
        for every criterion

One pair per evaluation, not per criterion -- this matches what ITSO
actually generates: a single LLM call scoring every criterion together,
not one call per criterion. Pairing a corrected fragment against a
full-response prompt would be a category mismatch for DPO, which compares
complete responses to a prompt.

Every export run reads full history, not a delta since the last run --
re-running after more corrections come in is safe (each run is a fresh,
complete snapshot). Do NOT concatenate the output of two separate export
runs into one training session: the same evaluation could appear in both
at different points of completeness, producing overlapping/redundant
entries. Always train from a single, freshly generated export.

Rows/evaluations that can't produce a usable pair are logged and skipped,
never silently dropped.

Training itself is out of scope here -- this script only produces the
JSONL a separate, manually-run LoRA DPO training script consumes. See
docs/superpowers/specs/2026-08-10-dpo-itso-scoring-design.md and
docs/superpowers/specs/2026-08-11-itso-review-modal-and-export-design.md.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentResult, CriterionScore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DpoPair:
    """One evaluation's DPO training pair: full-response chosen vs. rejected."""

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


def export_dpo_pairs(db: Any) -> Iterator[DpoPair]:
    """Yield one DpoPair per evaluation with at least one real ITSO correction."""

    edit_rows = (
        db.query(PreferenceLog)
        .filter(PreferenceLog.agent_name == "itso", PreferenceLog.action == "EDIT")
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
                AgentResult.agent_name == "itso",
            )
            .first()
        )
        if agent_result is None or not agent_result.prompt_text:
            logger.warning(
                "Skipping evaluation %s: no prompt_text snapshot (agent_result "
                "missing or predates prompt snapshotting). Affected preference "
                "logs: %s",
                evaluation_id,
                [str(log.log_id) for log in criterion_edits.values()],
            )
            continue

        original_scores = (
            db.query(CriterionScore)
            .filter(CriterionScore.agent_result_id == agent_result.agent_result_id)
            .all()
        )
        if not original_scores:
            logger.warning(
                "Skipping evaluation %s: no CriterionScore rows for its ITSO "
                "agent_result.",
                evaluation_id,
            )
            continue

        chosen_map: dict[str, dict[str, Any]] = {}
        rejected_map: dict[str, dict[str, Any]] = {}
        reviewer_ids: set[Any] = set()
        consumed_criterion_ids: set[str] = set()

        for score_row in original_scores:
            cid = score_row.criterion_id
            original_entry = {
                "score": score_row.score,
                "justification": score_row.justification,
            }
            rejected_map[cid] = original_entry

            log = criterion_edits.get(cid)
            if log is not None:
                consumed_criterion_ids.add(cid)

            if log is None or not _is_real_change(log.edited_json, score_row):
                if log is not None and not log.edited_json:
                    logger.warning(
                        "Preference log %s: EDIT action with empty edited_json "
                        "for criterion %s, falling back to the original value.",
                        log.log_id,
                        cid,
                    )
                elif log is not None:
                    logger.warning(
                        "Preference log %s: EDIT for criterion %s did not "
                        "change score or justification from the original, "
                        "falling back to the original value.",
                        log.log_id,
                        cid,
                    )
                chosen_map[cid] = original_entry
                continue

            chosen_map[cid] = {
                "score": log.edited_json.get("score"),
                "justification": log.edited_json.get("justification"),
            }
            reviewer_ids.add(log.user_id)

        unconsumed = set(criterion_edits) - consumed_criterion_ids
        for cid in unconsumed:
            logger.warning(
                "Preference log %s: criterion_id %s has no matching "
                "CriterionScore row for evaluation %s; ignored.",
                criterion_edits[cid].log_id,
                cid,
                evaluation_id,
            )

        if chosen_map == rejected_map:
            logger.warning(
                "Skipping evaluation %s: no criterion had a real correction "
                "survive (all edits degenerate, empty, or unmatched).",
                evaluation_id,
            )
            continue

        yield DpoPair(
            prompt=agent_result.prompt_text,
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
