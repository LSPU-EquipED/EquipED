"""Public facade for specialist-owned policy preparation plans."""

from __future__ import annotations

from equiped_harness.contracts.references import PolicyRetrievalPlan


def get_policy_plan(agent_id: str, adapter_version: int) -> PolicyRetrievalPlan | None:
    """Return the specialist's policy plan, importing only that agent's policy."""
    if agent_id == "itso" and adapter_version == 3:
        from equiped_harness.agents.itso.policy import get_itso_policy_plan

        return get_itso_policy_plan(adapter_version)
    return None


def format_policy_snapshot(plan, results, *, delivery_state: str):
    """Dispatch plan-specific formatting without loading unrelated agents."""
    if plan.agent_id == "itso":
        from equiped_harness.agents.itso.policy import build_policy_snapshot

        return build_policy_snapshot(plan, results, delivery_state=delivery_state)
    raise ValueError(f"unsupported policy plan kind: {plan.agent_id}")


def empty_policy_snapshot(plan, *, status: str, delivery_state: str):
    if plan.agent_id == "itso":
        from equiped_harness.agents.itso.policy import empty_policy_snapshot as build

        return build(plan, status=status, delivery_state=delivery_state)
    raise ValueError(f"unsupported policy plan kind: {plan.agent_id}")


__all__ = [
    "PolicyRetrievalPlan",
    "empty_policy_snapshot",
    "format_policy_snapshot",
    "get_policy_plan",
]
