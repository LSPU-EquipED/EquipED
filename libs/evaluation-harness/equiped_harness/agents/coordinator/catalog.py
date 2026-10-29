"""Historical Coordinator source spans and fingerprint validation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from equiped_harness.runtime.source_retrieval import SLM_SOURCE_SPAN_CHARS


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


def read_catalog(rows: Any) -> dict[str, CatalogItem]:
    """Restore persisted source spans after checking their exact fingerprints."""
    if not isinstance(rows, list):
        raise ValueError("current Coordinator catalog is invalid")
    result = {}
    fields = {"source_id", "source", "start", "end", "text", "fingerprint"}
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("current Coordinator catalog item is invalid")
        sid = row["source_id"]
        if (
            not isinstance(sid, str)
            or sid in result
            or not isinstance(row["text"], str)
        ):
            raise ValueError("current Coordinator catalog item is invalid")
        if (
            row["source"] not in {"slm", "objective", "assessment", "curriculum"}
            or type(row["start"]) is not int
            or type(row["end"]) is not int
            or row["start"] < 0
            or row["end"] < row["start"]
            or row["end"] - row["start"] != len(row["text"])
            or hashlib.sha256(row["text"].encode()).hexdigest() != row["fingerprint"]
        ):
            raise ValueError(
                "current Coordinator catalog span or fingerprint is invalid"
            )
        result[sid] = CatalogItem(**row)
    for namespace in ("objective", "assessment", "curriculum"):
        ids = [item.source_id for item in result.values() if item.source == namespace]
        if ids != [f"{namespace}-{index:04d}" for index in range(1, len(ids) + 1)]:
            raise ValueError("current Coordinator catalog namespace IDs are invalid")
    return result


def canonical_source(catalog: dict[str, CatalogItem]) -> str:
    slm_items = [item for item in catalog.values() if item.source == "slm"]
    if any(
        type(item.start) is not int or type(item.end) is not int for item in slm_items
    ):
        raise ValueError("SLM catalog spans are invalid")
    slm = sorted(
        slm_items,
        key=lambda item: item.start,
    )
    pieces: list[str] = []
    cursor = 0
    for index, item in enumerate(slm, 1):
        expected_id = f"slm-{index:04d}"
        if (
            item.source_id != expected_id
            or type(item.start) is not int
            or type(item.end) is not int
            or item.start != cursor
            or item.end <= item.start
            or item.end - item.start > SLM_SOURCE_SPAN_CHARS
            or item.end - item.start != len(item.text)
            or (index < len(slm) and item.end - item.start != SLM_SOURCE_SPAN_CHARS)
            or hashlib.sha256(item.text.encode("utf-8")).hexdigest() != item.fingerprint
        ):
            raise ValueError("SLM catalog spans are invalid")
        cursor = item.end
        pieces.append(item.text)
    return "".join(pieces)
