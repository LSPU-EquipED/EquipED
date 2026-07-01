"""SME domain agent."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from server.core.config import get_settings
from server.core.llm import get_llm_client

from .base import BaseAgent
from .contracts import AgentEvaluationResult, CriterionScore
from .scoring import registry

logger = logging.getLogger(__name__)


class SME(BaseAgent):
    agent_name = "sme"
    rubric_source_type = "rubric_sme"
    domain_keywords = (
        "accuracy", "content", "knowledge", "concepts", "theory",
        "definitions", "principles", "facts", "understanding", "correct",
    )

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Run the standard agent, then (optionally) overlay the code-side
        scoring engine on registered criteria.

        The overlay is OFF by default (``sme_use_scoring_engine``). When on, the
        registered criteria (e.g. A-05, OP-02) have their LLM-picked score
        replaced by the deterministic engine's score, computed from the FULL SLM
        text (``context_text``). Everything else is untouched, so the result
        shape and all downstream consumers stay identical.
        """
        result = super().run(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=chunk_infos,
            context_text=context_text,
            **kwargs,
        )

        settings = get_settings()
        if not getattr(settings, "sme_use_scoring_engine", False):
            return result

        # Prefer clean text extracted straight from the stored PDF (identical to
        # what the CLI reads). The chunk-join in ``context_text`` contains overlap
        # duplication from ingestion, which shifts the engine's slice and can flip
        # a boundary score -- so it is only a last-resort fallback.
        full_text = (
            self._load_document_text(document_id)
            or context_text
            or "\n".join(str(c.get("text", "")) for c in chunk_infos)
        )
        if not full_text.strip():
            logger.warning("SME scoring engine enabled but no full text available")
            return result

        return self._overlay_engine_scores(result, full_text, settings)

    def _load_document_text(self, document_id: uuid.UUID) -> str | None:
        """Extract the SLM's text straight from its stored PDF via PyMuPDF.

        Matches the CLI's extraction so the engine sees identical input in both
        the app and the manual tool. Returns ``None`` on any failure (missing
        file, no DB, etc.) so the caller can fall back to the chunk-join.
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
                logger.warning("SME engine: PDF not found at %s", path)
                return None

            parts: list[str] = []
            with fitz.open(path) as pdf:
                for page in pdf:
                    parts.append(page.get_text() or "")
            return "\n".join(parts)
        except Exception as exc:
            logger.warning(
                "SME engine: clean PDF extraction failed, using fallback text: %s",
                str(exc)[:200],
            )
            return None

    def _overlay_engine_scores(
        self,
        result: AgentEvaluationResult,
        full_text: str,
        settings: Any,
    ) -> AgentEvaluationResult:
        client = self._llm_client or get_llm_client()
        delay = int(getattr(settings, "sme_scoring_call_delay_seconds", 0) or 0)

        new_scores: list[CriterionScore] = []
        engine_calls = 0
        for score in result.criterion_scores:
            if not registry.is_registered(score.criterion_id):
                new_scores.append(score)
                continue

            # Intra-SME pacing: wait before each engine call except the first.
            if engine_calls > 0 and delay > 0:
                time.sleep(delay)
            engine_calls += 1

            try:
                band, justification, evidence = registry.run_criterion(
                    score.criterion_id, client, full_text
                )
                new_scores.append(
                    replace(
                        score,
                        score=band,
                        justification=justification,
                        evidence=evidence,
                        chunk_ids=(),  # engine works on full text, not chunks
                    )
                )
                logger.info(
                    "[SME_ENGINE] criterion=%s | old=%d | new=%d",
                    score.criterion_id,
                    score.score,
                    band,
                )
            except Exception as exc:
                # Never fail the whole agent on an engine error: keep the
                # original LLM-picked score for this criterion.
                logger.warning(
                    "[SME_ENGINE] criterion=%s failed, keeping old score: %s",
                    score.criterion_id,
                    str(exc)[:200],
                )
                new_scores.append(score)

        subtotal = (
            sum(s.score for s in new_scores) / len(new_scores)
            if new_scores
            else result.subtotal
        )
        return replace(
            result,
            criterion_scores=tuple(new_scores),
            subtotal=subtotal,
        )


SMEAgent = SME


__all__ = ["SME", "SMEAgent"]
