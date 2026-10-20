"""Backend tool contracts, not admission/consent authentication or scoring contracts."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Code(StrEnum):
    CAPACITY = "verification_capacity_exceeded"
    INVALID = "invalid_public_scope"
    DISABLED = "verification_disabled"
    RUNTIME = "browser_runtime_unavailable"
    KEY = "provider_configuration_unavailable"
    SECURITY = "unsafe_destination"
    DEADLINE = "tool_deadline_exceeded"
    HTTP = "provider_http_error"
    MALFORMED = "malformed_public_response"
    LIMIT = "response_limit_exceeded"
    ROBOTS = "robots_access_unavailable"
    ACCESS = "public_page_access_unavailable"
    BUDGET = "tool_reservation_exhausted"
    REPLAY = "tool_already_started"
    EXECUTION = "tool_execution_error"


class VerificationError(Exception):
    """Safe to expose code/hash only. Never carries URLs, queries or response bytes."""

    def __init__(self, code: Code, reference_hash: str = ""):
        self.code = code
        self.reference_hash = reference_hash
        self.http_status = 422 if code in {Code.CAPACITY, Code.INVALID} else 503
        super().__init__(f"{code.value}:{reference_hash}")


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)


def identity_hash(value: BaseModel) -> str:
    return hashlib.sha256(
        json.dumps(
            value.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def clean_field(value: str, maximum: int) -> bool:
    return bool(value and len(value) <= maximum and value == value.strip()) and not any(
        ord(c) < 32 or ord(c) == 127 for c in value
    )


class PublicReference(Frozen):
    """Public query fields from bibliography records or approved lesson/topic labels.

    The backend selects the permitted fields. Validation alone cannot establish
    whether arbitrary user-supplied text is public; body passages are excluded.
    """

    source_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    visibility: Literal["user_approved_public"]
    origin: Literal["approved_reference_inventory"]
    tags: tuple[Literal["doi", "title", "author", "year"], ...]
    doi: str | None = None
    title: str | None = None
    authors: tuple[str, ...] = ()
    year: int | None = Field(default=None, ge=1400, le=2200)

    @model_validator(mode="after")
    def public_fields(self):
        if self.doi is not None and not re.fullmatch(
            r"10\.\d{4,9}/[A-Za-z0-9._;()/:+-]{1,180}", self.doi
        ):
            raise ValueError(Code.INVALID)
        if self.title is not None and not clean_field(self.title, 300):
            raise ValueError(Code.INVALID)
        if len(self.authors) > 8 or any(not clean_field(a, 100) for a in self.authors):
            raise ValueError(Code.INVALID)
        actual = tuple(
            name
            for name, present in (
                ("doi", self.doi is not None),
                ("title", self.title is not None),
                ("author", bool(self.authors)),
                ("year", self.year is not None),
            )
            if present
        )
        if tuple(sorted(self.tags)) != tuple(sorted(actual)) or not actual:
            raise ValueError(Code.INVALID)
        return self

    @property
    def reference_hash(self) -> str:
        return identity_hash(self)


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


class Metadata(Frozen):
    doi: str | None = None
    title: str | None = None
    authors: tuple[str, ...] = ()
    years: tuple[int, ...] = ()
    publisher: str | None = None
    url: str | None = None


class Candidate(Frozen):
    url: str
    title: str
    match_code: Literal["title_exact", "title_relevant", "doi_exact"]
    # No search snippets/abstracts/source paragraphs are retained.


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
