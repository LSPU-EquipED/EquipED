"""Stateless ITSO execution pipeline."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from server.core.config import get_settings
from server.core.llm import ResponseContract, get_llm_client, get_llm_model_name
from server.modules.rubrics.contracts import (
    CriterionDefinition,
    GroundedScoreMeasurement,
    LlmRubricGuidanceConfig,
)
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO
from server.modules.rubrics.strategies.calculators import normalize_llm_guidance_score

from ..contracts import AgentEvaluationResult
from ..exceptions import AgentExecutionError, AgentLLMError
from ..provenance import sanitize_provenance
from ..runtime.context import ITSOExecutionContext, thaw
from ..runtime.llm import RunLLMClient
from ..runtime.prompt_budget import enforce_total_prompt_budget
from ..runtime.timing import PhaseTimer
from .prompt import build_prompt, pack_itso_chunks
from .response import (
    ITSO_RESPONSE_SCHEMA_VERSION,
    build_response_schema,
    collect_advisory_outputs,
    criterion_scores,
    parse_response,
)

logger = logging.getLogger(__name__)


def _extract_and_validate_snapshot(
    context: ITSOExecutionContext,
) -> tuple[tuple[CriterionDefinition, ...], tuple[str, ...], dict[str, str]]:
    """Validate snapshot form bounds and return ordered criteria, codes, titles."""
    snapshot = context.form_snapshot
    if not isinstance(snapshot, EvaluationFormSnapshotDTO):
        raise AgentExecutionError(
            "ITSO requires an EvaluationFormSnapshotDTO instance, "
            f"got {type(snapshot).__name__}"
        )

    if snapshot.agent_id != "itso" or snapshot.evaluation_id != context.evaluation_id:
        raise AgentExecutionError(
            f"ITSO snapshot mismatch: agent_id={snapshot.agent_id!r}, "
            f"evaluation_id={snapshot.evaluation_id!r} "
            f"(expected eval={context.evaluation_id!r})"
        )

    if snapshot.adapter_key != "itso" or snapshot.adapter_version != 1:
        raise AgentExecutionError(
            f"ITSO snapshot adapter mismatch: adapter_key={snapshot.adapter_key!r}, "
            f"adapter_version={snapshot.adapter_version!r} (expected 'itso', 1)"
        )

    ordered_criteria: list[CriterionDefinition] = []
    for domain in snapshot.form.domains:
        for criterion in domain.criteria:
            if not isinstance(criterion.strategy_config, LlmRubricGuidanceConfig):
                raise AgentExecutionError(
                    f"ITSO criterion '{criterion.criterion_code}' has unsupported "
                    f"strategy '{criterion.strategy_config.strategy}' "
                    "(expected 'llm_rubric_guidance')"
                )
            ordered_criteria.append(criterion)

    if not ordered_criteria:
        raise AgentExecutionError("ITSO snapshot contains no criteria")
    if len(ordered_criteria) > 10:
        raise AgentExecutionError("ITSO snapshot exceeds 10 criteria")

    casefolded_codes = [c.criterion_code.casefold() for c in ordered_criteria]
    if len(casefolded_codes) != len(set(casefolded_codes)):
        raise AgentExecutionError(
            "ITSO snapshot contains case-insensitive duplicate criterion codes"
        )

    criteria_tuple = tuple(ordered_criteria)
    expected_ids = tuple(c.criterion_code for c in ordered_criteria)
    expected_titles = {c.criterion_code: c.title for c in ordered_criteria}
    return criteria_tuple, expected_ids, expected_titles


def execute(
    context: ITSOExecutionContext,
    *,
    llm_client: Any | None = None,
    llm_temperature: float | None = None,
) -> AgentEvaluationResult:
    if not context.chunk_infos or not any(
        dict(chunk).get("text") for chunk in context.chunk_infos
    ):
        raise AgentExecutionError("document chunks are required for evaluation")

    # Fail boundedly before LLM call on missing/wrong snapshot
    ordered_criteria, expected_ids, expected_titles = _extract_and_validate_snapshot(
        context
    )
    criteria_specs = tuple((c.criterion_code, c.title) for c in ordered_criteria)

    start = time.perf_counter()
    timer = PhaseTimer("itso")
    texts = [
        str(dict(chunk).get("text", ""))
        for chunk in context.chunk_infos
        if dict(chunk).get("text")
    ]
    settings = get_settings()
    with timer.measure("retrieval"):
        references = _references(context)
    with timer.measure("prompt_build"):
        packed_chunks, packed_chunk_map, dropped, excerpted = pack_itso_chunks(
            context.chunk_infos,
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=settings.agent_prompt_budget_chars,
            small_doc_threshold=settings.agent_small_doc_threshold,
            domain_keywords=context.domain_keywords,
        )
        packed_chunk_ids = tuple(packed_chunk_map.keys())
        prompt = build_prompt(
            context,
            ordered_criteria=list(ordered_criteria),
            reference_context=references,
            packed_chunks=packed_chunks,
            dropped=dropped,
            excerpted=excerpted,
        )
    # Reserve a bounded, sanitized repair suffix before packing the first request.
    repair_suffix = (
        "\n\nVALIDATOR_FAILURE category=ITSO_INVALID path=criterion_scores. "
        "Regenerate ONLY the complete JSON response; do not include commentary."
    )
    total_budget = settings.agent_total_prompt_budget_chars
    initial_budget = total_budget - len(repair_suffix)
    if initial_budget < 0:
        raise AgentExecutionError("ITSO prompt budget cannot reserve repair suffix")
    budget = enforce_total_prompt_budget(
        prompt, budget_chars=initial_budget, agent_name="itso"
    )
    prompt = budget.prompt
    if len(prompt) + len(repair_suffix) > total_budget:
        raise AgentExecutionError("ITSO prompt exceeds total budget before transport")
    prompt_chars = len(prompt)
    logger.info(
        "[EVAL_PROMPT_SIZE] agent=itso | prompt_chars=%d | trimmed=%s | "
        "budget=%d | rubric_context=0 | reference_context=%d | "
        "prompt_version_id=%s",
        prompt_chars,
        "yes" if budget.trimmed else "no",
        settings.agent_total_prompt_budget_chars,
        len(references),
        str(context.prompt_version_id) if context.prompt_version_id else None,
    )
    temperature = (
        llm_temperature
        if llm_temperature is not None
        else settings.get_agent_temperature("itso")
    )
    client = llm_client or context.llm_client or get_llm_client()
    if getattr(settings, "llm_response_mode", "json_object") == "json_schema":
        response_contract = ResponseContract.json_schema(
            build_response_schema(packed_chunk_ids, criteria_specs=criteria_specs),
            name="itso_response_v1",
        )
    else:
        response_contract = ResponseContract.json_object()
    deadline = time.monotonic() + float(
        getattr(settings, "llm_request_timeout_seconds", 120)
    )
    repair_occurred = False
    adapter = RunLLMClient(client, "itso", default_response_contract=response_contract)
    requested = adapter.requested_model or get_llm_model_name()
    with timer.measure("llm_call"):
        try:
            completion = adapter.generate_result(
                prompt,
                temperature=temperature,
                max_new_tokens=settings.llm_max_new_tokens,
                deadline=deadline,
                response_contract=response_contract,
            )
            raw = completion.content
        except AgentLLMError as exc:
            if str(exc) == "LLM output was truncated":
                raw = ""
                repair_occurred = True
            else:
                raise
    with timer.measure("parse"):
        try:
            parsed = parse_response(
                raw,
                expected_ids=expected_ids,
                expected_titles=expected_titles,
                known_chunk_ids=packed_chunk_ids,
                packed_chunk_map=packed_chunk_map,
            )
        except AgentExecutionError as exc:
            del exc
            repair_prompt = prompt + repair_suffix
            if len(repair_prompt) > total_budget:
                raise AgentExecutionError("ITSO repair prompt exceeds total budget")
            with timer.measure("llm_repair"):
                repaired_result = adapter.generate_result(
                    repair_prompt,
                    temperature=temperature,
                    max_new_tokens=settings.llm_max_new_tokens,
                    deadline=deadline,
                    response_contract=response_contract,
                )
                repaired = repaired_result.content
            parsed = parse_response(
                repaired,
                expected_ids=expected_ids,
                expected_titles=expected_titles,
                known_chunk_ids=packed_chunk_ids,
                packed_chunk_map=packed_chunk_map,
            )
            repair_occurred = True
        scores = criterion_scores(
            parsed,
            expected_ids=expected_ids,
            expected_titles=expected_titles,
            known_chunk_ids=packed_chunk_ids,
            packed_chunk_map=packed_chunk_map,
        )
        # Strategy typed score normalization verification
        criteria_by_code = {c.criterion_code: c for c in ordered_criteria}
        for score_item in scores:
            crit_def = criteria_by_code[score_item.criterion_id]
            measurement_evidence = (
                score_item.evidence[0]
                if score_item.evidence
                else "ungrounded advisory output"
            )
            norm_res = normalize_llm_guidance_score(
                crit_def.strategy_config,  # type: ignore[arg-type]
                GroundedScoreMeasurement(
                    score=score_item.score,
                    evidence=measurement_evidence,
                ),
            )
            if norm_res.score != score_item.score:
                raise AgentExecutionError("Score normalization mismatch")

        advisory_outputs = collect_advisory_outputs(parsed, expected_ids=expected_ids)
    provenance = thaw(context.provenance)
    policy_evidence = thaw(context.policy_evidence)
    policy_trimmed = bool(policy_evidence) and ("=== POLICY EVIDENCE ===" not in prompt)
    runtime = {
        "requested_model": requested,
        "actual_model": adapter.actual_model,
        "requested_temperature": temperature,
        "fallback_occurred": adapter.fallback_occurred,
        "repair_occurred": repair_occurred,
        "prompt_trimmed": budget.trimmed,
        "reference_context_dropped": budget.reference_context_dropped,
        "policy_trimmed": policy_trimmed,
        "response_format_downgraded": adapter.telemetry.get(
            "response_format_downgraded", False
        ),
    }
    provenance.update(
        {
            key: value
            for key, value in runtime.items()
            if key not in provenance or key == "policy_trimmed"
        }
    )
    safe = sanitize_provenance(provenance) or None
    timer.log_summary(prompt_chars=len(prompt))
    return AgentEvaluationResult(
        agent_name="itso",
        evaluation_id=context.evaluation_id,
        document_id=context.document_id,
        subtotal=sum(score.score for score in scores) / len(scores) if scores else 0.0,
        criterion_scores=scores,
        prompt_version_id=context.prompt_version_id,
        summary=parsed.get("summary", ""),
        model_name=adapter.actual_model,
        processing_seconds=time.perf_counter() - start,
        token_count=sum(len(text.split()) for text in texts),
        success=True,
        error_message=None,
        raw_response=None,
        prompt_text=None,
        provenance=safe,
        advisory_outputs=advisory_outputs,
        metadata={
            "prompt_chars": prompt_chars,
            "rubric_context_size": 0,
            "reference_context_size": len(references),
            "prompt_trimmed": budget.trimmed,
            "reference_context_dropped": budget.reference_context_dropped,
            "prompt_version_id": (
                str(context.prompt_version_id) if context.prompt_version_id else None
            ),
            "prompt_version_chars": (
                len(context.prompt_version)
                if context.prompt_version is not None
                else None
            ),
            "prompt_version_hash": (
                hashlib.sha256(context.prompt_version.encode("utf-8")).hexdigest()
                if context.prompt_version is not None
                else None
            ),
            "response_schema_version": ITSO_RESPONSE_SCHEMA_VERSION,
        },
    )


def _references(context: ITSOExecutionContext) -> list[str]:
    cached = dict(context.precomputed_context)
    references: list[str] = []
    for source_type in ("syllabus", "curriculum"):
        values = cached.get(source_type, ())
        if not isinstance(values, tuple) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise AgentExecutionError(
                "ITSO precomputed reference context has an invalid shape"
            )
        references.extend(values)
    return references
