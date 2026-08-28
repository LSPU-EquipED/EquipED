"""Pydantic schemas for the admin rubric editor."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, field_validator


def _clean_title(value: str, *, max_length: int) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    if len(stripped) > max_length:
        raise ValueError(f"must be at most {max_length} characters")
    return stripped


class RubricCriterionOut(BaseModel):
    rubric_criterion_id: uuid.UUID
    criterion_code: str
    title: str
    description: str
    display_order: int


class RubricDomainOut(BaseModel):
    rubric_domain_id: uuid.UUID
    code: str
    title: str
    display_order: int
    criteria: list[RubricCriterionOut]


class RubricSetOut(BaseModel):
    rubric_set_id: uuid.UUID
    agent_id: str
    name: str
    version_number: int
    status: str
    domains: list[RubricDomainOut]


class RubricSetListResponse(BaseModel):
    rubric_sets: list[RubricSetOut]


class RubricCriterionUpdate(BaseModel):
    title: str
    description: str

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str) -> str:
        return _clean_title(value, max_length=300)

    @field_validator("description")
    @classmethod
    def _check_description(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class RubricDomainUpdate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str) -> str:
        return _clean_title(value, max_length=200)


__all__ = [
    "RubricCriterionOut",
    "RubricCriterionUpdate",
    "RubricDomainOut",
    "RubricDomainUpdate",
    "RubricSetListResponse",
    "RubricSetOut",
]
