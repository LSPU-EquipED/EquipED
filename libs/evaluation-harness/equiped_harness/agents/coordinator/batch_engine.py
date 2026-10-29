"""Two model-authored report batches over the proven Coordinator measurements."""

from __future__ import annotations

from equiped_harness.agents.coordinator import batch_findings
from equiped_harness.agents.coordinator.narrative_contract import measurement_projection
from equiped_harness.agents.coordinator.task_execution import _parse_json
from equiped_harness.agents.coordinator.unit_prompts import extraction_prompt
from equiped_harness.agents.coordinator.unit_validation import (
    validate_unit_coordinator_bundle,
)

CONTRACT = "coordinator_current.v5"


def _narrative_map(scores):
    return {
        **{
            s.criterion_id: batch_findings.ORGANIZATION_KEY
            if s.criterion_id.startswith("OP-")
            else batch_findings.ASSESSMENT_KEY
            for s in scores
        },
        "C-01": batch_findings.ASSESSMENT_KEY,
        "summary": batch_findings.ASSESSMENT_KEY,
    }


def validate_batch_bundle(result, snapshot=None):
    """Validate unchanged measurements, then bind both final model responses."""
    metadata = result.metadata
    if not isinstance(metadata, dict) or metadata.get("execution_contract") != CONTRACT:
        raise ValueError("Coordinator batch execution marker is invalid")
    bundle = metadata.get("current_bundle")
    if not isinstance(bundle, dict) or bundle.get("contract") != CONTRACT:
        raise ValueError("Coordinator batch bundle marker is invalid")
    units = _narrative_map(result.criterion_scores)
    if bundle.get("narrative_units") != units:
        raise ValueError("Coordinator narrative task inventory is invalid")
    responses, statuses = (
        metadata.get("group_responses"),
        metadata.get("envelope_status"),
    )
    if (
        not isinstance(responses, dict)
        or responses.get("__current_bundle__") != bundle
        or not isinstance(statuses, dict)
    ):
        raise ValueError("Coordinator narrative response history is invalid")
    for history in (responses, statuses):
        if {key for key in history if key.startswith("findings-")} != set(
            batch_findings.FINAL_KEYS
        ):
            raise ValueError("Coordinator batch response inventory is invalid")
    captures = {g.unit_key: g for g in result.generations}
    expected = {
        key
        for key, response in responses.items()
        if key != "__current_bundle__"
        and not (isinstance(response, dict) and set(response) == {"bundle_criterion"})
    }
    if result.generations and (
        len(captures) != len(result.generations) or set(captures) != expected
    ):
        raise ValueError("Coordinator captured generation history is incomplete")
    score_by_code = {s.criterion_id: s.score for s in result.criterion_scores}
    score_by_code["C-01"] = result.advisory_outputs.score
    findings = {}
    for key, ids in zip(
        batch_findings.FINAL_KEYS,
        (batch_findings.ORGANIZATION_IDS, batch_findings.ASSESSMENT_IDS),
        strict=True,
    ):
        final = key == batch_findings.ASSESSMENT_KEY
        status = statuses.get(key)
        if status not in {"ok", "repaired", "fallback"}:
            raise ValueError("Coordinator narrative status is invalid")
        response = batch_findings.validate_response(
            responses.get(key),
            ids,
            score_by_code,
            summary=final,
            fallback=status == "fallback",
        )
        findings.update(
            {row["criterion_id"]: row["finding"] for row in response["results"]}
        )
        if final and result.summary != response["summary"]:
            raise ValueError("Coordinator summary differs from model response")
        capture = captures.get(key)
        if capture:
            expected_ids = (
                tuple(s.criterion_id for s in result.criterion_scores) if final else ids
            )
            if (
                capture.response_json != response
                or capture.envelope_status != status
                or capture.criterion_ids != expected_ids
                or capture.response_contract_key != batch_findings.BATCH_CONTRACT
                or capture.response_contract_version != 1
            ):
                raise ValueError("Coordinator narrative capture identity is invalid")
            if (
                status != "fallback"
                and _parse_json(capture.response_text, include_summary=final)
                != response
            ):
                raise ValueError("Coordinator narrative differs from raw model wording")
    if any(
        s.justification != findings[s.criterion_id] for s in result.criterion_scores
    ):
        raise ValueError("Coordinator findings differ from model response")
    if result.advisory_outputs.justification != findings["C-01"]:
        raise ValueError("Coordinator advisory differs from model response")
    for key, response in responses.items():
        if isinstance(response, dict) and set(response) == {"bundle_criterion"}:
            code = response["bundle_criterion"]
            expected_status = (
                "fallback" if statuses[units[code]] == "fallback" else "ok"
            )
            if statuses.get(key) != expected_status:
                raise ValueError("Coordinator logical narrative status is invalid")
    validate_unit_coordinator_bundle(
        measurement_projection(result), snapshot, prompt_factory=extraction_prompt
    )
