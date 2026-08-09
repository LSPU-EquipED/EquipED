"""ITSO prompt construction."""

from __future__ import annotations

import json
from typing import Any

from server.core.config import get_settings

from ..runtime.context import ITSOExecutionContext
from ..runtime.prompt_budget import pack_chunks


def build_prompt(
    context: ITSOExecutionContext,
    *,
    rubric_context: list[str],
    reference_context: list[str],
) -> str:
    settings = get_settings()
    chunks, dropped, excerpted = pack_chunks(
        [dict(chunk) for chunk in context.chunk_infos],
        max_chunks=settings.agent_max_chunks,
        max_excerpt_chars=settings.agent_max_excerpt_chars,
        prompt_budget_chars=settings.agent_prompt_budget_chars,
        small_doc_threshold=settings.agent_small_doc_threshold,
        domain_keywords=context.domain_keywords,
        agent_name="itso",
    )
    instructions = [
        "Return JSON with summary and criterion_scores.",
        "Each criterion score must be between 1 and 4.",
        "Cite only the chunk_id values provided in document_chunks.",
        "Ground all claims in the provided context.",
    ]
    prov = dict(context.provenance)
    evidence_lines = []
    for key, label in (
        ("bibliography_found", "bibliography_section"),
        ("reference_count", "reference_entries"),
        ("intext_citation_count", "intext_citations"),
        ("doi_count", "doi_candidates"),
    ):
        if prov.get(key) is not None:
            value = prov[key]
            display_value = (
                ("FOUND" if value else "NOT_FOUND")
                if isinstance(value, bool)
                else value
            )
            evidence_lines.append(
                f"  - {label}: "
                f"{display_value}"
            )
    if evidence_lines:
        instructions += [
            "Local evidence precheck summary (deterministic, advisory only):",
            *evidence_lines,
            "",
            "Evidence status categories — use these where applicable in your "
            "criterion justification, NOT in the score field:",
            "  - VERIFIED: local evidence confirms the condition.",
            "  - NOT_VERIFIED: local evidence does not confirm the condition "
            "(this is NOT a negative finding).",
            "  - INSUFFICIENT_EVIDENCE: not enough local information to assess.",
            "  - TOOL_UNAVAILABLE: the tool needed to verify is not available "
            "in this environment.",
            "",
            "IMPORTANT: Do NOT assert plagiarism, invalid citation, misconduct, "
            "or legal noncompliance solely because local precheck signals are "
            "absent or do not confirm a condition. Absent local evidence means "
            "the information could not be verified locally — it does NOT imply "
            "a violation.",
        ]
    policy = dict(context.policy_evidence)
    if policy:
        lines = ["=== POLICY EVIDENCE ==="]
        enabled = policy.get("delivery_state") == "enabled"
        lines.append(
            "The following local policy clauses are provided as advisory evidence "
            "only. They are retrieved from institutionally approved documents "
            "stored on local LSPU-controlled infrastructure."
            if enabled
            else "Local policy evidence retrieval is configured for institutionally "
            "approved local/self-hosted LLM backends only. Policy clause delivery "
            "is currently blocked for the configured LLM endpoint."
        )
        for criterion in ("ITSO-03", "ITSO-04", "ITSO-05"):
            crit = policy.get("criteria", {}).get(criterion, {})
            lines.append(
                f"Criterion {criterion} ({crit.get('policy_area', 'unknown')}): "
                f"{'AVAILABLE' if crit.get('status') == 'available' else 'UNAVAILABLE'}"
            )
            if enabled:
                lines.extend(
                    f"  Clause {i}: {chunk.get('text', '')[:500]}"
                    for i, chunk in enumerate(crit.get("chunks", []), 1)
                )
            else:
                lines.append(
                    f"  - {criterion} ({crit.get('policy_area', 'unknown')}): "
                    "delivery_blocked"
                )
        lines.append(
            "IMPORTANT: Policy evidence absence or unavailability is NOT evidence "
            "of noncompliance. Do NOT conclude plagiarism, academic misconduct, "
            "or legal violations solely because policy evidence is absent, "
            "unavailable, or conflicting. Request human review where evidence is "
            "absent or conflicting. All policy evidence is advisory and must be "
            "verified by a qualified human reviewer."
        )
        instructions += ["", "\n".join(lines)]
    payload: dict[str, Any] = {
        "agent": "itso",
        "prompt_version": context.prompt_version,
        "document_chunks": chunks,
        "rubric_context": rubric_context,
        "reference_context": reference_context,
        "reference_text": context.reference_text,
        "instructions": instructions,
    }
    if dropped or excerpted:
        payload["note"] = " ".join(
            filter(
                None,
                [
                    "Only a subset of chunks was included due to document size."
                    if dropped
                    else "",
                    "Some chunk texts were excerpted (truncated) to fit context limits."
                    if excerpted
                    else "",
                    "Focus on the provided excerpts.",
                ],
            )
        )
    return json.dumps(payload, ensure_ascii=False)
