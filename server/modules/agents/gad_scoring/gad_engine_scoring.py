"""Criterion-specific execution engine shared by GAD agent entry points."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from server.core.config import get_settings
from server.core.llm import get_llm_model_name

from ..base import BaseAgent
from ..contracts import AgentEvaluationResult, CriterionScore
from ..exceptions import AgentExecutionError
from ..provenance import sanitize_provenance
from . import registry

logger = logging.getLogger(__name__)


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
        """Retain the standard hook for diagnostics and prompt-policy tests."""
        del rubric_context, reference_context, reference_text
        return json.dumps(
            {
                "agent": self.agent_name,
                "prompt_version": prompt_version,
                "document_chunks": chunk_infos,
                "instructions": [
                    "GAD scoring uses criterion-specific extraction prompts."
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
        settings = get_settings()
        packed_chunks, chunks_dropped, text_excerpted = self._pack_chunks(
            chunk_infos,
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=settings.agent_prompt_budget_chars,
            small_doc_threshold=settings.agent_small_doc_threshold,
        )
        if not packed_chunks:
            raise AgentExecutionError("no document chunks fit the GAD prompt budget")

        start = time.perf_counter()
        raw_by_criterion: dict[str, dict[str, Any]] = {}
        scores: list[CriterionScore] = []
        actual_models: list[str] = []
        prompt_trimmed = chunks_dropped or text_excerpted

        balance_definition = next(
            definition for definition in registry.CRITERIA if definition.balance
        )
        qualitative_definitions = tuple(
            definition for definition in registry.CRITERIA if not definition.balance
        )

        # Call 1 keeps representation counting isolated because its output
        # contract and measurement logic differ from the four instance-based
        # criteria.
        balance_prompt = registry.build_prompt(balance_definition, packed_chunks)
        balance_budget = self._enforce_total_prompt_budget(
            balance_prompt,
            budget_chars=settings.agent_total_prompt_budget_chars,
        )
        prompt_trimmed = prompt_trimmed or balance_budget.trimmed
        balance_response, balance_model = self._call_llm(
            balance_budget.prompt,
            temperature=0.0,
        )
        raw_by_criterion[balance_definition.criterion_id] = registry.parse_payload(
            balance_response,
            balance_definition.criterion_id,
        )
        actual_models.append(balance_model)

        # Call 2 shares document context across the four instance-based
        # criteria. The extra fixed-instruction allowance prevents the grouped
        # contract from displacing document evidence that fit the original
        # per-agent chunk budget.
        grouped_prompt = registry.build_grouped_prompt(
            qualitative_definitions,
            packed_chunks,
        )
        grouped_budget = self._enforce_total_prompt_budget(
            grouped_prompt,
            budget_chars=(
                settings.agent_total_prompt_budget_chars
                + settings.agent_prompt_budget_chars
            ),
        )
        prompt_trimmed = prompt_trimmed or grouped_budget.trimmed
        grouped_response, grouped_model = self._call_llm(
            grouped_budget.prompt,
            temperature=0.0,
        )
        raw_by_criterion.update(
            registry.parse_grouped_payload(
                grouped_response,
                qualitative_definitions,
            )
        )
        actual_models.append(grouped_model)

        # Preserve canonical rubric ordering and the existing deterministic
        # scoring/grounding path regardless of LLM call order.
        for definition in registry.CRITERIA:
            scores.append(
                registry.build_score(
                    definition,
                    raw_by_criterion[definition.criterion_id],
                    packed_chunks,
                )
            )

        criterion_scores = tuple(scores)
        processing_seconds = time.perf_counter() - start
        subtotal = sum(score.score for score in criterion_scores) / len(
            criterion_scores
        )
        requested_model = getattr(self._llm_client, "model", get_llm_model_name())
        actual_model = actual_models[-1] if actual_models else requested_model
        runtime_provenance = {
            **(provenance or {}),
            "requested_model": requested_model,
            "actual_model": actual_model,
            "requested_temperature": 0.0,
            "fallback_occurred": any(
                model != requested_model for model in actual_models
            ),
            "repair_occurred": False,
            "prompt_trimmed": prompt_trimmed,
            "reference_context_dropped": 0,
        }
        summaries = [
            str(raw_by_criterion[item.criterion_id]["summary"]).strip()
            for item in registry.CRITERIA
        ]

        logger.info(
            "[GAD_SCORING] criteria=%d | calls=%d | seconds=%.3f | subtotal=%.2f",
            len(criterion_scores),
            len(actual_models),
            processing_seconds,
            subtotal,
        )

        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=criterion_scores,
            summary=" ".join(summaries),
            model_name=actual_model,
            processing_seconds=processing_seconds,
            token_count=sum(
                len(str(chunk.get("text", "")).split()) for chunk in packed_chunks
            ),
            prompt_version_id=prompt_version_id,
            success=True,
            raw_response=json.dumps(raw_by_criterion, ensure_ascii=False),
            provenance=sanitize_provenance(runtime_provenance),
            metadata={
                "scoring_mode": "criterion_specific_code_bands",
                "llm_call_count": len(actual_models),
                "prompt_version": prompt_version,
            },
        )


__all__ = ["GADScoredAgent"]
