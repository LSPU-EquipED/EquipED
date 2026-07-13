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
from pathlib import Path
from typing import Any

from server.core.config import get_settings
from server.core.llm import get_llm_client, get_llm_model_name
from server.modules.rubrics.service import (
    get_active_rubric_criteria,
    resolve_rubric_agent_id,
)

from .base import BaseAgent
from .contracts import AgentEvaluationResult, CriterionScore
from .exceptions import AgentExecutionError
from .scoring import registry

logger = logging.getLogger(__name__)


class EngineScoredAgent(BaseAgent):
    """Base for agents whose full rubric is scored by the code-side engine."""

    def _load_document_text(self, document_id: uuid.UUID) -> str | None:
        """Extract the SLM's text straight from its stored PDF via PyMuPDF.

        Matches the CLI's extraction so the engine sees identical input in
        both the app and the manual tool. Returns ``None`` on any failure
        (missing file, no DB, etc.) so the caller can fall back to
        ``context_text``/joined chunk text.
        """
        try:
            import fitz  # PyMuPDF
            from server.core.database import get_session_factory
            from server.modules.documents.models import Document

            session = get_session_factory()()
            try:
                document = session.get(Document, document_id)
                file_path = getattr(document, "file_path", None) if document else None
            finally:
                session.close()

            if not file_path:
                return None
            path = Path(str(file_path))
            if not path.is_file():
                logger.warning("Engine scoring: PDF not found at %s", path)
                return None

            parts: list[str] = []
            with fitz.open(path) as pdf:
                for page in pdf:
                    parts.append(page.get_text() or "")
            return "\n".join(parts)
        except Exception as exc:
            logger.warning(
                "Engine scoring: clean PDF extraction failed, using fallback "
                "text: %s",
                str(exc)[:200],
            )
            return None

    def _resolve_full_text(
        self,
        document_id: uuid.UUID,
        context_text: str | None,
        chunk_infos: list[dict[str, Any]],
    ) -> str:
        """The SLM's clean text, or the best available fallback.

        Shared by the full engine pass and Coordinator's single-call path --
        both need identical full-text resolution, so this is pulled out to
        avoid duplicating the fallback chain.
        """
        return (
            self._load_document_text(document_id)
            or context_text
            or "\n".join(str(c.get("text", "")) for c in chunk_infos)
        )

    def _rubric_titles(self, db: Any | None) -> dict[str, str]:
        """This agent's own rubric criterion titles, keyed by code."""
        return get_active_rubric_criteria(
            resolve_rubric_agent_id(self.rubric_source_type), db=db
        )

    def _score_via_engine(
        self,
        client: Any,
        full_text: str,
        delay: float,
        raw_baskets_out: dict[str, dict[str, Any]] | None = None,
        basket_extract_kwargs: dict[str, dict[str, Any]] | None = None,
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
        forwarded to ``registry.run_grouped`` (see its docstring). Additive
        only -- SME's call site passes neither.
        """
        try:
            t0 = time.perf_counter()
            grouped = registry.run_grouped(
                client,
                full_text,
                delay=delay,
                raw_baskets_out=raw_baskets_out,
                basket_extract_kwargs=basket_extract_kwargs,
            )
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
                "per-criterion calls for every code: %s",
                self.agent_name,
                str(exc)[:200],
            )
            grouped = {}

        scores: dict[str, tuple[int, str, tuple[str, ...]]] = {}
        fallback_calls = 0
        for code in sorted(registry.REGISTERED_CODES):
            if code in grouped:
                scores[code] = grouped[code]
                continue

            if fallback_calls > 0 and delay > 0:
                time.sleep(delay)
            fallback_calls += 1
            t0 = time.perf_counter()
            try:
                scores[code] = registry.run_criterion(code, client, full_text)
            except Exception as exc:
                raise AgentExecutionError(
                    f"{self.agent_name} criterion {code} failed in both the "
                    f"grouped and per-criterion engine paths: {exc}"
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
        raw_baskets_out: dict[str, dict[str, Any]] | None = None,
        basket_extract_kwargs: dict[str, dict[str, Any]] | None = None,
    ) -> AgentEvaluationResult:
        """Full engine pass: load text, score every criterion, build a
        result. Used by SME and Coordinator.

        ``raw_baskets_out`` and ``basket_extract_kwargs``, if given, are
        forwarded to ``_score_via_engine`` (see its docstring) -- additive,
        SME's call site passes neither.
        """
        full_text = self._resolve_full_text(document_id, context_text, chunk_infos)
        if not full_text.strip():
            raise AgentExecutionError("no document text available for evaluation")

        char_count = len(full_text)
        token_estimate = max(1, char_count // 4)
        logger.info(
            "[ENGINE_TIMING] agent=%s | phase=full_start | chars=%d | token_estimate=%d",
            self.agent_name,
            char_count,
            token_estimate,
        )

        start = time.perf_counter()
        client = self._llm_client or get_llm_client()
        settings = get_settings()
        delay = int(getattr(settings, "sme_scoring_call_delay_seconds", 0) or 0)

        scores, fallback_calls = self._score_via_engine(
            client,
            full_text,
            delay,
            raw_baskets_out=raw_baskets_out,
            basket_extract_kwargs=basket_extract_kwargs,
        )
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
            model_name=getattr(client, "model", get_llm_model_name()),
            processing_seconds=total_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=prompt_version_id,
            success=True,
        )

__all__ = ["EngineScoredAgent"]
