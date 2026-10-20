"""Stateless ITSO execution pipeline."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import replace
from typing import Any

from equiped_harness.agents.itso.contracts import ITSOExecutionContext
from equiped_harness.agents.itso.document_review import (
    policy_context,
    review_chunks,
    review_coverage,
    validate_review_evidence,
)
from equiped_harness.agents.itso.prompt import (
    MISSING_BIBLIOGRAPHY_NOTICE,
    build_prompt,
    pack_itso_chunks,
    reference_limit_notice,
)
from equiped_harness.agents.itso.reporting import (
    _v3_reference_summary,
    cites_public_source,
    readable_reference_justification,
)
from equiped_harness.agents.itso.response import (
    ITSO_RESPONSE_SCHEMA_VERSION,
    build_response_schema,
    collect_advisory_outputs,
    criterion_scores,
    parse_response,
)
from equiped_harness.contracts import (
    CriterionDefinition,
    GroundedScoreMeasurement,
)
from equiped_harness.contracts.results import AgentEvaluationResult, CapturedGeneration
from equiped_harness.contracts.snapshots import EvaluationFormSnapshotDTO
from equiped_harness.exceptions import AgentExecutionError, AgentLLMError
from equiped_harness.manifests import get_agent_manifest, validate_form
from equiped_harness.provenance import sanitize_provenance
from equiped_harness.runtime.config import current_execution_config
from equiped_harness.runtime.context import thaw
from equiped_harness.runtime.llm import RunLLMClient
from equiped_harness.runtime.model import ResponseContract
from equiped_harness.runtime.prompt_budget import PromptBudgetResult
from equiped_harness.runtime.prompts import AgentPrompt
from equiped_harness.runtime.timing import PhaseTimer
from equiped_harness.strategies.calculators import normalize_llm_guidance_score

logger = logging.getLogger(__name__)

_V3_REPAIR_CATEGORIES = (
    "ITSOInvalidEvidence",
    "ITSOUnknownChunk",
    "ITSOInvalidCriterion",
    "ITSOInvalidCriterionScores",
    "ITSOInvalidScore",
    "ITSOInvalidJustification",
    "ITSOInvalidResponse",
    "ITSOInvalidJSON",
    "ITSOInvalidPublicSourceUse",
)


def execute(
    context: ITSOExecutionContext,
    *,
    llm_client: Any | None = None,
    llm_temperature: float | None = None,
) -> AgentEvaluationResult:
    """Validate the frozen form once, then run the bounded criterion envelopes."""
    version = getattr(context.form_snapshot, "adapter_version", None)
    if version != 3:
        raise AgentExecutionError(f"Unsupported ITSO adapter version {version}")
    criteria, _, _ = _extract_and_validate_snapshot(context)
    _references(context)
    timeout = float(
        getattr(current_execution_config(), "llm_request_timeout_seconds", 120)
    )
    deadline = time.monotonic() + timeout
    source_criteria = tuple(
        criterion
        for criterion in criteria
        if criterion.criterion_code in {"ITSO-01", "ITSO-02"}
    )
    document_criteria = tuple(
        criterion
        for criterion in criteria
        if criterion.criterion_code not in {"ITSO-01", "ITSO-02"}
    )
    if len(source_criteria) != 2 or len(document_criteria) != 3:
        raise AgentExecutionError(
            "ITSO adapter 3 requires ITSO-01/02 and ITSO-03/04/05 criteria"
        )
    groups = (source_criteria, document_criteria)
    results: list[AgentEvaluationResult] = []
    comparison_packet = None
    comparison_context = None
    packet_chunks, comparison_packet = _v3_comparison_packet(context)
    if not packet_chunks:
        raise AgentExecutionError(
            "ITSO adapter 3 requires a document chunk within prompt budget"
        )
    comparison_context = comparison_packet
    for index, group in enumerate(groups):
        group_context = context
        if index == 0:
            group_context = replace(
                context, chunk_infos=tuple(comparison_packet["module_excerpts"])
            )
        if index == 1:
            comparison_context = {
                "prior_source_findings": [
                    {
                        "criterion_id": score.criterion_id,
                        "score": score.score,
                        "reasoning": score.justification[:1800],
                        "evidence": list(score.evidence),
                    }
                    for score in results[0].criterion_scores
                ],
                "status": "validated advisory findings, not proof of ownership",
            }
        results.append(
            _execute_criteria(
                group_context,
                ordered_criteria=tuple(group),
                deadline=deadline,
                unit_key=f"envelope_{index}",
                comparison_context=comparison_context,
                llm_client=llm_client,
                llm_temperature=llm_temperature,
            )
        )
    if len(results) == 1:
        return results[0]
    if len({result.model_name for result in results}) != 1:
        raise AgentExecutionError("ITSO envelopes were served by different models")
    scores = tuple(score for result in results for score in result.criterion_scores)
    scores = tuple(
        sorted(
            scores,
            key=lambda score: tuple(c.criterion_code for c in criteria).index(
                score.criterion_id
            ),
        )
    )
    generations = tuple(
        generation for result in results for generation in result.generations
    )
    advisories = [
        result.advisory_outputs for result in results if result.advisory_outputs
    ]
    advisory = None
    if advisories:
        entries = tuple(
            item for output in advisories for item in output.ungrounded_criteria
        )
        if entries:
            from equiped_harness.contracts.results import AdvisoryOutput

            advisory = AdvisoryOutput(entries)
    provenance = dict(results[0].provenance or {})
    for key in (
        "repair_occurred",
        "fallback_occurred",
        "prompt_trimmed",
        "policy_trimmed",
        "response_format_downgraded",
    ):
        provenance[key] = any(
            result.provenance and result.provenance.get(key) for result in results
        )
    provenance["reference_context_dropped"] = sum(
        int(result.provenance.get("reference_context_dropped", 0))
        for result in results
        if result.provenance
    )
    metadata = dict(results[0].metadata)
    metadata["envelope_count"] = len(results)
    metadata["prompt_chars"] = sum(
        int(r.metadata.get("prompt_chars", 0)) for r in results
    )
    metadata["prompt_trimmed"] = any(
        bool(r.metadata.get("prompt_trimmed")) for r in results
    )
    metadata["reference_context_dropped"] = sum(
        int(r.metadata.get("reference_context_dropped", 0)) for r in results
    )
    source_summary, document_summary = (result.summary for result in results)
    coverage_markers = ("Readable public source text", "Only ")
    coverage_summaries = []
    for value, marker in zip(
        (source_summary, document_summary), coverage_markers, strict=True
    ):
        marker_index = value.rfind(marker)
        if marker_index >= 0:
            coverage_summaries.append(value[marker_index:].strip())
    final_summary = " ".join(part for part in coverage_summaries if part)

    return AgentEvaluationResult(
        agent_name="itso",
        evaluation_id=context.evaluation_id,
        document_id=context.document_id,
        subtotal=sum(s.score for s in scores) / len(scores),
        criterion_scores=scores,
        prompt_version_id=None,
        summary=final_summary,
        model_name=results[0].model_name,
        processing_seconds=sum(r.processing_seconds for r in results),
        token_count=sum(r.token_count for r in results),
        success=True,
        error_message=None,
        raw_response=None,
        prompt_text=None,
        provenance=sanitize_provenance(provenance) or None,
        advisory_outputs=advisory,
        metadata=metadata,
        generations=generations,
    )


def _v3_repair_suffix(
    category: str,
    *,
    criterion_id: str | None = None,
    reason: str | None = None,
    source_url: str | None = None,
    source_index: int | None = None,
    limit_notice: str | None = None,
) -> str:
    """Build bounded v3 repair feedback using trusted validator metadata only."""
    if reason == "unverified_top_score" and criterion_id == "ITSO-01":
        return (
            "\n\nVALIDATOR_FAILURE category=ITSOInvalidScore criterion=ITSO-01 "
            "reason=unverified_top_score. Under the frozen rule, ITSO-01 cannot "
            "score 4 while stating originality is unverified. Reassess against "
            "the score-3 and score-4 descriptors: unverified originality without "
            "a concrete source conflict supports advisory 3; 4 needs explicit "
            "support. Preserve source citations, exact verification limits, "
            "module quotes and all six required row fields for BOTH criteria. "
            "Regenerate complete JSON only."
        )
    if reason == "missing_review_evidence" and criterion_id:
        return (
            f"\n\nVALIDATOR_FAILURE category=ITSOInvalidEvidence "
            f"criterion={criterion_id} reason=missing_review_evidence. "
            "Choose a relevant exact quote and chunk_id from "
            "module_evidence_options. ITSO-01 requires a module comparison "
            "quote. ITSO-02/03 require a quote when acknowledgement/authorship "
            "options exist, even for provisional 3. Prepared by establishes "
            "a named author, not legal ownership. "
            "Reassess against the frozen rule. ITSO-04 scores below 4 need an "
            "exact module quotation demonstrating a confidentiality concern; "
            "without a detected concern, return advisory 4 and state the "
            "reviewed extracted-text scope. ITSO-03/05 scores 1, 2 or 4 need "
            "an exact module quotation supporting the finding; incomplete "
            "ownership/rights evidence with no concrete concern supports "
            "provisional 3. Select a verbatim quote and its chunk_id from "
            "document_chunks, or explain the scoped uncertainty. Never invent "
            "evidence. Regenerate the complete JSON only."
        )
    if reason == "ungrounded_evidence" and criterion_id:
        return (
            f"\n\nVALIDATOR_FAILURE category={category} "
            f"criterion={criterion_id} reason=ungrounded_evidence. "
            "A verbatim cited-chunk substring was not validated for this "
            "criterion. Replace it with an exact quote and chunk_id from "
            "module_evidence_options when available. Empty evidence is allowed "
            "only for findings whose quotation requirements permit it; "
            "explain their scoped uncertainty or absence. "
            "Keep the required source citations in justification. Do not infer "
            "statements as quotations. Regenerate the complete JSON response only; "
            "do not include commentary."
        )
    if reason == "missing_source_citation" and criterion_id and source_url:
        citation = (
            source_url if len(source_url) <= 300 else f"[source {source_index or 1}]"
        )
        return (
            f"\n\nVALIDATOR_FAILURE category={category} criterion={criterion_id} "
            "reason=missing_source_citation. ITSO-01 and ITSO-02 justification "
            "must each cite an actually retrieved source. Use source citations "
            "that identify the passages relevant to the comparison. "
            "Cite the "
            f"retrieved source {citation}, or preferably cite "
            f"[source {source_index or 1}] (its 1-based report position). "
            "Compare the supplied "
            "document statement against the retrieved passage in the supplied "
            "verification report, then put this exact "
            "valid source citation in the justification. External quotes are not "
            "document evidence. Retain the exact MODULE quotations from "
            "module_evidence_options in each row's evidence array and their "
            "chunk_ids. Do not remove or omit evidence. EVERY row must have "
            "criterion_id, criterion_title, score, justification, chunk_ids "
            "and evidence. BOTH ITSO-01 and ITSO-02 must cite the source. Keep "
            "the exact verification-limit sentence. Absent module hyperlinks "
            "are not a scoring penalty; unverified fields are limits, not "
            "proof of an originality problem. Under the frozen rule, ITSO-01 "
            "cannot score 4 when originality remains unverified. "
            "Regenerate the complete JSON "
            "response only; "
            "do not include commentary."
        )
    if reason == "missing_bibliography_limit" and criterion_id == "ITSO-02":
        return (
            f"\n\nVALIDATOR_FAILURE category={category} criterion=ITSO-02 "
            "reason=missing_bibliography_limit. Include this exact sentence in "
            f"the ITSO-02 justification: {MISSING_BIBLIOGRAPHY_NOTICE} "
            "Independent retrieved sources are not detected citations. "
            "Attribution remains unverified. Recommend adding citations. "
            "Regenerate the complete JSON response only; do not include commentary."
        )
    if reason == "missing_reference_limit" and criterion_id == "ITSO-02":
        notice = (limit_notice or "")[:500]
        return (
            "\n\nVALIDATOR_FAILURE category=ITSOInvalidPublicSourceUse "
            "criterion=ITSO-02 reason=missing_reference_limit. Include this "
            "exact trusted report-derived sentence in ITSO-02 justification: "
            f"{notice} Do not claim all or every reference was verified. "
            "Keep required source citations, any bibliography notice, and all "
            "evidence constraints. The frozen rubric remains authoritative; "
            "reassess reasoning and scores against its level descriptors and "
            "these observed limits. Regenerate the complete JSON response only; "
            "do not include commentary."
        )
    return (
        f"\n\nVALIDATOR_FAILURE category={category}. "
        "Regenerate the complete JSON response using the exact "
        "required shape and grounded evidence rules; do not include "
        "commentary."
    )


def _v3_repair_reserve(expected_ids: tuple[str, ...]) -> str:
    """Return the longest suffix possible from the v3 diagnostic allowlist."""
    category = max(_V3_REPAIR_CATEGORIES, key=len)
    criterion_id = max(expected_ids, key=len)
    citation_suffix = _v3_repair_suffix(
        "ITSOInvalidPublicSourceUse",
        criterion_id=max(expected_ids[:2], key=len),
        reason="missing_source_citation",
        source_url="https://" + "u" * 292,
        source_index=12000,
    )
    evidence_suffix = _v3_repair_suffix(
        category,
        criterion_id=criterion_id,
        reason="ungrounded_evidence",
    )
    review_suffix = _v3_repair_suffix(
        category, criterion_id=criterion_id, reason="missing_review_evidence"
    )
    score_suffix = _v3_repair_suffix(
        "ITSOInvalidScore", criterion_id="ITSO-01", reason="unverified_top_score"
    )
    bibliography_suffix = _v3_repair_suffix(
        "ITSOInvalidPublicSourceUse",
        criterion_id="ITSO-02",
        reason="missing_bibliography_limit",
    )
    coverage_suffix = _v3_repair_suffix(
        "ITSOInvalidPublicSourceUse",
        criterion_id="ITSO-02",
        reason="missing_reference_limit",
        limit_notice="Verification limits: " + "x" * 450 + ".",
    )
    return max(
        (
            citation_suffix,
            evidence_suffix,
            review_suffix,
            score_suffix,
            bibliography_suffix,
            coverage_suffix,
        ),
        key=len,
    )


def _append_repair(prompt: AgentPrompt, suffix: str) -> AgentPrompt:
    return replace(
        prompt,
        system_instruction=prompt.system_instruction + suffix,
    )


def _v3_comparison_packet(
    context: ITSOExecutionContext,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select short, exact module excerpts and independently sourced quotes."""
    report_text = dict(context.precomputed_context)["public_reference_verification"][0]
    report = json.loads(report_text)
    terms = [
        token.casefold()
        for row in report["references"][:5]
        for token in re.findall(
            r"[A-Za-z0-9]{4,}", f"{row['query']} {row.get('title') or ''}"
        )
    ]
    ignored = (
        "table of contents",
        "prepared by",
        "republic of the philippines",
        "learning resources management",
        "learning objectives:",
        "assessment:",
        "references:",
    )
    candidates: list[tuple[int, int, str, str]] = []
    for raw_chunk in context.chunk_infos:
        chunk = dict(raw_chunk)
        source = str(chunk.get("text", ""))
        if not source:
            continue
        if any(row.get("cited_reference") for row in report["references"][:5]):
            section = re.search(
                r"(?i)\b(?:learning\s+resources(?!\s+management)|references|"
                r"bibliography|works\s+cited)\b",
                source,
            )
            if section:
                excerpt = source[section.start() : section.start() + 450]
                if section.start() + 450 < len(source):
                    excerpt = excerpt.rsplit(" ", 1)[0]
                candidates.append(
                    (len(set(terms)) + 1, len(excerpt), str(chunk["chunk_id"]), excerpt)
                )
        for sentence in re.finditer(r"[^.!?\n]+[.!?]?", source):
            start, end = sentence.span()
            excerpt = source[start:end].strip()
            if len(excerpt) < 5 or any(
                marker in excerpt.casefold() for marker in ignored
            ):
                continue
            if len(excerpt) > 450:
                excerpt = excerpt[:450].rsplit(" ", 1)[0]
                end = start + len(excerpt)
            overlap = sum(term in excerpt.casefold() for term in set(terms))
            candidates.append((overlap, len(excerpt), str(chunk["chunk_id"]), excerpt))
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for _, _, chunk_id, excerpt in sorted(candidates, reverse=True):
        if chunk_id in selected_ids:
            continue
        selected.append({"chunk_id": chunk_id, "text": excerpt})
        selected_ids.add(chunk_id)
        if len(selected) == 3:
            break
    chunks = selected
    source_quotes = []
    for index, row in enumerate(report["references"][:5], start=1):
        excerpt = row.get("excerpt")
        status = str(row.get("status", "")).casefold()
        url = row.get("source_url")
        if (
            status in {"matched", "ambiguous", "mismatch", "mismatched"}
            and url
            and excerpt
        ):
            source_quote = re.split(
                r"(?<=[.!?])\s+|\n", str(excerpt).strip(), maxsplit=1
            )[0]
            quote = source_quote[:250].rsplit(" ", 1)[0]
            source_quotes.append({"source_id": index, "url": url, "quote": quote})
            break
    return chunks, {
        "module_excerpt_origin": "document_chunks; exact contiguous substrings",
        "independent_source_origin": "completed public reference retrieval",
        "module_excerpts": chunks,
        "module_citation_metadata": [
            {"source_id": index, **row["cited_reference"]}
            for index, row in enumerate(report["references"][:5], start=1)
            if row.get("cited_reference")
        ],
        "independent_source_quotes": source_quotes,
    }


def _v3_usable_source_urls(report_text: str) -> tuple[str, ...]:
    report = json.loads(report_text)
    return tuple(
        item["source_url"]
        for item in report["references"]
        if item["status"].strip().casefold()
        in {"matched", "ambiguous", "mismatch", "mismatched"}
        and isinstance(item.get("source_url"), str)
        and item["source_url"].startswith("https://")
        and bool(item["source_url"][8:].split("/", 1)[0].split("?", 1)[0].strip())
        and isinstance(item.get("excerpt"), str)
        and bool(item["excerpt"].strip())
    )


def _validate_v3_source_citations(
    parsed: dict[str, Any], report_text: str, expected_ids: tuple[str, ...]
) -> None:
    report = json.loads(report_text)
    usable_refs = {
        index: row
        for index, row in enumerate(report["references"], start=1)
        if row["status"].strip().casefold()
        in {"matched", "ambiguous", "mismatch", "mismatched"}
        and isinstance(row.get("source_url"), str)
        and row["source_url"].startswith("https://")
        and bool(row["source_url"][8:].split("/", 1)[0].split("?", 1)[0].strip())
        and isinstance(row.get("excerpt"), str)
        and bool(row["excerpt"].strip())
    }
    raw_scores = parsed.get("criterion_scores")
    rows_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(raw_scores, list):
        rows_by_id = {
            row.get("criterion_id"): row for row in raw_scores if isinstance(row, dict)
        }
    elif isinstance(raw_scores, dict):
        rows_by_id = {
            criterion_id: row if isinstance(row, dict) else {}
            for criterion_id, row in raw_scores.items()
        }
    for criterion_id in ("ITSO-01", "ITSO-02"):
        if criterion_id not in expected_ids:
            continue
        justification = rows_by_id.get(criterion_id, {}).get("justification", "")
        if not isinstance(justification, str):
            justification = ""
        cited_markers = {
            int(index)
            for index in re.findall(
                r"\[\s*source\s+([1-9][0-9]*)\s*\]", justification, re.I
            )
        }
        if cited_markers - set(usable_refs) or not any(
            cites_public_source(justification, row["source_url"])
            or index in cited_markers
            for index, row in usable_refs.items()
        ):
            error = AgentExecutionError(
                "ITSOInvalidPublicSourceUse: required public source citation is missing"
            )
            error.itso_diagnostic_category = "ITSOInvalidPublicSourceUse"
            error.itso_reason = "missing_source_citation"
            error.itso_criterion_id = criterion_id
            raise error
    if (
        report.get("bibliography_status") == "not_detected"
        and "ITSO-02" in expected_ids
    ):
        justification = rows_by_id.get("ITSO-02", {}).get("justification", "")
        if MISSING_BIBLIOGRAPHY_NOTICE.casefold() not in justification.casefold():
            error = AgentExecutionError(
                "ITSOInvalidPublicSourceUse: missing bibliography limit"
            )
            error.itso_diagnostic_category = "ITSOInvalidPublicSourceUse"
            error.itso_reason = "missing_bibliography_limit"
            error.itso_criterion_id = "ITSO-02"
            raise error
    limit_notice = reference_limit_notice(report)
    if limit_notice and "ITSO-02" in expected_ids:
        justification = rows_by_id.get("ITSO-02", {}).get("justification", "")
        if limit_notice.casefold() not in justification.casefold():
            error = AgentExecutionError(
                "ITSOInvalidPublicSourceUse: missing reference verification limit"
            )
            error.itso_diagnostic_category = "ITSOInvalidPublicSourceUse"
            error.itso_reason = "missing_reference_limit"
            error.itso_criterion_id = "ITSO-02"
            raise error


def _extract_and_validate_snapshot(
    context: ITSOExecutionContext,
) -> tuple[tuple[CriterionDefinition, ...], tuple[str, ...], dict[str, str]]:
    """Validate snapshot form bounds and return ordered criteria, codes, titles."""
    snapshot = context.form_snapshot
    if not isinstance(snapshot, EvaluationFormSnapshotDTO):
        raise AgentExecutionError(
            "ITSO requires an EvaluationFormSnapshotDTO instance, "
            f"got {type(snapshot).__name__}"
        )

    if snapshot.agent_id != "itso" or snapshot.evaluation_id != context.evaluation_id:
        raise AgentExecutionError(
            f"ITSO snapshot mismatch: agent_id={snapshot.agent_id!r}, "
            f"evaluation_id={snapshot.evaluation_id!r} "
            f"(expected eval={context.evaluation_id!r})"
        )

    if snapshot.adapter_key != "itso":
        raise AgentExecutionError(
            f"ITSO snapshot adapter mismatch: adapter_key={snapshot.adapter_key!r} "
            "(expected 'itso')"
        )
    try:
        manifest = get_agent_manifest("itso", 3)
    except ValueError as exc:
        raise AgentExecutionError(
            f"Unsupported ITSO adapter version {snapshot.adapter_version}"
        ) from exc
    report = validate_form(snapshot.form, manifest)
    if not report.is_valid:
        codes = ", ".join(
            issue.code for issue in report.issues if issue.severity == "error"
        )
        raise AgentExecutionError(f"ITSO snapshot violates adapter 3: {codes}")

    ordered_criteria: list[CriterionDefinition] = [
        criterion for domain in snapshot.form.domains for criterion in domain.criteria
    ]

    if not ordered_criteria:
        raise AgentExecutionError("ITSO snapshot contains no criteria")
    if len(ordered_criteria) > 10:
        raise AgentExecutionError("ITSO snapshot exceeds 10 criteria")

    casefolded_codes = [c.criterion_code.casefold() for c in ordered_criteria]
    if len(casefolded_codes) != len(set(casefolded_codes)):
        raise AgentExecutionError(
            "ITSO snapshot contains case-insensitive duplicate criterion codes"
        )

    criteria_tuple = tuple(ordered_criteria)
    expected_ids = tuple(c.criterion_code for c in ordered_criteria)
    expected_titles = {c.criterion_code: c.title for c in ordered_criteria}
    return criteria_tuple, expected_ids, expected_titles


def _execute_criteria(
    context: ITSOExecutionContext,
    *,
    ordered_criteria: tuple[CriterionDefinition, ...],
    deadline: float,
    unit_key: str,
    comparison_context: dict[str, Any] | None = None,
    llm_client: Any | None = None,
    llm_temperature: float | None = None,
) -> AgentEvaluationResult:
    if not context.chunk_infos or not any(
        dict(chunk).get("text") for chunk in context.chunk_infos
    ):
        raise AgentExecutionError("document chunks are required for evaluation")

    expected_ids = tuple(c.criterion_code for c in ordered_criteria)
    expected_titles = {c.criterion_code: c.title for c in ordered_criteria}
    criteria_specs = tuple((c.criterion_code, c.title) for c in ordered_criteria)

    start = time.perf_counter()
    timer = PhaseTimer("itso")
    texts = [
        str(dict(chunk).get("text", ""))
        for chunk in context.chunk_infos
        if dict(chunk).get("text")
    ]
    settings = current_execution_config()
    document_review = "ITSO-03" in expected_ids
    prompt_chunks = (
        review_chunks(
            context.chunk_infos, excerpt_chars=settings.agent_max_excerpt_chars
        )
        if document_review
        else context.chunk_infos
    )
    with timer.measure("retrieval"):
        references = _references(context)
    with timer.measure("prompt_build"):
        packed_chunks, packed_chunk_map, dropped, excerpted = pack_itso_chunks(
            prompt_chunks,
            max_chunks=settings.agent_max_chunks,
            max_excerpt_chars=settings.agent_max_excerpt_chars,
            prompt_budget_chars=settings.agent_prompt_budget_chars,
            small_doc_threshold=settings.agent_small_doc_threshold,
            domain_keywords=context.domain_keywords,
        )
        packed_chunk_ids = tuple(packed_chunk_map.keys())
        prompt = build_prompt(
            context,
            ordered_criteria=list(ordered_criteria),
            reference_context=references,
            packed_chunks=packed_chunks,
            dropped=dropped,
            excerpted=excerpted,
            comparison_context=comparison_context,
        )
    # Reserve a bounded, sanitized repair suffix before packing the first request.
    repair_suffix = _v3_repair_reserve(expected_ids)
    total_budget = settings.agent_total_prompt_budget_chars
    initial_budget = total_budget - len(repair_suffix)
    if initial_budget < 0:
        raise AgentExecutionError("ITSO prompt budget cannot reserve repair suffix")
    prompt, packed_chunk_map, dropped, excerpted, budget = _fit_v3_prompt_budget(
        context,
        ordered_criteria=list(ordered_criteria),
        references=references,
        packed_chunks=packed_chunks,
        packed_chunk_map=packed_chunk_map,
        dropped=dropped,
        excerpted=excerpted,
        comparison_context=comparison_context,
        budget_chars=initial_budget,
    )
    packed_chunk_ids = tuple(packed_chunk_map)
    if not packed_chunk_map or not any(
        text.strip() for text in packed_chunk_map.values()
    ):
        raise AgentExecutionError(
            "ITSO adapter 3 requires a document chunk within prompt budget"
        )
    if len(prompt) > initial_budget:
        raise AgentExecutionError(
            "ITSO required rubric and verification context exceed prompt budget"
        )
    if len(prompt) + len(repair_suffix) > total_budget:
        raise AgentExecutionError("ITSO prompt exceeds total budget before transport")
    prompt_chars = len(prompt)
    logger.info(
        "[EVAL_PROMPT_SIZE] agent=itso | prompt_chars=%d | trimmed=%s | "
        "budget=%d | rubric_context=0 | reference_context=%d | "
        "prompt_version_id=%s",
        prompt_chars,
        "yes" if budget.trimmed else "no",
        settings.agent_total_prompt_budget_chars,
        len(references),
        None,
    )
    temperature = (
        llm_temperature
        if llm_temperature is not None
        else settings.get_agent_temperature("itso")
    )
    client = llm_client or context.llm_client
    if getattr(settings, "llm_response_mode", "json_object") == "json_schema":
        response_contract = ResponseContract.json_schema(
            build_response_schema(packed_chunk_ids, criteria_specs=criteria_specs),
            name="itso_response_v1",
        )
    else:
        response_contract = ResponseContract.json_object()
    repair_occurred = False
    verification_text = dict(context.precomputed_context)[
        "public_reference_verification"
    ][0]
    adapter = RunLLMClient(client, "itso", default_response_contract=response_contract)
    requested = adapter.requested_model or "unknown"
    with timer.measure("llm_call"):
        try:
            completion = adapter.generate_result(
                prompt,
                temperature=temperature,
                max_new_tokens=settings.llm_max_new_tokens,
                deadline=deadline,
                response_contract=response_contract,
            )
            raw = completion.content
        except AgentLLMError as exc:
            if str(exc) == "LLM output was truncated":
                raw = ""
                repair_occurred = True
            else:
                raise
    with timer.measure("parse"):
        try:
            parsed = parse_response(
                raw,
                expected_ids=expected_ids,
                expected_titles=expected_titles,
                known_chunk_ids=packed_chunk_ids,
                packed_chunk_map=packed_chunk_map,
                strict_cited_grounding=True,
            )
            _validate_v3_source_citations(parsed, verification_text, expected_ids)
            validate_review_evidence(
                parsed, ordered_criteria, packed_chunk_map=packed_chunk_map
            )
        except AgentExecutionError as exc:
            category = getattr(exc, "itso_diagnostic_category", None)
            reason = getattr(exc, "itso_reason", None)
            criterion_id = getattr(exc, "itso_criterion_id", None)
            safe_category = (
                category if category in _V3_REPAIR_CATEGORIES else "ITSO_INVALID"
            )
            if reason == "ungrounded_evidence" and criterion_id in expected_ids:
                dynamic_suffix = _v3_repair_suffix(
                    safe_category,
                    criterion_id=criterion_id,
                    reason="ungrounded_evidence",
                )
            elif reason == "missing_review_evidence" and criterion_id in expected_ids:
                dynamic_suffix = _v3_repair_suffix(
                    safe_category, criterion_id=criterion_id, reason=reason
                )
            elif reason == "unverified_top_score" and criterion_id == "ITSO-01":
                dynamic_suffix = _v3_repair_suffix(
                    safe_category, criterion_id=criterion_id, reason=reason
                )
            elif reason == "missing_source_citation" and criterion_id in {
                "ITSO-01",
                "ITSO-02",
            }:
                source_url = next(iter(_v3_usable_source_urls(verification_text)), None)
                source_index = next(
                    index
                    for index, row in enumerate(
                        json.loads(verification_text)["references"], 1
                    )
                    if row.get("source_url") == source_url
                )
                dynamic_suffix = _v3_repair_suffix(
                    safe_category,
                    criterion_id=criterion_id,
                    reason=reason,
                    source_url=source_url,
                    source_index=source_index,
                )
            elif reason == "missing_bibliography_limit" and criterion_id == "ITSO-02":
                dynamic_suffix = _v3_repair_suffix(
                    safe_category,
                    criterion_id=criterion_id,
                    reason=reason,
                )
            elif reason == "missing_reference_limit" and criterion_id == "ITSO-02":
                report = json.loads(verification_text)
                dynamic_suffix = _v3_repair_suffix(
                    safe_category,
                    criterion_id=criterion_id,
                    reason=reason,
                    limit_notice=reference_limit_notice(report),
                )
            else:
                dynamic_suffix = _v3_repair_suffix(safe_category)
            repair_prompt = _append_repair(prompt, dynamic_suffix)
            if len(repair_prompt) > total_budget:
                repair_prompt = _append_repair(
                    prompt,
                    _v3_repair_suffix("ITSO_INVALID"),
                )
            if len(repair_prompt) > total_budget:
                raise AgentExecutionError(
                    "ITSO repair prompt exceeds total budget"
                ) from exc
            with timer.measure("llm_repair"):
                repaired_result = adapter.generate_result(
                    repair_prompt,
                    temperature=temperature,
                    max_new_tokens=settings.llm_max_new_tokens,
                    deadline=deadline,
                    response_contract=response_contract,
                )
                repaired = repaired_result.content
            parsed = parse_response(
                repaired,
                expected_ids=expected_ids,
                expected_titles=expected_titles,
                known_chunk_ids=packed_chunk_ids,
                packed_chunk_map=packed_chunk_map,
                strict_cited_grounding=True,
            )
            _validate_v3_source_citations(parsed, verification_text, expected_ids)
            validate_review_evidence(
                parsed, ordered_criteria, packed_chunk_map=packed_chunk_map
            )
            repair_occurred = True
        scores = criterion_scores(
            parsed,
            expected_ids=expected_ids,
            expected_titles=expected_titles,
            known_chunk_ids=packed_chunk_ids,
            packed_chunk_map=packed_chunk_map,
            strict_cited_grounding=True,
        )
        # Strategy typed score normalization verification
        criteria_by_code = {c.criterion_code: c for c in ordered_criteria}
        for score_item in scores:
            crit_def = criteria_by_code[score_item.criterion_id]
            measurement_evidence = (
                score_item.evidence[0]
                if score_item.evidence
                else "ungrounded advisory output"
            )
            norm_res = normalize_llm_guidance_score(
                crit_def.strategy_config,  # type: ignore[arg-type]
                GroundedScoreMeasurement(
                    score=score_item.score,
                    evidence=measurement_evidence,
                ),
            )
            if norm_res.score != score_item.score:
                raise AgentExecutionError("Score normalization mismatch")

        advisory_outputs = collect_advisory_outputs(parsed, expected_ids=expected_ids)
        model_response_payload = json.loads(json.dumps(parsed))
        result_summary = parsed.get("summary", "")
        uses_public_sources = bool(set(expected_ids) & {"ITSO-01", "ITSO-02"})
        if uses_public_sources:
            verification_summary = _v3_reference_summary(verification_text)
            summary_separator = " " if result_summary else ""
            model_summary = result_summary[
                : max(0, 2000 - len(verification_summary) - len(summary_separator))
            ]
            result_summary = f"{model_summary}{summary_separator}{verification_summary}"
        if document_review:
            # Keep the captured user context authoritative for detailed coverage.
            payload = json.loads(prompt.user_context)
            coverage = review_coverage(context, payload["document_chunks"])
            document_summary = (
                f"Only {coverage['reviewed_chunk_count']} of "
                f"{coverage['supplied_chunk_count']} text sections were reviewed; "
                "images and extraction omissions were not assessed. Ownership "
                "and permissions need human review. Institutional policy text "
                f"was {payload['local_policy_status']}."
            )
            summary_budget = max(0, 2000 - len(document_summary) - 1)
            if len(result_summary) > summary_budget:
                marker = "… [summary shortened]"
                result_summary = (
                    result_summary[: max(0, summary_budget - len(marker))].rstrip()
                    + marker
                )
            result_summary = (
                result_summary.rstrip()
                + (" " if result_summary else "")
                + document_summary
            )
    provenance = thaw(context.provenance)
    policy_evidence = thaw(context.policy_evidence)
    delivered_policy = policy_context(policy_evidence, set(expected_ids))
    policy_trimmed = (
        document_review and bool(policy_evidence) and not bool(delivered_policy)
    )
    runtime = {
        "requested_model": requested,
        "actual_model": adapter.actual_model,
        "requested_temperature": temperature,
        "fallback_occurred": adapter.fallback_occurred,
        "repair_occurred": repair_occurred,
        "prompt_trimmed": budget.trimmed,
        "reference_context_dropped": budget.reference_context_dropped,
        "policy_trimmed": policy_trimmed,
        "response_format_downgraded": adapter.telemetry.get(
            "response_format_downgraded", False
        ),
    }
    provenance.update(
        {
            key: value
            for key, value in runtime.items()
            if key not in provenance or key == "policy_trimmed"
        }
    )
    safe = sanitize_provenance(provenance) or None
    timer.log_summary(prompt_chars=len(prompt))

    response_payload = model_response_payload
    raw_completion = repaired if repair_occurred else raw
    effective_prompt = repair_prompt if repair_occurred else prompt
    prompt_text = effective_prompt.render_flat()
    generation = CapturedGeneration(
        unit_key=unit_key,
        criterion_ids=tuple(s.criterion_id for s in scores),
        prompt_text=prompt_text,
        prompt_messages=tuple(
            {"role": m.role, "content": m.content} for m in effective_prompt.messages
        ),
        response_text=(
            json.dumps(response_payload, ensure_ascii=False)
            if isinstance(response_payload, dict)
            else str(raw_completion)
        ),
        response_json=response_payload if isinstance(response_payload, dict) else None,
        response_contract_key="itso_scores.v1",
        response_contract_version=1,
        model_name=adapter.model,
        envelope_status="repaired" if repair_occurred else "ok",
    )

    # The full trusted report and its required exact limit sentence remain in
    # the captured generation. Keep persisted criterion reasoning concise; the
    # backend projects these same facts into its separate reference note.
    if "ITSO-02" in expected_ids:
        report = json.loads(verification_text)
        scores = tuple(
            replace(
                score,
                justification=readable_reference_justification(
                    score.justification, report
                ),
            )
            if score.criterion_id == "ITSO-02"
            else score
            for score in scores
        )

    return AgentEvaluationResult(
        agent_name="itso",
        evaluation_id=context.evaluation_id,
        document_id=context.document_id,
        subtotal=sum(score.score for score in scores) / len(scores) if scores else 0.0,
        criterion_scores=scores,
        prompt_version_id=None,
        summary=result_summary,
        model_name=adapter.actual_model,
        processing_seconds=time.perf_counter() - start,
        token_count=sum(len(text.split()) for text in texts),
        success=True,
        error_message=None,
        raw_response=None,
        prompt_text=None,
        provenance=safe,
        advisory_outputs=advisory_outputs,
        metadata={
            "prompt_chars": prompt_chars,
            "rubric_context_size": 0,
            "reference_context_size": len(references),
            "prompt_trimmed": budget.trimmed,
            "reference_context_dropped": budget.reference_context_dropped,
            "prompt_version_id": None,
            "response_schema_version": ITSO_RESPONSE_SCHEMA_VERSION,
        },
        generations=(generation,),
    )


def _references(context: ITSOExecutionContext) -> list[str]:
    cached = dict(context.precomputed_context)
    references: list[str] = []
    for source_type in ("syllabus", "curriculum"):
        values = cached.get(source_type, ())
        if not isinstance(values, tuple) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise AgentExecutionError(
                "ITSO precomputed reference context has an invalid shape"
            )
        references.extend(values)
    values = cached.get("public_reference_verification")
    if (
        not isinstance(values, tuple)
        or not values
        or len(values) != 1
        or any(
            not isinstance(value, str) or not value.strip() or len(value) > 24000
            for value in values
        )
    ):
        raise AgentExecutionError(
            "ITSO adapter 3 requires bounded public reference verification context"
        )
    try:
        report = json.loads("\n".join(values))
    except (TypeError, json.JSONDecodeError) as exc:
        raise AgentExecutionError(
            "ITSO public reference verification report is malformed"
        ) from exc
    if (
        not isinstance(report, dict)
        or report.get("status") != "completed"
        or report.get("scope") != ["ITSO-01", "ITSO-02"]
        or not isinstance(report.get("references"), list)
        or not report.get("references")
        or len(report["references"]) > 5
    ):
        raise AgentExecutionError(
            "ITSO public reference verification report is malformed"
        )
    coverage = report.get("coverage", {})
    if not isinstance(coverage, dict) or any(
        key in coverage
        and (type(coverage[key]) is not int or not 0 <= coverage[key] <= 12000)
        for key in ("found", "checked", "skipped", "total")
    ):
        raise AgentExecutionError("ITSO reference coverage is malformed")
    for item in report["references"]:
        if (
            not isinstance(item, dict)
            or any(
                key not in item or not isinstance(item[key], str)
                for key in ("query", "status")
            )
            or any(
                key not in item
                or item[key] is not None
                and not isinstance(item[key], str)
                for key in ("source_url", "title", "excerpt")
            )
            or isinstance(item.get("source_url"), str)
            and len(item["source_url"]) > 2048
            or any(
                not isinstance(item.get(key), list)
                or any(not isinstance(value, str) for value in item[key])
                for key in (
                    "matched_fields",
                    "mismatches",
                    *(("unverified_fields",) if "unverified_fields" in item else ()),
                )
            )
        ):
            raise AgentExecutionError(
                "ITSO public reference verification report is malformed"
            )
        citation = item.get("cited_reference")
        if citation is not None and (
            not isinstance(citation, dict)
            or not isinstance(citation.get("section"), str)
            or not 1 <= len(citation["section"]) <= 80
            or any(
                citation.get(key) is not None
                and (
                    not isinstance(citation[key], str)
                    or not 1 <= len(citation[key]) <= bound
                )
                for key, bound in (("title", 300), ("doi", 200))
            )
            or not isinstance(citation.get("authors"), list)
            or len(citation["authors"]) > 8
            or any(
                not isinstance(author, str) or not 1 <= len(author) <= 100
                for author in citation["authors"]
            )
            or citation.get("year") is not None
            and (
                type(citation["year"]) is not int
                or not 1400 <= citation["year"] <= 2200
            )
        ):
            raise AgentExecutionError(
                "ITSO public reference citation metadata is malformed"
            )
        if item["status"].casefold() in {"matched", "mismatch", "mismatched"} and (
            not isinstance(item["source_url"], str)
            or not item["source_url"].startswith(("https://", "http://"))
            or not isinstance(item["excerpt"], str)
            or not item["excerpt"].strip()
        ):
            raise AgentExecutionError(
                "ITSO public reference verification report contains ungrounded evidence"
            )
    usable = any(
        item["status"].strip().casefold()
        in {"matched", "ambiguous", "mismatch", "mismatched"}
        and isinstance(item["source_url"], str)
        and item["source_url"].startswith("https://")
        and bool(item["source_url"][8:].split("/", 1)[0].split("?", 1)[0].strip())
        and isinstance(item["excerpt"], str)
        and bool(item["excerpt"].strip())
        for item in report["references"]
    )
    if not usable:
        raise AgentExecutionError(
            "ITSO adapter 3 requires at least one usable public reference passage"
        )
    references.extend(values)
    return references


def _fit_v3_prompt_budget(
    context: ITSOExecutionContext,
    *,
    ordered_criteria: list[CriterionDefinition],
    references: list[str],
    packed_chunks: list[dict[str, Any]],
    packed_chunk_map: dict[str, str],
    dropped: bool,
    excerpted: bool,
    budget_chars: int,
    comparison_context: dict[str, Any] | None = None,
) -> tuple[str, dict[str, str], bool, bool, PromptBudgetResult]:
    """Fit document excerpts while keeping v3 rubric and report context intact."""
    chunks = [dict(chunk) for chunk in packed_chunks]
    chunk_map = dict(packed_chunk_map)
    original_chunk_count = len(chunks)
    trimmed = False

    while True:
        prompt = build_prompt(
            context,
            ordered_criteria=ordered_criteria,
            reference_context=references,
            packed_chunks=chunks,
            dropped=dropped,
            excerpted=excerpted,
            comparison_context=comparison_context,
        )
        if len(prompt) <= budget_chars or not chunks:
            result = PromptBudgetResult(prompt, 0, trimmed)
            return prompt, chunk_map, dropped, excerpted, result

        trimmed = True
        if len(chunks) > 1:
            removed = chunks.pop()
            chunk_map.pop(str(removed["chunk_id"]), None)
            dropped = True
            continue

        chunk = chunks[0]
        chunk_id = str(chunk["chunk_id"])
        text = str(chunk.get("text", ""))
        excess = len(prompt) - budget_chars
        target_length = len(text) - excess - 16
        if target_length >= 100 and target_length < len(text):
            excerpt = text[: target_length - 3].rstrip() + "..."
            chunk["text"] = excerpt
            chunk_map[chunk_id] = excerpt[:-3].rstrip()
            excerpted = True
            continue

        chunks.clear()
        chunk_map.clear()
        dropped = dropped or original_chunk_count > 0
