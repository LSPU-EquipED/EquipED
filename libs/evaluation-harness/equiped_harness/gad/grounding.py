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


def ground_single_excerpt(
    excerpt: str,
    claimed_chunk_id: str,
    packed_chunks: list[dict[str, Any]],
) -> tuple[str, str] | None:
    """Ground one excerpt against packed chunks, with a fallback search.

    Tries ``claimed_chunk_id`` first (exact substring match, same rule as
    ``ground_instances``). If that fails, searches every other packed
    chunk for the same excerpt before giving up. Mirrors ITSO's
    ``itso/response.py::_normalize_evidence`` fallback pattern.

    Returns ``(excerpt, actual_chunk_id)`` on success -- ``actual_chunk_id``
    is whichever chunk the excerpt was actually found in, which may differ
    from ``claimed_chunk_id``. Returns ``None`` if the excerpt is not found
    verbatim in any provided chunk.
    """
    if not isinstance(excerpt, str) or not excerpt:
        return None

    chunk_map: dict[str, str] = {}
    for chunk in packed_chunks:
        cid = str(chunk.get("chunk_id", "")).strip()
        text = str(chunk.get("text", ""))
        if cid:
            chunk_map[cid] = text

    claimed_text = chunk_map.get(claimed_chunk_id)
    if claimed_text is not None and excerpt in claimed_text:
        return excerpt, claimed_chunk_id

    for chunk_id, text in chunk_map.items():
        if chunk_id == claimed_chunk_id:
            continue
        if excerpt in text:
            return excerpt, chunk_id

    return None
