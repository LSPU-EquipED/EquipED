"""Deterministic prompt packing and total-budget enforcement."""

from __future__ import annotations

import json
import logging
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)


class PromptBudgetResult(NamedTuple):
    prompt: str
    reference_context_dropped: int
    trimmed: bool


def excerpt_text(text: str, max_chars: int) -> str:
    """Truncate chunk text to a safe excerpt length."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _score_chunk(chunk_text: str, domain_keywords: tuple[str, ...]) -> float:
    if not domain_keywords:
        return 0.0
    lower_text = chunk_text.lower()
    return sum(1.0 for keyword in domain_keywords if keyword in lower_text)


def select_chunks(
    chunk_infos: list[dict[str, Any]],
    *,
    max_chunks: int,
    small_doc_threshold: int,
    domain_keywords: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Select bounded chunks, preserving original order for ties."""
    if len(chunk_infos) <= small_doc_threshold:
        return chunk_infos

    scored = [
        (index, _score_chunk(info.get("text", ""), domain_keywords), info)
        for index, info in enumerate(chunk_infos)
    ]
    scored.sort(key=lambda item: (-item[1], item[0]))
    selected = [info for _, _, info in scored[:max_chunks]]
    selected.sort(key=lambda info: chunk_infos.index(info))
    return selected


def pack_chunks(
    chunk_infos: list[dict[str, Any]],
    *,
    max_chunks: int,
    max_excerpt_chars: int,
    prompt_budget_chars: int,
    small_doc_threshold: int,
    domain_keywords: tuple[str, ...] = (),
    agent_name: str = "runtime",
) -> tuple[list[dict[str, Any]], bool, bool]:
    """Apply caps and return packed chunks plus drop/excerpt flags."""
    is_small_doc = len(chunk_infos) <= small_doc_threshold
    selected = select_chunks(
        chunk_infos,
        max_chunks=max_chunks,
        small_doc_threshold=small_doc_threshold,
        domain_keywords=domain_keywords,
    )
    chunks_dropped = len(selected) < len(chunk_infos)

    packed: list[dict[str, Any]] = []
    text_excerpted = False
    for info in selected:
        original_text = str(info.get("text", ""))
        packed_text = (
            original_text
            if is_small_doc
            else excerpt_text(original_text, max_excerpt_chars)
        )
        if len(packed_text) < len(original_text):
            text_excerpted = True
        packed.append(
            {
                "chunk_id": info.get("chunk_id", ""),
                "page_number": info.get("page_number"),
                "text": packed_text,
            }
        )

    if not packed:
        return packed, chunks_dropped, text_excerpted

    packed_json = json.dumps(packed, ensure_ascii=False)
    if len(packed_json) > prompt_budget_chars:
        while len(packed_json) > prompt_budget_chars and packed:
            if len(packed) > 1:
                packed.pop()
            else:
                overhead = len(packed_json) - len(packed[0]["text"])
                safe_text_len = max(prompt_budget_chars - overhead - 3, 50)
                original_chunk_len = len(packed[0]["text"])
                packed[0]["text"] = excerpt_text(packed[0]["text"], safe_text_len)
                text_excerpted = True
                final_chunk_len = len(packed[0]["text"])
                if final_chunk_len < 100:
                    logger.warning(
                        "Agent %s: prompt budget guard hard-trimmed single "
                        "chunk to "
                        "%d chars (safe_text_len=%d, original_chars=%d, "
                        "prompt_budget_chars=%d); excerpt may be too small to "
                        "ground evaluation.",
                        agent_name,
                        final_chunk_len,
                        safe_text_len,
                        original_chunk_len,
                        prompt_budget_chars,
                    )
            packed_json = json.dumps(packed, ensure_ascii=False)
        if not packed:
            return [], chunks_dropped, text_excerpted
        chunks_dropped = True

    return packed, chunks_dropped, text_excerpted


def enforce_total_prompt_budget(
    prompt: str,
    *,
    budget_chars: int,
    agent_name: str = "runtime",
) -> PromptBudgetResult:
    """Trim a serialized prompt in the original reference/rubric order."""
    if len(prompt) <= budget_chars:
        return PromptBudgetResult(prompt, 0, False)

    original_len = len(prompt)
    try:
        payload = json.loads(prompt)
    except (ValueError, TypeError):
        logger.warning(
            "[EVAL_PROMPT_BUDGET] agent=%s | original=%d | trimmed=%d | "
            "budget=%d | status=invalid_json",
            agent_name,
            original_len,
            original_len,
            budget_chars,
        )
        return PromptBudgetResult(prompt, 0, False)

    if not isinstance(payload, dict):
        logger.warning(
            "[EVAL_PROMPT_BUDGET] agent=%s | original=%d | trimmed=%d | "
            "budget=%d | status=non_object_payload",
            agent_name,
            original_len,
            original_len,
            budget_chars,
        )
        return PromptBudgetResult(prompt, 0, False)

    reference_context = payload.get("reference_context")
    original_ref_count = (
        len(reference_context) if isinstance(reference_context, list) else 0
    )
    if isinstance(reference_context, list) and reference_context:
        reference_context.clear()

    rubric_context = payload.get("rubric_context")
    if isinstance(rubric_context, list):
        while (
            len(rubric_context) > 1
            and len(json.dumps(payload, ensure_ascii=False)) > budget_chars
        ):
            rubric_context.pop()

    if len(json.dumps(payload, ensure_ascii=False)) > budget_chars:
        for key in ("reference_context", "rubric_context"):
            entries = payload.get(key)
            if not isinstance(entries, list):
                continue
            for index, entry in enumerate(entries):
                if isinstance(entry, str) and len(entry) > 400:
                    entries[index] = entry[:397].rstrip() + "..."

    trimmed = json.dumps(payload, ensure_ascii=False)
    final_reference = payload.get("reference_context")
    final_ref_count = len(final_reference) if isinstance(final_reference, list) else 0
    trimmed_length = len(trimmed)
    status = "over_budget_after_trim" if trimmed_length > budget_chars else "ok"
    logger.warning(
        "[EVAL_PROMPT_BUDGET] agent=%s | original=%d | trimmed=%d | "
        "budget=%d | status=%s",
        agent_name,
        original_len,
        trimmed_length,
        budget_chars,
        status,
    )
    return PromptBudgetResult(
        trimmed,
        max(original_ref_count - final_ref_count, 0),
        True,
    )
