"""GAD domain agent — single combined-prompt evaluation of all 5 criteria."""

from __future__ import annotations

import json
import logging
from typing import Any

from server.core.config import get_settings

from .base import BaseAgent

logger = logging.getLogger(__name__)

_COMBINED_GAD_PROMPT = (
    "You are evaluating learning material for Gender and Development (GAD) "
    "compliance.\n\n"
    "Analyze the provided document chunks against ALL FIVE criteria below. "
    "For each criterion, assign a score from 1 to 4 and provide a "
    "justification with supporting evidence from the document.\n\n"
    "---\n"
    "GAD-01 (Free from gender stereotypes):\n"
    "Identify instances that reinforce stereotypes about gender roles, "
    "abilities, behaviors, occupations, or characteristics. Do not count "
    "educational/analytical/historical discussions presented for critical "
    "purposes.\n"
    "- Score 4: No instances detected.\n"
    "- Score 3: 1 instance.\n"
    "- Score 2: 2-3 instances.\n"
    "- Score 1: 4+ instances or pervasive stereotyping.\n\n"
    "---\n"
    "GAD-02 (Equal representation of females and males):\n"
    "Count meaningful female and male representations: named individuals, "
    "characters, illustrations depicting people, explicit gender references, "
    "gender-specific pronouns. Count each once per discussion. Do not infer "
    "gender when ambiguous. Ignore gender-neutral references.\n"
    "- Score 4: Representation difference ≤ 2.\n"
    "- Score 3: Difference 3-5.\n"
    "- Score 2: Difference 6-10.\n"
    "- Score 1: Difference 11+.\n\n"
    "---\n"
    "GAD-03 (Equal respect and potential):\n"
    "Identify instances where one gender is portrayed as less capable, less "
    "respected, less deserving, or having fewer opportunities. Do not count "
    "educational/analytical/historical discussions.\n"
    "- Score 4: No instances detected.\n"
    "- Score 3: 1-2 instances.\n"
    "- Score 2: 3-5 instances.\n"
    "- Score 1: 6+ instances or pervasive pattern.\n\n"
    "---\n"
    "GAD-04 (Reflects needs and life experiences of both genders):\n"
    "Identify instances where the material excludes or disproportionately "
    "favors one gender's experiences, activities, roles, responsibilities, "
    "interests, or aspirations. Do not count gender-neutral examples or "
    "educational/analytical/historical discussions.\n"
    "- Score 4: No instances detected.\n"
    "- Score 3: 1-2 instances.\n"
    "- Score 2: 3-5 instances.\n"
    "- Score 1: 6+ instances or pervasive exclusion.\n\n"
    "---\n"
    "GAD-05 (Promotes peace and equality regardless of gender, race, class, "
    "disability, religion, sexual orientation, or ethnic background):\n"
    "Identify instances of discriminatory, prejudicial, exclusionary, or "
    "inequality-promoting content related to any identity dimension. Do not "
    "count historical/educational/analytical/critical discussions.\n"
    "- Score 4: No instances detected.\n"
    "- Score 3: 1-2 instances.\n"
    "- Score 2: 3-5 instances.\n"
    "- Score 1: 6+ instances or pervasive discrimination.\n\n"
    "---\n"
    "Return only valid JSON with 'summary' (a brief overall GAD assessment "
    "written like a human reviewer comment, 1-2 natural sentences) and "
    "'criterion_scores' (an array of 5 objects, one per GAD criterion).\n\n"
    "Each criterion_score object must contain:\n"
    '- "criterion_id": string (e.g. "GAD-01")\n'
    '- "criterion_title": string (the criterion name)\n'
    '- "score": integer (1-4)\n'
    '- "justification": string explaining the score\n'
    '- "evidence": array of strings with supporting excerpts\n'
    '- "chunk_ids": array of chunk_id strings referencing relevant chunks'
)


class GAD(BaseAgent):
    agent_name = "gad"
    rubric_source_type = "rubric_gad"
    domain_keywords = (
        "gender", "inclusion", "diversity", "equity", "accessibility",
        "representation", "inclusive", "fair", "bias", "equal",
        "marginalized", "sensitivity",
    )

    def _build_prompt(
        self,
        *,
        chunk_infos: list[dict[str, Any]],
        rubric_context: list[str],
        reference_context: list[str],
        reference_text: str | None,
        prompt_version: str | None,
    ) -> str:
        settings = get_settings()
        packed_chunks, chunks_dropped, text_excerpted = self._pack_chunks(
            chunk_infos,
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=settings.agent_prompt_budget_chars,
            small_doc_threshold=settings.agent_small_doc_threshold,
        )
        payload = {
            "agent": self.agent_name,
            "prompt_version": prompt_version,
            "document_chunks": packed_chunks,
            "rubric_context": rubric_context,
            "reference_context": reference_context,
            "reference_text": reference_text,
            "instructions": [_COMBINED_GAD_PROMPT],
        }
        if chunks_dropped or text_excerpted:
            parts = []
            if chunks_dropped:
                parts.append(
                    "Only a subset of chunks was included due to document size."
                )
            if text_excerpted:
                parts.append(
                    "Some chunk texts were excerpted (truncated) to fit "
                    "context limits."
                )
            parts.append("Focus on the provided excerpts.")
            payload["note"] = " ".join(parts)
        return json.dumps(payload, ensure_ascii=False)


GADAgent = GAD


__all__ = [
    "GAD",
    "GADAgent",
]
