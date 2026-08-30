"""Allowlisted presentation DTOs for dynamic CID evaluation forms."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from .snapshot_contracts import EvaluationFormSnapshotDTO


class EvaluationFormCriterionPresentation(BaseModel):
    """Allowlisted criterion presentation for faculty evaluation results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rubric_criterion_id: uuid.UUID
    criterion_code: str
    title: str
    description: str
    display_order: int


class EvaluationFormDomainPresentation(BaseModel):
    """Allowlisted domain presentation for faculty evaluation results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rubric_domain_id: uuid.UUID
    code: str
    title: str
    display_order: int
    criteria: list[EvaluationFormCriterionPresentation]


class EvaluationFormPresentation(BaseModel):
    """Allowlisted form snapshot presentation for faculty evaluation results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    form_snapshot_id: uuid.UUID
    rubric_set_id: uuid.UUID
    version: int
    snapshot_hash: str
    adapter_key: str
    adapter_version: int
    domains: list[EvaluationFormDomainPresentation]


def build_evaluation_form_presentation(
    snapshot: EvaluationFormSnapshotDTO,
) -> EvaluationFormPresentation:
    """Build an allowlisted form presentation DTO from a verified snapshot DTO."""
    form = snapshot.form
    domains_presentation: list[EvaluationFormDomainPresentation] = []
    for domain in form.domains:
        criteria_presentation = [
            EvaluationFormCriterionPresentation(
                rubric_criterion_id=criterion.rubric_criterion_id,
                criterion_code=criterion.criterion_code,
                title=criterion.title,
                description=criterion.description,
                display_order=criterion.display_order,
            )
            for criterion in domain.criteria
        ]
        domains_presentation.append(
            EvaluationFormDomainPresentation(
                rubric_domain_id=domain.rubric_domain_id,
                code=domain.code,
                title=domain.title,
                display_order=domain.display_order,
                criteria=criteria_presentation,
            )
        )

    return EvaluationFormPresentation(
        form_snapshot_id=snapshot.snapshot_id,
        rubric_set_id=snapshot.rubric_set_id,
        version=form.version_number,
        snapshot_hash=snapshot.snapshot_hash,
        adapter_key=snapshot.adapter_key,
        adapter_version=snapshot.adapter_version,
        domains=domains_presentation,
    )


__all__ = [
    "EvaluationFormCriterionPresentation",
    "EvaluationFormDomainPresentation",
    "EvaluationFormPresentation",
    "build_evaluation_form_presentation",
]
