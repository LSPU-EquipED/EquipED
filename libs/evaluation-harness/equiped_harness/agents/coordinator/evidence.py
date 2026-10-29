"""Bounded, document-owned evidence for rubric judgments; no model or storage I/O."""

from __future__ import annotations

import re
from collections.abc import Mapping

from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.runtime.source_retrieval import source_hash

RETRIEVAL_CONTRACT = "slm_retrieval.v2"
GROUPS = ("organization", "assessment", "alignment")


def retrieval_queries(snapshot):
    criteria = tuple(c for d in snapshot.form.domains for c in d.criteria)
    return {
        "organization": "\n".join(
            f"{c.title}: {c.description}"
            for c in criteria
            if c.criterion_code.startswith("OP-")
        ),
        "assessment": "\n".join(
            f"{c.title}: {c.description}"
            for c in criteria
            if c.criterion_code.startswith("A-")
        ),
        "alignment": (
            "Stated learning objectives, intended learning outcomes, lesson"
            " topics and concepts for curriculum alignment."
        ),
    }


def validate_retrieval(value, document_id, canonical):
    fields = {
        "contract",
        "document_id",
        "source_hash",
        "embedding_model",
        "rankings",
        "passages",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != fields
        or value["contract"] != RETRIEVAL_CONTRACT
        or value["document_id"] != str(document_id)
        or value["source_hash"] != source_hash(canonical)
        or not isinstance(value["embedding_model"], str)
        or not value["embedding_model"].strip()
        or not isinstance(value["rankings"], Mapping)
        or set(value["rankings"]) != set(GROUPS)
        or not isinstance(value["passages"], Mapping)
    ):
        raise AgentExecutionError("Coordinator evidence identity is invalid")
    seen = set()
    for ids in value["rankings"].values():
        if (
            not isinstance(ids, (list, tuple))
            or not 1 <= len(ids) <= 12
            or any(not isinstance(i, str) or not i for i in ids)
            or len(set(ids)) != len(ids)
        ):
            raise AgentExecutionError("Coordinator evidence ranking is invalid")
        seen.update(ids)
    if seen != set(value["passages"]):
        raise AgentExecutionError("Coordinator evidence scope is incomplete")
    for item in value["passages"].values():
        if (
            not isinstance(item, Mapping)
            or set(item) != {"start", "end"}
            or type(item["start"]) is not int
            or type(item["end"]) is not int
            or not 0 <= item["start"] < item["end"] <= len(canonical)
            or item["end"] - item["start"] > 800
        ):
            raise AgentExecutionError("Coordinator evidence offsets are invalid")
    return value


def slm_passages(retrieval, canonical, group, *, budget=4800):
    selected, size = [], 0
    ranking = list(retrieval["rankings"][group])
    if group == "assessment":
        # A-05 compares the actual goals with tasks, rather than guessing goals
        # from assessment-only retrieval hits.
        ranking = list(retrieval["rankings"]["alignment"][:2]) + ranking
    for key in dict.fromkeys(ranking):
        item = retrieval["passages"][key]
        if size + item["end"] - item["start"] > budget:
            continue
        selected.append((item["start"], item["end"]))
        size += item["end"] - item["start"]
    return _passages(canonical, sorted(set(selected)), "S", "slm")


def curriculum_passages(text, slm, *, budget=4000):
    """Rank bounded curriculum windows by the reviewed module's topic vocabulary."""
    terms = set(re.findall(r"[a-z]{4,}", " ".join(p["text"] for p in slm).casefold()))
    stop = {
        "this",
        "that",
        "with",
        "from",
        "have",
        "will",
        "students",
        "learning",
        "module",
        "course",
        "their",
        "which",
    }
    terms -= stop
    spans = []
    start = 0
    while start < len(text):
        end = min(start + 800, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + 400, end)
            if boundary > start:
                end = boundary
        spans.append((start, end))
        start = end
    ranked = sorted(
        spans,
        key=lambda span: (
            -len(
                terms
                & set(re.findall(r"[a-z]{4,}", text[span[0] : span[1]].casefold()))
            ),
            span[0],
        ),
    )
    selected, size = [], 0
    for span in ranked:
        if size + span[1] - span[0] <= budget:
            selected.append(span)
            size += span[1] - span[0]
    return _passages(text, sorted(selected), "C", "curriculum")


def _passages(text, spans, prefix, source):
    return [
        {
            "source_id": f"{prefix}{i}",
            "source": source,
            "start": a,
            "end": b,
            "text": text[a:b],
        }
        for i, (a, b) in enumerate(spans, 1)
    ]
