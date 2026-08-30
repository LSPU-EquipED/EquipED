"""Pydantic schemas for the admin rubric editor."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import (
    MAX_CODE_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_SCORING_RULE_LENGTH,
    MAX_TITLE_LENGTH,
    StrategyConfig,
)


def _clean_str(value: str, *, max_length: int, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    if len(stripped) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return stripped


class RubricCriterionMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination_domain_id: uuid.UUID


class RubricCriterionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_criterion_id: uuid.UUID
    rubric_domain_id: uuid.UUID | None = None
    criterion_code: str
    title: str
    description: str
    scoring_rule: str | None = None
    scoring_strategy: str | None = None
    strategy_config: dict[str, Any] | None = None
    display_order: int


class RubricCriterionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_code: str
    title: str
    description: str
    scoring_rule: str | None = None
    strategy_config: StrategyConfig

    @field_validator("criterion_code")
    @classmethod
    def _check_criterion_code(cls, value: str) -> str:
        return _clean_str(
            value, max_length=MAX_CODE_LENGTH, field_name="criterion_code"
        )

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str) -> str:
        return _clean_str(value, max_length=MAX_TITLE_LENGTH, field_name="title")

    @field_validator("description")
    @classmethod
    def _check_description(cls, value: str) -> str:
        return _clean_str(
            value, max_length=MAX_DESCRIPTION_LENGTH, field_name="description"
        )

    @field_validator("scoring_rule")
    @classmethod
    def _clean_scoring_rule(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if len(stripped) > MAX_SCORING_RULE_LENGTH:
            raise ValueError(
                f"scoring_rule must be at most {MAX_SCORING_RULE_LENGTH} characters"
            )
        return stripped


class RubricCriterionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_code: str | None = None
    title: str | None = None
    description: str | None = None
    scoring_rule: str | None = None
    strategy_config: StrategyConfig | None = None

    @field_validator("criterion_code")
    @classmethod
    def _check_criterion_code(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("criterion_code must not be null")
        return _clean_str(
            value, max_length=MAX_CODE_LENGTH, field_name="criterion_code"
        )

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("title must not be null")
        return _clean_str(value, max_length=MAX_TITLE_LENGTH, field_name="title")

    @field_validator("description")
    @classmethod
    def _check_description(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("description must not be null")
        return _clean_str(
            value, max_length=MAX_DESCRIPTION_LENGTH, field_name="description"
        )

    @field_validator("scoring_rule")
    @classmethod
    def _clean_scoring_rule(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if len(stripped) > MAX_SCORING_RULE_LENGTH:
            raise ValueError(
                f"scoring_rule must be at most {MAX_SCORING_RULE_LENGTH} characters"
            )
        return stripped

    @field_validator("strategy_config")
    @classmethod
    def _check_strategy_config(
        cls, value: StrategyConfig | None
    ) -> StrategyConfig | None:
        if value is None:
            raise ValueError("strategy_config must not be null")
        return value

    @model_validator(mode="after")
    def _check_not_empty(self) -> RubricCriterionUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided in update")
        return self


class RubricDomainOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_domain_id: uuid.UUID
    rubric_set_id: uuid.UUID | None = None
    code: str
    title: str
    display_order: int
    criteria: list[RubricCriterionOut] = Field(default_factory=list)


class RubricDomainCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    title: str

    @field_validator("code")
    @classmethod
    def _check_code(cls, value: str) -> str:
        return _clean_str(value, max_length=MAX_CODE_LENGTH, field_name="code")

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str) -> str:
        return _clean_str(value, max_length=MAX_TITLE_LENGTH, field_name="title")


class RubricDomainUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = None
    title: str | None = None

    @field_validator("code")
    @classmethod
    def _check_code(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("code must not be null")
        return _clean_str(value, max_length=MAX_CODE_LENGTH, field_name="code")

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("title must not be null")
        return _clean_str(value, max_length=MAX_TITLE_LENGTH, field_name="title")

    @model_validator(mode="after")
    def _check_not_empty(self) -> RubricDomainUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided in update")
        return self


class RubricSetOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_set_id: uuid.UUID
    agent_id: str
    name: str
    version_number: int
    status: str
    adapter_key: str | None = None
    adapter_version: int | None = None
    published_at: datetime | None = None
    published_by: uuid.UUID | None = None
    created_at: datetime | None = None
    created_by: uuid.UUID | None = None
    retired_at: datetime | None = None
    retired_by: uuid.UUID | None = None
    is_active: bool | None = None
    domains: list[RubricDomainOut] = Field(default_factory=list)


class RubricSetListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_sets: list[RubricSetOut]
    activations: dict[str, uuid.UUID] = Field(default_factory=dict)


class RubricRevisionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revisions: list[RubricSetOut]
    active_pointers: dict[str, uuid.UUID] = Field(default_factory=dict)


class DomainReorderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_domain_id: uuid.UUID
    criterion_ids: list[uuid.UUID]


class RubricReorderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: list[DomainReorderItem]


class RubricPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    activate: bool = True


class ValidationIssueOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    code: str
    message: str
    severity: str = "error"


class ValidationReportOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    issues: list[ValidationIssueOut] = Field(default_factory=list)
    estimated_prompt_chars: int = 0
    criteria_count: int = 0


class RubricActivationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    rubric_set_id: uuid.UUID
    updated_by: uuid.UUID | None = None
    updated_at: datetime


__all__ = [
    "DomainReorderItem",
    "RubricActivationOut",
    "RubricCriterionCreate",
    "RubricCriterionMoveRequest",
    "RubricCriterionOut",
    "RubricCriterionUpdate",
    "RubricDomainCreate",
    "RubricDomainOut",
    "RubricDomainUpdate",
    "RubricPublishRequest",
    "RubricReorderRequest",
    "RubricRevisionsResponse",
    "RubricSetListResponse",
    "RubricSetOut",
    "ValidationIssueOut",
    "ValidationReportOut",
]
