"""GAD criterion 4 prompt and scoring."""

from __future__ import annotations

CRITERION_ID = "GAD-04"
CRITERION_TITLE = (
    "The material reflects the needs and life experiences of both male and "
    "female students"
)
CRITERION_KIND = "life_experience_instances"

GAD_ROW_4_PROMPT = (
    "Analyze the learning material and identify instances where the material:\n\n"
    "- Excludes one gender's experiences.\n"
    "- Disproportionately favors one gender's experiences.\n"
    "- Assumes that activities, roles, responsibilities, interests, or "
    "aspirations belong primarily to one gender.\n\n"
    "Do not count:\n\n"
    "- Gender-neutral examples.\n"
    "- Discussions presented for educational, analytical, historical, or "
    "critical purposes.\n\n"
    "Count each unique instance once.\n\n"
    "Replace all numeric placeholder values with actual counts from "
    "document_chunks. Do not copy the example value 0 unless no matching "
    "instances are found.\n\n"
    "Always include a non-empty summary written like a human reviewer comment. "
    "If instances are found, explain what should "
    "be improved so the material better reflects both male and female students' "
    "needs and life experiences. If no qualifying instances are found, explain "
    "what the material is doing well and what should be retained, such as "
    "inclusive examples, balanced scenarios, or activities that do not assume "
    "one gender's roles or interests. Keep the summary to 1-2 natural "
    "sentences.\n\n"
    "Return only valid JSON\n"
    "{\n"
    '  "criterion": "The material reflects the needs and life experiences of '
    'both male and female students",\n'
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


def score_life_experience_instances(instance_count: int) -> int:
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
    "GAD_ROW_4_PROMPT",
    "score_life_experience_instances",
]
