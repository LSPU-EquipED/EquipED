"""SME DPO training pair projection logic."""

from __future__ import annotations

import copy
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

from server.modules.agents.sme.group_response import parse_group_response
from server.modules.agents.sme.groups import CODE_TO_GROUP, GROUP_CODES
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.dpo.contracts import DpoPair
from server.modules.feedback.models import PreferenceLog
from server.modules.feedback.state import (
    EffectiveCriterionCorrection,
    get_effective_criterion_corrections_batch,
)
from server.modules.synthesis.models import AgentResult, CriterionScore

logger = logging.getLogger(__name__)


def _is_real_change(
    correction: EffectiveCriterionCorrection, original_score: CriterionScore
) -> bool:
    if correction.action != "EDIT":
        return False
    if correction.score is None and correction.justification is None:
        return False
    score = correction.score if correction.score is not None else original_score.score
    justification = (
        correction.justification.strip()
        if correction.justification is not None
        else (original_score.justification or "").strip()
    )
    orig_justification = (original_score.justification or "").strip()
    return not (score == original_score.score and justification == orig_justification)


def export_sme_dpo_pairs(db: Any) -> Iterator[DpoPair]:
    """Yield one DpoPair per successful grouped unit with valid SME feedback."""
    candidate_rows = (
        db.query(PreferenceLog.evaluation_id)
        .filter(PreferenceLog.agent_name.ilike("sme"))
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
            AgentResult.agent_name.ilike("sme"),
        )
        .all()
    )

    results_by_eval: dict[uuid.UUID, list[AgentResult]] = defaultdict(list)
    for result in agent_results:
        results_by_eval[result.evaluation_id].append(result)

    eligible_agent_results: dict[uuid.UUID, tuple[EvaluationJob, AgentResult]] = {}
    for eval_id in candidate_eval_ids:
        job = jobs_by_eval.get(eval_id)
        if job is None:
            logger.warning("Skipping evaluation %s: missing EvaluationJob row", eval_id)
            continue

        results = results_by_eval.get(eval_id, [])
        if len(results) != 1:
            logger.warning(
                "Skipping evaluation %s: expected exactly 1 SME AgentResult, found %d",
                eval_id,
                len(results),
            )
            continue

        agent_result = results[0]
        if agent_result.document_id != job.document_id:
            logger.warning(
                "Skipping evaluation %s: AgentResult document_id %s "
                "does not match EvaluationJob document_id %s",
                eval_id,
                agent_result.document_id,
                job.document_id,
            )
            continue

        if not agent_result.group_prompts or not agent_result.group_responses:
            logger.warning(
                "Skipping evaluation %s: missing group_prompts or group_responses",
                eval_id,
            )
            continue

        eligible_agent_results[eval_id] = (job, agent_result)

    if not eligible_agent_results:
        return

    selected_result_ids = [
        agent_result.agent_result_id
        for _, agent_result in eligible_agent_results.values()
    ]
    criterion_score_rows = (
        db.query(CriterionScore)
        .filter(CriterionScore.agent_result_id.in_(selected_result_ids))
        .all()
    )
    scores_by_result_id: dict[uuid.UUID, list[CriterionScore]] = defaultdict(list)
    for cs in criterion_score_rows:
        scores_by_result_id[cs.agent_result_id].append(cs)

    corrections_by_eval = get_effective_criterion_corrections_batch(
        db, list(eligible_agent_results.keys()), agent_names=["sme"]
    )

    for eval_id, (job, agent_result) in eligible_agent_results.items():
        scores = scores_by_result_id.get(agent_result.agent_result_id, [])

        lineage_error = False
        seen_codes: set[str] = set()
        for score in scores:
            if (
                score.agent_result_id != agent_result.agent_result_id
                or score.evaluation_id != job.evaluation_id
                or score.document_id != job.document_id
            ):
                logger.warning(
                    "Skipping evaluation %s: CriterionScore %s has mismatched "
                    "lineage (eval=%s, doc=%s, result=%s)",
                    eval_id,
                    score.criterion_score_id,
                    score.evaluation_id,
                    score.document_id,
                    score.agent_result_id,
                )
                lineage_error = True
                break
            if score.criterion_id in seen_codes:
                logger.warning(
                    "Skipping evaluation %s: duplicate CriterionScore for criterion %s",
                    eval_id,
                    score.criterion_id,
                )
                lineage_error = True
                break
            seen_codes.add(score.criterion_id)

        if lineage_error:
            continue

        scores_by_code: dict[str, CriterionScore] = {
            score.criterion_id: score for score in scores
        }
        titles_by_code: dict[str, str] = {
            score.criterion_id: score.criterion_title for score in scores
        }

        effective_corrections = corrections_by_eval.get(eval_id, {})

        corrections_by_group: dict[str, dict[str, EffectiveCriterionCorrection]] = (
            defaultdict(dict)
        )
        for (agent_name, criterion_id), correction in effective_corrections.items():
            group = CODE_TO_GROUP.get(criterion_id)
            if group is None:
                continue
            corrections_by_group[group][criterion_id] = correction

        for group, group_codes in GROUP_CODES.items():
            group_prompt = agent_result.group_prompts.get(group)
            group_response = agent_result.group_responses.get(group)
            if not group_prompt or not group_response:
                continue

            if any(code not in scores_by_code for code in group_codes):
                logger.warning(
                    "Skipping evaluation %s group %s: missing CriterionScore rows",
                    eval_id,
                    group,
                )
                continue

            group_titles = {code: titles_by_code[code] for code in group_codes}

            group_corr = corrections_by_group.get(group, {})

            # Rule: if any criterion in group has effective REJECT, skip group
            if any(corr.action == "REJECT" for corr in group_corr.values()):
                logger.warning(
                    "Skipping evaluation %s group %s: group has an active REJECT",
                    eval_id,
                    group,
                )
                continue

            # Validate rejected snapshot through strict parser
            try:
                rejected_str = json.dumps(group_response, ensure_ascii=False)
                parsed_rejected = parse_group_response(
                    rejected_str, group_codes, group_titles
                )
            except Exception as exc:
                logger.warning(
                    "Skipping evaluation %s group %s: rejected parse failed (%s)",
                    eval_id,
                    group,
                    exc,
                )
                continue

            # Build chosen by substituting only corrected score/justification
            chosen_data = copy.deepcopy(parsed_rejected)
            real_change_count = 0
            reviewer_ids: set[uuid.UUID] = set()

            for item in chosen_data.get("criterion_scores", []):
                cid = item.get("criterion_id")
                if cid in group_corr:
                    corr = group_corr[cid]
                    score_row = scores_by_code[cid]
                    if _is_real_change(corr, score_row):
                        if corr.score is not None:
                            item["score"] = corr.score
                        if corr.justification is not None:
                            item["justification"] = corr.justification
                        real_change_count += 1
                        if corr.user_id:
                            reviewer_ids.add(corr.user_id)

            if real_change_count == 0:
                continue

            try:
                chosen_str = json.dumps(chosen_data, ensure_ascii=False)
                parse_group_response(chosen_str, group_codes, group_titles)
            except Exception as exc:
                logger.warning(
                    "Skipping evaluation %s group %s: chosen parse failed (%s)",
                    eval_id,
                    group,
                    exc,
                )
                continue

            yield DpoPair(
                prompt=group_prompt,
                chosen=chosen_str,
                rejected=rejected_str,
                evaluation_id=eval_id,
                document_id=job.document_id,
                reviewer_ids=frozenset(reviewer_ids),
            )


__all__ = ["export_sme_dpo_pairs"]
