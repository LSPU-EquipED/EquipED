"""Training data module for EquipED agent preference feedback."""

from __future__ import annotations

from .capabilities import ContractCapability, get_contract_capability
from .contracts import DpoPackageManifest, DpoPair
from .exporter import export_dpo_package
from .projectors import (
    ProjectionResult,
    project_criterion_measurements_v1,
    project_gad_extraction_v1,
    project_itso_scores_v1,
)

__all__ = [
    "ContractCapability",
    "DpoPackageManifest",
    "DpoPair",
    "ProjectionResult",
    "export_dpo_package",
    "get_contract_capability",
    "project_criterion_measurements_v1",
    "project_gad_extraction_v1",
    "project_itso_scores_v1",
]
