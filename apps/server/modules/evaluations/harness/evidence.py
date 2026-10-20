"""Immutable, residency-gated institutional policy context for ITSO."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from server.core.config import get_settings
from server.core.endpoint_security import is_private_endpoint
from server.modules.embeddings.policy_retrieval import (
    ITSO_POLICY_MAP,
    retrieve_policy_context,
)

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

        endpoint = getattr(settings, "llm_api_base", None)
        endpoint_ok = isinstance(endpoint, str) and bool(endpoint)
        if endpoint_ok:
            endpoint_ok, _ = is_private_endpoint(endpoint)
        # Approval is the explicit feature flag; locality is an independent,
        # fail-closed technical gate. Never retrieve clauses without both.
        if delivery_state != "enabled" or not endpoint_ok:
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

    def build_policy_context(self) -> ITSOEvidenceSnapshot:
        """Build only the residency-gated policy snapshot for adapter v3."""
        policy_snapshot = self._build_policy_evidence_snapshot()
        provenance = {
            "policy_delivery_state": policy_snapshot["delivery_state"],
            "policy_evidence": policy_snapshot["provenance"],
            "policy_retrieval_version": policy_snapshot["retrieval_version"],
            "policy_trimmed": False,
        }
        return ITSOEvidenceSnapshot(
            provenance=_freeze(provenance),
            policy_evidence=_freeze(policy_snapshot.get("evidence")),
        )
