"""GAD criterion 2 prompt and scoring."""

from __future__ import annotations

CRITERION_ID = "GAD-02"
CRITERION_TITLE = "The material shows females and males an equal number of times"
CRITERION_KIND = "representation_balance"

# NOTE: not in the live prompt. Seeded FALLBACK_GAD_INSTRUCTIONS;
# edit that (or the DB scoring_rule) instead.
GAD_ROW_2_PROMPT = (
    "Analyze the learning material and count the number of meaningful female "
    "and male representations.\n\n"
    "Important: Count representations from the provided document_chunks, not "
    "from the rubric_context or reference_context.\n\n"
    "A meaningful representation includes:\n\n"
    "- Named individuals\n"
    "- Names listed under a gender-labeled group, heading, column, or label "
    "(for example, Female/Women/Girls or Male/Men/Boys)\n"
    "- Characters\n"
    "- Illustrations depicting people\n"
    "- Examples, scenarios, or case studies involving people\n"
    "- Explicit gender references (e.g., woman, man, girl, boy, female, male)\n"
    "- Gender-specific pronouns (e.g., she, her, he, him)\n\n"
    "If a list, table, or paragraph labels people as female or male, count "
    "each listed person/name in the matching gender count. If a person is "
    "introduced with a gendered role, title, or pronoun (for example, Ms., "
    "Mr., mother, father, sister, brother, she, he), count that person in the "
    "matching gender count.\n\n"
    "Count each meaningful representation only once within the same discussion, "
    "example, scenario, or case study.\n\n"
    "If the same individual appears in different examples or scenarios, count "
    "each appearance separately.\n\n"
    "Do not infer gender when it is ambiguous.\n\n"
    "Ignore gender-neutral references.\n\n"
    "If no meaningful female or male representations are present, return 0 for "
    "both counts.\n\n"
    "Replace all numeric placeholder values with actual counts from "
    "document_chunks. Do not copy the example value 0 unless no matching "
    "representations are found.\n\n"
    "Always include a non-empty summary written like a human reviewer comment. "
    "If the female and male counts are imbalanced, "
    "explain what should be improved to make representation more balanced. If "
    "the counts are balanced, explain what the material is doing well and what "
    "should be retained, such as maintaining varied examples and comparable "
    "visibility for female and male representations. If no meaningful "
    "representations are found, explain that representation coverage should be "
    "added where appropriate. Keep the summary to 1-2 natural sentences.\n\n"
    "Return only valid JSON\n"
    "{\n"
    '  "criterion": "The material shows females and males an equal number of '
    'times",\n'
    '  "female_count": 0,\n'
    '  "male_count": 0,\n'
    '  "summary": ""\n'
    "}"
)


def score_representation_balance(female_count: int, male_count: int) -> int:
    difference = abs(female_count - male_count)
    if difference <= 2:
        return 4
    if difference <= 5:
        return 3
    if difference <= 10:
        return 2
    return 1


__all__ = [
    "CRITERION_ID",
    "CRITERION_KIND",
    "CRITERION_TITLE",
    "GAD_ROW_2_PROMPT",
    "score_representation_balance",
]
