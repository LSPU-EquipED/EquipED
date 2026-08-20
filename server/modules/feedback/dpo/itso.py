"""ITSO DPO training pair projection logic."""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

from server.modules.agents.itso.response import (
    ITSO_CRITERIA,
    ITSO_CRITERIA_TITLES,
    parse_response,
)
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.dpo.contracts import DpoPair
from server.modules.feedback.models import PreferenceLog
from server.modules.feedback.state import (
    get_effective_criterion_corrections_batch,
)
from server.modules.synthesis.models import AgentResult, CriterionScore

logger = logging.getLogger(__name__)


def _parse_json_list(val: Any) -> list[str]:
    if not val:
        return []
    if isinstance(val, (list, tuple)):
        return [str(x) for x in val]
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return []
        try:
            parsed = json.loads(val_str)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
            if isinstance(parsed, str) and parsed:
                return [parsed]
        except Exception:
            return [val_str]
    return []


def _is_real_change(
    edited_score: int | None,
    edited_justification: str | None,
    original_score: CriterionScore,
) -> bool:
    if edited_score is None and edited_justification is None:
        return False
    score = edited_score if edited_score is not None else original_score.score
    justification = (
        edited_justification.strip()
        if edited_justification is not None
        else (original_score.justification or "").strip()
    )
    orig_justification = (original_score.justification or "").strip()
    return not (score == original_score.score and justification == orig_justification)


def export_itso_dpo_pairs(db: Any) -> Iterator[DpoPair]:
    """Yield one DpoPair per evaluation with valid ITSO feedback."""
    candidate_rows = (
        db.query(PreferenceLog.evaluation_id)
        .filter(PreferenceLog.agent_name.ilike("itso"))
        .distinct()
        .all()
    )
    candidate_eval_ids = [row[0] for row in candidate_rows if row[0] is not None]
    if not candidate_eval_ids:
        return

    evaluation_jobs = (
        db.query(EvaluationJob)
        .filter(EvaluationJob.evaluation_id.in_(candidate_eval_ids))
        .all()
    )
    jobs_by_eval = {job.evaluation_id: job for job in evaluation_jobs}

    agent_results = (
        db.query(AgentResult)
        .filter(
            AgentResult.evaluation_id.in_(candidate_eval_ids),
            AgentResult.agent_name.ilike("itso"),
        )
        .all()
    )
    agent_results_by_eval: dict[uuid.UUID, list[AgentResult]] = defaultdict(list)
    for r in agent_results:
        agent_results_by_eval[r.evaluation_id].append(r)

    eligible_agent_results: dict[uuid.UUID, tuple[EvaluationJob, AgentResult]] = {}
    for eval_id in candidate_eval_ids:
        job = jobs_by_eval.get(eval_id)
        if job is None:
            logger.warning(
                "Skipping evaluation %s: missing EvaluationJob row.",
                eval_id,
            )
            continue
        results_for_eval = agent_results_by_eval.get(eval_id, [])
        if len(results_for_eval) == 0:
            logger.warning(
                "Skipping evaluation %s: no ITSO agent_result found.",
                eval_id,
            )
            continue
        if len(results_for_eval) > 1:
            logger.warning(
                "Skipping evaluation %s: found %d duplicate ITSO agent_result "
                "rows; ambiguous pairing.",
                eval_id,
                len(results_for_eval),
            )
            continue
        agent_result = results_for_eval[0]
        if agent_result.document_id != job.document_id:
            logger.warning(
                "Skipping evaluation %s: AgentResult document_id %s "
                "does not match EvaluationJob document_id %s.",
                eval_id,
                agent_result.document_id,
                job.document_id,
            )
            continue
        if not agent_result.prompt_text:
            logger.warning(
                "Skipping evaluation %s: missing prompt_text snapshot (agent_result "
                "missing or predates prompt snapshotting).",
                eval_id,
            )
            continue
        eligible_agent_results[eval_id] = (job, agent_result)

    if not eligible_agent_results:
        return

    selected_result_ids = [
        r.agent_result_id for _, r in eligible_agent_results.values()
    ]
    criterion_scores = (
        db.query(CriterionScore)
        .filter(CriterionScore.agent_result_id.in_(selected_result_ids))
        .all()
    )
    scores_by_result_id: dict[uuid.UUID, list[CriterionScore]] = defaultdict(list)
    for cs in criterion_scores:
        scores_by_result_id[cs.agent_result_id].append(cs)

    corrections_by_eval = get_effective_criterion_corrections_batch(
        db, list(eligible_agent_results.keys()), agent_names=["itso"]
    )

    for eval_id, (job, agent_result) in eligible_agent_results.items():
        scores = scores_by_result_id.get(agent_result.agent_result_id, [])

        lineage_error = False
        seen_cids: set[str] = set()
        for s in scores:
            if (
                s.agent_result_id != agent_result.agent_result_id
                or s.evaluation_id != job.evaluation_id
                or s.document_id != job.document_id
            ):
                logger.warning(
                    "Skipping evaluation %s: CriterionScore %s has mismatched "
                    "lineage (eval=%s, doc=%s, result=%s).",
                    eval_id,
                    s.criterion_score_id,
                    s.evaluation_id,
                    s.document_id,
                    s.agent_result_id,
                )
                lineage_error = True
                break
            cid_key = (s.criterion_id or "").upper()
            if cid_key in seen_cids:
                logger.warning(
                    "Skipping evaluation %s: duplicate CriterionScore for %s.",
                    eval_id,
                    cid_key,
                )
                lineage_error = True
                break
            seen_cids.add(cid_key)

        if lineage_error:
            continue

        orig_by_cid = {s.criterion_id.upper(): s for s in scores if s.criterion_id}
        missing_criteria = [cid for cid in ITSO_CRITERIA if cid not in orig_by_cid]
        if missing_criteria:
            logger.warning(
                "Skipping evaluation %s: missing required ITSO criteria (%s).",
                eval_id,
                missing_criteria,
            )
            continue

        corrections = corrections_by_eval.get(eval_id, {})
        corrections_by_cid = {
            corr.criterion_id.upper(): corr
            for corr in corrections.values()
            if corr.agent_name.lower() == "itso" and corr.criterion_id
        }

        # If any criterion has latest action REJECT, the entire unit is disqualified
        if any(corr.action == "REJECT" for corr in corrections_by_cid.values()):
            logger.warning(
                "Skipping evaluation %s: ITSO unit contains a REJECT action.",
                eval_id,
            )
            continue

        active_edits = {
            cid: corr
            for cid, corr in corrections_by_cid.items()
            if corr.action == "EDIT"
        }
        if not active_edits:
            continue

        real_changes = 0
        for cid, edit in active_edits.items():
            if cid in orig_by_cid and _is_real_change(
                edit.score, edit.justification, orig_by_cid[cid]
            ):
                real_changes += 1

        if real_changes == 0:
            logger.warning(
                "Skipping evaluation %s: no criterion had a real correction "
                "survive (all edits degenerate, empty, or unmatched).",
                eval_id,
            )
            continue

        rejected_criterion_scores = []
        chosen_criterion_scores = []
        reviewer_ids: set[Any] = set()

        for cid in ITSO_CRITERIA:
            orig_score = orig_by_cid[cid]
            chunk_ids = _parse_json_list(orig_score.chunk_ids)
            evidence = _parse_json_list(orig_score.evidence)
            title = orig_score.criterion_title or ITSO_CRITERIA_TITLES[cid]

            rejected_criterion_scores.append(
                {
                    "criterion_id": cid,
                    "criterion_title": title,
                    "score": orig_score.score,
                    "justification": orig_score.justification or "",
                    "chunk_ids": chunk_ids,
                    "evidence": evidence,
                }
            )

            edit = active_edits.get(cid)
            if edit is not None and _is_real_change(
                edit.score, edit.justification, orig_score
            ):
                score = edit.score if edit.score is not None else orig_score.score
                justification = (
                    edit.justification
                    if edit.justification is not None
                    else (orig_score.justification or "")
                )
                if edit.user_id:
                    reviewer_ids.add(edit.user_id)
            else:
                score = orig_score.score
                justification = orig_score.justification or ""

            chosen_criterion_scores.append(
                {
                    "criterion_id": cid,
                    "criterion_title": title,
                    "score": score,
                    "justification": justification,
                    "chunk_ids": chunk_ids,
                    "evidence": evidence,
                }
            )

        rejected_envelope = {
            "summary": agent_result.summary or "",
            "criterion_scores": rejected_criterion_scores,
        }
        chosen_envelope = {
            "summary": agent_result.summary or "",
            "criterion_scores": chosen_criterion_scores,
        }

        rejected_json = json.dumps(rejected_envelope, ensure_ascii=False)
        chosen_json = json.dumps(chosen_envelope, ensure_ascii=False)

        known_chunk_ids = {
            chk
            for orig in orig_by_cid.values()
            for chk in _parse_json_list(orig.chunk_ids)
        }

        try:
            parse_response(rejected_json, known_chunk_ids=known_chunk_ids)
            parse_response(chosen_json, known_chunk_ids=known_chunk_ids)
        except Exception as exc:
            logger.warning(
                "Skipping evaluation %s: failed strict ITSO response validation: %s",
                eval_id,
                exc,
            )
            continue

        yield DpoPair(
            prompt=agent_result.prompt_text,
            chosen=chosen_json,
            rejected=rejected_json,
            evaluation_id=eval_id,
            document_id=job.document_id,
            reviewer_ids=frozenset(reviewer_ids),
        )


__all__ = [
    "export_itso_dpo_pairs",
]
