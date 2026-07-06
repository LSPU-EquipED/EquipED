"""SME domain agent."""

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
        prompt_version_id: uuid.UUID | None = None,
        db: Any | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Score every SME criterion with the code-side engine directly.

        SME's rubric maps 1:1 onto ``registry.REGISTERED_CODES`` (all 10
        criteria), so there is no LLM-guesses-everything base call worth
        making first -- the engine's grouped pass (``run_grouped``) is the
        sole primary scorer. Any code its baskets didn't cover falls back to
        a dedicated per-criterion engine call (``run_criterion``). A code
        that fails both raises ``AgentExecutionError``, matching every other
        agent's all-or-nothing failure contract (the Supervisor already
        handles a raised agent by marking it failed and excluding it from
        synthesis).
        """
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        full_text = (
            self._load_document_text(document_id)
            or context_text
            or "\n".join(str(c.get("text", "")) for c in chunk_infos)
        )
        if not full_text.strip():
            raise AgentExecutionError("no document text available for evaluation")

        start = time.perf_counter()
        client = self._llm_client or get_llm_client()
        settings = get_settings()
        delay = int(getattr(settings, "sme_scoring_call_delay_seconds", 0) or 0)

        try:
            grouped = registry.run_grouped(client, full_text, delay=delay)
        except Exception as exc:
            logger.warning(
                "[SME] grouped pass failed entirely, falling back to "
                "per-criterion calls for every code: %s",
                str(exc)[:200],
            )
            grouped = {}

        titles = get_active_rubric_criteria(
            resolve_rubric_agent_id(self.rubric_source_type), db=db
        )

        criterion_scores: list[CriterionScore] = []
        fallback_calls = 0
        for code in sorted(registry.REGISTERED_CODES):
            if code in grouped:
                band, justification, evidence = grouped[code]
            else:
                if fallback_calls > 0 and delay > 0:
                    time.sleep(delay)
                fallback_calls += 1
                try:
                    band, justification, evidence = registry.run_criterion(
                        code, client, full_text
                    )
                except Exception as exc:
                    raise AgentExecutionError(
                        f"SME criterion {code} failed in both the grouped and "
                        f"per-criterion engine paths: {exc}"
                    ) from exc

            criterion_scores.append(
                CriterionScore(
                    criterion_id=code,
                    criterion_title=titles.get(code, code),
                    score=band,
                    justification=justification,
                    chunk_ids=(),  # engine works on full text, not chunks
                    evidence=evidence,
                )
            )

        subtotal = sum(s.score for s in criterion_scores) / len(criterion_scores)
        processing_seconds = time.perf_counter() - start

        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=tuple(criterion_scores),
            summary="",
            model_name=get_llm_model_name(),
            processing_seconds=processing_seconds,
            token_count=len(full_text.split()),
            prompt_version_id=prompt_version_id,
            success=True,
        )

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


SMEAgent = SME


__all__ = ["SME", "SMEAgent"]
