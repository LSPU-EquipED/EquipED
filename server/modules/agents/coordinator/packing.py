"""Deterministic resource-affinity packing for Coordinator envelopes.

Splits the frozen snapshot into at most 3 envelopes by resource affinity
so Assessment criteria are never starved of prompt budget:

- Envelope 0: OP domain criteria (``OP-01..OP-05``) -- needs SLM source only.
- Envelope 1: SLM assessment criteria (``A-01..A-04``) -- needs SLM source
  only (no curriculum context).
- Envelope 2: Curriculum alignment criteria (``A-05``) -- needs SLM
  objectives + curriculum context.

Forms without OP/A resource structure (single domain or <= 3 domains
without a curriculum collision) preserve contiguous domain ordering with at
most 3 envelopes. The historical adapter-v1 form (single ``A-05``
criterion) yields exactly 1 envelope ``((A-05,),)``.
"""

from __future__ import annotations

from server.modules.rubrics.contracts import (
    CriterionDefinition,
    CurriculumAlignmentConfig,
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


def _is_curriculum_criterion(criterion: CriterionDefinition) -> bool:
    return criterion.criterion_code == "A-05" or isinstance(
        criterion.strategy_config, CurriculumAlignmentConfig
    )


def _is_op_criterion(criterion: CriterionDefinition) -> bool:
    return criterion.criterion_code.startswith("OP-") and not _is_curriculum_criterion(
        criterion
    )


def _is_assessment_criterion(criterion: CriterionDefinition) -> bool:
    return criterion.criterion_code.startswith("A-") and not _is_curriculum_criterion(
        criterion
    )


def pack_domains(
    domains: tuple[DomainDefinition, ...] | list[DomainDefinition],
) -> tuple[tuple[CriterionDefinition, ...], ...]:
    """Pack domains into at most 3 nonempty resource-affinity envelopes.

    - Historical adapter-v1 (single ``A-05`` criterion): 1 envelope.
    - When every criterion is classifiable as OP / A-assessment /
      curriculum (``A-05``): return the non-empty buckets in OP, assessment,
      curriculum order (1..3 envelopes). For the canonical OP + A form this
      is exactly ``((OP-01..OP-05,), (A-01..A-04,), (A-05,))``.
    - Otherwise: preserve contiguous domain ordering, max 3 envelopes --
      one envelope per domain when <= 3 non-empty domains, else partition
      into exactly 3 contiguous slices minimizing maximum domain-weight load.
    """
    non_empty = [d for d in domains if len(d.criteria) > 0]
    if not non_empty:
        raise AgentExecutionError("Coordinator snapshot contains no criteria")

    all_criteria: list[CriterionDefinition] = [c for d in non_empty for c in d.criteria]
    if len(all_criteria) == 1 and all_criteria[0].criterion_code == "A-05":
        return ((all_criteria[0],),)

    if all(
        _is_op_criterion(c)
        or _is_assessment_criterion(c)
        or _is_curriculum_criterion(c)
        for c in all_criteria
    ):
        op_group = tuple(c for c in all_criteria if _is_op_criterion(c))
        assess_group = tuple(c for c in all_criteria if _is_assessment_criterion(c))
        curriculum_group = tuple(c for c in all_criteria if _is_curriculum_criterion(c))
        envelopes = tuple(
            g for g in (op_group, assess_group, curriculum_group) if len(g) > 0
        )
        if envelopes:
            assert len(envelopes) <= 3
            return envelopes

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
