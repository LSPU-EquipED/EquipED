"""Tolerant verbatim substring grounding shared by evaluation agents.

Adapted from ``server/modules/agents/sme/response.py``. Locates a model
excerpt in source text while tolerating smart quotes, en/em dashes,
non-breaking spaces, case differences, token-boundary punctuation
variations, and colon prefixes. Every returned span is an exact slice of
``source`` bounded to ``max_chars``.
"""

from __future__ import annotations

import re


def find_verbatim_substring(
    excerpt: str, source: str, max_chars: int = 2000
) -> str | None:
    """Locate excerpt in source, tolerating quotes, dashes, and punctuation."""
    if not isinstance(excerpt, str) or not isinstance(source, str):
        return None
    if not excerpt.strip() or not source:
        return None
    if len(excerpt) > max_chars:
        return None
    if excerpt in source:
        return excerpt
    trans = str.maketrans(
        {"“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-", "\xa0": " "}
    )
    c_source = source.translate(trans)
    c_excerpt = excerpt.translate(trans)

    words = c_excerpt.split()
    if not words:
        return None
    pattern_simple = r"\s+".join(re.escape(w) for w in words)
    match_simple = re.search(pattern_simple, c_source, flags=re.IGNORECASE)
    if match_simple:
        span = source[match_simple.start() : match_simple.end()]
        if len(span) <= max_chars:
            return span
        return None

    token_words = re.findall(r"\b\w+\b", c_excerpt)
    if not token_words:
        return None

    if len(token_words) >= 2:
        pattern_words = r"[\s\W_]+".join(re.escape(w) for w in token_words)
        match_words = re.search(pattern_words, c_source, flags=re.IGNORECASE)
        if match_words:
            start, end = match_words.start(), match_words.end()
            if (
                end < len(source)
                and source[end] in ".?!;:"
                and excerpt.rstrip().endswith(source[end])
            ):
                end += 1
            if end - start <= max_chars:
                return source[start:end]
            return None

    if len(token_words) == 1:
        pattern_one = r"\b" + re.escape(token_words[0]) + r"\b"
        match_one = re.search(pattern_one, c_source, flags=re.IGNORECASE)
        if match_one:
            span = source[match_one.start() : match_one.end()]
            if len(span) <= max_chars:
                return span
            return None

    if ":" in c_excerpt:
        sub = c_excerpt.split(":", 1)[1].strip()
        sub_tokens = re.findall(r"\b\w+\b", sub)
        if sub_tokens:
            p_sub = (
                r"\b" + re.escape(sub_tokens[0]) + r"\b"
                if len(sub_tokens) == 1
                else r"[\s\W_]+".join(re.escape(w) for w in sub_tokens)
            )
            match_sub = re.search(p_sub, c_source, flags=re.IGNORECASE)
            if match_sub:
                start, end = match_sub.start(), match_sub.end()
                if (
                    end < len(source)
                    and source[end] in ".?!;:"
                    and excerpt.rstrip().endswith(source[end])
                ):
                    end += 1
                if end - start <= max_chars:
                    return source[start:end]
                return None

    if len(token_words) >= 4:
        for window_size in range(len(token_words) - 1, 2, -1):
            for i in range(len(token_words) - window_size + 1):
                sub_tokens = token_words[i : i + window_size]
                p_window = r"[\s\W_]+".join(re.escape(w) for w in sub_tokens)
                m_window = re.search(p_window, c_source, flags=re.IGNORECASE)
                if m_window:
                    start, end = m_window.start(), m_window.end()
                    if (
                        end < len(source)
                        and source[end] in ".?!;:"
                        and excerpt.rstrip().endswith(source[end])
                    ):
                        end += 1
                    if end - start <= max_chars:
                        return source[start:end]

    return None


__all__ = ["find_verbatim_substring"]
