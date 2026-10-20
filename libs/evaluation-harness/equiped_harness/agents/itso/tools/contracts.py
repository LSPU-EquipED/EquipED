"""Backend tool contracts, not admission/consent authentication or scoring contracts."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from equiped_harness.tools.contracts import Code
from equiped_harness.tools.contracts import VerificationError as VerificationError


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
