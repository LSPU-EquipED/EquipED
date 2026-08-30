"""Deterministic domain packing for SME evaluation envelopes.

Preserves snapshot domain and criterion order, packing into at most 3
nonempty primary extraction envelopes.
"""

from __future__ import annotations

from server.modules.rubrics.contracts import (
    CriterionDefinition,
    DomainDefinition,
    LlmRubricGuidanceConfig,
)

from ..exceptions import AgentExecutionError


def domain_weight(domain: DomainDefinition) -> int:
    """Bounded character estimate of criterion metadata in a domain."""
    w = len(domain.title)
    for c in domain.criteria:
        w += len(c.criterion_code) + len(c.title) + len(c.description)
        if c.scoring_rule:
            w += len(c.scoring_rule)
        if isinstance(c.strategy_config, LlmRubricGuidanceConfig):
            w += len(c.strategy_config.guidance)
    return max(w, 1)


def pack_domains(
    domains: tuple[DomainDefinition, ...] | list[DomainDefinition],
) -> tuple[tuple[CriterionDefinition, ...], ...]:
    """Pack domains into at most 3 nonempty contiguous envelopes.

    - Non-empty domains are preserved in their exact snapshot order.
    - If non-empty domains <= 3: each domain forms one envelope (1..3 envelopes).
    - If non-empty domains > 3: partition domains into exactly 3 contiguous
      slices, minimizing maximum domain-weight load.
    """
    non_empty = [d for d in domains if len(d.criteria) > 0]
    if not non_empty:
        raise AgentExecutionError("SME snapshot contains no criteria")

    n = len(non_empty)
    if n <= 3:
        return tuple(tuple(d.criteria) for d in non_empty)

    weights = [domain_weight(d) for d in non_empty]
    best_split: tuple[int, int] | None = None
    best_cost: tuple[int, int, int, int] | None = None

    for i in range(1, n - 1):
        for j in range(i + 1, n):
            w1 = sum(weights[:i])
            w2 = sum(weights[i:j])
            w3 = sum(weights[j:])
            max_w = max(w1, w2, w3)
            imbalance = max_w - min(w1, w2, w3)
            cost = (max_w, imbalance, i, j)
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best_split = (i, j)

    assert best_split is not None
    i, j = best_split
    env1 = tuple(c for d in non_empty[:i] for c in d.criteria)
    env2 = tuple(c for d in non_empty[i:j] for c in d.criteria)
    env3 = tuple(c for d in non_empty[j:] for c in d.criteria)
    return (env1, env2, env3)


__all__ = ["domain_weight", "pack_domains"]
