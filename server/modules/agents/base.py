"""Shared agent base for retrieval and local LLM calls."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from contextlib import contextmanager
from typing import Any

from server.core.config import get_settings
from server.core.llm import get_llm_client, get_llm_model_name
from server.modules.embeddings.collections import resolve_collection_name
from server.modules.embeddings.retrieval import retrieve_context
from server.modules.rubrics.service import get_active_rubric_context

from .contracts import AgentEvaluationResult, CriterionScore
from .exceptions import AgentExecutionError, AgentLLMError

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Lightweight timing helper (local, no external deps)
# ------------------------------------------------------------------

class _PhaseTimer:
    """Accumulate named phase durations for a single agent run."""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self.phases: dict[str, float] = {}

    @contextmanager
    def measure(self, phase: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - t0
            self.phases[phase] = self.phases.get(phase, 0.0) + elapsed

    def log_summary(self, prompt_chars: int = 0, parse_error: str = "") -> None:
        parts = [f"agent={self.agent_name}"]
        for phase, secs in self.phases.items():
            parts.append(f"{phase}={secs:.3f}s")
        if prompt_chars:
            parts.append(f"prompt_chars={prompt_chars}")
        if parse_error:
            parts.append(f"parse_error={parse_error}")
        logger.info("[EVAL_TIMING] %s", " | ".join(parts))


class BaseAgent:
    """Base implementation for domain-specialized evaluation agents."""

    agent_name: str = "base"
    rubric_source_type: str = "rubric_sme"
    reference_source_types: tuple[str, ...] = ("syllabus", "curriculum")
    max_rubric_chunks: int = 5
    max_reference_chunks: int = 5

    # Domain-specific keywords for deterministic chunk selection.
    # Subclasses override this to bias toward relevant chunks.
    domain_keywords: tuple[str, ...] = ()

    def __init__(self, *, llm_client: Any | None = None) -> None:
        self._llm_client = llm_client

    # ------------------------------------------------------------------
    # Per-agent prompt packing (Phase 1, deterministic)
    # ------------------------------------------------------------------

    @staticmethod
    def _excerpt_text(text: str, max_chars: int) -> str:
        """Truncate chunk text to a safe excerpt length."""
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rstrip() + "..."

    def _score_chunk(self, chunk_text: str) -> float:
        """Score a chunk by domain keyword overlap (deterministic)."""
        if not self.domain_keywords:
            return 0.0
        lower_text = chunk_text.lower()
        score = sum(1.0 for kw in self.domain_keywords if kw in lower_text)
        return score

    def _select_chunks(
        self,
        chunk_infos: list[dict[str, Any]],
        *,
        max_chunks: int,
        small_doc_threshold: int,
    ) -> list[dict[str, Any]]:
        """Select a bounded subset of chunks for this agent.

        For small documents (below threshold), all chunks pass through.
        For larger documents, chunks are scored by domain keyword overlap
        and the top-N are selected. Ties are broken by original order.
        """
        if len(chunk_infos) <= small_doc_threshold:
            return chunk_infos

        scored = [
            (idx, self._score_chunk(info.get("text", "")), info)
            for idx, info in enumerate(chunk_infos)
        ]
        scored.sort(key=lambda t: (-t[1], t[0]))
        selected = [info for _, _, info in scored[:max_chunks]]
        selected.sort(key=lambda info: chunk_infos.index(info))
        return selected

    def _pack_chunks(
        self,
        chunk_infos: list[dict[str, Any]],
        *,
        max_chunks: int,
        max_excerpt_chars: int,
        prompt_budget_chars: int,
        small_doc_threshold: int,
    ) -> tuple[list[dict[str, Any]], bool, bool]:
        """Apply per-agent caps and return (packed_chunks, chunks_dropped, text_excerpted).

        - chunks_dropped: True when fewer chunks are sent than the original count.
        - text_excerpted: True when any chunk text was shortened from its original.
        """
        is_small_doc = len(chunk_infos) <= small_doc_threshold

        # Step 1: Select chunks (small docs pass through unchanged).
        selected = self._select_chunks(
            chunk_infos,
            max_chunks=max_chunks,
            small_doc_threshold=small_doc_threshold,
        )
        chunks_dropped = len(selected) < len(chunk_infos)

        # Step 2: Build packed list. Small docs skip excerpting entirely.
        packed: list[dict[str, Any]] = []
        text_excerpted = False
        for info in selected:
            original_text = str(info.get("text", ""))
            if is_small_doc:
                packed_text = original_text
            else:
                packed_text = self._excerpt_text(original_text, max_excerpt_chars)
                if len(packed_text) < len(original_text):
                    text_excerpted = True
            packed.append(
                {
                    "chunk_id": info.get("chunk_id", ""),
                    "page_number": info.get("page_number"),
                    "text": packed_text,
                }
            )

        # Step 3: Budget guard — enforce after serialization, loop until fit.
        # Handles both multi-chunk and single-chunk over-budget cases.
        if not packed:
            return packed, chunks_dropped, text_excerpted

        packed_json = json.dumps(packed, ensure_ascii=False)
        if len(packed_json) > prompt_budget_chars:
            # Iteratively shrink until the serialized payload fits the budget.
            while len(packed_json) > prompt_budget_chars and packed:
                if len(packed) > 1:
                    # Drop the lowest-scoring chunk first.
                    packed.pop()
                else:
                    # Single chunk: hard-trim its text to fit.
                    # Account for JSON overhead (keys, braces, quotes).
                    overhead = len(packed_json) - len(packed[0]["text"])
                    safe_text_len = max(prompt_budget_chars - overhead - 3, 50)
                    packed[0]["text"] = self._excerpt_text(
                        packed[0]["text"], safe_text_len,
                    )
                    text_excerpted = True
                packed_json = json.dumps(packed, ensure_ascii=False)
            if not packed:
                # Edge case: even an empty list exceeds budget (shouldn't happen
                # with reasonable budgets, but guard defensively).
                return [], chunks_dropped, text_excerpted
            chunks_dropped = True

        return packed, chunks_dropped, text_excerpted

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
        db: Any | None = None,
    ) -> AgentEvaluationResult:
        start = time.perf_counter()
        timer = _PhaseTimer(self.agent_name)
        parse_error = ""
        prompt_chars = 0
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        chunk_texts = [str(chunk.get("text", "")) for chunk in chunk_infos if chunk.get("text")]
        if not chunk_texts:
            raise AgentExecutionError("document chunks are required for evaluation")

        query_text = "\n".join(chunk_texts)

        with timer.measure("retrieval"):
            rubric_context = self._retrieve_rubric_context(
                query_text,
                precomputed_context=precomputed_context,
                db=db,
            )
            reference_context = self._retrieve_reference_context(
                context_text or query_text,
                reference_document_ids=reference_document_ids,
                precomputed_context=precomputed_context,
            )

        with timer.measure("prompt_build"):
            prompt = self._build_prompt(
                chunk_infos=chunk_infos,
                rubric_context=rubric_context,
                reference_context=reference_context,
                reference_text=reference_text,
                prompt_version=prompt_version,
            )
        prompt_chars = len(prompt)

        with timer.measure("llm_call"):
            raw_response = self._call_llm(prompt)

        with timer.measure("parse"):
            try:
                parsed = self._parse_response(raw_response)
            except AgentExecutionError as exc:
                # First-line recovery: if the response failed JSON parsing
                # (most likely truncated by the max_new_tokens budget), make a
                # single low-risk repair call before giving up. All other
                # failure modes (validation, schema) keep existing behavior.
                if not isinstance(exc.__cause__, json.JSONDecodeError):
                    parse_error = str(exc)
                    raise AgentExecutionError(
                        f"{exc}: raw_response={raw_response[:500]}"
                    ) from exc

                logger.warning(
                    "Agent %s: initial JSON parse failed, attempting single "
                    "repair call: %s",
                    self.agent_name,
                    exc.__cause__,
                )
                with timer.measure("llm_repair"):
                    try:
                        repair_response = self._call_llm(
                            self._build_repair_prompt(raw_response)
                        )
                    except AgentLLMError as repair_exc:
                        parse_error = f"repair call failed: {repair_exc}"
                        raise AgentExecutionError(
                            f"{exc}: raw_response={raw_response[:500]}"
                        ) from repair_exc
                try:
                    parsed = self._parse_response(repair_response)
                except AgentExecutionError as repair_exc:
                    parse_error = f"repair parse failed: {repair_exc}"
                    raise AgentExecutionError(
                        f"{exc}: raw_response={raw_response[:500]}"
                    ) from repair_exc
                # Repair succeeded — use the repaired response downstream so
                # the stored raw_response and timing reflect the recovered run.
                raw_response = repair_response

        processing_seconds = time.perf_counter() - start

        with timer.measure("parse"):
            try:
                criterion_scores = tuple(self._build_criterion_scores(parsed))
            except AgentExecutionError as exc:
                parse_error = str(exc)
                raise AgentExecutionError(
                    f"{exc}: raw_response={raw_response[:500]}"
                ) from exc

        subtotal = (
            sum(score.score for score in criterion_scores) / len(criterion_scores)
            if criterion_scores
            else 0.0
        )
        token_count = sum(len(text.split()) for text in chunk_texts)

        timer.log_summary(prompt_chars=prompt_chars, parse_error=parse_error)

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
        db: Any | None = None,
    ) -> list[str]:
        source_type = self.rubric_source_type
        if precomputed_context and source_type in precomputed_context:
            return precomputed_context[source_type]
        try:
            rubric_context = get_active_rubric_context(source_type.replace("rubric_", ""), db=db)
            if rubric_context:
                return rubric_context[: self.max_rubric_chunks * 10]
        except Exception:
            return []
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
        settings = get_settings()
        packed_chunks, chunks_dropped, text_excerpted = self._pack_chunks(
            chunk_infos,
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=settings.agent_prompt_budget_chars,
            small_doc_threshold=settings.agent_small_doc_threshold,
        )
        payload = {
            "agent": self.agent_name,
            "prompt_version": prompt_version,
            "document_chunks": packed_chunks,
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
        if chunks_dropped or text_excerpted:
            parts = []
            if chunks_dropped:
                parts.append(
                    "Only a subset of chunks was included due to document size."
                )
            if text_excerpted:
                parts.append(
                    "Some chunk texts were excerpted (truncated) to fit context limits."
                )
            parts.append("Focus on the provided excerpts.")
            payload["note"] = " ".join(parts)
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

    # Concise repair prompt for truncated/invalid JSON recovery. Keeps the
    # model focused on completion rather than re-prompting with the full
    # context, which would waste tokens.
    # Note: literal braces in the schema hint are escaped ({{ ... }}) so
    # str.format() does not interpret them as placeholders.
    _REPAIR_PROMPT_TEMPLATE = (
        "Your previous JSON response was truncated or invalid. "
        "Continue or repair it, returning ONLY a complete valid JSON object "
        "with the same fields (summary: string, criterion_scores: array of "
        "{{criterion_id, score 1-4, justification, chunk_ids, evidence}}). "
        "Prior partial output:\n\n{partial}"
    )

    def _build_repair_prompt(self, partial_response: str) -> str:
        """Build a concise repair prompt embedding the prior partial output.

        Caps the embedded partial text so a runaway model output doesn't
        blow the repair prompt budget. The cap mirrors the bounded nature
        of the original prompt and is more than enough to recover from
        typical truncation at the end of a JSON object.
        """
        max_partial_chars = 4000
        partial = partial_response or ""
        if len(partial) > max_partial_chars:
            partial = partial[: max_partial_chars - 3].rstrip() + "..."
        return self._REPAIR_PROMPT_TEMPLATE.format(partial=partial)

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
