"""ITSO domain agent."""

from __future__ import annotations

import json
from typing import Any

from .base import BaseAgent


class ITSO(BaseAgent):
    agent_name = "itso"
    rubric_source_type = "rubric_itso"
    domain_keywords = (
        "security",
        "privacy",
        "data",
        "protection",
        "encryption",
        "authentication",
        "threat",
        "vulnerability",
        "confidential",
        "integrity",
        "access control",
        "risk",
        "plagiarism",
        "citation",
        "reference",
        "bibliography",
        "source",
        "intellectual property",
        "copyright",
        "ownership",
        "student data",
        "rights",
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
        """Override to inject local precheck evidence summary and
        evidence-status guidance into the ITSO prompt.

        The precheck data comes from ``self._current_provenance``
        (set by the supervisor before dispatch). When provenance is
        absent (e.g. historical runs or tests), the prompt is built
        without evidence-status instructions for backward compatibility.
        """
        from server.modules.agents.base import get_settings as _get_settings

        settings = _get_settings()
        packed_chunks, chunks_dropped, text_excerpted = self._pack_chunks(
            chunk_infos,
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=settings.agent_prompt_budget_chars,
            small_doc_threshold=settings.agent_small_doc_threshold,
        )

        instructions = [
            "Return JSON with summary and criterion_scores.",
            "Each criterion score must be between 1 and 4.",
            "Cite only the chunk_id values provided in document_chunks.",
            "Ground all claims in the provided context.",
        ]

        # Inject local precheck evidence summary when available.
        prov = getattr(self, "_current_provenance", None)
        if prov and isinstance(prov, dict):
            bib_found = prov.get("bibliography_found")
            ref_count = prov.get("reference_count")
            cit_count = prov.get("intext_citation_count")
            doi_count = prov.get("doi_count")

            evidence_lines: list[str] = []
            if bib_found is not None:
                evidence_lines.append(
                    "  - bibliography_section: "
                    + ("FOUND" if bib_found else "NOT_FOUND")
                )
            if ref_count is not None:
                evidence_lines.append(f"  - reference_entries: {ref_count}")
            if cit_count is not None:
                evidence_lines.append(f"  - intext_citations: {cit_count}")
            if doi_count is not None:
                evidence_lines.append(f"  - doi_candidates: {doi_count}")

            if evidence_lines:
                instructions.append(
                    "Local evidence precheck summary (deterministic, advisory only):"
                )
                instructions.extend(evidence_lines)
                instructions.append("")
                instructions.append(
                    "Evidence status categories — use these where applicable "
                    "in your criterion justification, NOT in the score field:"
                )
                instructions.append(
                    "  - VERIFIED: local evidence confirms the condition."
                )
                instructions.append(
                    "  - NOT_VERIFIED: local evidence does not confirm the condition "
                    "(this is NOT a negative finding)."
                )
                instructions.append(
                    "  - INSUFFICIENT_EVIDENCE: not enough local information to assess."
                )
                instructions.append(
                    "  - TOOL_UNAVAILABLE: the tool needed to verify is not available "
                    "in this environment."
                )
                instructions.append("")
                instructions.append(
                    "IMPORTANT: Do NOT assert plagiarism, invalid citation, "
                    "misconduct, or legal noncompliance solely because local "
                    "precheck signals are absent or do not confirm a condition. "
                    "Absent local evidence means the information could not be "
                    "verified locally — it does NOT imply a violation."
                )

        payload: dict[str, Any] = {
            "agent": self.agent_name,
            "prompt_version": prompt_version,
            "document_chunks": packed_chunks,
            "rubric_context": rubric_context,
            "reference_context": reference_context,
            "reference_text": reference_text,
            "instructions": instructions,
        }
        if chunks_dropped or text_excerpted:
            parts = []
            if chunks_dropped:
                parts.append(
                    "Only a subset of chunks was included due to document size."
                )
            if text_excerpted:
                parts.append(
                    "Some chunk texts were excerpted (truncated) to fit context limits."
                )
            parts.append("Focus on the provided excerpts.")
            payload["note"] = " ".join(parts)
        return json.dumps(payload, ensure_ascii=False)


ITSOAgent = ITSO


__all__ = ["ITSO", "ITSOAgent"]
