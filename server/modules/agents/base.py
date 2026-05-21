"""Shared agent base for retrieval and local LLM calls."""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from server.core.config import get_settings
from server.core.llm import get_llm_client, get_llm_model_name
from server.modules.embeddings.collections import resolve_collection_name
from server.modules.embeddings.retrieval import retrieve_context

from .contracts import AgentEvaluationResult, CriterionScore
from .exceptions import AgentExecutionError, AgentLLMError, AgentRetrievalError


class BaseAgent:
    """Base implementation for domain-specialized evaluation agents."""

    agent_name: str = "base"
    rubric_source_type: str = "rubric_sme"
    reference_source_types: tuple[str, ...] = ("syllabus", "curriculum")
    max_rubric_chunks: int = 5
    max_reference_chunks: int = 5

    def __init__(self, *, llm_client: Any | None = None) -> None:
        self._llm_client = llm_client

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        reference_text: str | None = None,
        prompt_version: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        reference_document_ids: dict[str, uuid.UUID] | None = None,
    ) -> AgentEvaluationResult:
        start = time.perf_counter()
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        chunk_texts = [str(chunk.get("text", "")) for chunk in chunk_infos if chunk.get("text")]
        if not chunk_texts:
            raise AgentExecutionError("document chunks are required for evaluation")

        rubric_context = self._retrieve_rubric_context("\n".join(chunk_texts))
        reference_context = self._retrieve_reference_context(
            context_text or "\n".join(chunk_texts),
            reference_document_ids=reference_document_ids,
        )
        prompt = self._build_prompt(
            chunk_infos=chunk_infos,
            rubric_context=rubric_context,
            reference_context=reference_context,
            reference_text=reference_text,
            prompt_version=prompt_version,
        )
        raw_response = self._call_llm(prompt)
        parsed = self._parse_response(raw_response)
        processing_seconds = time.perf_counter() - start

        criterion_scores = tuple(self._build_criterion_scores(parsed))
        subtotal = (
            sum(score.score for score in criterion_scores) / len(criterion_scores)
            if criterion_scores
            else 0.0
        )
        token_count = sum(len(text.split()) for text in chunk_texts)
        return AgentEvaluationResult(
            agent_name=self.agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=subtotal,
            criterion_scores=criterion_scores,
            prompt_version_id=prompt_version_id,
            summary=parsed.get("summary", ""),
            model_name=get_llm_model_name(),
            processing_seconds=processing_seconds,
            token_count=token_count,
            success=True,
            raw_response=raw_response,
            metadata={
                "rubric_context_size": len(rubric_context),
                "reference_context_size": len(reference_context),
                "prompt_version": prompt_version,
                "prompt_version_id": (
                    str(prompt_version_id) if prompt_version_id else None
                ),
            },
        )

    def _retrieve_rubric_context(self, query_text: str) -> list[str]:
        try:
            collection_name = resolve_collection_name(self.rubric_source_type)
            chunks = retrieve_context(
                query_text,
                collection_name,
                n_results=self.max_rubric_chunks,
            )
            return [chunk.text for chunk in chunks]
        except Exception as exc:
            raise AgentRetrievalError(
                f"Failed to retrieve rubric context for {self.agent_name}"
            ) from exc

    def _retrieve_reference_context(
        self,
        query_text: str,
        *,
        reference_document_ids: dict[str, uuid.UUID] | None = None,
    ) -> list[str]:
        results: list[str] = []
        for source_type in self.reference_source_types:
            if not reference_document_ids or source_type not in reference_document_ids:
                raise AgentExecutionError(
                    "Missing scoped reference document for "
                    f"{self.agent_name}:{source_type}"
                )
            try:
                collection_name = resolve_collection_name(source_type)
                chunks = retrieve_context(
                    query_text,
                    collection_name,
                    n_results=self.max_reference_chunks,
                    document_id_filter=str(reference_document_ids[source_type]),
                )
                results.extend(chunk.text for chunk in chunks)
            except Exception as exc:
                raise AgentRetrievalError(
                    f"Failed to retrieve reference context for {self.agent_name}"
                ) from exc
        return results

    def _build_prompt(
        self,
        *,
        chunk_infos: list[dict[str, Any]],
        rubric_context: list[str],
        reference_context: list[str],
        reference_text: str | None,
        prompt_version: str | None,
    ) -> str:
        payload = {
            "agent": self.agent_name,
            "prompt_version": prompt_version,
            "document_chunks": chunk_infos,
            "rubric_context": rubric_context,
            "reference_context": reference_context,
            "reference_text": reference_text,
            "instructions": [
                "Return JSON with summary and criterion_scores.",
                "Each criterion score must be between 1 and 4.",
                "Cite only the chunk_id values provided in document_chunks.",
                "Ground all claims in the provided context.",
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

    def _call_llm(self, prompt: str) -> str:
        client = self._llm_client or get_llm_client()
        settings = get_settings()
        try:
            return client.generate(
                prompt,
                temperature=settings.llm_temperature,
                max_new_tokens=settings.llm_max_new_tokens,
            )
        except Exception as exc:
            raise AgentLLMError(f"LLM call failed for {self.agent_name}") from exc

    def _parse_response(self, raw_response: str) -> dict[str, Any]:
        if not isinstance(raw_response, str):
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned a non-string response"
            )
        try:
            payload = self._extract_json_payload(raw_response)
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned invalid JSON"
            ) from exc
        return self._validate_response(parsed)

    def _extract_json_payload(self, raw_response: str) -> str:
        payload = raw_response.strip()
        fenced_match = re.match(
            r"^```(?:json)?\s*(.*?)\s*```$", payload, flags=re.IGNORECASE | re.DOTALL
        )
        if fenced_match:
            return fenced_match.group(1).strip()
        return payload

    def _validate_response(self, parsed: Any) -> dict[str, Any]:
        if not isinstance(parsed, dict):
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned an invalid response structure"
            )
        summary = parsed.get("summary", "")
        if not isinstance(summary, str):
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned an invalid summary"
            )
        criterion_scores = parsed.get("criterion_scores")
        if not isinstance(criterion_scores, list):
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned invalid criterion_scores"
            )
        return {"summary": summary, "criterion_scores": criterion_scores}

    def _build_criterion_scores(
        self, parsed: dict[str, Any]
    ) -> list[CriterionScore]:
        criterion_scores: list[CriterionScore] = []
        for index, item in enumerate(parsed["criterion_scores"]):
            if not isinstance(item, dict):
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned an invalid criterion score "
                    f"at index {index}"
                )
            criterion_id = item.get("criterion_id")
            score = item.get("score")
            justification = item.get("justification", "")
            chunk_ids = item.get("chunk_ids", ())
            evidence = item.get("evidence", ())
            if not isinstance(criterion_id, str) or not criterion_id:
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned an invalid criterion_id "
                    f"at index {index}"
                )
            if not isinstance(justification, str):
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned an invalid justification "
                    f"at index {index}"
                )
            if not isinstance(chunk_ids, (list, tuple)):
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned invalid chunk_ids "
                    f"at index {index}"
                )
            if not isinstance(evidence, (list, tuple)):
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned invalid evidence "
                    f"at index {index}"
                )
            criterion_title = item.get("criterion_title", criterion_id)
            if not isinstance(criterion_title, str):
                criterion_title = criterion_id
            if not isinstance(score, int):
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned an invalid score "
                    f"at index {index}"
                )
            try:
                criterion_score = CriterionScore(
                    criterion_id=criterion_id,
                    criterion_title=criterion_title,
                    score=score,
                    justification=justification,
                    chunk_ids=tuple(chunk_ids),
                    evidence=tuple(evidence),
                )
            except (TypeError, ValueError) as exc:
                raise AgentExecutionError(
                    f"Agent {self.agent_name} returned an invalid criterion score "
                    f"at index {index}"
                ) from exc
            criterion_scores.append(criterion_score)
        return criterion_scores


__all__ = ["BaseAgent"]
