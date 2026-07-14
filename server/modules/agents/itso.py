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
        """Override to inject local precheck evidence summary,
        evidence-status guidance, and POLICY EVIDENCE section into the
        ITSO prompt.

        The precheck data comes from ``self._current_provenance``
        (set by the supervisor before dispatch). Policy evidence comes
        from ``self._current_policy_evidence``. When provenance is
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

        # Inject POLICY EVIDENCE section from frozen snapshot (ITSO only).
        # Blocked by default via itso_policy_delivery_enabled config.
        policy_evidence = getattr(self, "_current_policy_evidence", None)
        if policy_evidence and isinstance(policy_evidence, dict):
            delivery_state = policy_evidence.get("delivery_state", "blocked")
            criteria_evidence = policy_evidence.get("criteria", {})

            if delivery_state == "enabled":
                # Build policy evidence section with clause text.
                section_lines: list[str] = []
                section_lines.append("=== POLICY EVIDENCE ===")
                section_lines.append(
                    "The following local policy clauses are provided as "
                    "advisory evidence only. They are retrieved from "
                    "institutionally approved documents stored on local "
                    "LSPU-controlled infrastructure."
                )
                section_lines.append("")

                for criterion_id in ("ITSO-03", "ITSO-04", "ITSO-05"):
                    crit = criteria_evidence.get(criterion_id, {})
                    area = crit.get("policy_area", "unknown")
                    status = crit.get("status", "unavailable")
                    chunks = crit.get("chunks", [])
                    section_lines.append(
                        f"Criterion {criterion_id} ({area}): "
                        f"{'AVAILABLE' if status == 'available' else 'UNAVAILABLE'}"
                    )
                    if chunks:
                        for i, chunk in enumerate(chunks, 1):
                            text = chunk.get("text", "")[:500]
                            section_lines.append(f"  Clause {i}: {text}")
                    section_lines.append("")

                section_lines.append(
                    "IMPORTANT: Policy evidence absence or unavailability "
                    "is NOT evidence of noncompliance. Do NOT conclude "
                    "plagiarism, academic misconduct, or legal violations "
                    "solely because policy evidence is absent, unavailable, "
                    "or conflicting. Request human review where evidence is "
                    "absent or conflicting. All policy evidence is advisory "
                    "and must be verified by a qualified human reviewer."
                )
                instructions.append("")
                instructions.append("\n".join(section_lines))
            else:
                # Delivery blocked by config — inject empty advisory only.
                blocked_lines: list[str] = []
                blocked_lines.append("=== POLICY EVIDENCE ===")
                blocked_lines.append(
                    "Local policy evidence retrieval is configured for "
                    "institutionally approved local/self-hosted LLM backends "
                    "only. Policy clause delivery is currently blocked for "
                    "the configured LLM endpoint."
                )
                for criterion_id in ("ITSO-03", "ITSO-04", "ITSO-05"):
                    crit = criteria_evidence.get(criterion_id, {})
                    area = crit.get("policy_area", "unknown")
                    blocked_lines.append(
                        f"  - {criterion_id} ({area}): delivery_blocked"
                    )
                blocked_lines.append("")
                blocked_lines.append(
                    "IMPORTANT: Policy evidence is unavailable because "
                    "the configured LLM backend is not institutionally "
                    "confirmed as local/self-hosted. Do NOT conclude "
                    "plagiarism, academic misconduct, or legal violations "
                    "when policy evidence is absent. Request human review "
                    "where evidence is needed."
                )
                instructions.append("")
                instructions.append("\n".join(blocked_lines))

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
