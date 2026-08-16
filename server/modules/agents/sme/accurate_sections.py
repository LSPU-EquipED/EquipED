"""OP-04 Accurate Sections: are the SLM's paragraphs/sections clear, internally
consistent, and free of self-evident errors?

Rubric intent: "Paragraphs and sections have clear and accurate information."
We measure this as a COVERAGE RATIO (Pattern A): split the main lesson content
into SECTIONS, then judge each for clarity/internal accuracy.

    clean_ratio = clean_sections / total_sections

mapped on the moderate scale (>=80% -> 4, >=50% -> 3, >=20% -> 2, else 1). No
sections at all -> 1 by the empty rule.

SCOPE (deliberate, user decision): "accurate" here means clarity and INTERNAL
consistency only -- NOT external/domain fact-checking. The model cannot
reliably verify specialized LSPU course content against outside knowledge, and
this is an advisory-only system reviewed by human CID reviewers; a hallucinated
"fact-check" would be worse than no check. A section is flagged ONLY for:
unclear/garbled writing, internal self-contradiction, contradicting another
section in the same document, or a blatant self-evident error (e.g. a formula
that doesn't compute, a claim contradicted two sentences later) -- never for
"the model thinks this fact is wrong."

Like OP-01, this reads the MAIN LESSON CONTENT across the whole document (not
the bottom tasks section), so it uses the same shared ``downsample`` slice
(see slicing.py) -- evenly-spaced samples so later sections are represented,
not just the first ones. The prompt must explain the sampling gap marker so the
model does not mistake an omitted span for a broken section.

Shape mirrors clear_directions.py / prescriptive_feedback.py: a pure
``compute`` (facts -> band) plus a thin ``evaluate`` wrapper the CLI uses to
run it standalone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..runtime.llm import parse_json_payload
from .bands import ratio_band
from .slicing import GAP_MARKER, downsample

PROMPT = f"""You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

NOTE: the content below is SAMPLED from across the whole document -- the marker
"{GAP_MARKER.strip()}" marks a span that was OMITTED to fit the sample. Do NOT
treat a "{GAP_MARKER.strip()}" gap itself as a broken or incomplete section --
only judge sections you can actually read in full.

1. Split the visible content into an ordered list of SECTIONS (each a distinct
   paragraph or block of related paragraphs).
2. For each section, judge whether it is "clean" using this rule -- is_clean is
   true ONLY IF ALL of the following hold:
   - The writing is CLEAR and readable (not garbled, not incomplete).
   - It does NOT contradict itself internally.
   - It does NOT contradict another section you can see in this sample.
   - It contains no BLATANT, SELF-EVIDENT error (e.g. a stated formula that
     does not compute, a claim directly contradicted a few sentences later).
   Do NOT judge whether specialized subject-matter facts are correct against
   your own outside knowledge -- you cannot verify that reliably. Only flag
   what is verifiable FROM THE TEXT ITSELF.
3. If a section is not clean, quote the specific problematic text as "issue".
   If clean, leave "issue" empty.
4. Skip any section that is cut off by a "{GAP_MARKER.strip()}" gap on either
   side -- you cannot judge what you cannot read in full.

Return ONLY valid JSON in exactly this shape:
{{{{
  "sections": [
    {{{{"id": 1, "title": "short section label", "is_clean": true,
      "issue": ""}}}}
  ]
}}}}

SLM CONTENT (sampled):
{{content}}
"""


def slice_for_accuracy(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample evenly across the whole document (see slicing.downsample)."""
    return downsample(text, budget=budget, windows=windows)


@dataclass
class AccuracyResult:
    score: int
    pct: float | None
    clean: int
    total: int
    sections: list[dict[str, Any]]
    flagged: list[dict[str, Any]]


def compute(sections: list[dict[str, Any]]) -> AccuracyResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    Denominator = DISTINCT sections found (deduped by title/label, the class of
    bug that inflated A-05 to 10/3). Numerator = sections judged clean.
    Unlike the task-based criteria, "clean" needs no evidence quote to count --
    absence of an issue IS the positive signal here; a flagged section is the
    one that must carry a quoted issue (enforced in the CLI readout, not the
    band math, since an unquoted flag still represents "not clean").
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for section in sections:
        key = str(section.get("title", "")).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(section)

    clean = sum(1 for s in unique if s.get("is_clean"))
    flagged = [s for s in unique if not s.get("is_clean")]

    band = ratio_band(clean, len(unique), scale="moderate")
    return AccuracyResult(
        score=band.band,
        pct=band.pct,
        clean=clean,
        total=len(unique),
        sections=unique,
        flagged=flagged,
    )


def evaluate(client: Any, text: str) -> AccuracyResult:
    """Thin wrapper: fetch facts from the LLM, then compute the band.

    Used by the CLI to run OP-04 standalone. At integration the facts come
    from a shared/grouped call instead, but ``compute`` stays the same.
    """
    content = slice_for_accuracy(text)
    raw = client.generate(
        PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1800,
    )
    data = parse_json_payload(raw)
    return compute(list(data.get("sections", [])))


__all__ = [
    "AccuracyResult",
    "compute",
    "evaluate",
    "slice_for_accuracy",
    "PROMPT",
]
