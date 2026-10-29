"""Thin Layer 3 coordinator for multi-agent evaluation."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any

from equiped_harness.contracts.references import PolicyEvidenceSnapshot
from equiped_harness.contracts.snapshots import EvaluationFormSnapshotDTO
from equiped_harness.exceptions import SupervisorExecutionError
from equiped_harness.policy import get_policy_plan
from equiped_harness.registry import AGENT_IDS, get_agent_class
from server.modules.documents.models import DocumentChunk
from server.modules.embeddings.policy_context import (
    PolicyContextLoader,
)
from server.modules.evaluations.context import EvaluationContextBuilder
from server.modules.evaluations.dispatch import AgentDispatcher
from server.modules.evaluations.execution_result import SupervisorResult

logger = logging.getLogger(__name__)


class Supervisor:
    def __init__(
        self, *, agents: list[Any] | None = None, db: Any | None = None
    ) -> None:
        self.db = db
        self.agents = agents or [get_agent_class(name)() for name in AGENT_IDS]

    def run_evaluation(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunks: list[DocumentChunk],
        form_snapshots: tuple[EvaluationFormSnapshotDTO, ...],
        query_text: str | None = None,
        context: dict[str, Any] | None = None,
        heartbeat_callback: Callable[[], None] | None = None,
        lora_by_agent: Mapping[str, Sequence[Mapping] | None] | None = None,
    ) -> SupervisorResult:
        started = time.perf_counter()
        context = context or {}
        context = {**context, "document_id": document_id}
        prepared = EvaluationContextBuilder(self.db, self.agents).build(
            chunks=chunks,
            query_text=query_text,
            context=context,
            form_snapshots=form_snapshots,
        )
        policy_plan = next(
            (
                plan
                for snapshot in form_snapshots
                if (
                    plan := get_policy_plan(snapshot.agent_id, snapshot.adapter_version)
                )
                is not None
            ),
            None,
        )
        if policy_plan is not None:
            evidence = PolicyContextLoader(self.db).build_policy_context(policy_plan)
        else:
            evidence = PolicyEvidenceSnapshot(
                provenance=MappingProxyType({}), policy_evidence=MappingProxyType({})
            )
        # All authorized local reads are complete before worker-owned tool/model I/O.
        # Release the transaction; never send this session or attached rows to workers.
        if self.db is not None and callable(getattr(self.db, "commit", None)):
            self.db.commit()
        results, failures = AgentDispatcher(self.agents).dispatch(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=prepared.chunk_infos,
            form_snapshots=form_snapshots,
            context_text=prepared.query_text,
            prompt_versions=prepared.prompt_versions,
            reference_document_ids=prepared.reference_document_ids,
            precomputed_context=prepared.precomputed_context,
            provenance=evidence.provenance,
            policy_evidence=evidence.policy_evidence,
            roadmap_context=context.get("roadmap"),
            canonical_source_text=prepared.canonical_source_text,
            authoritative_curriculum_text=prepared.authoritative_curriculum_text,
            source_retrieval=prepared.source_retrieval,
            heartbeat_callback=heartbeat_callback,
            lora_by_agent=lora_by_agent,
        )
        logger.info(
            "[EVAL_TIMING] phase=evaluation_total | seconds=%.3f | "
            "agents=%d | failures=%d",
            time.perf_counter() - started,
            len(results),
            len(failures),
        )
        if not results:
            raise SupervisorExecutionError("No usable agent outputs were produced")
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=results,
            failures=failures,
        )


__all__ = ["Supervisor", "SupervisorResult"]
