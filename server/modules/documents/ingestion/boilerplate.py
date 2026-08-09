"""Deterministic boilerplate removal for page-level document text."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

_MAX_BOILERPLATE_LINES = 6
_HEADER_SCAN_LIMIT = 18
_HEADER_MIN_MATCHES = 2
_HEADER_LABEL_PREFIXES = (
    "program:",
    "course:",
    "department:",
    "school:",
    "section:",
    "subject:",
    "instructor:",
)
_HEADER_ANCHORS = (
    "republic of the philippines",
    "laguna state polytechnic university",
    "iso 9001",
    "level i institutionally accredited",
)


def strip_repeated_page_boilerplate(page_texts: Sequence[str]) -> list[str]:
    """Remove repeated page headers and footers from page text.

    The heuristic is intentionally conservative: it strips repeated leading
    or trailing line signatures that appear on most pages.
    """

    texts = list(page_texts)
    if len(texts) < 2:
        return texts

    texts = _strip_known_header_blocks(texts)
    texts = _strip_repeated_header_lines(texts)

    footer = _detect_repeated_sequence(texts, from_start=False)

    return [_strip_sequence(text, footer, from_start=False) for text in texts]


def _strip_known_header_blocks(texts: list[str]) -> list[str]:
    cleaned: list[str] = []

    for text in texts:
        lines = _nonempty_lines(text)
        if not lines:
            cleaned.append(text)
            continue

        header_range = _find_known_header_range(lines)
        if header_range is None:
            cleaned.append(text)
            continue

        start, end = header_range
        cleaned_lines = lines[:start] + lines[end:]
        cleaned.append("\n".join(cleaned_lines).strip())

    return cleaned


def _find_known_header_range(lines: list[str]) -> tuple[int, int] | None:
    scan_limit = min(len(lines), _HEADER_SCAN_LIMIT)
    matched_indexes: list[int] = []

    for index in range(scan_limit):
        if _matches_header_anchor(lines[index]):
            matched_indexes.append(index)

    if len(matched_indexes) < _HEADER_MIN_MATCHES:
        return None

    start = matched_indexes[0]
    end = matched_indexes[-1] + 1

    while start > 0 and _looks_header_like(
        lines[start - 1], _boilerplate_signature(lines[start - 1])
    ):
        start -= 1

    while end < len(lines) and _looks_header_like(
        lines[end], _boilerplate_signature(lines[end])
    ):
        end += 1

    return start, end


def _matches_header_anchor(line: str) -> bool:
    normalized = _canonicalize_line(line)
    if not normalized:
        return False

    if normalized.startswith(_HEADER_LABEL_PREFIXES):
        return True

    if any(anchor in normalized for anchor in _HEADER_ANCHORS):
        return True

    if (
        "laguna state" in normalized
        and "polytechnic" in normalized
        and "university" in normalized
    ):
        return True

    if "iso 9001" in normalized and "certified" in normalized:
        return True

    if "institutionally accredited" in normalized and "level" in normalized:
        return True

    return False


def _strip_repeated_header_lines(texts: list[str]) -> list[str]:
    threshold = max(2, (len(texts) * 2 + 2) // 3)
    top_signatures: Counter[str] = Counter()

    pages_lines = [_nonempty_lines(text) for text in texts]
    for lines in pages_lines:
        seen: set[str] = set()
        for line in lines[:_MAX_BOILERPLATE_LINES]:
            signature = _boilerplate_signature(line)
            if signature and signature not in seen:
                top_signatures[signature] += 1
                seen.add(signature)

    cleaned: list[str] = []
    for lines in pages_lines:
        index = 0
        while index < min(len(lines), _MAX_BOILERPLATE_LINES):
            line = lines[index]
            signature = _boilerplate_signature(line)
            if not signature:
                index += 1
                continue

            repeated = top_signatures.get(signature, 0) >= threshold
            if repeated or _looks_header_like(line, signature):
                index += 1
                continue
            break

        cleaned.append("\n".join(lines[index:]).strip())

    return cleaned


def _detect_repeated_sequence(
    texts: Sequence[str], *, from_start: bool
) -> tuple[str, ...]:
    threshold = max(2, (len(texts) * 2 + 2) // 3)
    candidate_counts: Counter[tuple[str, ...]] = Counter()

    for text in texts:
        lines = _nonempty_lines(text)
        if not lines:
            continue

        for size in range(_MAX_BOILERPLATE_LINES, 0, -1):
            if len(lines) < size:
                continue

            block = lines[:size] if from_start else lines[-size:]
            candidate = tuple(
                signature
                for signature in (
                    _line_signature(line, from_start=from_start) for line in block
                )
                if signature
            )
            if len(candidate) == size:
                candidate_counts[candidate] += 1

    for size in range(_MAX_BOILERPLATE_LINES, 0, -1):
        for block, count in candidate_counts.items():
            if len(block) == size and count >= threshold:
                return block

    return ()


def _strip_sequence(text: str, sequence: tuple[str, ...], *, from_start: bool) -> str:
    if not sequence:
        return text

    lines = _nonempty_lines(text)
    if len(lines) < len(sequence):
        return text

    signatures = [_line_signature(line, from_start=from_start) for line in lines]

    if from_start:
        index = 0
        for signature in sequence:
            while index < len(lines) and not signatures[index]:
                index += 1
            if index >= len(lines) or signatures[index] != signature:
                break
            index += 1
        else:
            lines = lines[index:]
    else:
        index = len(lines) - 1
        for signature in reversed(sequence):
            while index >= 0 and not signatures[index]:
                index -= 1
            if index < 0 or signatures[index] != signature:
                break
            index -= 1
        else:
            lines = lines[: index + 1]

    return "\n".join(line for line in lines if line.strip()).strip()


def _nonempty_lines(text: str) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text)
    return [line.strip() for line in normalized.split("\n") if line.strip()]


def _canonicalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip().lower()


def _boilerplate_signature(line: str) -> str:
    normalized = _canonicalize_line(line)
    normalized = re.sub(r"page\s+\d+\s+of\s+\d+", "page <num> of <num>", normalized)
    normalized = re.sub(
        r"\b(program|course|department|school|section|subject)\s*:\s*[^\n]+",
        r"\1:",
        normalized,
    )
    normalized = re.sub(r"[^a-z0-9<> ]+", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _footer_signature(line: str) -> str:
    normalized = _canonicalize_line(line)
    normalized = re.sub(r"[^a-z0-9 ]+", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _line_signature(line: str, *, from_start: bool) -> str:
    if from_start:
        return _boilerplate_signature(line)
    return _footer_signature(line)


def _looks_header_like(line: str, signature: str) -> bool:
    if len(signature) <= 4:
        return False
    lowered = _canonicalize_line(line)
    if lowered.startswith(_HEADER_LABEL_PREFIXES):
        return True
    if re.fullmatch(r"page\s+\d+(\s+of\s+\d+)?", lowered):
        return True
    if any(token in lowered for token in ("prepared by", "academic year", "semester")):
        return True
    return bool(re.search(r"\b(lspu|slm)\b", lowered))


__all__ = ["strip_repeated_page_boilerplate"]
