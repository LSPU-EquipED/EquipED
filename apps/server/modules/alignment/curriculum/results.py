"""Pure outcome, failure, provenance, evidence, and summary building."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

from .alignment_check import AlignmentCheckOutcome
from .comparison import compare_objective
from .document_text import DocumentPage, find_evidence_page

#: Failure classification labels persisted in provenance.
FAILURE_NONE = "none"
FAILURE_REJECTED = "rejected_response"
FAILURE_CONFIG = "configuration"
FAILURE_TRANSIENT = "transient"
FAILURE_CALL = "call_failed"

#: Provenance ``error_kind`` values that represent a transient (retryable)
#: LLM call failure rather than a rejected response or a config error.
TRANSIENT_KINDS = frozenset(
    {
        "timeout",
        "connection",
        *{f"http_{code}" for code in (408, 429, *range(500, 600))},
    }
)

REJECTED_RESPONSE_KINDS = frozenset({"response_schema", "response_coverage"})


@dataclass(frozen=True)
class EvaluatedAlignmentResult:
    """Frozen outcome representing the full evaluated curriculum alignment check."""

    model_name: str | None
    objective_results: list[dict[str, Any]]
    summary: dict[str, int]
    success: bool
    error_message: str | None
    provenance: dict[str, Any]


def empty_summary(total_mapped_objectives: int) -> dict[str, int]:
    return {
        "total_mapped_objectives": total_mapped_objectives,
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
        "not_observed": 0,
    }


def classify_failure(outcome: AlignmentCheckOutcome) -> str:
    """Safe, coarse failure classification persisted in provenance."""
    if outcome.success:
        return FAILURE_NONE
    kind = outcome.provenance.error_kind if outcome.provenance else None
    if kind in REJECTED_RESPONSE_KINDS:
        return FAILURE_REJECTED
    if kind == "config":
        return FAILURE_CONFIG
    if kind in TRANSIENT_KINDS:
        return FAILURE_TRANSIENT
    return FAILURE_CALL


def build_failure_message(outcome: AlignmentCheckOutcome) -> str:
    """Concise safe failure text distinguishing rejection, transient, and
    configuration failures -- never echoing provider payloads."""
    kind = outcome.provenance.error_kind if outcome.provenance else None
    if kind in REJECTED_RESPONSE_KINDS:
        return (
            "The alignment check could not complete: the model returned a "
            "malformed or incomplete response that was rejected."
        )
    if kind == "config":
        return (
            "The alignment check could not complete: the LLM configuration "
            "is invalid (unsupported provider, missing model, or unusable "
            "timeout)."
        )
    if kind in TRANSIENT_KINDS:
        return (
            "The alignment check could not complete: the LLM call failed "
            "transiently (timeout, rate limit, or service error) and no "
            "retry succeeded."
        )
    return (
        "The alignment check could not complete: the LLM call failed and no "
        "retry succeeded."
    )


def build_persistable_provenance(
    outcome: AlignmentCheckOutcome,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    """Safe provenance JSON for the existing JSON column.

    Dataclass provenance fields plus text-source and coverage metadata and a
    coarse failure classification. Never contains document text, raw prompts,
    or document/check IDs.
    """
    base = dataclasses.asdict(outcome.provenance) if outcome.provenance else {}
    return {
        **base,
        "text_source": {"source": "persisted_chunks", "ocr_aware": True},
        "coverage": coverage,
        "failure": classify_failure(outcome),
    }


def build_failed_result(
    outcome: AlignmentCheckOutcome,
    coverage: dict[str, Any],
    fallback_model: str | None,
    total_mapped_objectives: int,
) -> EvaluatedAlignmentResult:
    return EvaluatedAlignmentResult(
        model_name=(outcome.provenance.model if outcome.provenance else fallback_model),
        objective_results=[],
        summary=empty_summary(total_mapped_objectives),
        success=False,
        error_message=build_failure_message(outcome),
        provenance=build_persistable_provenance(outcome, coverage),
    )


def build_successful_result(
    outcome: AlignmentCheckOutcome,
    coverage: dict[str, Any],
    fallback_model: str | None,
    mapped: list[dict[str, Any]],
    evaluated_pages: list[DocumentPage],
) -> EvaluatedAlignmentResult:
    scope_bounded = coverage.get("scope") == "bounded"
    llm_by_code = {item.objective_code: item for item in outcome.results}

    objective_results: list[dict[str, Any]] = []
    status_counts = {
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
        "not_observed": 0,
    }
    for objective in mapped:
        code = objective["code"]
        llm_result = llm_by_code.get(code)
        is_addressed = bool(llm_result and llm_result.is_addressed)
        observed_level = llm_result.observed_level if llm_result else None
        evidence = llm_result.evidence if llm_result else None

        evidence_page = None
        if is_addressed and evidence:
            evidence_page = find_evidence_page(evaluated_pages, evidence)
            if evidence_page is None:
                # Evidence not grounded in the evaluated pages -- downgrade
                # rather than trust an ungrounded claim (design spec s.7).
                is_addressed = False
                observed_level = None
                evidence = None

        status = compare_objective(
            is_addressed=is_addressed,
            observed_level=observed_level,
            expected_level=objective["expected_level"],
        )
        if scope_bounded and status == "not_addressed":
            # Bounded scope: absence in the evaluated pages is "not observed",
            # never a whole-document "not addressed" claim.
            status = "not_observed"
        status_counts[status.replace("-", "_")] += 1

        objective_results.append(
            {
                "code": code,
                "description": objective["description"],
                "expected_level": objective["expected_level"],
                "is_addressed": is_addressed,
                "observed_level": observed_level,
                "status": status,
                "evidence": evidence,
                "evidence_page": evidence_page,
            }
        )

    return EvaluatedAlignmentResult(
        model_name=(outcome.provenance.model if outcome.provenance else fallback_model),
        objective_results=objective_results,
        summary={"total_mapped_objectives": len(mapped), **status_counts},
        success=True,
        error_message=None,
        provenance=build_persistable_provenance(outcome, coverage),
    )


__all__ = [
    "EvaluatedAlignmentResult",
    "empty_summary",
    "classify_failure",
    "build_failure_message",
    "build_persistable_provenance",
    "build_failed_result",
    "build_successful_result",
]
