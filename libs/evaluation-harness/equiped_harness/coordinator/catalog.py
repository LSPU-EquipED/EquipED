"""Exact source spans and deterministic IDs for current Coordinator tasks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from equiped_harness.coordinator.objective_gauging import ObjectiveSource
from equiped_harness.exceptions import AgentExecutionError

_MAX_CATALOG_EXCERPT = 4_000


@dataclass(frozen=True, slots=True)
class CatalogItem:
    source_id: str
    source: str
    start: int
    end: int
    text: str
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source": self.source,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "fingerprint": self.fingerprint,
        }


def _item(source_id: str, source: str, start: int, end: int) -> CatalogItem:
    text = source[start:end]
    return CatalogItem(
        source_id=source_id,
        source="slm",
        start=start,
        end=end,
        text=text,
        fingerprint=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _catalog(
    canonical: str, inventory: ObjectiveSource, curriculum: str
) -> dict[str, CatalogItem]:
    # Ordinary criteria receive one complete SLM unit.  Objective and
    # assessment IDs are separate namespaces and can never be confused.
    result: dict[str, CatalogItem] = {}
    for offset in range(0, len(canonical), _MAX_CATALOG_EXCERPT):
        index = offset // _MAX_CATALOG_EXCERPT + 1
        result[f"slm-{index:04d}"] = _item(
            f"slm-{index:04d}",
            canonical,
            offset,
            min(len(canonical), offset + _MAX_CATALOG_EXCERPT),
        )
    for objective in inventory.objectives:
        result[f"objective-{objective.objective_id[4:]}"] = CatalogItem(
            source_id=f"objective-{objective.objective_id[4:]}",
            source="objective",
            start=objective.start,
            end=objective.end,
            text=objective.text,
            fingerprint=hashlib.sha256(objective.text.encode("utf-8")).hexdigest(),
        )
    cursor = 0
    assessment_count = 0
    for section in inventory.assessment_sections:
        start = canonical.find(section, cursor)
        if start < 0:
            start = canonical.find(section)
        if start < 0:
            raise AgentExecutionError("Assessment section has no exact source span")
        for offset in range(0, len(section), _MAX_CATALOG_EXCERPT):
            assessment_count += 1
            key = f"assessment-{assessment_count:04d}"
            text = section[offset : offset + _MAX_CATALOG_EXCERPT]
            result[key] = CatalogItem(
                key,
                "assessment",
                start + offset,
                start + offset + len(text),
                text,
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        cursor = start + len(section)
    for offset in range(0, len(curriculum), _MAX_CATALOG_EXCERPT):
        key = f"curriculum-{offset // _MAX_CATALOG_EXCERPT + 1:04d}"
        text = curriculum[offset : offset + _MAX_CATALOG_EXCERPT]
        result[key] = CatalogItem(
            key,
            "curriculum",
            offset,
            offset + len(text),
            text,
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
    return result
