"""Pure frozen envelope contracts and verifiers for persistable agent results."""

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import dataclass
from typing import Any

from server.modules.agents.contracts import (
    AdvisoryOutput,
    AgentEvaluationResult,
)
from server.modules.agents.contracts import (
    CriterionScore as InputCriterionScore,
)
from server.modules.agents.provenance import sanitize_provenance
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO
from server.modules.synthesis.exceptions import EvaluationResultIntegrityError

ERROR_MESSAGE_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]{0,63} \(reference: [0-9a-f]{16}\)\Z"
)

MAX_CRITERIA_COUNT = 100
MAX_PROCESSING_SECONDS = 86400.0
MAX_TOKEN_COUNT = 10_000_000
MAX_MODEL_NAME_LENGTH = 200
MAX_SUMMARY_LENGTH = 10_000
MAX_ERROR_MESSAGE_LENGTH = 200
MAX_RAW_RESPONSE_BYTES = 128_000
MAX_PROMPT_TEXT_LENGTH = 32_000
MAX_CRITERION_ID_LENGTH = 100
MAX_CRITERION_TITLE_LENGTH = 300
MAX_JUSTIFICATION_LENGTH = 4_000
MAX_EVIDENCE_ITEMS = 100
MAX_EVIDENCE_ITEM_LENGTH = 4_000
MAX_EVIDENCE_JSON_BYTES = 256 * 1024
MAX_CHUNK_ITEMS = 100
MAX_CHUNK_ITEM_LENGTH = 128
MAX_GROUP_PAYLOAD_BYTES = 256 * 1024
MAX_PROVENANCE_BYTES = 64 * 1024
MAX_JSON_DEPTH = 8


def _validate_json_depth_and_types(obj: Any, depth: int = 1) -> None:
    if depth > MAX_JSON_DEPTH:
        raise EvaluationResultIntegrityError("JSON payload depth exceeded")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise EvaluationResultIntegrityError("JSON object keys must be strings")
            _validate_json_depth_and_types(v, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _validate_json_depth_and_types(item, depth + 1)
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        if isinstance(obj, float) and not math.isfinite(obj):
            raise EvaluationResultIntegrityError(
                "Non-finite numbers are not allowed in JSON payloads"
            )
    else:
        raise EvaluationResultIntegrityError("Invalid type in JSON payload")


def _serialize_bounded_json(obj: Any, max_bytes: int, name: str) -> str:
    _validate_json_depth_and_types(obj)
    try:
        encoded_str = json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise EvaluationResultIntegrityError(f"Invalid JSON in {name}") from exc
    if len(encoded_str.encode("utf-8")) > max_bytes:
        raise EvaluationResultIntegrityError(f"{name} JSON size exceeded maximum bytes")
    return encoded_str


def derive_itso_ungrounded_criterion_ids(
    criterion_scores: tuple[PersistableCriterionScore, ...],
    chunk_id_map: dict[str, tuple[str, ...]] | None = None,
) -> set[str]:
    """Derive the deterministic set of ITSO ungrounded criterion IDs.

    A criterion is ungrounded if ANY of:
    - justification is blank / empty
    - evidence is empty / missing
    - chunk_ids are empty / missing (or empty after ownership filtering)
    """
    ungrounded: set[str] = set()
    for score in criterion_scores:
        chunks = (
            chunk_id_map.get(score.criterion_id, ())
            if chunk_id_map is not None
            else score.chunk_ids_raw
        )
        is_evidence_empty = score.evidence_json is None
        is_justification_blank = (
            not score.justification or not score.justification.strip()
        )
        is_chunks_empty = not chunks or len(chunks) == 0

        if is_justification_blank or is_evidence_empty or is_chunks_empty:
            ungrounded.add(score.criterion_id)
    return ungrounded


@dataclass(frozen=True, slots=True)
class PersistableCriterionScore:
    criterion_id: str
    criterion_title: str
    score: int
    justification: str
    evidence_json: str | None
    chunk_ids_raw: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PersistableAgentResult:
    agent_name: str
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    form_snapshot_id: uuid.UUID
    prompt_version_id: uuid.UUID | None
    subtotal: float
    processing_seconds: float
    token_count: int
    model_name: str
    summary: str
    success: bool
    error_message: str | None
    raw_response: str | None
    prompt_text: str | None
    group_prompts_json: str | None
    group_responses_json: str | None
    provenance_json: str | None
    advisory_outputs_json: str | None
    advisory_output_dto: AdvisoryOutput | None
    criterion_scores: tuple[PersistableCriterionScore, ...]


def build_persistable_agent_result(
    result: AgentEvaluationResult,
    snapshot: EvaluationFormSnapshotDTO,
) -> PersistableAgentResult:
    """Validate and build an immutable persistable result envelope."""
    if not isinstance(result, AgentEvaluationResult):
        raise EvaluationResultIntegrityError("Invalid agent result item type")
    if result.agent_name != snapshot.agent_id:
        raise EvaluationResultIntegrityError("Agent result and snapshot mismatch")
    if result.evaluation_id != snapshot.evaluation_id:
        raise EvaluationResultIntegrityError("Agent result evaluation mismatch")

    if isinstance(result.processing_seconds, bool) or not isinstance(
        result.processing_seconds, (int, float)
    ):
        raise EvaluationResultIntegrityError("Invalid processing_seconds type")
    if not math.isfinite(result.processing_seconds) or not (
        0.0 <= float(result.processing_seconds) <= MAX_PROCESSING_SECONDS
    ):
        raise EvaluationResultIntegrityError("processing_seconds out of bounds")

    if isinstance(result.token_count, bool) or not isinstance(result.token_count, int):
        raise EvaluationResultIntegrityError("Invalid token_count type")
    if not (0 <= result.token_count <= MAX_TOKEN_COUNT):
        raise EvaluationResultIntegrityError("token_count out of bounds")

    if (
        not isinstance(result.model_name, str)
        or not result.model_name.strip()
        or len(result.model_name) > MAX_MODEL_NAME_LENGTH
    ):
        raise EvaluationResultIntegrityError("Invalid model_name")

    if not isinstance(result.metadata, dict):
        raise EvaluationResultIntegrityError("metadata must be a dict")

    if result.provenance is not None and not isinstance(result.provenance, dict):
        raise EvaluationResultIntegrityError("provenance must be a dict or None")
    if not isinstance(result.criterion_scores, tuple):
        raise EvaluationResultIntegrityError("criterion_scores must be a tuple")

    sanitized_prov = sanitize_provenance(result.provenance)
    prov_json = (
        _serialize_bounded_json(sanitized_prov, MAX_PROVENANCE_BYTES, "provenance")
        if sanitized_prov is not None
        else None
    )

    if not result.success:
        if (
            result.metadata.get("group_prompts") is not None
            or result.metadata.get("group_responses") is not None
        ):
            raise EvaluationResultIntegrityError(
                "Failed result must not contain group payloads"
            )
        if result.subtotal != 0:
            raise EvaluationResultIntegrityError("Failed result subtotal must be 0")
        if len(result.criterion_scores) != 0:
            raise EvaluationResultIntegrityError(
                "Failed agent result must not contain criterion scores"
            )
        if result.summary != "":
            raise EvaluationResultIntegrityError("Failed result summary must be empty")
        if result.token_count != 0:
            raise EvaluationResultIntegrityError("Failed result token_count must be 0")
        if (
            result.raw_response is not None
            or result.prompt_text is not None
            or result.advisory_outputs is not None
        ):
            raise EvaluationResultIntegrityError(
                "Failed result must not contain raw response, prompt text, or advisory"
            )
        if (
            not isinstance(result.error_message, str)
            or len(result.error_message) > MAX_ERROR_MESSAGE_LENGTH
            or not ERROR_MESSAGE_PATTERN.match(result.error_message)
        ):
            raise EvaluationResultIntegrityError("Invalid failure error_message format")

        return PersistableAgentResult(
            agent_name=result.agent_name,
            evaluation_id=result.evaluation_id,
            document_id=result.document_id,
            form_snapshot_id=snapshot.snapshot_id,
            prompt_version_id=result.prompt_version_id,
            subtotal=0.0,
            processing_seconds=float(result.processing_seconds),
            token_count=0,
            model_name=result.model_name,
            summary="",
            success=False,
            error_message=result.error_message,
            raw_response=None,
            prompt_text=None,
            group_prompts_json=None,
            group_responses_json=None,
            provenance_json=prov_json,
            advisory_outputs_json=None,
            advisory_output_dto=None,
            criterion_scores=(),
        )

    # Success validations
    if result.error_message is not None:
        raise EvaluationResultIntegrityError(
            "Successful result cannot have error_message"
        )

    if result.agent_name == "itso":
        if result.raw_response is not None or result.prompt_text is not None:
            raise EvaluationResultIntegrityError(
                "Successful ITSO result must not contain raw_response or prompt_text"
            )

    if not isinstance(result.summary, str) or len(result.summary) > MAX_SUMMARY_LENGTH:
        raise EvaluationResultIntegrityError("Invalid summary length")

    raw_resp = result.raw_response
    if raw_resp is not None:
        if (
            not isinstance(raw_resp, str)
            or len(raw_resp.encode("utf-8")) > MAX_RAW_RESPONSE_BYTES
        ):
            raise EvaluationResultIntegrityError("raw_response exceeded maximum bytes")

    prompt_txt = result.prompt_text
    if prompt_txt is not None:
        if not isinstance(prompt_txt, str) or len(prompt_txt) > MAX_PROMPT_TEXT_LENGTH:
            raise EvaluationResultIntegrityError("prompt_text exceeded maximum length")

    group_prompts = result.metadata.get("group_prompts")
    if group_prompts is not None and not isinstance(group_prompts, dict):
        raise EvaluationResultIntegrityError("group_prompts must be a dict or None")
    gp_json = (
        _serialize_bounded_json(group_prompts, MAX_GROUP_PAYLOAD_BYTES, "group_prompts")
        if group_prompts is not None
        else None
    )

    group_responses = result.metadata.get("group_responses")
    if group_responses is not None and not isinstance(group_responses, dict):
        raise EvaluationResultIntegrityError("group_responses must be a dict or None")
    gr_json = (
        _serialize_bounded_json(
            group_responses, MAX_GROUP_PAYLOAD_BYTES, "group_responses"
        )
        if group_responses is not None
        else None
    )

    combined_group_bytes = (len(gp_json.encode("utf-8")) if gp_json else 0) + (
        len(gr_json.encode("utf-8")) if gr_json else 0
    )
    if combined_group_bytes > MAX_GROUP_PAYLOAD_BYTES:
        raise EvaluationResultIntegrityError("Combined group payload size exceeded")

    if result.agent_name != "itso" and result.advisory_outputs is not None:
        raise EvaluationResultIntegrityError(
            "Non-ITSO agents must not have advisory_outputs"
        )

    claimed_advisory_cids: set[str] = set()
    if result.agent_name == "itso" and result.advisory_outputs is not None:
        if not isinstance(result.advisory_outputs, AdvisoryOutput):
            raise EvaluationResultIntegrityError(
                "advisory_outputs must be AdvisoryOutput or None"
            )
        adv_dto = result.advisory_outputs
        if len(adv_dto.ungrounded_criteria) > len(snapshot.criterion_codes):
            raise EvaluationResultIntegrityError(
                "Advisory criteria count exceeds snapshot criterion count"
            )
        for u in adv_dto.ungrounded_criteria:
            if u.criterion_id not in snapshot.criterion_codes_set:
                raise EvaluationResultIntegrityError(
                    "Unknown criterion in advisory outputs"
                )
        claimed_advisory_cids = {u.criterion_id for u in adv_dto.ungrounded_criteria}
        if len(claimed_advisory_cids) != len(adv_dto.ungrounded_criteria):
            raise EvaluationResultIntegrityError(
                "Duplicate criterion in advisory outputs"
            )
        adv_json = _serialize_bounded_json(
            adv_dto.to_dict(), MAX_GROUP_PAYLOAD_BYTES, "advisory_outputs"
        )
    else:
        adv_dto = None
        adv_json = None

    if len(result.criterion_scores) > MAX_CRITERIA_COUNT:
        raise EvaluationResultIntegrityError("criterion_scores exceeded maximum count")

    for score in result.criterion_scores:
        if not isinstance(score, InputCriterionScore):
            raise EvaluationResultIntegrityError("Invalid criterion score item type")
        if (
            not isinstance(score.criterion_id, str)
            or score.criterion_id != score.criterion_id.strip()
            or not score.criterion_id
            or len(score.criterion_id) > MAX_CRITERION_ID_LENGTH
        ):
            raise EvaluationResultIntegrityError("Invalid criterion_id")

    snapshot_criteria_map = {
        c.criterion_code: c.title
        for domain in snapshot.form.domains
        for c in domain.criteria
    }

    returned_codes = [s.criterion_id for s in result.criterion_scores]
    if len(returned_codes) != len(set(returned_codes)):
        raise EvaluationResultIntegrityError("Duplicate criterion code in agent result")
    if set(returned_codes) != snapshot.criterion_codes_set:
        raise EvaluationResultIntegrityError(
            "Criterion code set mismatch against snapshot"
        )

    if adv_dto is not None:
        for u in adv_dto.ungrounded_criteria:
            if u.criterion_id not in set(returned_codes):
                raise EvaluationResultIntegrityError(
                    "Advisory criterion not found in returned scores"
                )

    scores_out: list[PersistableCriterionScore] = []
    total_score = 0
    total_evidence_bytes = 0
    for score in result.criterion_scores:
        if (
            isinstance(score.score, bool)
            or not isinstance(score.score, int)
            or not (1 <= score.score <= 4)
        ):
            raise EvaluationResultIntegrityError("criterion score out of bounds")

        is_claimed_ungrounded_itso = (
            result.agent_name == "itso" and score.criterion_id in claimed_advisory_cids
        )
        if is_claimed_ungrounded_itso:
            if not isinstance(score.justification, str):
                raise EvaluationResultIntegrityError(
                    "Invalid criterion justification type"
                )
            if (
                score.justification
                and score.justification != score.justification.strip()
            ):
                raise EvaluationResultIntegrityError(
                    "Criterion justification contains untrimmed whitespace"
                )
            if len(score.justification) > MAX_JUSTIFICATION_LENGTH:
                raise EvaluationResultIntegrityError(
                    "Invalid criterion justification length"
                )
        else:
            if (
                not isinstance(score.justification, str)
                or not score.justification.strip()
                or score.justification != score.justification.strip()
                or len(score.justification) > MAX_JUSTIFICATION_LENGTH
            ):
                raise EvaluationResultIntegrityError("Invalid criterion justification")

        snapshot_title = snapshot_criteria_map[score.criterion_id]
        if len(snapshot_title) > MAX_CRITERION_TITLE_LENGTH:
            raise EvaluationResultIntegrityError(
                "Snapshot title exceeded maximum length"
            )

        if score.evidence is None:
            ev_json = None
        else:
            if not isinstance(score.evidence, tuple):
                raise EvaluationResultIntegrityError("evidence must be a tuple")
            if len(score.evidence) > MAX_EVIDENCE_ITEMS:
                raise EvaluationResultIntegrityError(
                    "evidence items exceeded maximum count"
                )
            for ev in score.evidence:
                if (
                    not isinstance(ev, str)
                    or not ev.strip()
                    or len(ev) > MAX_EVIDENCE_ITEM_LENGTH
                ):
                    raise EvaluationResultIntegrityError("Invalid evidence item")
            if score.evidence:
                ev_json = _serialize_bounded_json(
                    list(score.evidence), MAX_EVIDENCE_JSON_BYTES, "evidence"
                )
                total_evidence_bytes += len(ev_json.encode("utf-8"))
            else:
                ev_json = None

        if score.chunk_ids is None:
            c_raw = ()
        else:
            if not isinstance(score.chunk_ids, tuple):
                raise EvaluationResultIntegrityError("chunk_ids must be a tuple")
            if len(score.chunk_ids) > MAX_CHUNK_ITEMS:
                raise EvaluationResultIntegrityError("chunk_ids exceeded maximum count")
            for cid in score.chunk_ids:
                if (
                    not isinstance(cid, str)
                    or not cid
                    or cid != cid.strip()
                    or len(cid) > MAX_CHUNK_ITEM_LENGTH
                ):
                    raise EvaluationResultIntegrityError("Invalid chunk_id")
            c_raw = tuple(str(cid) for cid in score.chunk_ids)

        scores_out.append(
            PersistableCriterionScore(
                criterion_id=score.criterion_id,
                criterion_title=snapshot_title,
                score=score.score,
                justification=score.justification,
                evidence_json=ev_json,
                chunk_ids_raw=c_raw,
            )
        )
        total_score += score.score

    if total_evidence_bytes > MAX_EVIDENCE_JSON_BYTES:
        raise EvaluationResultIntegrityError(
            "Aggregate evidence JSON exceeded maximum bytes"
        )

    derived_subtotal = total_score / len(scores_out) if scores_out else 0.0
    if (
        isinstance(result.subtotal, bool)
        or not isinstance(result.subtotal, (int, float))
        or not math.isfinite(result.subtotal)
    ):
        raise EvaluationResultIntegrityError("Invalid subtotal value")
    if not math.isclose(result.subtotal, derived_subtotal, rel_tol=1e-5, abs_tol=1e-5):
        raise EvaluationResultIntegrityError("Subtotal mismatch against derived mean")

    if result.agent_name == "itso":
        derived_itso_ungrounded = derive_itso_ungrounded_criterion_ids(
            tuple(scores_out)
        )
        if derived_itso_ungrounded != claimed_advisory_cids:
            raise EvaluationResultIntegrityError(
                "ITSO advisory criteria mismatch against derived ungrounded set"
            )

    return PersistableAgentResult(
        agent_name=result.agent_name,
        evaluation_id=result.evaluation_id,
        document_id=result.document_id,
        form_snapshot_id=snapshot.snapshot_id,
        prompt_version_id=result.prompt_version_id,
        subtotal=derived_subtotal,
        processing_seconds=float(result.processing_seconds),
        token_count=result.token_count,
        model_name=result.model_name,
        summary=result.summary,
        success=True,
        error_message=None,
        raw_response=raw_resp,
        prompt_text=prompt_txt,
        group_prompts_json=gp_json,
        group_responses_json=gr_json,
        provenance_json=prov_json,
        advisory_outputs_json=adv_json,
        advisory_output_dto=adv_dto,
        criterion_scores=tuple(scores_out),
    )


__all__ = [
    "PersistableCriterionScore",
    "PersistableAgentResult",
    "build_persistable_agent_result",
    "derive_itso_ungrounded_criterion_ids",
]
