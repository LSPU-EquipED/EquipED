"""Thin Layer 3 coordinator for multi-agent evaluation."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from types import MappingProxyType
from typing import Any

from server.modules.agents.itso.evidence import (
    ITSOEvidenceBuilder,
    ITSOEvidenceSnapshot,
)
from server.modules.documents.models import DocumentChunk
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO

from ..coordinator.agent import Coordinator
from ..exceptions import SupervisorExecutionError
from ..gad.agent import GAD
from ..itso.agent import ITSO
from ..sme.agent import SME
from .context import EvaluationContextBuilder
from .dispatch import AgentDispatcher
from .result import SupervisorResult

logger = logging.getLogger(__name__)


class Supervisor:
    def __init__(
        self, *, agents: list[Any] | None = None, db: Any | None = None
    ) -> None:
        self.db = db
        self.agents = agents or [
            SME(),
            Coordinator(),
            GAD(),
            ITSO(),
        ]

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
    ) -> SupervisorResult:
        started = time.perf_counter()
        context = context or {}
        context = {**context, "document_id": document_id}
        prepared = EvaluationContextBuilder(self.db, self.agents).build(
            chunks=chunks, query_text=query_text, context=context
        )
        if any(getattr(agent, "agent_name", "") == "itso" for agent in self.agents):
            evidence = ITSOEvidenceBuilder(self.db).build(prepared.chunk_infos)
        else:
            evidence = ITSOEvidenceSnapshot(
                provenance=MappingProxyType({}), policy_evidence=MappingProxyType({})
            )
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
            heartbeat_callback=heartbeat_callback,
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
