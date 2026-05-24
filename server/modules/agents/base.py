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
from .exceptions import AgentExecutionError, AgentLLMError


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
        precomputed_context: dict[str, list[str]] | None = None,
    ) -> AgentEvaluationResult:
        start = time.perf_counter()
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        chunk_texts = [str(chunk.get("text", "")) for chunk in chunk_infos if chunk.get("text")]
        if not chunk_texts:
            raise AgentExecutionError("document chunks are required for evaluation")

        query_text = "\n".join(chunk_texts)
        rubric_context = self._retrieve_rubric_context(
            query_text, precomputed_context=precomputed_context,
        )
        reference_context = self._retrieve_reference_context(
            context_text or query_text,
            reference_document_ids=reference_document_ids,
            precomputed_context=precomputed_context,
        )
        prompt = self._build_prompt(
            chunk_infos=chunk_infos,
            rubric_context=rubric_context,
            reference_context=reference_context,
            reference_text=reference_text,
            prompt_version=prompt_version,
        )
        raw_response = self._call_llm(prompt)
        try:
            parsed = self._parse_response(raw_response)
        except AgentExecutionError as exc:
            raise AgentExecutionError(
                f"{exc}: raw_response={raw_response[:500]}"
            ) from exc
        processing_seconds = time.perf_counter() - start

        try:
            criterion_scores = tuple(self._build_criterion_scores(parsed))
        except AgentExecutionError as exc:
            raise AgentExecutionError(
                f"{exc}: raw_response={raw_response[:500]}"
            ) from exc
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

    def _retrieve_rubric_context(
        self,
        query_text: str,
        *,
        precomputed_context: dict[str, list[str]] | None = None,
    ) -> list[str]:
        source_type = self.rubric_source_type
        if precomputed_context and source_type in precomputed_context:
            return precomputed_context[source_type]
        try:
            collection_name = resolve_collection_name(source_type)
            chunks = retrieve_context(
                query_text,
                collection_name,
                n_results=self.max_rubric_chunks,
            )
            return [chunk.text for chunk in chunks]
        except Exception:
            return []

    def _retrieve_reference_context(
        self,
        query_text: str,
        *,
        reference_document_ids: dict[str, uuid.UUID] | None = None,
        precomputed_context: dict[str, list[str]] | None = None,
    ) -> list[str]:
        results: list[str] = []
        for source_type in self.reference_source_types:
            # Check precomputed cache first (per-source-type, not merged).
            if precomputed_context and source_type in precomputed_context:
                results.extend(precomputed_context[source_type])
                continue
            if not reference_document_ids or source_type not in reference_document_ids:
                continue
            try:
                collection_name = resolve_collection_name(source_type)
                chunks = retrieve_context(
                    query_text,
                    collection_name,
                    n_results=self.max_reference_chunks,
                    document_id_filter=str(reference_document_ids[source_type]),
                )
                results.extend(chunk.text for chunk in chunks)
            except Exception:
                continue
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
            raise AgentLLMError(
                f"LLM call failed for {self.agent_name}: {exc}"
            ) from exc

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
        if not payload.startswith("{"):
            start = payload.find("{")
            end = payload.rfind("}")
            if start != -1 and end != -1 and end > start:
                return payload[start : end + 1].strip()
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
        if not isinstance(criterion_scores, (list, dict)):
            raise AgentExecutionError(
                f"Agent {self.agent_name} returned invalid criterion_scores"
            )
        return {"summary": summary, "criterion_scores": criterion_scores}

    def _build_criterion_scores(
        self, parsed: dict[str, Any]
    ) -> list[CriterionScore]:
        raw_scores = parsed["criterion_scores"]
        if isinstance(raw_scores, dict):
            parsed_scores = []
            for criterion_id, score_entry in raw_scores.items():
                score = score_entry
                justification = ""
                chunk_ids: tuple[str, ...] = ()
                evidence: tuple[str, ...] = ()
                if isinstance(score_entry, dict):
                    score = score_entry.get("score")
                    justification = str(score_entry.get("justification", ""))
                    evidence_value = score_entry.get("evidence", ())
                    chunk_ids_value = score_entry.get("chunk_ids", ())
                    evidence = self._normalize_text_tuple(evidence_value)
                    chunk_ids = self._normalize_text_tuple(chunk_ids_value)
                parsed_scores.append(
                    {
                        "criterion_id": criterion_id,
                        "score": score,
                        "justification": justification,
                        "chunk_ids": chunk_ids,
                        "evidence": evidence,
                    }
                )
        else:
            parsed_scores = raw_scores

        criterion_scores: list[CriterionScore] = []
        for index, item in enumerate(parsed_scores):
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
                justification = str(justification)
            if not isinstance(chunk_ids, (list, tuple)):
                chunk_ids = self._normalize_text_tuple(chunk_ids)
            if not isinstance(evidence, (list, tuple)):
                evidence = self._normalize_text_tuple(evidence)
            criterion_title = item.get("criterion_title", criterion_id)
            if not isinstance(criterion_title, str):
                criterion_title = criterion_id
            score = self._normalize_score(score)
            if score is None:
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

    def _normalize_score(self, score: Any) -> int | None:
        if isinstance(score, bool):
            return None
        if isinstance(score, int):
            return score
        if isinstance(score, float) and score.is_integer():
            return int(score)
        if isinstance(score, str):
            text = score.strip()
            try:
                numeric = float(text)
            except ValueError:
                return None
            if not numeric.is_integer():
                return None
            return int(numeric)
        return None

    def _normalize_text_tuple(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,)
        if isinstance(value, (list, tuple)):
            return tuple(str(item) for item in value)
        return ()


__all__ = ["BaseAgent"]
