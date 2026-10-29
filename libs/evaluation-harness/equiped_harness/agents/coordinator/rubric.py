"""Qualitative, evidence-grounded Coordinator rubric guidance for adapter v4."""

from __future__ import annotations

from equiped_harness.contracts import LlmRubricGuidanceConfig, LlmScoreDescriptor

_LEVELS = (
    (
        4,
        (
            "Strong: clearly and consistently demonstrated in the reviewed "
            "text, with relevant evidence."
        ),
    ),
    (3, "Adequate: demonstrated with minor gaps or limited supporting detail."),
    (
        2,
        (
            "Limited or weak: only partly demonstrated, with substantial gaps "
            "or unclear evidence."
        ),
    ),
    (1, "Not demonstrated in the reviewed text; do not infer evidence that is absent."),
)

_GUIDANCE = {
    "OP-01": (
        "Evaluate coherence across the learning plan and its components, "
        "using explicit evidence from the reviewed text."
    ),
    "OP-02": (
        "Look for actual interactive learner responses or actions. Passive"
        " descriptions of interaction do not demonstrate interaction."
    ),
    "OP-03": (
        "Assess whether essential instructions are clear. Identification "
        "tasks may be simple and need not use numbered steps."
    ),
    "OP-04": (
        "Judge clarity and internal consistency of the instructional explanation "
        "itself. The material need not announce its accuracy or include a separate "
        "consistency check. Interaction and assessment are separate criteria."
    ),
    "OP-05": (
        "Look for actual extension or enrichment beyond core instruction. "
        "Illustrative examples alone are not extension."
    ),
    "A-01": (
        "Assess opportunities for application and analysis rather than recall alone."
    ),
    "A-02": (
        "Assess genuine variety in assessment approaches; labels alone do "
        "not demonstrate variety."
    ),
    "A-03": (
        "Look for an ongoing progress record or checkpoints. A task alone "
        "is not a progress tracker."
    ),
    "A-04": (
        "Assess constructive feedback, support, and incentives. Positive "
        "encouragement helps, while credit alone is limited evidence."
    ),
    "A-05": (
        "Compare stated learning objectives with actual assessment tasks. "
        "A goal statement alone does not demonstrate that it is assessed. "
        "Explain direct skill and concept matches and concrete gaps."
    ),
}


def guidance_for(code: str) -> LlmRubricGuidanceConfig:
    """Return the v4 qualitative scoring config for a canonical criterion code."""
    try:
        guidance = _GUIDANCE[code]
    except KeyError as exc:
        raise ValueError(f"Unknown Coordinator rubric criterion: {code}") from exc
    descriptors = tuple(
        LlmScoreDescriptor(score=score, descriptor=descriptor)
        for score, descriptor in _LEVELS
    )
    return LlmRubricGuidanceConfig(guidance=guidance, level_descriptors=descriptors)
