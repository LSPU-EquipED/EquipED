"""Model-authored Coordinator reporting over independently validated measurements.

The v3 projection is an integrity check, never a displayed finding. It preserves
historical score and evidence validation without duplicating that implementation.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

from equiped_harness.agents.coordinator.model_findings import (
    FINDING_CONTRACT,
    SUMMARY_CONTRACT,
    SUMMARY_UNIT_KEY,
    finding_unit_key,
    validate_finding_response,
    validate_summary_response,
)
from equiped_harness.agents.coordinator.unit_reporting import (
    build_unit_summary,
    render_unit_justification,
)
from equiped_harness.contracts.results import AgentEvaluationResult

CONTRACT = "coordinator_current.v4"
_MEASUREMENT_CONTRACT = "coordinator_current.v3"


def measurement_projection(result: AgentEvaluationResult) -> AgentEvaluationResult:
    """Recover the v3 measurement view for the existing independent validator."""
    metadata = copy.deepcopy(result.metadata)
    bundle = metadata["current_bundle"]
    units = bundle.pop("narrative_units")
    bundle["contract"] = _MEASUREMENT_CONTRACT
    metadata["execution_contract"] = _MEASUREMENT_CONTRACT
    responses = metadata["group_responses"]
    statuses = metadata["envelope_status"]
    for key in units.values():
        responses.pop(key, None)
        statuses.pop(key, None)
    responses["__current_bundle__"] = bundle
    for key, response in responses.items():
        if isinstance(response, dict) and set(response) == {"bundle_criterion"}:
            code = response["bundle_criterion"]
            statuses[key] = (
                "ok" if bundle["reasoning_status"][code] == "complete" else "fallback"
            )
    explanations = bundle["explanations"]
    scores = tuple(
        replace(
            score,
            justification=render_unit_justification(
                explanations[score.criterion_id],
                bundle["objective"]
                if score.criterion_id == "A-05"
                else bundle["criteria"][score.criterion_id],
                score.score,
                kind="objective" if score.criterion_id == "A-05" else None,
            ),
        )
        for score in result.criterion_scores
    )
    return replace(
        result,
        criterion_scores=scores,
        summary=build_unit_summary(
            list(scores), explanations, bundle["reasoning_status"]
        ),
        advisory_outputs=result.advisory_outputs.model_copy(
            update={
                "justification": render_unit_justification(
                    explanations["C-01"],
                    bundle["curriculum"],
                    result.advisory_outputs.score,
                    kind="curriculum",
                )
            }
        ),
        metadata=metadata,
        generations=tuple(
            g for g in result.generations if g.unit_key not in units.values()
        ),
    )


def validate_narrative_bundle(
    result: AgentEvaluationResult, snapshot: Any | None = None
) -> None:
    """Bind displayed prose to captured model responses and frozen score facts."""
    from equiped_harness.agents.coordinator.unit_prompts import extraction_prompt
    from equiped_harness.agents.coordinator.unit_validation import (
        validate_unit_coordinator_bundle,
    )

    metadata = result.metadata
    if not isinstance(metadata, dict) or metadata.get("execution_contract") != CONTRACT:
        raise ValueError("Coordinator narrative execution marker is invalid")
    bundle = metadata.get("current_bundle")
    if not isinstance(bundle, dict) or bundle.get("contract") != CONTRACT:
        raise ValueError("Coordinator narrative bundle marker is invalid")
    units = bundle.get("narrative_units")
    codes = [score.criterion_id for score in result.criterion_scores] + ["C-01"]
    expected = {code: finding_unit_key(code) for code in codes}
    expected["summary"] = SUMMARY_UNIT_KEY
    if units != expected:
        raise ValueError("Coordinator narrative task inventory is invalid")
    responses = metadata.get("group_responses")
    statuses = metadata.get("envelope_status")
    if (
        not isinstance(responses, dict)
        or responses.get("__current_bundle__") != bundle
        or not isinstance(statuses, dict)
    ):
        raise ValueError("Coordinator narrative response history is invalid")
    for history in (responses, statuses):
        if {key for key in history if key.startswith("finding-")} != set(
            units.values()
        ):
            raise ValueError("Coordinator narrative response inventory is invalid")
    generations = {generation.unit_key: generation for generation in result.generations}
    if len(generations) != len(result.generations):
        raise ValueError("Coordinator narrative generations are duplicated")
    if generations:
        expected_captures = {
            key
            for key, response in responses.items()
            if key != "__current_bundle__"
            and not (
                isinstance(response, dict) and set(response) == {"bundle_criterion"}
            )
        }
        if set(generations) != expected_captures:
            raise ValueError("Coordinator captured generation history is incomplete")
    for code, key in units.items():
        status = statuses.get(key)
        if status not in {"ok", "repaired", "fallback"}:
            raise ValueError("Coordinator narrative response status is invalid")
        response = responses.get(key)
        if code == "summary":
            validate_summary_response(response, fallback=status == "fallback")
            text = response["results"][0]["summary"]
            expected_text, contract, criterion_ids = (
                result.summary,
                SUMMARY_CONTRACT,
                tuple(score.criterion_id for score in result.criterion_scores),
            )
        else:
            score = (
                result.advisory_outputs
                if code == "C-01"
                else next(
                    score
                    for score in result.criterion_scores
                    if score.criterion_id == code
                )
            )
            validate_finding_response(
                response, code, score.score, fallback=status == "fallback"
            )
            text = response["results"][0]["finding"]
            expected_text, contract, criterion_ids = (
                score.justification,
                FINDING_CONTRACT,
                ("A-05",) if code == "C-01" else (code,),
            )
        if text != expected_text:
            raise ValueError("Coordinator finding differs from its model response")
        captured = generations.get(key)
        if result.generations and (
            captured is None
            or captured.response_json != response
            or captured.envelope_status != status
            or captured.response_contract_key != contract
            or captured.response_contract_version != 1
            or captured.criterion_ids != criterion_ids
        ):
            raise ValueError("Coordinator finding differs from its captured generation")
        if captured is not None and status != "fallback":
            from equiped_harness.agents.coordinator.task_execution import _parse_json

            if _parse_json(captured.response_text) != response:
                raise ValueError(
                    "Coordinator finding differs from the model's raw text"
                )
    for key, response in responses.items():
        if isinstance(response, dict) and set(response) == {"bundle_criterion"}:
            code = response["bundle_criterion"]
            if code not in expected or code == "summary":
                raise ValueError("Coordinator logical criterion reference is invalid")
            expected_status = (
                "ok"
                if bundle["reasoning_status"][code] == "complete"
                and statuses[units[code]] != "fallback"
                else "fallback"
            )
            if statuses.get(key) != expected_status:
                raise ValueError("Coordinator finding limitation status was tampered")
    validate_unit_coordinator_bundle(
        measurement_projection(result), snapshot, prompt_factory=extraction_prompt
    )
