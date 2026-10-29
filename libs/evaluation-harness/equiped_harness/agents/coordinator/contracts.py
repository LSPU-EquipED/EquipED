"""Coordinator-specific advisory contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from equiped_harness.runtime.bands import ratio_band


class CurriculumObjectiveMatch(BaseModel):
    """Validated curriculum evidence for one frozen source objective."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    objective_id: str = Field(pattern=r"^OBJ-[0-9]{4}$")
    objective_text: str = Field(min_length=1, max_length=4000)
    matched: bool
    excerpt: str = Field(max_length=4000)
    rejected: bool

    @model_validator(mode="after")
    def _validate_support(self) -> CurriculumObjectiveMatch:
        if self.objective_text != self.objective_text.strip():
            raise ValueError("objective_text must be trimmed")
        if (
            self.matched != bool(self.excerpt.strip())
            or self.excerpt != self.excerpt.strip()
        ):
            raise ValueError("only matched objectives carry evidence")
        if self.matched and self.rejected:
            raise ValueError("rejected claims cannot be matched")
        return self


class CoordinatorAlignmentAdvisory(BaseModel):
    """Versioned scored supplement, never an official rubric score."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    contract: Literal["coordinator_alignment.v1"]
    criterion_id: Literal["C-01"]
    criterion_title: Literal["Curriculum Alignment"]
    advisory_only: Literal[True]
    score: int = Field(ge=1, le=4, strict=True)
    justification: str = Field(min_length=1, max_length=4000, strict=True)
    objective_matches: tuple[CurriculumObjectiveMatch, ...] = Field(
        min_length=1, max_length=100
    )

    @model_validator(mode="before")
    @classmethod
    def _validate_disposition(cls, data: Any) -> Any:
        if not isinstance(data, dict) or data.get("advisory_only") is not True:
            raise ValueError("advisory_only must be literal True")
        return data

    @model_validator(mode="after")
    def _validate_coverage(self) -> CoordinatorAlignmentAdvisory:
        if (
            not self.justification.strip()
            or self.justification != self.justification.strip()
        ):
            raise ValueError("justification must be non-blank and trimmed")
        ids = [row.objective_id for row in self.objective_matches]
        if ids != [f"OBJ-{i + 1:04d}" for i in range(len(ids))]:
            raise ValueError("objective IDs must be complete and canonical")
        texts = [
            " ".join(row.objective_text.split()).casefold()
            for row in self.objective_matches
        ]
        if len(texts) != len(set(texts)):
            raise ValueError("duplicate objectives")
        expected = ratio_band(
            sum(row.matched for row in self.objective_matches), len(ids)
        ).band
        if self.score != expected or self.advisory_only is not True:
            raise ValueError("advisory score or disposition is invalid")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Any) -> CoordinatorAlignmentAdvisory:
        return cls.model_validate(data)


class AlignmentEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    source: Literal["slm", "curriculum"]
    excerpt: str = Field(min_length=1, max_length=2000)


class CoordinatorAlignmentJudgment(BaseModel):
    """Qualitative curriculum judgment; no inferred objective denominator."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    contract: Literal["coordinator_alignment.v2"] = "coordinator_alignment.v2"
    criterion_id: Literal["C-01"] = "C-01"
    criterion_title: Literal["Curriculum Alignment"] = "Curriculum Alignment"
    advisory_only: Literal[True] = True
    score: int = Field(ge=1, le=4, strict=True)
    justification: str = Field(min_length=30, max_length=1600, strict=True)
    evidence: tuple[AlignmentEvidence, ...] = Field(min_length=2, max_length=4)
    objective_matches: tuple[CurriculumObjectiveMatch, ...] = ()

    @model_validator(mode="after")
    def _validate_evidence(self):
        if {e.source for e in self.evidence} != {
            "slm",
            "curriculum",
        } or self.objective_matches:
            raise ValueError(
                "Curriculum judgment requires both source kinds and no objective counts"
            )
        return self

    def to_dict(self):
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data):
        return cls.model_validate(data)


__all__ = [
    "CoordinatorAlignmentAdvisory",
    "CurriculumObjectiveMatch",
    "AlignmentEvidence",
    "CoordinatorAlignmentJudgment",
]
