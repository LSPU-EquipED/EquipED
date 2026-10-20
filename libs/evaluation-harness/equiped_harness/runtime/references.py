"""Pure reference query preparation helpers shared by runtime adapters."""

from __future__ import annotations

from typing import Any


def select_reference_query_texts(
    chunk_infos: list[dict[str, Any]] | None, *, max_anchors: int
) -> list[str]:
    if not chunk_infos or max_anchors < 1:
        return []
    non_empty = [
        str(info.get("text", "")).strip()
        for info in chunk_infos
        if str(info.get("text", "")).strip()
    ]
    if not non_empty:
        return []
    if len(non_empty) <= max_anchors:
        return non_empty
    last_index = len(non_empty) - 1
    candidate_indices = [0, last_index // 2, last_index]
    seen: set[int] = set()
    selected: list[str] = []
    for index in candidate_indices:
        if index not in seen:
            seen.add(index)
            selected.append(non_empty[index])
    return selected[:max_anchors]


def dedupe_context_chunks(chunks: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for chunk in chunks:
        if chunk not in seen:
            seen.add(chunk)
            result.append(chunk)
    return result


__all__ = ["dedupe_context_chunks", "select_reference_query_texts"]
