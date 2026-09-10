"""Synthesis service facade re-exporting persistence, results, and matrix."""

from __future__ import annotations

from server.modules.rubrics.snapshots import load_verified_evaluation_snapshots
from server.modules.synthesis.evaluation_results import (
    _reviewer_correction_payload,
    get_evaluation_results,
)
from server.modules.synthesis.master_synthesis import get_master_synthesis_detail
from server.modules.synthesis.matrix import get_monitoring_matrix
from server.modules.synthesis.persistence import (
    _scheduled_ids_for_job,
    _validated_chunk_ids,
    load_verified_persisted_agent_results,
    persist_agent_outputs,
)

__all__ = [
    "persist_agent_outputs",
    "load_verified_persisted_agent_results",
    "load_verified_evaluation_snapshots",
    "get_evaluation_results",
    "get_monitoring_matrix",
    "get_master_synthesis_detail",
    "_scheduled_ids_for_job",
    "_validated_chunk_ids",
    "_reviewer_correction_payload",
]
