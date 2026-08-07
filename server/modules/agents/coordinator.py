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

import dataclasses
import json
import logging
import time
import uuid
from typing import Any

from server.core.llm import get_llm_client, get_llm_model_name
from server.modules.embeddings.collections import COL_REFERENCE_ALL
from server.modules.embeddings.retrieval import retrieve_context

from .contracts import AgentEvaluationResult, CriterionScore
from .engine_scoring import EngineScoredAgent
from .exceptions import AgentExecutionError
from .scoring import curriculum_alignment, objective_alignment, skeleton

logger = logging.getLogger(__name__)

_CURRICULUM_N_RESULTS = 3


def _format_roadmap_note(roadmap_context: dict[str, Any] | None) -> str:
    """Compact advisory sentence(s) from a program-roadmap context dict.

    Produces a short note like: "Program roadmap places this course at Year
    {year} Semester {semester} with {competency_stage} competency; prescribed
    tech stack: {tech_stack}." Optional pieces (semester, tech_stack,
    competency_stage) are omitted when None. An empty dict (or None) yields an
    empty string, and any non-dict value returns "" rather than raising.
    Purely advisory -- never affects scoring.
    """
    if not isinstance(roadmap_context, dict) or not roadmap_context:
        return ""

    year = roadmap_context.get("year")
    semester = roadmap_context.get("semester")
    tech_stack = roadmap_context.get("tech_stack")
    competency_stage = roadmap_context.get("competency_stage")

    position = ""
    if year is not None:
        semester_part = f" Semester {semester}" if semester is not None else ""
        position = f"Year {year}{semester_part}"

    stage_part = (
        f" with {competency_stage} competency" if competency_stage else ""
    )
    tech_part = f" prescribed tech stack: {tech_stack}" if tech_stack else ""

    if not position and not stage_part and not tech_part:
        return ""

    body = f"{position}{stage_part}"
    if tech_part:
        body = f"{body};{tech_part}".rstrip("; ")
    return f"Program roadmap places this course at {body}."


def _build_alignment_summary(criterion_scores: tuple[CriterionScore, ...]) -> str:
    """Summarize objective-to-curriculum alignment from Coordinator's own
    A-05 score.

    A-05 is the one criterion Coordinator always computes independently
    (curriculum-grounded when a curriculum is attached, SLM-only otherwise --
    see ``run()``), so it's the only source of Coordinator-specific insight;
    the other 9 scores are reused from SME (see ``merge_with_sme``) and
    would misrepresent Coordinator's own review if summarized here.
    """
    a05 = next((c for c in criterion_scores if c.criterion_id == "A-05"), None)
    if a05 is None:
        return ""
    return f"Objective-curriculum alignment: {a05.justification}"


def _build_llm_alignment_summary(
    criterion_scores: tuple[CriterionScore, ...],
    client: Any,
) -> str:
    """LLM-written Coordinator summary: a positive observation first (which
    may cite ANY strong criterion across the full merged rubric, not just
    A-05), then the single area most in need of improvement -- Coordinator's
    own objective-curriculum alignment (A-05) when it has a real gap,
    otherwise the weakest-scoring criterion elsewhere.

    Requires the FULL merged 10-criterion set to let the positive line draw
    on more than A-05 -- callers with only A-05 available (e.g. Coordinator's
    own ``run()``, before SME's scores are merged in) should not call this;
    use ``_build_alignment_summary`` instead and let the merge step upgrade
    it later. The LLM only rephrases facts already computed by the engine
    (scores and their justifications); it is not asked to score anything.
    Falls back to the deterministic ``_build_alignment_summary`` text (A-05
    only) if the call fails, the response isn't valid JSON, or no client is
    available -- a summary-generation failure must never take down
    Coordinator's result.
    """
    fallback = _build_alignment_summary(criterion_scores)
    a05 = next((c for c in criterion_scores if c.criterion_id == "A-05"), None)
    if a05 is None or client is None:
        return fallback

    others = sorted(
        (c for c in criterion_scores if c.criterion_id != "A-05"),
        key=lambda c: -c.score,
    )
    others_context = [
        {"criterion": c.criterion_title, "score": c.score, "note": c.justification}
        for c in others
    ]

    prompt = json.dumps(
        {
            "task": "Write a 2-sentence Program Coordinator review comment "
            "using ONLY these facts -- invent nothing.",
            "your_criterion": {
                "name": "Objective-Curriculum Alignment",
                "score": a05.score,
                "note": a05.justification,
            },
            "other_rubric_context": others_context,
            "score_scale": "1=Poor, 4=Very Satisfactory",
            "structure": "Sentence 1 = positive (your_criterion or the "
            "best entry in other_rubric_context). Sentence 2 = area to "
            "improve (your_criterion if it has a real gap, else the "
            "lowest-scoring entry in other_rubric_context).",
            "style": "Terse, qualitative, no raw numbers/percentages, no "
            "filler openers. Example: 'Objectives are well-aligned with "
            "the curriculum. Assessment types are limited; more variety "
            "would strengthen coverage.'",
            "instructions": 'Return ONLY valid JSON: {"summary": "..."}.',
        },
        ensure_ascii=False,
    )

    try:
        raw = client.generate(prompt, temperature=0.3, max_new_tokens=220)
        payload = raw.strip()
        if payload.startswith("```"):
            payload = payload.strip("`")
            if payload.lower().startswith("json"):
                payload = payload[4:]
        parsed = json.loads(payload.strip())
        summary = parsed.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    except Exception as exc:
        logger.warning(
            "Coordinator LLM summary generation failed, using deterministic "
            "fallback: %s",
            str(exc)[:200],
        )
    return fallback


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

        if llm_client is not None:
            self._llm_client = llm_client

        start = time.perf_counter()
        full_text = self._resolve_full_text(document_id, context_text, chunk_infos)
        if not full_text.strip():
            raise AgentExecutionError("no document text available for evaluation")

        curriculum_id = (reference_document_ids or {}).get("curriculum")
        curriculum_text = ""
        if curriculum_id is not None:
            try:
                curriculum_text = self._prepare_curriculum_text(
                    document_id, curriculum_id, db
                )
            except Exception as exc:
                # Retrieval failure is additive-only -- fall back to plain
                # SLM-only A-05, same as if no curriculum were attached.
                logger.warning(
                    "Coordinator curriculum retrieval failed, scoring A-05 "
                    "SLM-only: %s",
                    str(exc)[:200],
                )
                curriculum_text = ""

        client = self._llm_client or get_llm_client()
        roadmap_note = None
        if roadmap_context:
            try:
                roadmap_note = _format_roadmap_note(roadmap_context) or None
            except Exception:
                roadmap_note = None
        basket = skeleton.extract_basket_a1(
            client,
            full_text,
            curriculum_text=curriculum_text or None,
            roadmap_context=roadmap_note,
        )
        objectives = list(basket.get("objectives", []))

        if curriculum_text and basket.get("curriculum_alignment"):
            scored = curriculum_alignment.compute(
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
            model_name=getattr(client, "model", get_llm_model_name()),
            processing_seconds=total_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=prompt_version_id,
            success=True,
        )

    @staticmethod
    def merge_with_sme(
        coordinator_result: AgentEvaluationResult,
        sme_result: AgentEvaluationResult,
        *,
        llm_client: Any | None = None,
    ) -> AgentEvaluationResult:
        """Splice SME's 9 non-A-05 scores with Coordinator's own A-05 score.

        No I/O beyond one optional LLM call: the summary is generated here
        (not in Coordinator's own ``run()``) specifically because this is
        the first point where the FULL 10-criterion context exists --
        letting the summary's positive line cite any strong criterion, not
        just A-05 (see ``_build_llm_alignment_summary``). Called from
        ``evaluations/orchestrator.py`` after both agents have already
        finished running. Coordinator's and SME's rubric text is
        intentionally identical (see module docstring), so the 9 reused
        scores' titles need no re-lookup. If ``llm_client`` is ``None`` or
        the call fails, falls back to the deterministic A-05-only summary.
        """
        coordinator_a05 = next(
            (
                c
                for c in coordinator_result.criterion_scores
                if c.criterion_id == "A-05"
            ),
            None,
        )
        if coordinator_a05 is None:
            raise AgentExecutionError(
                "Coordinator's own result has no A-05 score to merge"
            )

        merged_scores = tuple(
            coordinator_a05 if c.criterion_id == "A-05" else c
            for c in sme_result.criterion_scores
        )
        subtotal = sum(c.score for c in merged_scores) / len(merged_scores)

        return dataclasses.replace(
            sme_result,
            agent_name=coordinator_result.agent_name,
            criterion_scores=merged_scores,
            subtotal=subtotal,
            summary=_build_llm_alignment_summary(merged_scores, llm_client),
            model_name=coordinator_result.model_name,
            processing_seconds=coordinator_result.processing_seconds,
            token_count=coordinator_result.token_count,
            prompt_version_id=coordinator_result.prompt_version_id,
        )

    def run_full_independent(
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
        """Full independent engine pass (6 calls, all 10 criteria).

        Used ONLY as the orchestrator's fallback when SME failed (or wasn't
        run), so Coordinator can still always produce a complete result on
        its own. Not called by Supervisor's normal parallel dispatch.
        """
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        if llm_client is not None:
            self._llm_client = llm_client
        client = self._llm_client or get_llm_client()

        curriculum_id = (reference_document_ids or {}).get("curriculum")
        curriculum_text = ""
        if curriculum_id is not None:
            try:
                curriculum_text = self._prepare_curriculum_text(
                    document_id, curriculum_id, db
                )
            except Exception as exc:
                logger.warning(
                    "Coordinator curriculum retrieval failed, scoring A-05 "
                    "SLM-only: %s",
                    str(exc)[:200],
                )
                curriculum_text = ""

        raw_baskets: dict[str, dict[str, Any]] = {}
        roadmap_note = None
        if roadmap_context:
            try:
                roadmap_note = _format_roadmap_note(roadmap_context) or None
            except Exception:
                roadmap_note = None
        basket_extract_kwargs = (
            {
                "A1": {
                    "curriculum_text": curriculum_text or None,
                    "roadmap_context": roadmap_note or None,
                }
            }
            if curriculum_text or roadmap_note
            else None
        )

        result = self._run_full_engine_scoring(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=chunk_infos,
            context_text=context_text,
            prompt_version_id=prompt_version_id,
            db=db,
            raw_baskets_out=raw_baskets,
            basket_extract_kwargs=basket_extract_kwargs,
        )

        if curriculum_text:
            try:
                result = self._apply_curriculum_alignment(
                    result=result,
                    raw_baskets=raw_baskets,
                    curriculum_text=curriculum_text,
                )
            except Exception as exc:
                logger.warning(
                    "Coordinator curriculum alignment check failed, keeping "
                    "SLM-only A-05: %s",
                    str(exc)[:200],
                )

        return dataclasses.replace(
            result,
            summary=_build_llm_alignment_summary(result.criterion_scores, client),
        )

    def _prepare_curriculum_text(
        self, document_id: uuid.UUID, curriculum_id: Any, db: Any | None
    ) -> str:
        query_text = self._slm_query_text(document_id, db)
        if not query_text:
            return ""
        return self._retrieve_curriculum_text(query_text, curriculum_id)

    def _apply_curriculum_alignment(
        self,
        *,
        result: AgentEvaluationResult,
        raw_baskets: dict[str, dict[str, Any]],
        curriculum_text: str,
    ) -> AgentEvaluationResult:
        basket_a1 = raw_baskets.get("A1", {})
        objectives = list(basket_a1.get("objectives", []))
        curriculum_alignment_rows = list(basket_a1.get("curriculum_alignment", []))
        if not objectives or not curriculum_alignment_rows:
            return result

        aligned = curriculum_alignment.compute(
            objectives, curriculum_alignment_rows, curriculum_text
        )

        original_title = next(
            (
                c.criterion_title
                for c in result.criterion_scores
                if c.criterion_id == "A-05"
            ),
            "A-05",
        )
        new_score = CriterionScore(
            criterion_id="A-05",
            criterion_title=original_title,
            score=aligned.score,
            justification=(
                f"Curriculum-grounded (coordinator-only): {aligned.aligned}/"
                f"{aligned.total_objectives} objective(s) addressed by this "
                f"course's curriculum content. Score {aligned.score}."
            ),
            chunk_ids=(),
            evidence=tuple(
                str(a.get("evidence", ""))
                for a in aligned.curriculum_alignment
                if a.get("is_addressed") and a.get("evidence")
            ),
        )

        updated_scores = tuple(
            new_score if c.criterion_id == "A-05" else c
            for c in result.criterion_scores
        )
        subtotal = sum(c.score for c in updated_scores) / len(updated_scores)

        return dataclasses.replace(
            result, criterion_scores=updated_scores, subtotal=subtotal
        )

    def _slm_query_text(self, document_id: uuid.UUID, db: Any | None) -> str:
        if db is None:
            return ""
        from server.modules.documents.models import Document

        doc = db.get(Document, document_id)
        if doc is None:
            return ""
        parts = [doc.course_code, doc.course_title or doc.title]
        return " ".join(p for p in parts if p).strip()

    def _retrieve_curriculum_text(self, query_text: str, curriculum_id: Any) -> str:
        chunks = retrieve_context(
            query_text,
            COL_REFERENCE_ALL,
            n_results=_CURRICULUM_N_RESULTS,
            document_id_filter=str(curriculum_id),
        )
        return "\n\n".join(c.text for c in chunks)


ProgramCoordinator = Coordinator


__all__ = ["Coordinator", "ProgramCoordinator"]
