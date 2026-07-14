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

        for definition in registry.CRITERIA:
            prompt = registry.build_prompt(definition, packed_chunks)
            budget = self._enforce_total_prompt_budget(
                prompt,
                budget_chars=settings.agent_total_prompt_budget_chars,
            )
            prompt_trimmed = prompt_trimmed or budget.trimmed
            # Like the SME extraction engine, GAD measurements are never
            # creative. Temperature is an internal invariant, not a setting.
            raw_response, actual_model = self._call_llm(
                budget.prompt,
                temperature=0.0,
            )
            payload = registry.parse_payload(raw_response, definition.criterion_id)
            raw_by_criterion[definition.criterion_id] = payload
            scores.append(registry.build_score(definition, payload, packed_chunks))
            actual_models.append(actual_model)

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
