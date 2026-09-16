"""Training data module for EquipED agent preference feedback."""

from __future__ import annotations

from .capabilities import ContractCapability, get_contract_capability
from .contracts import DpoPackageManifest, DpoPair
from .dpo import (
    DpoPair as StreamDpoPair,
)
from .dpo import (
    export_item_level_dpo_pairs,
    export_score_level_dpo_pairs,
)
from .exporter import export_dpo_package
from .projectors import (
    ProjectionResult,
    project_criterion_measurements_v1,
    project_gad_extraction_v1,
    project_gad_scores_v1,
    project_itso_scores_v1,
)

__all__ = [
    "ContractCapability",
    "DpoPackageManifest",
    "DpoPair",
    "StreamDpoPair",
    "ProjectionResult",
    "export_dpo_package",
    "export_item_level_dpo_pairs",
    "export_score_level_dpo_pairs",
    "get_contract_capability",
    "project_criterion_measurements_v1",
    "project_gad_extraction_v1",
    "project_gad_scores_v1",
    "project_itso_scores_v1",
]
