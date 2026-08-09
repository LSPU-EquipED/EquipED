"""Ground combined GAD evidence against frozen document chunks."""

from __future__ import annotations

from typing import Any

MAX_INSTANCES_PER_CRITERION = 10

# ---------------------------------------------------------------------------
# 1.3 — Evidence grounding and entry limits
# ---------------------------------------------------------------------------


def ground_instances(
    section_key: str,
    instances: list[dict[str, Any]],
    packed_chunks: list[dict[str, Any]],
) -> tuple[list[str], list[str], int]:
    """Validate instance excerpts and chunk_ids against frozen packed chunks.

    Returns (accepted_excerpts, accepted_chunk_ids, rejected_count).
    * Unknown chunk_ids, malformed references, duplicate normalised excerpts,
      and excerpts absent from their cited chunk are rejected.
    * Accepted excerpts are the **canonical source text** (not normalised).
    * Chunk IDs are deduplicated per chunk.
    """
    chunk_map: dict[str, str] = {}
    for chunk in packed_chunks:
        cid = str(chunk.get("chunk_id", "")).strip()
        text = str(chunk.get("text", ""))
        if cid:
            chunk_map[cid] = text

    def _normalized(text: str) -> str:
        return " ".join(text.casefold().split())

    normalized_chunks = {
        cid: _normalized(text) for cid, text in chunk_map.items()
    }

    seen_excerpts: set[str] = set()
    accepted_excerpts: list[str] = []
    accepted_chunk_ids: list[str] = []
    rejected = 0

    for inst in instances:
        if not isinstance(inst, dict):
            rejected += 1
            continue
        excerpt = str(inst.get("excerpt", "")).strip()
        chunk_id = str(inst.get("chunk_id", "")).strip()

        if not excerpt or not chunk_id:
            rejected += 1
            continue

        # Duplicate check (normalised) — case-fold, whitespace-normalise
        norm_excerpt = _normalized(excerpt)
        if not norm_excerpt or norm_excerpt in seen_excerpts:
            rejected += 1
            continue

        # Chunk ID must be known
        if chunk_id not in normalized_chunks:
            rejected += 1
            continue

        # Excerpt must be present in the cited chunk's normalised text
        if norm_excerpt not in normalized_chunks[chunk_id]:
            rejected += 1
            continue

        seen_excerpts.add(norm_excerpt)
        # Persist the canonical source excerpt (as provided by model)
        accepted_excerpts.append(excerpt)
        if chunk_id not in accepted_chunk_ids:
            accepted_chunk_ids.append(chunk_id)

    return accepted_excerpts, accepted_chunk_ids, rejected


