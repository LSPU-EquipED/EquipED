"""GAD criterion 5 prompt and scoring."""

from __future__ import annotations

CRITERION_ID = "GAD-05"
CRITERION_TITLE = (
    "The material promotes peace and equality regardless of gender, race, "
    "class, disability, religion, sexual orientation, or ethnic background"
)
CRITERION_KIND = "peace_equality_instances"

GAD_ROW_5_PROMPT = (
    "Analyze the learning material and identify instances of discriminatory, "
    "prejudicial, exclusionary, or inequality-promoting content related to:\n\n"
    "- Gender\n"
    "- Race\n"
    "- Social class\n"
    "- Disability\n"
    "- Religion\n"
    "- Sexual orientation\n"
    "- Ethnic background\n\n"
    "Do not count:\n\n"
    "Historical discussions.\n"
    "Educational discussions.\n"
    "Analytical or critical discussions of discrimination.\n\n"
    "Count each unique instance once.\n\n"
    "Replace all numeric placeholder values with actual counts from "
    "document_chunks. Do not copy the example value 0 unless no matching "
    "instances are found.\n\n"
    "Always include a non-empty summary written like a human reviewer comment. "
    "If instances are found, explain what should "
    "be improved to remove discriminatory, prejudicial, exclusionary, or "
    "inequality-promoting content, and mention the relevant category in plain "
    "language. If no qualifying instances are found, explain what the material "
    "is doing well and what should be retained, such as respectful language, "
    "inclusive examples, and fair treatment across identity groups. Keep the "
    "summary to 1-2 natural sentences.\n\n"
    "Return only valid JSON\n"
    "{\n"
    '  "criterion": "The material promotes peace and equality regardless of '
    'gender, race, class, disability, religion, sexual orientation, or ethnic '
    'background",\n'
    '  "instance_count": 0,\n'
    '  "instances": [\n'
    "    {\n"
    '      "excerpt": "",\n'
    '      "explanation": "",\n'
    '      "category": ""\n'
    "    }\n"
    "  ],\n"
    '  "summary": ""\n'
    "}"
)


def score_peace_equality_instances(instance_count: int) -> int:
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
    "GAD_ROW_5_PROMPT",
    "score_peace_equality_instances",
]
