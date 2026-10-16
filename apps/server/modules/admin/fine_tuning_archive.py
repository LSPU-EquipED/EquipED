"""File-backed research snapshots, independent of live validation records."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ArchivedOutput(BaseModel):
    score: int = Field(ge=1, le=4)
    status: Literal["ok", "repaired", "fallback", "unavailable"]
    evidence: list[str] | None
    reasoning: str | None
    stored_justification: str | None


class ArchivedCriterion(BaseModel):
    id: str
    title: str
    expected: int = Field(ge=1, le=4)
    base: ArchivedOutput
    adapter: ArchivedOutput
    audit_note: str | None


class ArchivedPromptHash(BaseModel):
    criteria: list[str]
    sha256: str


class ArchivedComparison(BaseModel):
    title: str
    base_validation_id: str
    adapter_validation_id: str
    base_evaluation_id: str
    adapter_evaluation_id: str
    prompt_hashes: list[ArchivedPromptHash]
    criteria: list[ArchivedCriterion]


class ArchivedTraining(BaseModel):
    steps: int
    epochs: float
    first_loss: float
    last_loss: float
    first_margin: float
    last_margin: float


class ArchivedExperiment(BaseModel):
    id: str
    title: str
    adapter_label: str
    scope: str
    reference_kind: str
    pair_count: int | None
    dataset_note: str
    summary: str
    limitations: list[str]
    primary_criteria: list[str] | None
    training: ArchivedTraining | None
    runs: list[ArchivedComparison]


class FineTuningArchive(BaseModel):
    schema_version: int
    archived_on: str
    experiments: list[ArchivedExperiment]


def load_fine_tuning_archive() -> FineTuningArchive:
    """Read curated snapshots without opening a database or calling a model."""
    path = Path(__file__).parent / "data" / "fine_tuning_results.json"
    return FineTuningArchive.model_validate_json(path.read_text(encoding="utf-8"))
