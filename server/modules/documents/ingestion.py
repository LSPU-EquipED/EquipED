"""Layer 1 ingestion: extract, OCR fallback, and chunking."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from server.core.config import get_settings

from .boilerplate import strip_repeated_page_boilerplate
from .exceptions import (
    ExtractionFailedError,
    OcrLimitExceededError,
    PasswordProtectedPDFError,
)
from .ocr import perform_ocr_on_page
from .schemas import DocumentChunkData

_MIN_SELECTABLE_TEXT_LEN = 20
_MAX_CHUNK_TOKENS = 2000
_DEFAULT_CHUNK_TOKENS = 450
_DEFAULT_CHUNK_OVERLAP = 60
_MIN_MERGE_THRESHOLD = 100

# Policy-specific chunking targets (100–250 tokens per chunk)
_POLICY_MIN_CHUNK_TOKENS = 100
_POLICY_TARGET_CHUNK_TOKENS = 250
_POLICY_MAX_CHUNK_TOKENS = 500

logger = logging.getLogger(__name__)


def _has_meaningful_selectable_text(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 100:
        return False
    words = re.findall(r"[a-zA-Z]+", stripped)
    if len(words) < 8:
        return False
    return True


@dataclass(slots=True)
class ExtractedPage:
    page_number: int
    text: str
    is_ocr: bool


@dataclass(slots=True)
class _ChunkDraft:
    text: str
    units: list[str]
    token_count: int


def resolve_agent_domain(source_type: str) -> str:
    domain_map = {
        "rubric_sme": "sme",
        "rubric_coord": "coordinator",
        "rubric_gad": "gad",
        "rubric_itso": "itso",
        "slm": "all",
        "syllabus": "all",
        "curriculum": "all",
        "policy": "all",
    }
    return domain_map.get(source_type, "all")


def ingest_document(
    file_path: str,
    source_type: str,
    document_id: str,
    *,
    program: str | None = None,
) -> list[DocumentChunkData]:
    """Extract text from a PDF and return Layer-1 chunks.

    `program` is the program code selected at upload time (only meaningful
    for `source_type == "curriculum"`) — it scopes multi-program CMOs (see
    `curriculum_extraction.extract_curriculum_map_courses`) down to the
    program the document was uploaded for.
    """

    domain = resolve_agent_domain(source_type)
    doc_uuid = uuid.UUID(document_id)

    if source_type == "curriculum":
        course_chunks = _ingest_curriculum_courses(
            file_path, source_type, domain, doc_uuid, program
        )
        if course_chunks:
            return course_chunks

    pages = _extract_pages(file_path)
    chunks: list[DocumentChunkData] = []

    if source_type == "policy":
        return _ingest_policy_document(pages, domain, doc_uuid)

    for page in pages:
        page_chunks = _chunk_page_text(page.text)
        for text in page_chunks:
            chunks.append(
                DocumentChunkData(
                    chunk_id=uuid.uuid4(),
                    document_id=doc_uuid,
                    source_type=source_type,
                    agent_domain=domain,
                    page_number=page.page_number,
                    text=text,
                    token_count=_token_count(text),
                    is_ocr=page.is_ocr,
                )
            )

    return chunks


def _ingest_curriculum_courses(
    file_path: str,
    source_type: str,
    domain: str,
    doc_uuid: uuid.UUID,
    program: str | None,
) -> list[DocumentChunkData]:
    """Per-course chunks for CMO-style curriculum PDFs.

    Falls back to the generic page-chunking path (via an empty return) on
    layouts this extractor doesn't recognize, so curriculum documents that
    aren't single-course-per-page CMOs still ingest normally.
    """

    from .curriculum_extraction import (
        extract_curriculum_courses,
        extract_curriculum_map_courses,
        map_keywords_for_program,
    )

    records = extract_curriculum_courses(file_path)
    if not records:
        records = extract_curriculum_map_courses(
            file_path, included_programs=map_keywords_for_program(program)
        )
    chunks: list[DocumentChunkData] = []
    for record in records:
        text = f"Course: {record.course_title}\n\n{record.course_description}"
        chunks.append(
            DocumentChunkData(
                chunk_id=uuid.uuid4(),
                document_id=doc_uuid,
                source_type=source_type,
                agent_domain=domain,
                page_number=record.page_number,
                text=text,
                token_count=_token_count(text),
                is_ocr=True,
            )
        )
    return chunks


def _ingest_policy_document(
    pages: list[ExtractedPage],
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
def _extract_pages(file_path: str) -> list[ExtractedPage]:
    pdf = Path(file_path)
    if not pdf.exists():
        raise ExtractionFailedError(f"File not found: {file_path}")

    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise ExtractionFailedError("PyMuPDF is not installed") from exc

    pages: list[ExtractedPage] = []
    try:
        with fitz.open(pdf) as doc:
            if doc.is_encrypted:
                raise PasswordProtectedPDFError("PDF is password-protected")

            raw_pages: list[str] = []
            is_ocr_flags: list[bool] = []
            page_numbers: list[int] = []
            settings = get_settings()

            # Pre-scan pages to count how many require OCR
            ocr_candidate_indices = []
            for index, page in enumerate(doc, start=1):
                selectable = (page.get_text() or "").strip()
                if not _has_meaningful_selectable_text(selectable):
                    ocr_candidate_indices.append(index)

            if len(ocr_candidate_indices) > settings.ocr_max_pages:
                raise OcrLimitExceededError(
                    f"Document requires OCR for {len(ocr_candidate_indices)} "
                    f"pages, which exceeds the maximum limit of "
                    f"{settings.ocr_max_pages} pages."
                )

            for index, page in enumerate(doc, start=1):
                selectable = (page.get_text() or "").strip()
                if _has_meaningful_selectable_text(selectable):
                    raw_pages.append(selectable)
                    is_ocr_flags.append(False)
                    page_numbers.append(index)
                    continue

                # Run OCR using our new robust implementation
                outcome = perform_ocr_on_page(page, settings)

                raw_pages.append(outcome.text)
                is_ocr_flags.append(True)
                page_numbers.append(index)
    except (ExtractionFailedError, PasswordProtectedPDFError):
        raise
    except Exception as exc:
        logger.exception(
            "Document extraction failed",
            extra={
                "file_path": str(pdf),
                "exception_class": exc.__class__.__name__,
                "exception_message": str(exc),
            },
        )
        raise ExtractionFailedError("Failed to extract document pages") from exc

    cleaned_pages = strip_repeated_page_boilerplate(raw_pages)
    pages = [
        ExtractedPage(page_number, text, is_ocr)
        for page_number, text, is_ocr in zip(
            page_numbers, cleaned_pages, is_ocr_flags, strict=False
        )
        if text.strip()
    ]

    return pages


def _chunk_page_text(text: str) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    if not normalized:
        return []

    structural_units = _split_structural_units(normalized)
    if len(structural_units) == 1 and _looks_weak_structure(normalized):
        structural_units = _split_sentence_units(normalized)

    drafts = _assemble_chunks(structural_units)
    drafts = _merge_tiny_chunks(drafts)
    return [draft.text for draft in drafts]


def _split_structural_units(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]
    if not blocks:
        return []

    units: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if len(lines) == 1:
            units.append(lines[0])
        else:
            units.append("\n".join(lines))
    return units


def _looks_weak_structure(text: str) -> bool:
    return len([block for block in re.split(r"\n\s*\n+", text) if block.strip()]) <= 1


def _split_sentence_units(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    ]
    if not sentences:
        return []

    units: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _token_count(sentence)
        if sentence_tokens > _MAX_CHUNK_TOKENS:
            if current:
                units.append(" ".join(current).strip())
                current = []
                current_tokens = 0
            units.extend(_hard_split(sentence, _DEFAULT_CHUNK_TOKENS))
            continue

        if current and current_tokens + sentence_tokens > _DEFAULT_CHUNK_TOKENS:
            units.append(" ".join(current).strip())
            current = []
            current_tokens = 0

        current.append(sentence)
        current_tokens += sentence_tokens

    if current:
        units.append(" ".join(current).strip())
    return [unit for unit in units if unit]


def _assemble_chunks(units: list[str]) -> list[_ChunkDraft]:
    drafts: list[_ChunkDraft] = []
    current_units: list[str] = []
    current_tokens = 0
    pending_overlap = ""
    pending_overlap_tokens = 0

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue

        unit_tokens = _token_count(unit)
        if unit_tokens > _MAX_CHUNK_TOKENS:
            if current_units:
                drafts.append(_draft_from_units(current_units))
                current_units = []
                current_tokens = 0
            pending_overlap = ""
            pending_overlap_tokens = 0
            drafts.extend(_drafts_from_hard_split(unit))
            continue

        if not current_units and pending_overlap:
            if pending_overlap_tokens + unit_tokens <= _DEFAULT_CHUNK_TOKENS:
                current_units = [pending_overlap]
                current_tokens = pending_overlap_tokens
            pending_overlap = ""
            pending_overlap_tokens = 0

        if current_units and current_tokens + unit_tokens > _DEFAULT_CHUNK_TOKENS:
            drafts.append(_draft_from_units(current_units))
            pending_overlap = _build_overlap_seed(current_units)
            pending_overlap_tokens = _token_count(pending_overlap)
            current_units = []
            current_tokens = 0

            if (
                pending_overlap
                and pending_overlap_tokens + unit_tokens <= _DEFAULT_CHUNK_TOKENS
            ):
                current_units = [pending_overlap]
                current_tokens = pending_overlap_tokens
                pending_overlap = ""
                pending_overlap_tokens = 0

        current_units.append(unit)
        current_tokens += unit_tokens

    if current_units:
        drafts.append(_draft_from_units(current_units))

    return [draft for draft in drafts if draft.text]


def _merge_tiny_chunks(drafts: list[_ChunkDraft]) -> list[_ChunkDraft]:
    merged: list[_ChunkDraft] = []
    for draft in drafts:
        if merged and draft.token_count < _MIN_MERGE_THRESHOLD:
            previous = merged[-1]
            combined_text = f"{previous.text}\n\n{draft.text}".strip()
            combined_tokens = _token_count(combined_text)
            if combined_tokens <= _MAX_CHUNK_TOKENS:
                merged[-1] = _ChunkDraft(
                    text=combined_text,
                    units=previous.units + draft.units,
                    token_count=combined_tokens,
                )
                continue
        merged.append(draft)
    return merged


def _draft_from_units(units: list[str]) -> _ChunkDraft:
    text = "\n\n".join(unit.strip() for unit in units if unit.strip()).strip()
    return _ChunkDraft(
        text=text,
        units=[unit for unit in units if unit.strip()],
        token_count=_token_count(text),
    )


def _drafts_from_hard_split(text: str) -> list[_ChunkDraft]:
    parts = _hard_split(text, _DEFAULT_CHUNK_TOKENS, _DEFAULT_CHUNK_OVERLAP)
    return [
        _ChunkDraft(text=part, units=[part], token_count=_token_count(part))
        for part in parts
        if part
    ]


def _build_overlap_seed(units: list[str]) -> str:
    if not units:
        return ""

    last_unit = units[-1].strip()
    if not last_unit:
        return ""

    if _token_count(last_unit) <= _DEFAULT_CHUNK_OVERLAP:
        return last_unit

    sentence_tail = _sentence_tail(last_unit)
    if sentence_tail and _token_count(sentence_tail) <= _DEFAULT_CHUNK_OVERLAP:
        return sentence_tail

    return _word_tail(last_unit, _DEFAULT_CHUNK_OVERLAP)


def _sentence_tail(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    ]
    if not sentences:
        return ""
    return sentences[-1]


def _word_tail(text: str, overlap_tokens: int) -> str:
    words = text.split()
    if not words:
        return ""
    if len(words) <= overlap_tokens:
        return text.strip()
    return " ".join(words[-overlap_tokens:])


def _hard_split(text: str, max_tokens: int, overlap_tokens: int = 0) -> list[str]:
    words = text.split()
    if not words:
        return []

    step = max(1, max_tokens - overlap_tokens)
    chunks: list[str] = []
    for index in range(0, len(words), step):
        chunk = " ".join(words[index : index + max_tokens]).strip()
        if chunk:
            chunks.append(chunk)
        if index + max_tokens >= len(words):
            break
    return chunks


def _token_count(text: str) -> int:
    return len(text.split())


def _has_weak_structure(text: str) -> bool:
    return _looks_weak_structure(text)


__all__ = ["ingest_document", "resolve_agent_domain"]
