"""Parallel Layer 3 dispatch and failure isolation."""

from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import re
import time
from collections.abc import Mapping
from dataclasses import replace

from server.core.config import get_settings
from server.core.llm import get_llm_client_for_agent

from ..contracts import AgentEvaluationResult
from ..exceptions import SupervisorExecutionError
from ..provenance import sanitize_provenance

logger = logging.getLogger(__name__)


def _thaw(value):
    """Copy immutable dispatch snapshots into agent-private mutable values."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


class AgentDispatcher:
    def __init__(self, agents):
        self.agents = agents

    @staticmethod
    def _failed_result(
        *,
        agent_name,
        evaluation_id,
        document_id,
        prompt_id,
        started,
        client=None,
        provenance=None,
        exc=None,
    ):
        elapsed = max(0.0, time.perf_counter() - started)
        category = type(exc).__name__ if exc is not None else "AgentError"
        reference = (
            hashlib.sha256(str(exc).encode()).hexdigest()[:16] if exc else "unknown"
        )
        logger.warning(
            "[EVAL_TIMING] agent=%s | status=failed | seconds=%.3f | "
            "category=%s | reference=%s",
            agent_name,
            elapsed,
            category,
            reference,
        )
        return AgentEvaluationResult(
            agent_name=agent_name,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=0.0,
            criterion_scores=(),
            summary="",
            model_name=getattr(client, "model", "unknown"),
            processing_seconds=elapsed,
            token_count=0,
            prompt_version_id=prompt_id,
            success=False,
            error_message=f"{category} (reference: {reference})",
            provenance=_thaw(provenance) if agent_name == "itso" else None,
        )

    @staticmethod
    def _sanitize_returned_failure(
        result: AgentEvaluationResult,
    ) -> AgentEvaluationResult:
        """Keep structured failure fields while removing untrusted diagnostics."""
        safe_match = re.fullmatch(
            r"(GADExecutionFailure|AgentReportedFailure) \(reference: ([0-9a-f]{16})\)",
            result.error_message or "",
        )
        if safe_match:
            category, reference = safe_match.group(1), safe_match.group(2)
        else:
            raw = (
                "|".join(
                    str(value)[:2000]
                    for value in (
                        result.error_message,
                        result.raw_response,
                        result.summary,
                    )
                    if value is not None
                )
                or "agent reported failure"
            )
            category = "AgentReportedFailure"
            reference = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return replace(
            result,
            subtotal=0.0,
            criterion_scores=(),
            success=False,
            summary="",
            token_count=0,
            error_message=f"{category} (reference: {reference})",
            raw_response=None,
            metadata={},
            advisory_outputs=None,
            provenance=sanitize_provenance(_thaw(result.provenance)),
        )

    def _run_single_agent(
        self,
        *,
        agent,
        agent_name,
        evaluation_id,
        document_id,
        chunk_infos,
        context_text,
        prompt_row,
        reference_document_ids,
        precomputed_context,
        provenance=None,
        policy_evidence=None,
        roadmap_context=None,
    ):
        started = time.perf_counter()
        client = None
        try:
            client = get_llm_client_for_agent(agent_name)
            kwargs = {
                "evaluation_id": evaluation_id,
                "document_id": document_id,
                "chunk_infos": _thaw(chunk_infos),
                "context_text": context_text,
                "prompt_version": prompt_row.prompt_text,
                "prompt_version_id": prompt_row.version_id,
                "reference_document_ids": _thaw(reference_document_ids),
                "precomputed_context": _thaw(precomputed_context),
                "llm_client": client,
            }
            if agent_name == "itso":
                kwargs.update(
                    llm_temperature=get_settings().get_agent_temperature("itso"),
                    provenance=_thaw(provenance),
                    policy_evidence=_thaw(policy_evidence),
                )
            elif agent_name == "coordinator":
                kwargs["roadmap_context"] = _thaw(roadmap_context)
            result = agent.run(**kwargs)
            if not isinstance(result, AgentEvaluationResult):
                raise TypeError("agent returned an invalid result contract")
            if (
                result.agent_name != agent_name
                or result.evaluation_id != evaluation_id
                or result.document_id != document_id
                or result.prompt_version_id != prompt_row.version_id
            ):
                raise ValueError("agent returned an invalid result identity")
            if not result.success:
                result = self._sanitize_returned_failure(result)
                reference = (result.error_message or "").rsplit(" ", 1)[-1].rstrip(")")
                logger.warning(
                    "[EVAL_TIMING] agent=%s | status=failed | seconds=%.3f | "
                    "category=AgentReportedFailure | reference=%s",
                    agent_name,
                    max(0.0, time.perf_counter() - started),
                    reference,
                )
                return result
            logger.info(
                "[EVAL_TIMING] agent=%s | status=ok | seconds=%.3f | parallel=true",
                agent_name,
                time.perf_counter() - started,
            )
            return result
        except Exception as exc:
            return self._failed_result(
                agent_name=agent_name,
                evaluation_id=evaluation_id,
                document_id=document_id,
                prompt_id=prompt_row.version_id,
                started=started,
                client=client,
                provenance=provenance,
                exc=exc,
            )

    def dispatch(
        self,
        *,
        evaluation_id,
        document_id,
        chunk_infos,
        context_text,
        prompt_versions,
        reference_document_ids,
        precomputed_context,
        provenance,
        policy_evidence,
        roadmap_context,
    ):
        results, failures, pending = [], {}, {}
        snapshots = {
            "chunk_infos": chunk_infos,
            "reference_document_ids": reference_document_ids,
            "precomputed_context": precomputed_context,
            "provenance": provenance,
            "policy_evidence": policy_evidence,
            "roadmap_context": roadmap_context,
        }
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, len(self.agents))
        ) as pool:
            for agent in self.agents:
                name = getattr(agent, "agent_name", agent.__class__.__name__)
                prompt = prompt_versions.get(name)
                if prompt is None:
                    raise SupervisorExecutionError(
                        f"No active prompt found for agent {name}"
                    )
                started = time.perf_counter()
                future = pool.submit(
                    self._run_single_agent,
                    agent=agent,
                    agent_name=name,
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    chunk_infos=snapshots["chunk_infos"],
                    context_text=context_text,
                    prompt_row=prompt,
                    reference_document_ids=snapshots["reference_document_ids"],
                    precomputed_context=snapshots["precomputed_context"],
                    provenance=snapshots["provenance"] if name == "itso" else None,
                    policy_evidence=(
                        snapshots["policy_evidence"] if name == "itso" else None
                    ),
                    roadmap_context=(
                        snapshots["roadmap_context"] if name == "coordinator" else None
                    ),
                )
                pending[future] = (name, prompt, started)
            for future in concurrent.futures.as_completed(pending):
                name, prompt, started = pending[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = self._failed_result(
                        agent_name=name,
                        evaluation_id=evaluation_id,
                        document_id=document_id,
                        prompt_id=prompt.version_id,
                        started=started,
                        provenance=snapshots["provenance"] if name == "itso" else None,
                        exc=exc,
                    )
                if not isinstance(result, AgentEvaluationResult):
                    result = self._failed_result(
                        agent_name=name,
                        evaluation_id=evaluation_id,
                        document_id=document_id,
                        prompt_id=prompt.version_id,
                        started=started,
                        provenance=snapshots["provenance"] if name == "itso" else None,
                        exc=TypeError("agent returned an invalid result contract"),
                    )
                results.append(result)
                if not result.success:
                    failures[name] = result.error_message or "agent failed"
        return results, failures
