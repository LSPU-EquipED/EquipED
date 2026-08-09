"""Stateless ITSO execution pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from server.core.config import get_settings
from server.core.llm import get_llm_client, get_llm_model_name
from server.modules.embeddings.collections import resolve_collection_name
from server.modules.embeddings.retrieval import retrieve_context
from server.modules.rubrics.service import (
    get_active_rubric_context,
    resolve_rubric_agent_id,
)

from ..contracts import AgentEvaluationResult
from ..exceptions import AgentExecutionError
from ..provenance import sanitize_provenance
from ..runtime.context import ITSOExecutionContext, thaw
from ..runtime.llm import FallbackAwareClient
from ..runtime.prompt_budget import enforce_total_prompt_budget
from ..runtime.timing import PhaseTimer
from .prompt import build_prompt
from .response import criterion_scores, parse_response

logger = logging.getLogger(__name__)


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
    start = time.perf_counter()
    timer = PhaseTimer("itso")
    texts = [
        str(dict(chunk).get("text", ""))
        for chunk in context.chunk_infos
        if dict(chunk).get("text")
    ]
    query = "\n".join(texts)
    with timer.measure("retrieval"):
        rubric = _rubric(query, context)
        references = _references(query, context)
    with timer.measure("prompt_build"):
        prompt = build_prompt(
            context, rubric_context=rubric, reference_context=references
        )
    settings = get_settings()
    budget = enforce_total_prompt_budget(
        prompt, budget_chars=settings.agent_total_prompt_budget_chars, agent_name="itso"
    )
    prompt = budget.prompt
    prompt_chars = len(prompt)
    logger.info(
        "[EVAL_PROMPT_SIZE] agent=itso | prompt_chars=%d | trimmed=%s | "
        "budget=%d | rubric_context=%d | reference_context=%d | "
        "prompt_version_id=%s",
        prompt_chars,
        "yes" if budget.trimmed else "no",
        settings.agent_total_prompt_budget_chars,
        len(rubric),
        len(references),
        str(context.prompt_version_id) if context.prompt_version_id else None,
    )
    temperature = (
        llm_temperature
        if llm_temperature is not None
        else settings.get_agent_temperature("itso")
    )
    client = llm_client or context.llm_client or get_llm_client()
    adapter = FallbackAwareClient(client, "itso")
    requested = adapter.requested_model or get_llm_model_name()
    with timer.measure("llm_call"):
        raw = adapter.generate(
            prompt, temperature=temperature, max_new_tokens=settings.llm_max_new_tokens
        )
    repair_occurred = False
    with timer.measure("parse"):
        try:
            parsed = parse_response(raw)
        except AgentExecutionError as exc:
            if not isinstance(exc.__cause__, json.JSONDecodeError):
                raise
            repair_prompt = (
                "Your previous JSON response was truncated or invalid. "
                "Return ONLY a complete valid JSON object with the same fields. "
                "Prior partial output:\n\n" + raw[:4000]
            )
            with timer.measure("llm_repair"):
                repaired = adapter.generate(
                    repair_prompt,
                    temperature=temperature,
                    max_new_tokens=settings.llm_max_new_tokens,
                )
            parsed = parse_response(repaired)
            raw = repaired
            repair_occurred = True
        scores = criterion_scores(parsed)
    provenance = thaw(context.provenance)
    policy_evidence = thaw(context.policy_evidence)
    policy_trimmed = bool(policy_evidence) and (
        "=== POLICY EVIDENCE ===" not in prompt
    )
    runtime = {
        "requested_model": requested,
        "actual_model": adapter.actual_model,
        "requested_temperature": temperature,
        "fallback_occurred": adapter.fallback_occurred,
        "repair_occurred": repair_occurred,
        "prompt_trimmed": budget.trimmed,
        "reference_context_dropped": budget.reference_context_dropped,
        "policy_trimmed": policy_trimmed,
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
        raw_response=raw,
        provenance=safe,
        metadata={
            "prompt_chars": prompt_chars,
            "rubric_context_size": len(rubric),
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
        },
    )


def _rubric(query: str, context: ITSOExecutionContext) -> list[str]:
    cached = dict(context.precomputed_context)
    if "rubric_itso" in cached:
        return list(cached["rubric_itso"])
    try:
        return get_active_rubric_context(resolve_rubric_agent_id("rubric_itso")) or []
    except Exception:
        return []


def _references(query: str, context: ITSOExecutionContext) -> list[str]:
    result: list[str] = []
    cached = dict(context.precomputed_context)
    if "syllabus" in cached or "curriculum" in cached:
        return list(cached.get("syllabus", ())) + list(
            cached.get("curriculum", ())
        )  # type: ignore[arg-type]
    for source in ("syllabus", "curriculum"):
        try:
            document_ids = dict(context.reference_document_ids)
            if source in document_ids:
                result.extend(
                    chunk.text
                    for chunk in retrieve_context(
                        query,
                        resolve_collection_name(source),
                        n_results=5,
                        document_id_filter=str(document_ids[source]),
                    )
                )
        except Exception:
            continue
    return result
