"""A-03 Progress Monitoring: does the SLM let a teacher track a student's
progress over time, not just a one-off grade?

Rubric intent: "The material keeps an on-going record of students' progress
and allows the teacher to monitor student performance." We measure this as an
INSTANCE COUNT (Pattern B, like OP-02/OP-05): count how many genuine monitoring
mechanisms occur, banding by amount.

    band: 0 -> 1, 1 -> 2, 2-3 -> 3, 4+ -> 4

This deliberately counts INSTANCES, not distinct types -- the opposite choice
from A-02 (Varied Assessment Tools), and for a reason rooted in each rubric's
own wording. A-02 says "varied": five identical quizzes are one kind, not five,
so instances there are noise. A-03 says "on-going record": "on-going" means
repeated over time, so frequency IS the signal -- five well-spaced checkpoints
genuinely monitor progress more than one. Counting only distinct TYPES would
score a module with five checkpoints the same (band 2, one type) as a module
with a single checkpoint, which misses exactly what "on-going" is asking about.

The LLM still classifies each mechanism into one of four fixed, code-owned
types (see MONITORING_TYPES below) -- same "boundary lives in code, not the
prompt" approach as A-01/A-02 -- but the type only gates WHAT counts as
monitoring; the four-type taxonomy is not itself the denominator. A mechanism
counts only if real content can be quoted as evidence -- a bare heading with no
content is not enough (same real-content rule as the other criteria, see
openspec/specs/sme-engine-scoring/spec.md). Accepted trade-off: a
narrow-but-frequent module
(e.g. five reflections and nothing else) can score high on breadth it doesn't
have -- a softer failure than under-counting on-going-ness, and tunable via
THRESHOLDS if real SLMs show it's a problem.

Where the mechanisms live: per openspec/specs/sme-engine-scoring/spec.md, SLM tasks
and assessments are concentrated near the BOTTOM of the PDF under a strong
header (usually "Performance Task(s)"). The input slice anchors on that
section header and reads to the end -- the same header-anchored approach as
A-01/OP-05 (chosen over a wider slice; the accepted trade-off is that a
monitoring cue embedded mid-lesson, e.g. a checkpoint between topics, may be
missed).

Shape mirrors enhancement_activities.py: a pure ``compute`` (facts -> band)
plus a thin ``evaluate`` wrapper the CLI uses to run it standalone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...runtime.llm import parse_json_payload
from .bands import count_band

# 4+ mechanism instances -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1.
THRESHOLDS: tuple[tuple[int, int], ...] = ((4, 4), (2, 3), (1, 2))

# Fixed, code-owned taxonomy -- exactly four monitoring mechanisms. The LLM
# maps each mechanism it finds to one of these; unrecognized labels are
# dropped (see _normalize_type).
MONITORING_TYPES: tuple[str, ...] = (
    "checkpoint",  # periodic stop-and-check between topics/lessons
    "self_assessment",  # student rates/checks their own understanding
    "reflection",  # metacognitive prompt about the learning itself
    "cumulative",  # task that builds across lessons / culminating task
)

# Same header-anchored, tail-fallback slice as A-01/OP-05 (bottom-only, per
# user decision) -- see module docstring for the trade-off this accepts.
SECTION_ANCHORS: tuple[str, ...] = (
    "performance task",
    "performance tasks",
    "learning tasks",
    "enrichment activit",
    "enhancement activit",
    "assessment task",
    "questions for reflection",
)

PROMPT = """You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

Identify which of these FOUR progress-monitoring mechanisms the module
provides. Each is DISTINCT -- do not confuse them:

- "checkpoint"       -- a periodic stop-and-check point between topics or
                        lessons (e.g. a short quiz or check after each
                        section, a pre-test/post-test pair).
- "self_assessment"  -- the student rates or checks THEIR OWN understanding
                        (e.g. "Rate your confidence", a self-check rubric,
                        peer assessment).
- "reflection"       -- a metacognitive prompt about the LEARNING ITSELF, not
                        the subject content (e.g. "What did you learn?",
                        "Questions for Reflection", a learning journal entry).
- "cumulative"        -- a task that builds ON or PULLS TOGETHER material
                        across multiple lessons (e.g. a culminating
                        performance task, an integrative project, a final
                        output that combines earlier skills).

STRICT rules:
- Classify by what the mechanism actually asks the student to do, not by its
  title alone.
- You must be able to quote the actual mechanism's content as evidence. A bare
  heading with no content (e.g. just "Reflection") is NOT sufficient -- still
  list it, but with empty "evidence".
- List EVERY occurrence you find, even if several are the same type (e.g. a
  checkpoint after each of three sections is THREE mechanisms, not one) --
  frequency is what this criterion measures. Only skip an entry if it is the
  exact same mechanism you already listed (e.g. the same checkpoint quoted
  twice).
- If a mechanism does not clearly fit one of the four types, do not force it
  -- omit it rather than guessing.

For each mechanism found, put a short label in "text", one of the four types
in "monitoring_type", and the exact text as evidence.

Return ONLY valid JSON in exactly this shape:
{{
  "mechanisms": [
    {{"id": 1, "text": "short label", "monitoring_type": "checkpoint",
      "evidence": "exact mechanism text"}}
  ]
}}

SLM CONTENT:
{content}
"""


def slice_for_monitoring(text: str, *, body: int = 9000) -> str:
    """Read only the tasks/assessments section, anchored on its header.

    SLMs place their real tasks and assessments near the bottom under a strong
    header (usually "Performance Task(s)"). We find the EARLIEST such header
    and read from there to the end (capped at ``body`` chars). If no header is
    found, fall back to the tail of the document, where these mechanisms live
    regardless.
    """
    lower = text.lower()

    start: int | None = None
    for anchor in SECTION_ANCHORS:
        idx = lower.find(anchor)
        if idx != -1 and (start is None or idx < start):
            start = idx

    if start is None:
        return text[-body:] if len(text) > body else text
    return text[start : start + body]


def _normalize_type(raw: str) -> str:
    """Map free-text type to one of MONITORING_TYPES, or "" if unrecognized.

    Matches by prefix/equality against the canonical, underscore-joined form.
    Anything unrecognized normalizes to "" and is dropped -- conservative, so a
    mis-tagged or invented type cannot inflate the count.
    """
    cleaned = raw.strip().lower().replace(" ", "_").replace("-", "_")
    for kind in MONITORING_TYPES:
        if cleaned == kind or cleaned.startswith(kind):
            return kind
    return ""


@dataclass
class MonitoringResult:
    score: int
    count: int
    types: list[str]
    mechanisms: list[dict[str, Any]]
    genuine: list[dict[str, Any]]


def compute(mechanisms: list[dict[str, Any]]) -> MonitoringResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    Counts DISTINCT mechanism INSTANCES that carry real content (the evidence
    requirement enforces the "must have real content, not just a heading"
    rule) and a recognized type (the type gates what counts as monitoring, but
    is not itself the denominator). Dedupe is by LABEL, not by type -- three
    separately-labelled checkpoints count as three (frequency is the signal
    for "on-going"), while the exact same mechanism listed twice collapses to
    one (the class of bug that inflated A-05 to 10/3). This mirrors
    enhancement_activities.compute's dedupe, not the type-set dedupe A-02 uses
    -- see the module docstring for why the two criteria diverge.
    """
    seen: set[str] = set()
    genuine: list[dict[str, Any]] = []
    types: set[str] = set()
    for mechanism in mechanisms:
        evidence = str(mechanism.get("evidence", "")).strip()
        if not evidence:  # bare heading / no real content -> does not count
            continue
        kind = _normalize_type(str(mechanism.get("monitoring_type", "")))
        if not kind:  # unrecognized type -> dropped, not guessed
            continue
        key = str(mechanism.get("text", "")).strip().lower() or evidence.lower()
        if key in seen:  # exact same mechanism listed twice -> dedupe
            continue
        seen.add(key)
        genuine.append(mechanism)
        types.add(kind)

    count = len(genuine)
    score = count_band(count, THRESHOLDS)
    return MonitoringResult(
        score=score,
        count=count,
        types=sorted(types),
        mechanisms=mechanisms,
        genuine=genuine,
    )


def evaluate(client: Any, text: str) -> MonitoringResult:
    """Thin wrapper: fetch facts from the LLM, then compute the band.

    Used by the CLI to run A-03 standalone. At integration the facts come from
    a shared/grouped call instead, but ``compute`` stays the same.
    """
    content = slice_for_monitoring(text)
    raw = client.generate(
        PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1500,
    )
    data = parse_json_payload(raw)
    return compute(list(data.get("mechanisms", [])))


__all__ = [
    "MonitoringResult",
    "compute",
    "evaluate",
    "slice_for_monitoring",
    "MONITORING_TYPES",
    "THRESHOLDS",
    "PROMPT",
]
