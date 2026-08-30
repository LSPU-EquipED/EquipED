"""Program coordinator domain agent.

Coordinator evaluates curriculum alignment for the Student Learning Material (SLM)
against authoritative curriculum documents (Criterion A-05). Under published
Revision 2, Coordinator executes independently and produces its own single-criterion
result without inheriting or merging Subject Matter Expert (SME) scores.

Entry point:
- ``run()`` -- called by ``Supervisor`` in parallel with every other agent.
  Makes exactly ONE LLM call to extract objectives and evaluates curriculum
  grounding to score A-05. Returns an independent, single-criterion A-05 result.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from server.core.llm import get_llm_model_name
from server.modules.rubrics.contracts import (
    CriterionDefinition,
    CurriculumAlignmentConfig,
)
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO

from ..contracts import AgentEvaluationResult, CriterionScore
from ..exceptions import AgentExecutionError
from ..runtime.llm import RunLLMClient
from . import curriculum, extraction
from .summary import _build_alignment_summary

logger = logging.getLogger(__name__)


def _validate_and_extract_criterion(
    form_snapshot: EvaluationFormSnapshotDTO,
    evaluation_id: uuid.UUID,
    agent_name: str,
) -> CriterionDefinition:
    """Validate snapshot invariants and return the single canonical A-05 criterion."""
    if not isinstance(form_snapshot, EvaluationFormSnapshotDTO):
        raise AgentExecutionError(
            "Coordinator requires a valid EvaluationFormSnapshotDTO"
        )

    if form_snapshot.agent_id != agent_name:
        raise AgentExecutionError(
            f"Snapshot agent_id '{form_snapshot.agent_id}' does not match "
            f"'{agent_name}'"
        )
    if form_snapshot.evaluation_id != evaluation_id:
        raise AgentExecutionError(
            f"Snapshot evaluation_id '{form_snapshot.evaluation_id}' does not match "
            f"'{evaluation_id}'"
        )
    if form_snapshot.adapter_key != agent_name or form_snapshot.adapter_version != 1:
        raise AgentExecutionError(
            f"Invalid snapshot adapter key '{form_snapshot.adapter_key}' or "
            f"version {form_snapshot.adapter_version}"
        )

    criteria: list[CriterionDefinition] = [
        criterion
        for domain in form_snapshot.form.domains
        for criterion in domain.criteria
    ]
    if len(criteria) != 1:
        raise AgentExecutionError(
            "Coordinator snapshot must contain exactly 1 criterion, "
            f"found {len(criteria)}"
        )

    criterion = criteria[0]
    if criterion.criterion_code != "A-05":
        raise AgentExecutionError(
            "Coordinator snapshot criterion must be 'A-05', "
            f"found '{criterion.criterion_code}'"
        )
    if not isinstance(criterion.strategy_config, CurriculumAlignmentConfig):
        raise AgentExecutionError(
            "Coordinator snapshot criterion strategy must be "
            "CurriculumAlignmentConfig, "
            f"found {type(criterion.strategy_config).__name__}"
        )

    return criterion


class Coordinator:
    agent_name = "coordinator"
    rubric_source_type = "rubric_coord"
    reference_source_types = ("syllabus",)
    domain_keywords = (
        "program",
        "outcomes",
        "objectives",
        "curriculum",
        "alignment",
        "competencies",
        "learning outcomes",
        "course",
        "standards",
        "assessment",
        "goals",
    )

    def __init__(self, *, llm_client: Any | None = None) -> None:
        self._default_llm_client = llm_client

    def _resolve_full_text(
        self,
        document_id: uuid.UUID,
        context_text: str | None,
        chunk_infos: list[dict[str, Any]],
        canonical_source_text: str | None = None,
    ) -> str:
        del document_id, context_text, chunk_infos
        if not canonical_source_text or not canonical_source_text.strip():
            raise AgentExecutionError("canonical source text is required")
        return canonical_source_text

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        form_snapshot: EvaluationFormSnapshotDTO,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        llm_client: Any | None = None,
        reference_document_ids: dict[str, Any] | None = None,
        roadmap_context: dict[str, Any] | None = None,
        canonical_source_text: str | None = None,
        curriculum_id: uuid.UUID | None = None,
        curriculum_context: str | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Single-call curriculum-grounded A-05 check.

        Evaluates objective-curriculum alignment against authoritative curriculum
        context and returns an independent single-criterion result.
        """
        del kwargs
        criterion = _validate_and_extract_criterion(
            form_snapshot, evaluation_id, self.agent_name
        )

        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        start = time.perf_counter()
        full_text = self._resolve_full_text(
            document_id, context_text, chunk_infos, canonical_source_text
        )
        if not full_text.strip():
            raise AgentExecutionError("no document text available for evaluation")

        curriculum_id = curriculum_id or (reference_document_ids or {}).get(
            "curriculum"
        )
        if (
            curriculum_id is None
            or not isinstance(curriculum_context, str)
            or not curriculum_context.strip()
        ):
            raise AgentExecutionError(
                "Coordinator requires curriculum_id and authoritative "
                "curriculum context"
            )
        curriculum_text = curriculum_context.strip()

        client = llm_client or self._default_llm_client
        if client is None:
            raise AgentExecutionError("Coordinator requires an assigned LLM client")
        adapter = (
            client
            if isinstance(client, RunLLMClient)
            else RunLLMClient(
                client,
                self.agent_name,
                requested_model=(
                    getattr(client, "model", None) or get_llm_model_name()
                ),
            )
        )
        roadmap_note = curriculum.format_roadmap_note(roadmap_context)
        basket = extraction.extract(
            adapter,
            full_text,
            curriculum_text,
            criterion=criterion,
            roadmap_note=roadmap_note,
        )
        objectives = list(basket.get("objectives", []))

        if curriculum_text and basket.get("curriculum_alignment"):
            scored = curriculum.compute(
                objectives, list(basket["curriculum_alignment"]), curriculum_text
            )
            if scored.grounding_rejected_count > 0:
                logger.info(
                    "[COORDINATOR_GROUNDING] evaluation_id=%s | "
                    "grounding_rejected_count=%d",
                    evaluation_id,
                    scored.grounding_rejected_count,
                )
                justification = (
                    f"Curriculum-grounded (coordinator-only): {scored.aligned}/"
                    f"{scored.total_objectives} objective(s) addressed by this "
                    f"course's curriculum content ({scored.grounding_rejected_count} "
                    f"unsupported claim(s) rejected). Score {scored.score}."
                )
            else:
                justification = (
                    f"Curriculum-grounded (coordinator-only): {scored.aligned}/"
                    f"{scored.total_objectives} objective(s) addressed by this "
                    f"course's curriculum content. Score {scored.score}."
                )
            evidence = tuple(
                str(a.get("evidence", ""))
                for a in scored.curriculum_alignment
                if a.get("is_addressed") and a.get("evidence")
            )
        else:
            raise AgentExecutionError(
                "Coordinator curriculum alignment response is missing"
            )

        criterion_score = CriterionScore(
            criterion_id=criterion.criterion_code,
            criterion_title=criterion.title,
            score=scored.score,
            justification=justification,
            chunk_ids=(),
            evidence=evidence,
        )
        total_seconds = time.perf_counter() - start

        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=float(criterion_score.score),
            criterion_scores=(criterion_score,),
            # Revision-2 independent single-criterion summary for A-05.
            summary=_build_alignment_summary((criterion_score,)),
            model_name=adapter.actual_model or adapter.requested_model,
            processing_seconds=total_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=None,
            success=True,
            provenance={
                "requested_model": adapter.requested_model,
                "actual_model": adapter.actual_model,
                "fallback_occurred": adapter.fallback_occurred,
                "extraction_calls": 1,
                "summary_calls": 0,
                "grounding_rejected_count": scored.grounding_rejected_count,
            },
        )


__all__ = ["Coordinator"]
