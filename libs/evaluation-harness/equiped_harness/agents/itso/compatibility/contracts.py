"""Read-only historical ITSO source and assessment contracts.

These DTOs preserve durable identity, hashes, and stored-result validation. They
do not execute evaluations.
"""

from __future__ import annotations

import hashlib
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ITSO_CRITERION_IDS = ("ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05")
CriterionID = Literal["ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05"]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]
MAX_SOURCE_CHARACTERS = 200_000
MAX_REFERENCE_CANDIDATES = 1_000


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FrozenDTO(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )


class SourcePage(FrozenDTO):
    page_number: int = Field(ge=1, strict=True)
    start_offset: int = Field(ge=0, strict=True)
    end_offset: int = Field(ge=0, strict=True)
    text_hash: Digest
    is_ocr: bool = False
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def ordered_offsets(self) -> SourcePage:
        if self.end_offset < self.start_offset:
            raise ValueError("page offsets must be ordered")
        return self


class SourceSpan(FrozenDTO):
    source_id: str = Field(min_length=1, max_length=80)
    start_offset: int = Field(ge=0, strict=True)
    end_offset: int = Field(ge=0, strict=True)
    page_number: int | None = Field(default=None, ge=1, strict=True)
    text_hash: Digest

    @model_validator(mode="after")
    def ordered_offsets(self) -> SourceSpan:
        if self.end_offset <= self.start_offset:
            raise ValueError("evidence span must be nonempty and ordered")
        return self


class ReferenceCandidate(FrozenDTO):
    reference_id: str = Field(min_length=1, max_length=80)
    start_offset: int = Field(ge=0, strict=True)
    end_offset: int = Field(ge=0, strict=True)
    text_hash: Digest

    @model_validator(mode="after")
    def ordered_offsets(self) -> ReferenceCandidate:
        if self.end_offset <= self.start_offset:
            raise ValueError("reference span must be nonempty and ordered")
        return self


class CanonicalSourceSnapshot(FrozenDTO):
    contract: Literal["itso_source.v1"] = "itso_source.v1"
    source_id: str = Field(min_length=1, max_length=80)
    source_hash: Digest  # canonical hash, distinct from raw PDF identity
    raw_pdf_hash: Digest | None = None
    canonical_text: str = Field(min_length=1)
    pages: tuple[SourcePage, ...]
    references: tuple[ReferenceCandidate, ...]
    scan_complete: bool = True
    inventory_complete: bool = False
    inventory_version: str = "reference-candidates.regex.v1"
    inventory_uncertainties: tuple[str, ...] = (
        "Candidate detection cannot establish complete bibliography coverage.",
        "Images and visual personal-data coverage are unknown.",
    )
    extractor_version: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def complete_bounded_inventory(self) -> CanonicalSourceSnapshot:
        text = self.canonical_text
        if len(text) > MAX_SOURCE_CHARACTERS:
            raise ValueError("canonical source exceeds complete-scan bound")
        if len(self.references) > MAX_REFERENCE_CANDIDATES:
            raise ValueError("reference inventory exceeds complete-scan bound")
        if not self.scan_complete:
            raise ValueError("incomplete source scan cannot be used for assessment")
        if text_hash(text) != self.source_hash:
            raise ValueError("source hash does not match canonical text")
        if not self.pages:
            raise ValueError("source must retain every page")
        cursor = 0
        for number, page in enumerate(self.pages, 1):
            if page.page_number != number:
                raise ValueError("page map must include every page in order")
            if page.start_offset < cursor or page.end_offset > len(text):
                raise ValueError("page map overlaps or exceeds canonical source")
            if text[cursor : page.start_offset].strip():
                raise ValueError("page map omits source text")
            if text_hash(text[page.start_offset : page.end_offset]) != page.text_hash:
                raise ValueError("page hash mismatch")
            cursor = page.end_offset
        if text[cursor:].strip():
            raise ValueError("page map omits source text")
        ids: set[str] = set()
        for item in self.references:
            if item.reference_id in ids:
                raise ValueError("duplicate reference identity")
            ids.add(item.reference_id)
            if item.end_offset > len(text):
                raise ValueError("reference span exceeds canonical source")
            if text_hash(text[item.start_offset : item.end_offset]) != item.text_hash:
                raise ValueError("reference hash mismatch")
        return self

    def validate_span(self, span: SourceSpan, quote: str | None = None) -> None:
        if span.source_id != self.source_id or span.end_offset > len(
            self.canonical_text
        ):
            raise ValueError("evidence source identity mismatch")
        actual = self.canonical_text[span.start_offset : span.end_offset]
        if text_hash(actual) != span.text_hash or (
            quote is not None and quote != actual
        ):
            raise ValueError("evidence grounding mismatch")
        if span.page_number is not None:
            page = next(
                (p for p in self.pages if p.page_number == span.page_number), None
            )
            if page is None or not (
                page.start_offset
                <= span.start_offset
                < span.end_offset
                <= page.end_offset
            ):
                raise ValueError("evidence page mismatch")


class EvidenceFact(FrozenDTO):
    fact_id: str = Field(min_length=1, max_length=100)
    predicate: str = Field(min_length=1, max_length=100)
    value: str = Field(max_length=2000)
    authority: Literal[
        "proposed_model",
        "verified_mechanical",
        "confirmed_reviewer",
        "rejected_reviewer",
        "unresolved",
    ]
    source_spans: tuple[SourceSpan, ...]
    origin: str = Field(min_length=1, max_length=100)
    method_version: str | None = None
    policy_version: str | None = None
    reviewer_id: str | None = None
    reviewed_at: str | None = None

    @model_validator(mode="after")
    def authority_provenance(self) -> EvidenceFact:
        if self.authority in {"confirmed_reviewer", "rejected_reviewer"} and not (
            self.reviewer_id and self.reviewed_at and self.policy_version
        ):
            raise ValueError("reviewer authority requires actor, time and policy")
        if self.authority == "verified_mechanical" and self.method_version not in {
            "exact-title.v1",
            "exact-author.v1",
            "exact-year.v1",
            "citation-link.v1",
            "hash-offset.v1",
        }:
            raise ValueError("mechanical verification method is not allowlisted")
        return self


class LocatedEvidence(FrozenDTO):
    evidence_id: str = Field(min_length=1, max_length=100)
    span: SourceSpan
    quote: str = Field(min_length=1, max_length=8000)
    relationship: str = Field(min_length=1, max_length=100)


class CriterionAssessment(FrozenDTO):
    criterion_id: CriterionID
    applicability: Literal["applicable", "not_applicable", "unknown"]
    applicability_reason: str = "Context requires authorized review"
    evidence_state: Literal[
        "observed",
        "searched_no_match_with_coverage",
        "none_supplied_or_located",
        "incomplete",
        "unavailable",
    ]
    verification: Literal[
        "unverified",
        "local_exact_match",
        "local_near_match",
        "provider_matched",
        "provider_mismatched",
        "provider_ambiguous",
        "not_found_in_named_registry",
        "unsupported_type",
        "unavailable",
    ]
    evidence: tuple[EvidenceFact, ...] = ()
    concerns: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    score: int | None = Field(default=None, ge=1, le=4, strict=True)
    score_withheld_reason: str | None = None
    rule_version: str | None = None

    @model_validator(mode="after")
    def score_provenance(self) -> CriterionAssessment:
        if self.score is None and not self.score_withheld_reason:
            raise ValueError("unscored criterion requires a withholding reason")
        if self.score is not None and (
            not self.rule_version or self.score_withheld_reason
        ):
            raise ValueError(
                "numeric score requires rule provenance and no null reason"
            )
        return self


class InterpretationGeneration(FrozenDTO):
    criterion_id: CriterionID
    attempt: int = Field(ge=1, le=2, strict=True)
    content: str = Field(max_length=16_000)
    served_model: str
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    physical_attempts: int = Field(ge=1)
    accepted: bool


class ITSOAssessmentResult(FrozenDTO):
    contract: Literal["itso_evidence.v1"] = "itso_evidence.v1"
    agent_name: Literal["itso"] = "itso"
    evaluation_id: str
    document_id: str
    source_hash: Digest
    raw_pdf_hash: Digest
    execution_status: Literal["COMPLETED", "FAILED"]
    scoring_complete: bool
    criteria: tuple[CriterionAssessment, ...]
    subtotal: float | None = Field(default=None, ge=1, le=4)
    generations: tuple[InterpretationGeneration, ...] = ()
    error_code: str | None = None

    @model_validator(mode="after")
    def exact_criteria_and_conservative_subtotal(self) -> ITSOAssessmentResult:
        if tuple(item.criterion_id for item in self.criteria) != ITSO_CRITERION_IDS:
            raise ValueError("result must contain the five official criteria in order")
        scores = tuple(item.score for item in self.criteria)
        complete = all(score is not None for score in scores)
        if self.scoring_complete != complete:
            raise ValueError("scoring_complete must reflect all five criterion scores")
        expected = (
            sum(score for score in scores if score is not None) / 5
            if complete
            else None
        )
        if self.subtotal != expected:
            raise ValueError("subtotal is the mean of all five non-null scores")
        if len(self.generations) > 10:
            raise ValueError("logical model call bound exceeded")
        if self.execution_status == "FAILED" and not self.error_code:
            raise ValueError("failed execution requires a bounded error code")
        return self


def build_source_snapshot(
    source_id: str,
    canonical_text: str,
    page_ranges: tuple[tuple[int, int, int], ...],
    extractor_version: str,
    *,
    raw_pdf_hash: str | None = None,
) -> CanonicalSourceSnapshot:
    """Scan every character; regex candidates are NOT a complete bibliography."""
    if len(canonical_text) > MAX_SOURCE_CHARACTERS:
        raise ValueError("canonical source exceeds complete-scan bound")
    pages = tuple(
        SourcePage(
            page_number=page,
            start_offset=start,
            end_offset=end,
            text_hash=text_hash(canonical_text[start:end]),
            warnings=("blank_or_no_canonical_text",) if start == end else (),
        )
        for page, start, end in page_ranges
    )
    candidates: list[ReferenceCandidate] = []
    for match in re.finditer(
        r"(?m)^[ \t]*(?:\[\d+\]|\d+[.)]|[A-Z][^\n]{2,180}\(\d{4}\))[^\n]*",
        canonical_text,
    ):
        if len(candidates) == MAX_REFERENCE_CANDIDATES:
            raise ValueError("reference inventory exceeds complete-scan bound")
        start, end = match.span()
        candidates.append(
            ReferenceCandidate(
                reference_id=f"ref-{len(candidates) + 1:04d}",
                start_offset=start,
                end_offset=end,
                text_hash=text_hash(canonical_text[start:end]),
            )
        )
    return CanonicalSourceSnapshot(
        source_id=source_id,
        source_hash=text_hash(canonical_text),
        raw_pdf_hash=raw_pdf_hash,
        canonical_text=canonical_text,
        pages=pages,
        references=tuple(candidates),
        inventory_complete=False,
        extractor_version=extractor_version,
    )
