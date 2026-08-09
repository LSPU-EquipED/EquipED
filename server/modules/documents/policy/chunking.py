"""Clause-aware chunking for policy documents."""

from __future__ import annotations

import re
import uuid
from typing import Any

from ..schemas import DocumentChunkData

# Policy-specific chunking targets (100–250 tokens per chunk)
_POLICY_MIN_CHUNK_TOKENS = 100
_POLICY_TARGET_CHUNK_TOKENS = 250
_POLICY_MAX_CHUNK_TOKENS = 500


def _token_count(text: str) -> int:
    return len(text.split())


def build_policy_chunks(
    pages: list[Any],
    domain: str,
    doc_uuid: uuid.UUID,
) -> list[DocumentChunkData]:
    """Clause-aware chunking for policy documents.

    Splits text on clause/section boundaries (e.g. "Section X", "Clause Y",
    "Article Z", numbered headings) and preserves the section reference in
    each chunk. Each chunk preserves its source page's ``page_number`` and
    ``is_ocr`` flags. Uses a target of 100–250 tokens per chunk with
    globally increasing ``chunk_index`` even when a clause is further
    sub-chunked.
    """
    # Policy section heading pattern
    _SECTION_HEADING_RE = re.compile(
        r"(?:^|\n)\s*"
        r"((?:Section|Clause|Article|Rule|Policy)\s+\w+(?:[.:]\s*.*)?)"
        r"(?:\n|$)",
        re.IGNORECASE,
    )

    # Build an ordered list of (page_number, is_ocr, text) for page-level
    # provenance, then split each page into clause-level units.
    page_units: list[tuple[int, bool, str, str | None]] = []

    for page in pages:
        page_text = page.text.strip()
        if not page_text:
            continue

        splits = list(_SECTION_HEADING_RE.finditer(page_text))
        if not splits:
            page_units.append((page.page_number, page.is_ocr, page_text, None))
        else:
            # Preamble before first heading
            if splits[0].start() > 0:
                preamble = page_text[: splits[0].start()].strip()
                if preamble:
                    page_units.append((page.page_number, page.is_ocr, preamble, None))

            for i, m in enumerate(splits):
                next_start = (
                    splits[i + 1].start() if i + 1 < len(splits) else len(page_text)
                )
                section_text = page_text[m.start() : next_start].strip()
                if section_text:
                    ref_raw = m.group(1)
                    page_units.append(
                        (
                            page.page_number,
                            page.is_ocr,
                            section_text,
                            ref_raw.strip() if ref_raw else None,
                        )
                    )

    chunks: list[DocumentChunkData] = []
    global_index = 0

    for page_number, is_ocr, clause_text, section_ref in page_units:
        if not clause_text:
            continue

        # Use policy-specific target chunk size for sub-chunking
        token_count = _token_count(clause_text)
        if token_count > _POLICY_TARGET_CHUNK_TOKENS:
            sub_chunks = _policy_sub_chunk(clause_text)
        else:
            sub_chunks = [clause_text]

        for sub_text in sub_chunks:
            chunks.append(
                DocumentChunkData(
                    chunk_id=uuid.uuid4(),
                    document_id=doc_uuid,
                    source_type="policy",
                    agent_domain=domain,
                    page_number=page_number,
                    text=sub_text,
                    token_count=_token_count(sub_text),
                    is_ocr=is_ocr,
                    section_ref=section_ref,
                    chunk_index=global_index,
                )
            )
            global_index += 1

    return chunks


def _policy_sub_chunk(text: str) -> list[str]:
    """Split policy text into chunks targeting 100–250 tokens.

    Preserves sentence boundaries where possible and avoids tiny orphan
    chunks at the end by re-merging short trailing content.
    """
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", normalized)
        if s.strip()
    ]
    if not sentences:
        return [normalized]

    chunks: list[str] = []
    current: list[str] = []
    current_count = 0

    for sentence in sentences:
        sentence_tokens = _token_count(sentence)

        # A single sentence that exceeds the target: hard-split it
        if sentence_tokens > _POLICY_TARGET_CHUNK_TOKENS:
            if current:
                chunks.append(" ".join(current))
                current = []
                current_count = 0
            # Hard-split the oversized sentence
            words = sentence.split()
            for start in range(0, len(words), _POLICY_TARGET_CHUNK_TOKENS):
                part = " ".join(words[start:start + _POLICY_TARGET_CHUNK_TOKENS])
                chunks.append(part)
            continue

        # If adding this sentence would exceed target, flush current
        if current and current_count + sentence_tokens > _POLICY_TARGET_CHUNK_TOKENS:
            if current_count >= _POLICY_MIN_CHUNK_TOKENS:
                chunks.append(" ".join(current))
                current = []
                current_count = 0
            else:
                # Current is below min threshold — keep building rather
                # than emitting a too-small chunk
                pass

        current.append(sentence)
        current_count += sentence_tokens

    # Flush remaining
    if current:
        if (
            chunks
            and current_count < _POLICY_MIN_CHUNK_TOKENS
            and _token_count(chunks[-1]) + current_count <= _POLICY_MAX_CHUNK_TOKENS
        ):
            # Merge short trailing content into the previous chunk
            chunks[-1] = chunks[-1] + " " + " ".join(current)
        else:
            chunks.append(" ".join(current))

    return chunks if chunks else [normalized]
