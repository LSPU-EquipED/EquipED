"""Single-pass GAD execution engine — one combined fact-only LLM call.

Task 2.2-3.4: replaces five sequential criterion-level calls with one
combined extraction, one bounded repair, and deterministic registry scoring.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from server.core.config import get_settings
from server.core.llm import get_llm_model_name

from ..base import BaseAgent
from ..contracts import AgentEvaluationResult
from ..exceptions import AgentExecutionError
from ..provenance import sanitize_provenance
from . import registry, single_pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Repair envelope overhead reservation
# ---------------------------------------------------------------------------
# The repair prompt = full initial prompt (frozen context + instructions) +
# fixed template text + error detail + partial prior response.
#
# Worst-case overhead (characters):
#   "\n\nYour previous GAD extraction..."  ≈ 350
#   "\n\nError: "                           ≈ 12
#   error_detail[:500]                      = 500
#   "\n\nPrior response:\n"                 ≈ 22
#   partial_response[:4000]                 = 4000
#   "\n\nReturn ONLY..."                    ≈ 50
#   Total ≈ 4934
#
# Rounded to 5500 for safety margin.  This is reserved from the total prompt
# budget BEFORE initial chunk packing so that the repair prompt (built from
# the same frozen chunks + this overhead) never exceeds the configured total.
# The initial prompt is constrained to (total_budget - _REPAIR_OVERHEAD_RESERVE)
# which guarantees the repair prompt fits total_budget without any slicing.
_REPAIR_OVERHEAD_RESERVE = 5500


class GADScoredAgent(BaseAgent):
    """Base for GAD agents whose measurements are converted to bands in code."""

    def _build_prompt(
        self,
        *,
        chunk_infos: list[dict[str, Any]],
        rubric_context: list[str],
        reference_context: list[str],
        reference_text: str | None,
        prompt_version: str | None,
    ) -> str:
        """Retain the standard hook for diagnostics and prompt-policy tests.

        GAD uses its own GAD-local combined prompt builder (``single_pass``),
        so this method returns a minimal placeholder for the BaseAgent
        interface contract.
        """
        del rubric_context, reference_context, reference_text
        return json.dumps(
            {
                "agent": self.agent_name,
                "prompt_version": prompt_version,
                "document_chunks": chunk_infos,
                "instructions": [
                    "GAD scoring uses single-pass fact-only extraction."
                ],
            },
            ensure_ascii=False,
        )

    def _run_gad_scoring(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        prompt_version: str | None,
        prompt_version_id: uuid.UUID | None,
        provenance: dict[str, Any] | None,
    ) -> AgentEvaluationResult:
        """Execute single-pass GAD extraction.

        ``prompt_version`` from the supervisor is actually the managed GAD
        prompt TEXT (the active ``PromptVersion.prompt_text``). Its version
        identity is ``prompt_version_id``.
        """
        settings = get_settings()

        # ---- Reserve repair envelope overhead from total budget ----
        # The repair prompt = full initial prompt + _REPAIR_OVERHEAD_RESERVE.
        # We pack chunks to fit within (total_budget - reserve) so that the
        # repair prompt never exceeds total_budget.  See module doc on
        # _REPAIR_OVERHEAD_RESERVE for the overhead breakdown.
        total_budget = settings.agent_total_prompt_budget_chars
        repair_reserve = _REPAIR_OVERHEAD_RESERVE
        if repair_reserve >= total_budget:
            raise AgentExecutionError(
                f"GAD repair overhead ({repair_reserve}) exceeds total prompt "
                f"budget ({total_budget}). Increase AGENT_TOTAL_PROMPT_BUDGET_CHARS."
            )
        repair_safe_budget = total_budget - repair_reserve

        # Pack chunks using the repair-safe budget (accounts for instructions
        # AND repair overhead).  This ensures the same frozen chunks serve
        # both initial and repair calls within total_budget.
        packed_chunks, chunks_dropped, text_excerpted = self._pack_chunks(
            chunk_infos,
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=min(
                settings.agent_prompt_budget_chars,
                repair_safe_budget,
            ),
            small_doc_threshold=settings.agent_small_doc_threshold,
        )
        if not packed_chunks:
            raise AgentExecutionError(
                "no document chunks fit the GAD prompt budget "
                f"(repair-safe budget={repair_safe_budget})"
            )

        start = time.perf_counter()
        prompt_trimmed = chunks_dropped or text_excerpted
        requested_model = getattr(self._llm_client, "model", get_llm_model_name())
        had_fallback = False
        had_repair = False

        # ------------------------------------------------------------------
        # 3.4 — Timing accumulators
        # ------------------------------------------------------------------
        extraction_seconds = 0.0
        validation_seconds = 0.0
        scoring_seconds = 0.0

        # ------------------------------------------------------------------
        # 2.1 — Build one combined extraction prompt
        # ------------------------------------------------------------------
        gad_managed_prompt = prompt_version  # supervisor passes prompt text

        combined_prompt = single_pass.build_combined_prompt(
            packed_chunks=packed_chunks,
            prompt_version=str(prompt_version_id) if prompt_version_id else None,
            gad_managed_prompt=gad_managed_prompt,
        )

        # ---- Budget enforcement (repair-safe) ----
        # Constrain the initial prompt to repair_safe_budget so that adding
        # the repair envelope overhead later fits within total_budget.
        # GAD's prompt has no reference_context or rubric_context, so
        # _enforce_total_prompt_budget is a length check + warning pass.
        # The real packing cap comes from the prompt_budget_chars passed to
        # _pack_chunks above.
        initial_budget = self._enforce_total_prompt_budget(
            combined_prompt,
            budget_chars=repair_safe_budget,
        )
        combined_prompt = initial_budget.prompt
        prompt_trimmed = prompt_trimmed or initial_budget.trimmed

        # The packed chunks within combined_prompt are the FROZEN set — same
        # for initial, repair, and grounding.
        try:
            final_payload = json.loads(combined_prompt)
            frozen_chunks: list[dict[str, Any]] = final_payload.get(
                "document_chunks", packed_chunks
            )
        except (json.JSONDecodeError, TypeError):
            frozen_chunks = packed_chunks

        # ------------------------------------------------------------------
        # Phase 2: one combined extraction call (2.2)
        # ------------------------------------------------------------------
        t0 = time.perf_counter()
        raw_response: str | None = None
        actual_model: str = requested_model
        try:
            raw_response, actual_model = self._call_llm(
                combined_prompt,
                temperature=0.0,
            )
        except AgentExecutionError:
            # Transport failure — return failed result immediately
            elapsed = time.perf_counter() - start
            return _failed_result(
                evaluation_id=evaluation_id,
                document_id=document_id,
                prompt_version_id=prompt_version_id,
                prompt_version=prompt_version,
                model_name=actual_model,
                requested_model=requested_model,
                requested_temperature=0.0,
                prompt_trimmed=prompt_trimmed,
                had_fallback=had_fallback,
                had_repair=had_repair,
                error_message="GAD LLM transport failure",
                processing_seconds=elapsed,
                provenance=provenance,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start
            return _failed_result(
                evaluation_id=evaluation_id,
                document_id=document_id,
                prompt_version_id=prompt_version_id,
                prompt_version=prompt_version,
                model_name=actual_model,
                requested_model=requested_model,
                requested_temperature=0.0,
                prompt_trimmed=prompt_trimmed,
                had_fallback=had_fallback,
                had_repair=had_repair,
                error_message=f"GAD LLM call failed: {exc}",
                processing_seconds=elapsed,
                provenance=provenance,
            )

        requested_temperature = 0.0
        had_fallback = actual_model != requested_model
        extraction_seconds = time.perf_counter() - t0

        # ------------------------------------------------------------------
        # Phase 3: parse and validate combined response
        # ------------------------------------------------------------------
        t0 = time.perf_counter()
        combined: dict[str, Any] | None = None
        try:
            combined = single_pass.parse_combined_response(raw_response)
        except AgentExecutionError as exc:
            # 3.1 — Single whole-envelope repair using SAME frozen context
            logger.warning(
                "GAD combined response invalid, attempting repair: %s",
                exc,
            )
            repair_prompt = single_pass.build_combined_repair_prompt(
                full_prompt_context=combined_prompt,
                partial_response=raw_response or "",
                error_detail=str(exc),
            )
            # ---- Repair prompt budget invariant assertion ----
            # The initial prompt was constrained to repair_safe_budget and
            # the repair prompt adds at most _REPAIR_OVERHEAD_RESERVE, so it
            # MUST fit within total_budget.  Fail honestly if the invariant
            # somehow does not hold (should never happen).
            if len(repair_prompt) > total_budget:
                elapsed = time.perf_counter() - start
                return _failed_result(
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    prompt_version_id=prompt_version_id,
                    prompt_version=prompt_version,
                    model_name=actual_model,
                    requested_model=requested_model,
                    requested_temperature=0.0,
                    prompt_trimmed=prompt_trimmed,
                    had_fallback=had_fallback,
                    had_repair=False,
                    error_message=(
                        f"GAD repair prompt exceeds total budget: "
                        f"{len(repair_prompt)} > {total_budget}"
                    ),
                    processing_seconds=elapsed,
                    provenance=provenance,
                )
            # Blocker 3: set repair-attempt provenance BEFORE invoking repair,
            # so even transport failure reflects the attempt.
            had_repair = True
            try:
                repair_response, repair_model = self._call_llm(
                    repair_prompt,
                    temperature=0.0,
                )
                if repair_model != actual_model:
                    actual_model = repair_model
                    had_fallback = True
            except AgentExecutionError as repair_exc:
                # Repair transport failure
                elapsed = time.perf_counter() - start
                return _failed_result(
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    prompt_version_id=prompt_version_id,
                    prompt_version=prompt_version,
                    model_name=actual_model,
                    requested_model=requested_model,
                    requested_temperature=requested_temperature,
                    prompt_trimmed=prompt_trimmed,
                    had_fallback=had_fallback,
                    had_repair=had_repair,
                    error_message=str(repair_exc),
                    processing_seconds=elapsed,
                    provenance=provenance,
                )
            except Exception as repair_exc:
                elapsed = time.perf_counter() - start
                return _failed_result(
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    prompt_version_id=prompt_version_id,
                    prompt_version=prompt_version,
                    model_name=actual_model,
                    requested_model=requested_model,
                    requested_temperature=requested_temperature,
                    prompt_trimmed=prompt_trimmed,
                    had_fallback=had_fallback,
                    had_repair=had_repair,
                    error_message=f"GAD repair call failed: {repair_exc}",
                    processing_seconds=elapsed,
                    provenance=provenance,
                )

            # Parse the repair response
            try:
                combined = single_pass.parse_combined_response(repair_response)
            except AgentExecutionError as repair_parse_exc:
                elapsed = time.perf_counter() - start
                return _failed_result(
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    prompt_version_id=prompt_version_id,
                    prompt_version=prompt_version,
                    model_name=actual_model,
                    requested_model=requested_model,
                    requested_temperature=requested_temperature,
                    prompt_trimmed=prompt_trimmed,
                    had_fallback=had_fallback,
                    had_repair=had_repair,
                    error_message=str(repair_parse_exc),
                    processing_seconds=elapsed,
                    provenance=provenance,
                )

        validation_seconds = time.perf_counter() - t0

        # ------------------------------------------------------------------
        # Phase 4: deterministic scoring through registry (2.3)
        # ------------------------------------------------------------------
        t0 = time.perf_counter()
        try:
            criterion_scores, ev_candidates, ev_accepted, ev_rejected = (
                single_pass.score_from_combined(combined, frozen_chunks)
            )
        except AgentExecutionError as exc:
            # Registry scoring failure is NOT repairable (design constraint)
            scoring_time = time.perf_counter() - start
            return _failed_result(
                evaluation_id=evaluation_id,
                document_id=document_id,
                prompt_version_id=prompt_version_id,
                prompt_version=prompt_version,
                model_name=actual_model,
                requested_model=requested_model,
                requested_temperature=requested_temperature,
                prompt_trimmed=prompt_trimmed,
                had_fallback=had_fallback,
                had_repair=had_repair,
                error_message=str(exc),
                processing_seconds=scoring_time,
                provenance=provenance,
            )

        scoring_seconds = time.perf_counter() - t0
        processing_seconds = time.perf_counter() - start

        subtotal = (
            sum(score.score for score in criterion_scores) / len(criterion_scores)
            if criterion_scores
            else 0.0
        )

        # Build combined summary from all five criterion summaries
        summaries_list: list[str] = []
        for definition in registry.CRITERIA:
            section = combined.get(definition.criterion_id.lower(), {})
            if isinstance(section, dict):
                s = str(section.get("summary", "")).strip()
                if s:
                    summaries_list.append(s)
        combined_summary = " ".join(summaries_list)

        # ------------------------------------------------------------------
        # Provenance (3.3) — include bounded timing counters
        # ------------------------------------------------------------------
        runtime_provenance: dict[str, Any] = {
            **(provenance or {}),
            "requested_model": requested_model,
            "actual_model": actual_model,
            "requested_temperature": requested_temperature,
            "fallback_occurred": had_fallback,
            "repair_occurred": had_repair,
            "prompt_trimmed": (
                initial_budget.trimmed or chunks_dropped or text_excerpted
            ),
            "reference_context_dropped": initial_budget.reference_context_dropped,
            "extraction_schema_version": single_pass.EXTRACTION_SCHEMA_VERSION,
            "registry_version": registry.REGISTRY_VERSION,
            "evidence_candidates": ev_candidates,
            "evidence_accepted": ev_accepted,
            "evidence_rejected": ev_rejected,
            "gad_extraction_seconds": round(extraction_seconds, 4),
            "gad_validation_seconds": round(validation_seconds, 4),
            "gad_scoring_seconds": round(scoring_seconds, 4),
        }
        sanitized = sanitize_provenance(runtime_provenance)
        merged_provenance = sanitized if sanitized is not None else {}

        token_count = sum(
            len(str(chunk.get("text", "")).split()) for chunk in frozen_chunks
        )

        # ------------------------------------------------------------------
        # 3.4 — Timing log
        # ------------------------------------------------------------------
        logger.info(
            "[GAD_SCORING] criteria=%d | extraction=%.3fs | validation=%.3fs | "
            "scoring=%.3fs | total=%.3fs | subtotal=%.2f | evidence=%d/%d/%d "
            "(cand/acc/rej) | model=%s",
            len(criterion_scores),
            extraction_seconds,
            validation_seconds,
            scoring_seconds,
            processing_seconds,
            subtotal,
            ev_candidates,
            ev_accepted,
            ev_rejected,
            actual_model,
        )

        # ------------------------------------------------------------------
        # 2.4 — Standard result shape (unchanged contract)
        # ------------------------------------------------------------------
        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=tuple(criterion_scores),
            summary=combined_summary,
            model_name=actual_model,
            processing_seconds=processing_seconds,
            token_count=token_count,
            prompt_version_id=prompt_version_id,
            success=True,
            raw_response=json.dumps(combined, ensure_ascii=False),
            provenance=merged_provenance if merged_provenance else None,
            metadata={
                "scoring_mode": "single_pass_code_bands",
                "llm_call_count": 1 if not had_repair else 2,
                "prompt_version": str(prompt_version_id) if prompt_version_id else None,
                "extraction_schema_version": single_pass.EXTRACTION_SCHEMA_VERSION,
                "registry_version": registry.REGISTRY_VERSION,
            },
        )


# ---------------------------------------------------------------------------
# 3.2 — Failed GAD result factory
# ---------------------------------------------------------------------------


def _failed_result(
    *,
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
    prompt_version_id: uuid.UUID | None,
    prompt_version: str | None,
    model_name: str,
    requested_model: str,
    requested_temperature: float,
    prompt_trimmed: bool,
    had_fallback: bool,
    had_repair: bool,
    error_message: str,
    processing_seconds: float,
    provenance: dict[str, Any] | None,
) -> AgentEvaluationResult:
    """Return a failed GAD result with real timing and known metadata.

    No partial criteria — the entire GAD agent is marked failed.
    Normal synthesis partial-result handling applies upstream.
    """
    runtime_provenance: dict[str, Any] = {
        **(provenance or {}),
        "requested_model": requested_model,
        "actual_model": model_name,
        "requested_temperature": requested_temperature,
        "fallback_occurred": had_fallback,
        "repair_occurred": had_repair,
        "prompt_trimmed": prompt_trimmed,
        "reference_context_dropped": 0,
        "extraction_schema_version": single_pass.EXTRACTION_SCHEMA_VERSION,
        "registry_version": registry.REGISTRY_VERSION,
    }
    sanitized = sanitize_provenance(runtime_provenance)
    merged_provenance = sanitized if sanitized is not None else {}

    logger.warning(
        "[GAD_FAILURE] seconds=%.3f | error=%s | repair=%s",
        processing_seconds,
        error_message[:200],
        had_repair,
    )

    return AgentEvaluationResult(
        agent_name="gad",
        evaluation_id=evaluation_id,
        document_id=document_id,
        subtotal=0.0,
        criterion_scores=(),
        summary="",
        model_name=model_name,
        processing_seconds=processing_seconds,
        token_count=0,
        prompt_version_id=prompt_version_id,
        success=False,
        error_message=error_message,
        raw_response=None,
        provenance=merged_provenance if merged_provenance else None,
        metadata={
            "scoring_mode": "single_pass_failed",
            "llm_call_count": 1 if not had_repair else 2,
            "prompt_version": str(prompt_version_id) if prompt_version_id else None,
        },
    )


__all__ = ["GADScoredAgent"]
