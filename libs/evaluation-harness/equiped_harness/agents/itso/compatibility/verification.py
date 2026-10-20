"""Read-only DTOs for interpreting saved ITSO public verification records.

These contracts preserve the serialized verification plan and capture shape used
by existing assessments. Current public-search tools do not depend on them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from equiped_harness.tools.contracts import Code, VerificationError

from ..tools.contracts import (
    Candidate,
    Frozen,
    Metadata,
    PublicReference,
    clean_field,
    identity_hash,
)


class Profile(Frozen):
    version: Literal["itso-public-v1"] = "itso-public-v1"
    doi_max: int = Field(default=20, ge=0, le=20)
    query_max: int = Field(default=5, ge=0, le=5)
    page_max: int = Field(default=5, ge=0, le=5)
    attempt_max: int = Field(default=95, ge=0, le=95)

    @property
    def profile_hash(self) -> str:
        return identity_hash(self)

    def reserve(self, d: int, q: int, p: int) -> int:
        r = 3 * d + 2 * q + 5 * p
        if not (
            0 <= d <= self.doi_max
            and 0 <= q <= self.query_max
            and 0 <= p <= self.page_max
            and r <= self.attempt_max
        ):
            raise VerificationError(Code.CAPACITY)
        return r


class ReferenceTask(Frozen):
    task_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    kind: Literal["doi", "search"]
    reference: PublicReference

    @model_validator(mode="after")
    def fields(self):
        if (self.kind == "doi" and not self.reference.doi) or (
            self.kind == "search" and not self.reference.title
        ):
            raise ValueError(Code.INVALID)
        return self


class PageTask(Frozen):
    task_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    upstream_task_id: str
    candidate_rank: int = Field(ge=0, le=2)
    purpose: Literal["reference_metadata", "license_metadata"]
    # Redirects are frozen by the authenticated manifest, not inferred from HTML.
    redirect_urls: tuple[str, ...] = Field(default=(), max_length=2)
    robots_redirect_urls: tuple[str, ...] = Field(default=(), max_length=2)


class VerificationPlan(Frozen):
    scope_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    source_snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    disclosure_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile: Profile = Profile()
    profile_hash: str
    references: tuple[ReferenceTask, ...] = ()
    pages: tuple[PageTask, ...] = ()

    @model_validator(mode="after")
    def scope(self):
        if self.profile_hash != self.profile.profile_hash:
            raise ValueError(Code.INVALID)
        ids = [t.task_id for t in (*self.references, *self.pages)]
        if len(set(ids)) != len(ids):
            raise ValueError(Code.INVALID)
        upstream = {t.task_id for t in self.references}
        slots = [(p.upstream_task_id, p.candidate_rank) for p in self.pages]
        if any(p.upstream_task_id not in upstream for p in self.pages) or (
            len(set(slots)) != len(slots)
        ):
            raise ValueError(Code.INVALID)
        self.profile.reserve(
            sum(t.kind == "doi" for t in self.references),
            sum(t.kind == "search" for t in self.references),
            len(self.pages),
        )
        return self

    @property
    def reservation(self) -> int:
        return self.profile.reserve(
            sum(t.kind == "doi" for t in self.references),
            sum(t.kind == "search" for t in self.references),
            len(self.pages),
        )

    @property
    def plan_hash(self) -> str:
        return identity_hash(self)


class PageMetadata(Frozen):
    title: str | None = Field(default=None, max_length=300)
    canonical: str | None = Field(default=None, max_length=2048)
    publisher: str | None = Field(default=None, max_length=200)
    license_spans: tuple[str, ...] = Field(default=(), max_length=8)
    license_state: Literal["observed_label_only", "unknown"] = "unknown"

    @model_validator(mode="after")
    def bounded_labels(self):
        if any(not clean_field(span, 180) for span in self.license_spans):
            raise ValueError(Code.MALFORMED)
        if bool(self.license_spans) != (self.license_state == "observed_label_only"):
            raise ValueError(Code.MALFORMED)
        return self


class ToolCapture(Frozen):
    task_id: str
    reference_hash: str
    source_snapshot_hash: str
    method_version: Literal["itso-public-v1"] = "itso-public-v1"
    provider: Literal["crossref", "datacite", "brave", "public_page", "disabled"]
    status: Literal[
        "found",
        "matched",
        "mismatched",
        "ambiguous",
        "not_found_registry",
        "unsupported",
        "unavailable",
        "execution_error",
    ]
    reason: Code | None = None
    metadata: Metadata | None = None
    matched_fields: tuple[str, ...] = ()
    mismatched_fields: tuple[str, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    page: PageMetadata | None = None
    final_url: str | None = None
    content_sha256: str | None = None
    request_sha256: str | None = None
    http_status: int | None = None
    retrieved_at: str
    attempt_count: int
    plan_hash: str
