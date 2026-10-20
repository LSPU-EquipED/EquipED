"""Local, residency-gated loading for library-owned policy plans."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

from equiped_harness.contracts.references import (
    PolicyEvidenceSnapshot,
    PolicyRetrievalPlan,
    PolicyRetrievalResult,
)
from equiped_harness.policy import empty_policy_snapshot, format_policy_snapshot

from server.core.config import get_settings
from server.core.endpoint_security import is_private_endpoint
from server.modules.embeddings.policy_retrieval import retrieve_policy_context

logger = logging.getLogger(__name__)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


class PolicyContextLoader:
    """Load policy evidence for an explicit immutable specialist policy plan."""

    def __init__(self, db: Any | None = None) -> None:
        self.db = db

    def _compute_query_embedding(self, query_text: str) -> list[float] | None:
        if not query_text or not query_text.strip():
            return None
        try:
            from server.core.embedding import get_embedding_model

            model = get_embedding_model()
            return model.encode([query_text], show_progress_bar=False).tolist()[0]
        except Exception:
            return None

    def _endpoint_is_local(self, settings: Any) -> bool:
        endpoint = getattr(settings, "llm_api_base", None)
        return (
            isinstance(endpoint, str)
            and bool(endpoint)
            and is_private_endpoint(endpoint)[0]
        )

    def build_policy_context(self, plan: PolicyRetrievalPlan) -> PolicyEvidenceSnapshot:
        settings = get_settings()
        delivery_state = (
            "enabled"
            if getattr(settings, "itso_policy_delivery_enabled", False)
            else "blocked"
        )

        if delivery_state != "enabled" or not self._endpoint_is_local(settings):
            snapshot = empty_policy_snapshot(
                plan, status="unavailable", delivery_state="blocked"
            )
        elif self.db is None:
            snapshot = empty_policy_snapshot(
                plan, status="unavailable", delivery_state=delivery_state
            )
        else:
            embedding = self._compute_query_embedding(plan.query_text)
            if embedding is None:
                snapshot = empty_policy_snapshot(
                    plan, status="unavailable", delivery_state=delivery_state
                )
            else:
                results: dict[str, PolicyRetrievalResult | None] = {}
                for criterion_id, policy_areas in plan.criteria_areas.items():
                    try:
                        results[criterion_id] = retrieve_policy_context(
                            policy_areas,
                            embedding,
                            self.db,
                            max_chunks=plan.max_chunks,
                        )
                    except Exception:
                        logger.warning("policy:retrieval criterion failed", extra={})
                        results[criterion_id] = None
                snapshot = format_policy_snapshot(
                    plan, results, delivery_state=delivery_state
                )

        provenance = {
            "policy_delivery_state": snapshot["delivery_state"],
            "policy_evidence": snapshot["provenance"],
            "policy_retrieval_version": snapshot["retrieval_version"],
            "policy_trimmed": False,
        }
        return PolicyEvidenceSnapshot(
            provenance=_freeze(provenance),
            policy_evidence=_freeze(snapshot.get("evidence")),
        )


__all__ = ["PolicyContextLoader"]
