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

    seen_excerpts: set[str] = set()
    accepted_excerpts: list[str] = []
    accepted_chunk_ids: list[str] = []
    rejected = 0

    for inst in instances:
        if not isinstance(inst, dict):
            rejected += 1
            continue
        excerpt = inst.get("excerpt", "")
        chunk_id = inst.get("chunk_id", "")

        if not isinstance(excerpt, str) or not isinstance(chunk_id, str):
            rejected += 1
            continue
        if not excerpt or not chunk_id:
            rejected += 1
            continue

        # Duplicate check (normalised) — case-fold, whitespace-normalise
        norm_excerpt = _normalized(excerpt)
        if not norm_excerpt or norm_excerpt in seen_excerpts:
            rejected += 1
            continue

        # Chunk ID must be known.  Acceptance is deliberately exact: the
        # normalized form is used only to detect duplicate claims.
        if chunk_id not in chunk_map:
            rejected += 1
            continue

        if excerpt not in chunk_map[chunk_id]:
            rejected += 1
            continue

        seen_excerpts.add(norm_excerpt)
        # Persist the canonical source excerpt (as provided by model)
        accepted_excerpts.append(excerpt)
        if chunk_id not in accepted_chunk_ids:
            accepted_chunk_ids.append(chunk_id)

    return accepted_excerpts, accepted_chunk_ids, rejected
