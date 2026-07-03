"""GAD criterion 3 prompt and scoring."""

from __future__ import annotations

CRITERION_ID = "GAD-03"
CRITERION_TITLE = (
    "The material shows females and males with equal respect and potential"
)
CRITERION_KIND = "respect_potential_instances"

GAD_ROW_3_PROMPT = (
    "Analyze the learning material and identify instances that portray one "
    "gender as less capable, less respected, less deserving, or having fewer "
    "opportunities than another.\n\n"
    "Do not count discussions of discrimination presented for educational, "
    "analytical, historical, or critical purposes.\n\n"
    "Count each unique instance once.\n\n"
    "Females and males are presented with equal respect and potential.\n"
    "Replace all numeric placeholder values with actual counts from "
    "document_chunks. Do not copy the example value 0 unless no matching "
    "instances are found.\n"
    "Always include a non-empty summary written like a human reviewer comment. "
    "If instances are found, explain what should "
    "be improved so females and males are shown with equal respect, capability, "
    "and opportunity. If no qualifying instances are found, explain what the "
    "material is doing well and what should be retained, such as respectful "
    "language, fair opportunities, or balanced portrayals of potential. Keep "
    "the summary to 1-2 natural sentences.\n"
    "Return only valid JSON\n"
    "{\n"
    '  "criterion": "The material shows females and males with equal respect '
    'and potential",\n'
    '  "instance_count": 0,\n'
    '  "instances": [\n'
    "    {\n"
    '      "excerpt": "",\n'
    '      "explanation": ""\n'
    "    }\n"
    "  ],\n"
    '  "summary": ""\n'
    "}"
)


def score_respect_potential_instances(instance_count: int) -> int:
    if instance_count == 0:
        return 4
    if instance_count <= 2:
        return 3
    if instance_count <= 5:
        return 2
    return 1


__all__ = [
    "CRITERION_ID",
    "CRITERION_KIND",
    "CRITERION_TITLE",
    "GAD_ROW_3_PROMPT",
    "score_respect_potential_instances",
]
