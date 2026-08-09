"""Program coordinator domain agent.

Coordinator's rubric is intentionally identical to SME's (see
``server/data/rubrics/rubrics.json``, agent_id="coordinator" -- same 10
codes/titles/descriptions as SME's). 9 of those 10 criteria would always
produce the same score/justification as SME's (same SLM input, same math) --
paying for a second full 6-call engine pass just to arrive at an answer SME
already computed was tipping full evaluations (SME's 6 + Coordinator's 6 +
GAD's 1 + ITSO's 1 = ~14 calls) over the shared LLM rate limit.

So Coordinator now has three entry points instead of one:

- ``run()`` -- what ``Supervisor`` actually calls (dispatched in parallel with
  every other agent, unchanged). Makes exactly ONE LLM call: extracts
  objectives and scores ONLY A-05 (curriculum-aware when a curriculum
  document is attached, else identical to SME's SLM-only A-05). Returns an
  intentionally incomplete result (just A-05) -- Coordinator can't know
  whether SME will succeed while running concurrently with it, so it can't
  decide here whether reuse is even possible.
- ``merge_with_sme()`` -- pure, no I/O. Splices SME's 9 non-A-05 scores
  together with Coordinator's own A-05 score into the real, complete
  10-criterion result. Called from ``evaluations/orchestrator.py`` AFTER
  both agents have already finished (Supervisor's parallel dispatch has
  no ordering problem to solve here since synthesis already waits for
  everyone).
- ``run_full_independent()`` -- today's original full engine pass (6 calls,
  all 10 criteria), used ONLY as the orchestrator's fallback when SME failed
  (or wasn't run), so Coordinator can still always produce a complete,
  independent result on its own when reuse isn't possible.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from server.core.llm import get_llm_client, get_llm_model_name

from ..contracts import AgentEvaluationResult, CriterionScore
from ..exceptions import AgentExecutionError
from ..runtime.llm import FallbackAwareClient, error_reference
from ..sme import extraction, objective_alignment
from ..sme.pipeline import EngineScoredAgent
from . import curriculum
from .summary import _build_alignment_summary

logger = logging.getLogger(__name__)

class Coordinator(EngineScoredAgent):
    agent_name = "coordinator"
    rubric_source_type = "rubric_coord"
    reference_source_types = ("syllabus",)
    domain_keywords = (
        "program", "outcomes", "objectives", "curriculum", "alignment",
        "competencies", "learning outcomes", "course", "standards",
        "assessment", "goals",
    )

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        db: Any | None = None,
        llm_client: Any | None = None,
        reference_document_ids: dict[str, Any] | None = None,
        roadmap_context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Cheap single-call A-05 check -- called by Supervisor in parallel
        with every other agent. Only computes A-05; the other 9 criteria are
        spliced in from SME's result afterward (see ``merge_with_sme``).
        """
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        start = time.perf_counter()
        full_text = self._resolve_full_text(document_id, context_text, chunk_infos)
        if not full_text.strip():
            raise AgentExecutionError("no document text available for evaluation")

        curriculum_id = (reference_document_ids or {}).get("curriculum")
        curriculum_text = ""
        if curriculum_id is not None:
            try:
                curriculum_text = curriculum.prepare_curriculum_text(
                    self, document_id, curriculum_id, db
                )
            except Exception as exc:
                # Retrieval failure is additive-only -- fall back to plain
                # SLM-only A-05, same as if no curriculum were attached.
                logger.warning(
                    "Coordinator curriculum retrieval failed, scoring A-05 "
                    "SLM-only (category=%s, reference=%s)",
                    type(exc).__name__, error_reference(exc),
                )
                curriculum_text = ""

        client = llm_client or self._default_llm_client or get_llm_client()
        adapter = (
            client
            if isinstance(client, FallbackAwareClient)
            else FallbackAwareClient(
                client,
                self.agent_name,
                requested_model=(
                    getattr(client, "model", None) or get_llm_model_name()
                ),
            )
        )
        roadmap_note = None
        if roadmap_context:
            try:
                roadmap_note = curriculum.format_roadmap_note(roadmap_context) or None
            except Exception:
                roadmap_note = None
        basket = extraction.extract_basket_a1(
            adapter,
            full_text,
            curriculum_text=curriculum_text or None,
            roadmap_context=roadmap_note,
        )
        objectives = list(basket.get("objectives", []))

        if curriculum_text and basket.get("curriculum_alignment"):
            scored = curriculum.compute(
                objectives, list(basket["curriculum_alignment"]), curriculum_text
            )
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
            alignment_rows = list(basket.get("alignment", []))
            assessments = list(basket.get("assessments", []))
            scored = objective_alignment.compute(
                objectives, assessments, alignment_rows
            )
            justification = (
                f"{scored.aligned}/{scored.total_objectives} objective(s) "
                f"measured by this SLM's own assessments. Score {scored.score}."
            )
            evidence = tuple(
                str(a.get("evidence", ""))
                for a in alignment_rows
                if a.get("is_measured") and a.get("evidence")
            )

        titles = self._rubric_titles(db)
        criterion_score = CriterionScore(
            criterion_id="A-05",
            criterion_title=titles.get("A-05", "A-05"),
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
            # Cheap placeholder -- only A-05 is known here. merge_with_sme()
            # (or run_full_independent()) regenerates the real summary once
            # the full 10-criterion context is available, so this value
            # never reaches a user; no LLM call is worth spending on it.
            summary=_build_alignment_summary((criterion_score,)),
            model_name=adapter.actual_model or get_llm_model_name(),
            processing_seconds=total_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=prompt_version_id,
            success=True,
            provenance={
                "requested_model": adapter.requested_model,
                "actual_model": adapter.actual_model,
                "fallback_occurred": adapter.fallback_occurred,
            },
        )


    def run_full_independent(self, **kwargs: Any) -> AgentEvaluationResult:
        from .reconciliation import run_full_independent

        return run_full_independent(self, **kwargs)


__all__ = ["Coordinator"]
