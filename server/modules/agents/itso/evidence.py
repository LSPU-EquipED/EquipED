"""Immutable ITSO precheck and policy evidence snapshots."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from server.core.config import get_settings
from server.modules.embeddings.policy_retrieval import (
    ITSO_POLICY_MAP,
    retrieve_policy_context,
)

from .precheck import run_itso_precheck

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ITSOEvidenceSnapshot:
    provenance: MappingProxyType | None
    policy_evidence: MappingProxyType | None


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


class ITSOEvidenceBuilder:
    _PROVENANCE_CHUNK_ID_CAP = 64
    _POLICY_RETRIEVAL_VERSION = "1"

    def __init__(self, db: Any | None = None) -> None:
        self.db = db

    def _compute_query_embedding(self, query_text: str) -> list[float] | None:
        """Encode query text once for reuse across retrieval calls."""
        if not query_text or not query_text.strip():
            return None
        try:
            from server.core.embedding import get_embedding_model

            model = get_embedding_model()
            return model.encode([query_text], show_progress_bar=False).tolist()[0]
        except Exception:
            return None

    def _precompute_itso_context(
        self,
        chunk_infos: list[dict[str, Any]],
    ) -> ITSOEvidenceSnapshot:
        """Build a frozen ITSO evidence snapshot and phase-1 provenance.

        Called once per evaluation, before agent dispatch. The result
        contains:
        - ``provenance``: phase-1 provenance dict (precheck result, chunk ids,
          rubric/prompt version context + policy evidence provenance).
        - precheck fields: bounded precheck signals embedded in provenance.
        - ``policy_evidence``: full policy evidence snapshot (for prompt
          injection — contains policy clause text, never persisted).

        This snapshot is immutable after creation and is injected into
        the ITSO agent kwargs so retries do not rebuild evidence.
        """
        if not chunk_infos:
            return ITSOEvidenceSnapshot(provenance=None, policy_evidence=None)

        # Build the SLM text for precheck from chunk texts (same ordering
        # the agent would produce).
        slm_text = "\n".join(
            str(info.get("text", "")) for info in chunk_infos if info.get("text")
        )
        precheck = run_itso_precheck(slm_text)

        # Ordered chunk identifiers (immutable snapshot, bounded).
        all_chunk_ids = [
            str(info.get("chunk_id", ""))
            for info in chunk_infos
            if info.get("chunk_id")
        ]
        chunk_ids_hash = hashlib.sha256(
            "|".join(all_chunk_ids).encode("utf-8")
        ).hexdigest()
        chunk_ids_ordered = all_chunk_ids[: self._PROVENANCE_CHUNK_ID_CAP]

        provenance: dict[str, Any] = {
            # Phase-1: frozen before dispatch.
            "precheck_version": precheck["version"],
            "precheck_result_hash": precheck["result_hash"],
            "bibliography_found": precheck["bibliography_found"],
            "reference_count": precheck["reference_count"],
            "intext_citation_count": precheck["intext_citation_count"],
            "doi_count": precheck["doi_count"],
            "coverage_ratio": precheck["coverage_ratio"],
            "chunk_ids_ordered": chunk_ids_ordered,
            "chunk_id_count": len(all_chunk_ids),
            "chunk_ids_hash": chunk_ids_hash,
        }

        # Build policy evidence snapshot (fail open, never blocks).
        policy_snapshot = self._build_policy_evidence_snapshot()
        policy_evidence = policy_snapshot.get("evidence")
        provenance["policy_delivery_state"] = policy_snapshot["delivery_state"]
        provenance["policy_evidence"] = policy_snapshot["provenance"]
        provenance["policy_retrieval_version"] = policy_snapshot[
            "retrieval_version"
        ]
        provenance["policy_trimmed"] = False

        return ITSOEvidenceSnapshot(
            provenance=_freeze(provenance),
            policy_evidence=_freeze(policy_evidence),
        )

    def _build_policy_evidence_snapshot(self) -> dict[str, Any]:
        """Build a frozen, attempt-scoped ITSO policy evidence snapshot.

        Retrieves bounded policy clauses for ITSO-03/04/05 from the local
        Chroma policy collection. The snapshot contains:
        - ``evidence``: full evidence dict with clause text for prompt injection
          (``None`` when retrieval fails or is unavailable).
        - ``provenance``: safe opaque metadata for persistence (hashes,
          statuses, counts — no raw text/IDs).
        - ``delivery_state``: ``"enabled"`` or ``"blocked"`` based on config.
        - ``retrieval_version``: version string.

        All policy retrieval errors fail open — the snapshot returns
        ``evidence=None`` with per-criterion ``unavailable`` provenance
        and the evaluation continues without policy evidence.
        """
        settings = get_settings()
        delivery_state = (
            "enabled"
            if getattr(settings, "itso_policy_delivery_enabled", False)
            else "blocked"
        )

        if delivery_state != "enabled":
            return self._empty_policy_snapshot("unavailable", "blocked")

        if self.db is None:
            return self._empty_policy_snapshot("unavailable", delivery_state)

        # Compute a single query embedding from the chunk text for reuse
        # across all three ITSO criterion queries.
        query_text = self._build_policy_query_text()
        if not query_text:
            return self._empty_policy_snapshot("unavailable", delivery_state)

        query_embedding = self._compute_query_embedding(query_text)
        if query_embedding is None:
            return self._empty_policy_snapshot("unavailable", delivery_state)

        evidence_per_criterion: dict[str, Any] = {}
        provenance_per_criterion: dict[str, Any] = {}

        for criterion_id in ("ITSO-03", "ITSO-04", "ITSO-05"):
            try:
                result = retrieve_policy_context(
                    criterion_id,
                    query_embedding,
                    self.db,
                    max_chunks=5,
                )
            except Exception:
                logger.warning("policy:retrieval criterion failed", extra={})
                evidence_per_criterion[criterion_id] = {
                    "policy_area": ITSO_POLICY_MAP.get(criterion_id, ("unknown",))[0],
                    "status": "unavailable",
                    "chunks": [],
                }
                provenance_per_criterion[criterion_id] = {
                    "status": "unavailable",
                    "chunk_count": 0,
                    "provenance_hash": hashlib.sha256(b"empty").hexdigest(),
                }
                continue

            area = ITSO_POLICY_MAP.get(criterion_id, ("unknown",))[0]
            if result.status == "available":
                evidence_per_criterion[criterion_id] = {
                    "policy_area": area,
                    "status": "available",
                    "chunks": [
                        {
                            "chunk_id": c.chunk_id,
                            "text": c.text,
                            "page_number": c.page_number,
                            "policy_area": c.policy_area,
                        }
                        for c in result.chunks
                    ],
                }
                provenance_per_criterion[criterion_id] = {
                    "status": "available",
                    "chunk_count": result.chunk_count,
                    "provenance_hash": result.provenance_hash,
                }
            else:
                evidence_per_criterion[criterion_id] = {
                    "policy_area": area,
                    "status": "unavailable",
                    "chunks": [],
                }
                provenance_per_criterion[criterion_id] = {
                    "status": "unavailable",
                    "chunk_count": 0,
                    "provenance_hash": result.provenance_hash,
                }

        return {
            "evidence": {
                "delivery_state": delivery_state,
                "retrieval_version": self._POLICY_RETRIEVAL_VERSION,
                "criteria": evidence_per_criterion,
            },
            "provenance": provenance_per_criterion,
            "delivery_state": delivery_state,
            "retrieval_version": self._POLICY_RETRIEVAL_VERSION,
        }

    def _empty_policy_snapshot(
        self,
        status: str,
        delivery_state: str,
    ) -> dict[str, Any]:
        """Return a safe empty policy snapshot when retrieval cannot proceed."""
        empty_hash = hashlib.sha256(b"empty").hexdigest()
        empty_provenance: dict[str, Any] = {}
        for cid in ("ITSO-03", "ITSO-04", "ITSO-05"):
            empty_provenance[cid] = {
                "status": status,
                "chunk_count": 0,
                "provenance_hash": empty_hash,
            }
        return {
            "evidence": None,
            "provenance": empty_provenance,
            "delivery_state": delivery_state,
            "retrieval_version": self._POLICY_RETRIEVAL_VERSION,
        }

    def _build_policy_query_text(self) -> str:
        """Build a query text for policy retrieval.

        Returns a default query targeting IT general policy areas.
        """
        return "information security data privacy intellectual property academic rights"

    def build(self, chunk_infos: list[dict[str, Any]]) -> ITSOEvidenceSnapshot:
        return self._precompute_itso_context(chunk_infos)
