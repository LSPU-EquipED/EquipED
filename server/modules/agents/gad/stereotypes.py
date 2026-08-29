"""GAD criterion 1 prompt and scoring."""

from __future__ import annotations

CRITERION_ID = "GAD-01"
CRITERION_TITLE = "The material is free from gender stereotypes"
CRITERION_KIND = "stereotype_instances"

# NOTE: not in the live prompt. Seeded FALLBACK_GAD_INSTRUCTIONS;
# edit that (or the DB scoring_rule) instead.
GAD_ROW_1_PROMPT = (
    "Analyze the learning material and identify instances of gender stereotypes "
    "or gender-biased representations.\n\n"
    "Count an instance if it:\n\n"
    "- Reinforces stereotypes about gender roles, abilities, behaviors, "
    "occupations, or characteristics.\n"
    "- Explicitly or implicitly portrays one gender using stereotypical "
    "assumptions.\n\n"
    "Do not count:\n\n"
    "- Discussions of gender stereotypes presented for educational, analytical, "
    "historical, or critical purposes.\n"
    "- Gender-neutral content.\n\n"
    "Count each unique instance once.\n\n"
    "Replace all numeric placeholder values with actual counts from "
    "document_chunks. Do not copy the example value 0 unless no matching "
    "instances are found.\n\n"
    "Always include a non-empty summary written like a human reviewer comment. "
    "If instances are found, explain what should "
    "be improved to remove gender stereotypes or biased portrayals. If no "
    "qualifying instances are found, explain what the material is doing well "
    "and what should be retained, such as neutral language, fair role "
    "portrayals, or non-stereotyped examples. Keep the summary to 1-2 natural "
    "sentences.\n\n"
    "Return only valid JSON\n"
    "{\n"
    '  "criterion": "The material is free from gender stereotypes",\n'
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


def score_stereotype_instances(instance_count: int) -> int:
    if instance_count == 0:
        return 4
    if instance_count == 1:
        return 3
    if instance_count <= 3:
        return 2
    return 1


__all__ = [
    "CRITERION_ID",
    "CRITERION_KIND",
    "CRITERION_TITLE",
    "GAD_ROW_1_PROMPT",
    "score_stereotype_instances",
]
