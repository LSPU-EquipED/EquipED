"""SME domain agent."""

from __future__ import annotations

import uuid
from typing import Any

from .contracts import AgentEvaluationResult
from .engine_scoring import EngineScoredAgent
from .exceptions import AgentExecutionError


class SME(EngineScoredAgent):
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
        llm_client: Any | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Score every SME criterion with the code-side engine directly.

        SME's rubric maps 1:1 onto ``registry.REGISTERED_CODES`` (all 10
        criteria), so there is no LLM-guesses-everything base call worth
        making first -- the engine's grouped pass is the sole primary
        scorer, with a per-criterion fallback for anything it misses (see
        ``EngineScoredAgent._score_via_engine``). A code that fails both
        raises ``AgentExecutionError``, matching every other agent's
        all-or-nothing failure contract (the Supervisor already handles a
        raised agent by marking it failed and excluding it from synthesis).
        """
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        if llm_client is not None:
            self._llm_client = llm_client

        return self._run_full_engine_scoring(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=chunk_infos,
            context_text=context_text,
            prompt_version_id=prompt_version_id,
            db=db,
        )


SMEAgent = SME


__all__ = ["SME", "SMEAgent"]
