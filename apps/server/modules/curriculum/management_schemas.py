"""Administrator contracts for the structured curriculum catalog."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ObjectiveInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=4000)
    program: Literal["BSCS", "BSInfoTech"]

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.upper()
        if len(value) > 50:
            raise ValueError("Code must contain at most 50 characters")
        return value


class ObjectiveEdit(ObjectiveInput):
    version: int = Field(ge=1)


class MappingEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective_id: UUID
    level: Literal["I", "E", "D"]


class MappingEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    entries: list[MappingEntry] = Field(max_length=500)


class ObjectiveResponse(ObjectiveInput):
    objective_id: UUID
    version: int
    mapping_count: int


class ObjectiveListResponse(BaseModel):
    items: list[ObjectiveResponse]


class MappingResponse(MappingEdit):
    course_id: UUID
