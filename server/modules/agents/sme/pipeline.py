"""Shared engine-scoring base for SME and Coordinator.

Both agents' rubrics map 1:1 onto ``registry.REGISTERED_CODES`` (SME's and
Coordinator's rubric sets are identical -- see
``server/data/rubrics/rubrics.json``), so both score via the code-side
engine rather than an LLM-guesses-everything prompt. This module holds
everything that's agent-agnostic: loading the SLM's clean text, running the
grouped-basket-then-per-criterion-fallback pass, and building the final
``AgentEvaluationResult``.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from server.core.llm import ResponseContract, get_llm_client, get_llm_model_name
from server.modules.rubrics.service import (
    get_active_rubric_criteria,
    get_active_rubric_descriptions,
    resolve_rubric_agent_id,
)

from ..contracts import AgentEvaluationResult, CriterionScore
from ..exceptions import AgentExecutionError
from ..runtime.llm import RunLLMClient, error_reference
from . import groups, registry
from .grouped_execution import execute_group
from .grouped_prompt import FALLBACK_DESCRIPTIONS as _FALLBACK_DESCRIPTIONS

logger = logging.getLogger(__name__)


class EngineScoredAgent:
    """Base for agents whose full rubric is scored by the code-side engine."""

    agent_name = "engine"
    rubric_source_type = "rubric_sme"

    def __init__(self, *, llm_client: Any | None = None) -> None:
        self._default_llm_client = llm_client

    def _resolve_full_text(
        self,
        document_id: uuid.UUID,
        context_text: str | None,
        chunk_infos: list[dict[str, Any]],
        canonical_source_text: str | None = None,
    ) -> str:
        """The SLM's clean text, or the best available fallback.

        Shared by the full engine pass and Coordinator's single-call path --
        both need identical full-text resolution, so this is pulled out to
        avoid duplicating the fallback chain.
        """
        if not canonical_source_text or not canonical_source_text.strip():
            raise AgentExecutionError("canonical source text is required")
        return canonical_source_text

    def _rubric_titles(self, db: Any | None) -> dict[str, str]:
        """This agent's own rubric criterion titles, keyed by code."""
        return get_active_rubric_criteria(
            resolve_rubric_agent_id(self.rubric_source_type), db=db
        )

    def _rubric_descriptions(self, db: Any | None) -> dict[str, str]:
        """This agent's own rubric criterion descriptions, keyed by code."""
        return get_active_rubric_descriptions(
            resolve_rubric_agent_id(self.rubric_source_type), db=db
        )

    def _score_via_engine(
        self,
        client: Any,
        full_text: str,
        raw_baskets_out: dict[str, dict[str, Any]] | None = None,
        basket_extract_kwargs: dict[str, dict[str, Any]] | None = None,
        prompt_preamble: str | None = None,
        canonical_source_text: str | None = None,
    ) -> tuple[dict[str, tuple[int, str, tuple[str, ...]]], int]:
        """Score every registered criterion: grouped pass, then per-criterion
        fallback for anything the grouped pass didn't cover.

        Returns ``(scores, fallback_count)``.  Raises
        ``AgentExecutionError`` for any code that fails BOTH the grouped pass
        and its own per-criterion fallback -- matches every agent's
        all-or-nothing failure contract (the Supervisor already catches a
        raised agent, marks it ``success=False``, and excludes it from
        synthesis weighting).

        ``raw_baskets_out`` and ``basket_extract_kwargs``, if given, are
        forwarded to ``registry.run_grouped``. Additive only -- SME's call
        site passes neither.
        """
        telemetry = getattr(client, "telemetry", None)
        try:
            t0 = time.perf_counter()
            grouped = registry.run_grouped(
                client,
                full_text,
                raw_baskets_out=raw_baskets_out,
                basket_extract_kwargs=basket_extract_kwargs,
                prompt_preamble=prompt_preamble,
            )
            # ``run_grouped`` performs six physical basket transports.  Keep
            # this accounting at the transport boundary rather than counting
            # the single pipeline lane invocation.
            if isinstance(telemetry, dict):
                telemetry["grouped_calls"] = telemetry.get("grouped_calls", 0) + 6
            grouped_seconds = time.perf_counter() - t0
            logger.info(
                "[ENGINE_TIMING] agent=%s | phase=grouped | seconds=%.3f | criteria=%d",
                self.agent_name,
                grouped_seconds,
                len(grouped),
            )
        except Exception as exc:
            logger.warning(
                "[%s] grouped pass failed entirely, falling back to "
                "per-criterion calls for every code: category=%s | reference=%s",
                self.agent_name,
                type(exc).__name__,
                error_reference(exc),
            )
            grouped = {}

        scores: dict[str, tuple[int, str, tuple[str, ...]]] = {}
        fallback_calls = 0
        for code in sorted(registry.REGISTERED_CODES):
            if code in grouped:
                scores[code] = grouped[code]
                continue

            fallback_calls += 1
            if isinstance(telemetry, dict):
                telemetry["fallback_calls"] = telemetry.get("fallback_calls", 0) + 1
            t0 = time.perf_counter()
            try:
                scores[code] = registry.run_criterion(
                    code, client, full_text, prompt_preamble=prompt_preamble
                )
            except Exception as exc:
                raise AgentExecutionError(
                    f"{self.agent_name} criterion {code} failed in both the "
                    "grouped and per-criterion engine paths "
                    f"(category={type(exc).__name__}, reference={error_reference(exc)})"
                ) from exc
            logger.info(
                "[ENGINE_TIMING] agent=%s | phase=fallback | code=%s | seconds=%.3f",
                self.agent_name,
                code,
                time.perf_counter() - t0,
            )

        return scores, fallback_calls

    def _run_full_engine_scoring(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None,
        prompt_version_id: uuid.UUID | None,
        db: Any | None,
        canonical_source_text: str | None = None,
        llm_client: Any | None = None,
        raw_baskets_out: dict[str, dict[str, Any]] | None = None,
        basket_extract_kwargs: dict[str, dict[str, Any]] | None = None,
        prompt_preamble: str | None = None,
    ) -> AgentEvaluationResult:
        """Full engine pass: load text, score every criterion, build a
        result. Used by SME and Coordinator.

        ``raw_baskets_out`` and ``basket_extract_kwargs``, if given, are
        forwarded to ``_score_via_engine`` (see its docstring) -- additive,
        SME's call site passes neither.
        """
        client = None
        try:
            full_text = self._resolve_full_text(
                document_id, context_text, chunk_infos, canonical_source_text
            )
        except Exception:
            if self.agent_name == "sme":
                raise AgentExecutionError("SME preflight failed")
            raise
        if not full_text.strip():
            raise AgentExecutionError("no document text available for evaluation")

        char_count = len(full_text)
        token_estimate = max(1, char_count // 4)
        logger.info(
            "[ENGINE_TIMING] agent=%s | phase=full_start | chars=%d | "
            "token_estimate=%d",
            self.agent_name,
            char_count,
            token_estimate,
        )

        start = time.perf_counter()
        primary_client = llm_client or self._default_llm_client or get_llm_client()
        # Keep one adapter for the complete run.  In particular, do not create
        # a new adapter for each basket: a persistently failing primary must be
        # fallback-aware on both grouped and per-criterion calls.
        client = (
            primary_client
            if isinstance(primary_client, RunLLMClient)
            else RunLLMClient(
                primary_client,
                self.agent_name,
                requested_model=(
                    getattr(primary_client, "model", None) or get_llm_model_name()
                ),
                default_response_contract=ResponseContract.json_object(),
            )
        )
        try:
            scores, fallback_calls = self._score_via_engine(
                client,
                full_text,
                raw_baskets_out=raw_baskets_out,
                basket_extract_kwargs=basket_extract_kwargs,
                prompt_preamble=prompt_preamble,
            )
        except Exception as exc:
            setattr(exc, "telemetry", dict(client.telemetry))
            raise
        titles = self._rubric_titles(db)

        criterion_scores = tuple(
            CriterionScore(
                criterion_id=code,
                criterion_title=titles.get(code, code),
                score=band,
                justification=justification,
                chunk_ids=(),
                evidence=evidence,
            )
            for code, (band, justification, evidence) in sorted(scores.items())
        )

        subtotal = sum(s.score for s in criterion_scores) / len(criterion_scores)
        total_seconds = time.perf_counter() - start
        actual_model = (
            client.actual_model
            if client.actual_model != "unknown"
            else client.requested_model
        )

        logger.info(
            "[ENGINE_TIMING] agent=%s | phase=full_end | seconds=%.3f | "
            "chars=%d | token_estimate=%d | criteria=%d | fallback=%d",
            self.agent_name,
            total_seconds,
            char_count,
            token_estimate,
            len(criterion_scores),
            fallback_calls,
        )

        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=criterion_scores,
            summary="",
            model_name=actual_model,
            processing_seconds=total_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=prompt_version_id,
            success=True,
            provenance={
                "requested_model": client.requested_model,
                "actual_model": actual_model,
                "fallback_occurred": client.fallback_occurred,
                "logical_calls": client.telemetry["call_count"],
                "physical_attempts": client.telemetry["attempt_count"],
                "input_tokens": client.telemetry["prompt_tokens"],
                "output_tokens": client.telemetry["completion_tokens"],
                "truncation_count": client.telemetry["cap_hit_count"],
                "cap_hit_count": client.telemetry["cap_hit_count"],
                "criterion_fallback_calls": fallback_calls,
                "grouped_calls": client.telemetry["grouped_calls"],
                "fallback_calls": client.telemetry["fallback_calls"],
                "provider_seconds_ms": round(
                    client.telemetry["provider_seconds"] * 1000
                ),
                "trim_count": client.telemetry["cap_hit_count"],
            },
        )

    def _run_full_llm_scoring(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None,
        prompt_version_id: uuid.UUID | None,
        db: Any | None,
        canonical_source_text: str | None = None,
        llm_client: Any | None = None,
        prompt_preamble: str | None = None,
    ) -> AgentEvaluationResult:
        """Score every criterion via 3 grouped direct-LLM-scoring calls
        (``groups.GROUP_CODES``), falling back to the existing per-criterion
        engine path (``registry.run_criterion``) for any group whose call
        fails outright. Additive: does not modify ``_score_via_engine`` or
        ``_run_full_engine_scoring``, which Coordinator still uses unchanged.
        """
        full_text = self._resolve_full_text(
            document_id, context_text, chunk_infos, canonical_source_text
        )
        if not full_text.strip():
            raise AgentExecutionError("no document text available for evaluation")

        start = time.perf_counter()
        primary_client = llm_client or self._default_llm_client or get_llm_client()
        client = (
            primary_client
            if isinstance(primary_client, RunLLMClient)
            else RunLLMClient(
                primary_client,
                self.agent_name,
                requested_model=(
                    getattr(primary_client, "model", None) or get_llm_model_name()
                ),
                default_response_contract=ResponseContract.json_object(),
            )
        )
        titles = self._rubric_titles(db)
        descriptions = self._rubric_descriptions(db)

        all_scores: dict[str, CriterionScore] = {}
        group_prompts: dict[str, str] = {}
        fallback_calls = 0

        for group_name in groups.GROUP_NAMES:
            codes = groups.GROUP_CODES[group_name]
            group_titles = {code: titles.get(code, code) for code in codes}
            group_descriptions = {
                code: descriptions.get(code, _FALLBACK_DESCRIPTIONS[code])
                for code in codes
            }
            try:
                scores, prompt_text = execute_group(
                    group_name,
                    codes,
                    group_titles,
                    group_descriptions,
                    client,
                    full_text,
                    prompt_preamble=prompt_preamble,
                )
            except Exception as exc:
                logger.warning(
                    "[SME_LLM_SCORING] group=%s failed, falling back to "
                    "per-criterion engine path: category=%s | reference=%s",
                    group_name,
                    type(exc).__name__,
                    error_reference(exc),
                )
            else:
                for score in scores:
                    all_scores[score.criterion_id] = score
                group_prompts[group_name] = prompt_text
                continue

            for code in codes:
                fallback_calls += 1
                try:
                    band, justification, evidence = registry.run_criterion(
                        code, client, full_text, prompt_preamble=prompt_preamble
                    )
                except Exception as fallback_exc:
                    raise AgentExecutionError(
                        f"{self.agent_name} criterion {code} failed in both "
                        "the grouped LLM-scoring path and the per-criterion "
                        f"engine fallback (category="
                        f"{type(fallback_exc).__name__}, "
                        f"reference={error_reference(fallback_exc)})"
                    ) from fallback_exc
                all_scores[code] = CriterionScore(
                    criterion_id=code,
                    criterion_title=titles.get(code, code),
                    score=band,
                    justification=justification,
                    chunk_ids=(),
                    evidence=evidence,
                )

        criterion_scores = tuple(all_scores[code] for code in sorted(all_scores))
        subtotal = sum(s.score for s in criterion_scores) / len(criterion_scores)
        total_seconds = time.perf_counter() - start
        actual_model = (
            client.actual_model
            if client.actual_model != "unknown"
            else client.requested_model
        )

        logger.info(
            "[SME_LLM_SCORING] agent=%s | seconds=%.3f | criteria=%d | "
            "groups_scored=%d | criterion_fallback_calls=%d",
            self.agent_name,
            total_seconds,
            len(criterion_scores),
            len(group_prompts),
            fallback_calls,
        )

        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=criterion_scores,
            summary="",
            model_name=actual_model,
            processing_seconds=total_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=prompt_version_id,
            success=True,
            metadata={"group_prompts": group_prompts},
            provenance={
                "requested_model": client.requested_model,
                "actual_model": actual_model,
                "fallback_occurred": client.fallback_occurred,
                "criterion_fallback_calls": fallback_calls,
                "logical_calls": client.telemetry["call_count"],
                "physical_attempts": client.telemetry["attempt_count"],
                "input_tokens": client.telemetry["prompt_tokens"],
                "output_tokens": client.telemetry["completion_tokens"],
                "truncation_count": client.telemetry["cap_hit_count"],
                "cap_hit_count": client.telemetry["cap_hit_count"],
                "grouped_calls": len(group_prompts),
                "fallback_calls": fallback_calls,
                "provider_seconds_ms": round(
                    client.telemetry["provider_seconds"] * 1000
                ),
                "trim_count": client.telemetry["cap_hit_count"],
            },
        )


__all__ = ["EngineScoredAgent"]
