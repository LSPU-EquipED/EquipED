"""Shared fact-extraction ("skeleton") pass: 6 LLM calls instead of ~10.

Each SME criterion below used to run its own ``evaluate()`` -- its own slice,
its own prompt, its own LLM call -- even though several of them read the SAME
region of the document and ask for overlapping facts. This module groups
criteria into "baskets" by the slice they need, extracting each basket's facts
with ONE LLM call, so several criteria share a call instead of each paying
for its own.

History of this design (see openspec/specs/sme-engine-scoring/spec.md for the canonical contract):

1. First attempt: 2 baskets (all 7 assessment/task criteria in one call, all 3
   content criteria in another). Rejected outright by the provider -- HTTP 413,
   request too large (~9k tokens requested against a ~6k-token ceiling).
2. Second attempt: 3 baskets (assessment-centric A1, task-centric A2 bundling
   tasks+monitoring+enhancement, and content B bundling topics+sections+
   feedback). Fit the token budget, but a real SLM comparison against the
   validated per-criterion oracle showed monitoring, enhancement, and sections
   -- all SECONDARY categories within their multi-category prompt -- came back
   completely empty, while the oracle found real content in the same region
   (5 monitoring instances, 6 enhancement activities, 16 clean sections). The
   PRIMARY category in each prompt (tasks; topics/transitions) extracted fine.
   This looks like classic multi-task attention degradation: the model gives
   the first-listed category real effort and shortchanges the rest.
3. Current design (below): the 3 categories that failed get their OWN
   dedicated single-purpose call each, reusing the exact validated prompts
   from their original per-criterion modules. Categories that demonstrably
   extracted fine when bundled (objectives+assessments+alignment; tasks;
   topics/transitions+feedback) stay merged. Net: 6 calls instead of today's
   ~10 -- a smaller win than originally hoped, but the reliable one.

- **Basket A1** (assessment-centric): objectives + bottom section. Feeds
  A-02, A-05.
- **Basket A2** (task-centric): bottom section only. Feeds A-01, OP-02, OP-03.
- **Basket A3** (monitoring-only, single-purpose): bottom section. Feeds A-03.
- **Basket A4** (enhancement-only, single-purpose): bottom section. Feeds OP-05.
- **Basket B1** (topics/transitions + feedback): whole-doc downsample. Feeds
  OP-01, A-04.
- **Basket B2** (sections-only, single-purpose): whole-doc downsample. Feeds
  OP-04.

Every criterion's ``compute()`` is UNCHANGED -- only the source of its facts
changes, from a per-criterion ``evaluate()`` call to a shared basket dict.
``registry.run_grouped`` is what routes basket facts into each ``compute()``;
this module only extracts the facts.

OP-02 and OP-03 previously read a different, older head+vocabulary slice
(see interactivity.py / clear_directions.py). Basket A2 instead anchors on
the SECTION_ANCHORS bottom section like A-01/A-03/OP-05 -- a deliberate,
user-approved change. A real-SLM comparison also showed this fixes a bug: the
old vocabulary-anchored OP-03 slice was pulling in lecture CONTENT (e.g.
"CUNIEFORM", "URUK CITY") and mislabeling it as student tasks with
directions -- the bottom anchor avoids that.
"""

from __future__ import annotations

import json
from typing import Any

from .slicing import GAP_MARKER, downsample

# Same bottom-section anchors used by learner_transformation / varied_assessment
# / progress_monitoring / enhancement_activities -- the fullest variant (with
# "questions for reflection"), since Basket A2 also has to cover what OP-02/
# OP-03 used to read via their own vocabulary markers.
SECTION_ANCHORS: tuple[str, ...] = (
    "performance task",
    "performance tasks",
    "learning tasks",
    "enrichment activit",
    "enhancement activit",
    "assessment task",
    "questions for reflection",
)

BASKET_A1_PROMPT = """SLM ANALYSIS -- ASSESSMENT FACTS

You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

The content below has two parts: the OBJECTIVES near the top, then the
ASSESSMENTS section near the bottom (they may be separated by an
"[...lecture body omitted...]" marker -- ignore that marker, it just means
content between the two parts was left out).

1. OBJECTIVES: List every stated learning objective / target from the top
   part. Keep each as written, briefly.

2. ASSESSMENTS: List every ASSESSMENT TOOL used to gauge student progress
   (any quiz, test, task, or activity whose PURPOSE is to measure or record
   what the student has learned -- not just practice). For EACH, classify it
   into EXACTLY ONE of these seven types:
   - "objective_test"    -- selected-response: multiple choice, true/false,
                            matching, identification
   - "written"           -- short-answer or essay questions, written composition
   - "reflection"        -- reflection journal, reaction paper, learning log
   - "performance_task"  -- performance task, demonstration, skills exhibition
   - "project"           -- project, product, portfolio, extended-work output
   - "oral"              -- oral recitation, presentation, defense, interview
   - "self_assessment"   -- self-check, self-rating, peer assessment
   If it does not clearly fit one of the seven, omit it rather than guessing.

3. ALIGNMENT: For EACH objective, decide whether it is measured by one of the
   assessments above, using this STRICT rule: an assessment measures an
   objective ONLY IF completing it requires the student to directly
   demonstrate the specific knowledge or skill named in the objective (match
   the objective's action verb and topic). A general reflection/essay prompt
   does NOT count unless it targets that objective's specific knowledge. If
   unsure, mark is_measured = false. For every objective you mark true, quote
   the exact assessment text that measures it in "evidence".

STRICT rules:
- You must be able to quote real content as "evidence". A bare title/heading
  with no content under it is NOT sufficient -- still list the item, but with
  empty evidence.
- List each DISTINCT item once per list. Do not repeat the same item.

Return ONLY valid JSON in exactly this shape:
{{
  "objectives": [{{"id": 1, "text": "..."}}],
  "assessments": [
    {{"id": 1, "text": "short label", "assessment_type": "objective_test",
      "evidence": "exact assessment text"}}
  ],
  "alignment": [
    {{"objective_id": 1, "is_measured": true, "assessment_ids": [1],
      "evidence": "exact quote"}}
  ]
}}

SLM CONTENT:
{content}
"""

BASKET_A1_CURRICULUM_PROMPT = """SLM ANALYSIS -- ASSESSMENT AND CURRICULUM FACTS

You are analyzing a Self-Paced Learning Module (SLM) alongside its official
curriculum's course content.

Your ONLY job is to extract facts. Do NOT assign any score.

The SLM CONTENT below has two parts: the OBJECTIVES near the top, then the
ASSESSMENTS section near the bottom (they may be separated by an
"[...lecture body omitted...]" marker -- ignore that marker, it just means
content between the two parts was left out).

1. OBJECTIVES: List every stated learning objective / target from the top
   part. Keep each as written, briefly.

2. ASSESSMENTS: List every ASSESSMENT TOOL used to gauge student progress
   (any quiz, test, task, or activity whose PURPOSE is to measure or record
   what the student has learned -- not just practice). For EACH, classify it
   into EXACTLY ONE of these seven types:
   - "objective_test"    -- selected-response: multiple choice, true/false,
                            matching, identification
   - "written"           -- short-answer or essay questions, written composition
   - "reflection"        -- reflection journal, reaction paper, learning log
   - "performance_task"  -- performance task, demonstration, skills exhibition
   - "project"           -- project, product, portfolio, extended-work output
   - "oral"              -- oral recitation, presentation, defense, interview
   - "self_assessment"   -- self-check, self-rating, peer assessment
   If it does not clearly fit one of the seven, omit it rather than guessing.

3. ALIGNMENT: For EACH objective, decide whether it is measured by one of the
   assessments above, using this STRICT rule: an assessment measures an
   objective ONLY IF completing it requires the student to directly
   demonstrate the specific knowledge or skill named in the objective (match
   the objective's action verb and topic). A general reflection/essay prompt
   does NOT count unless it targets that objective's specific knowledge. If
   unsure, mark is_measured = false. For every objective you mark true, quote
   the exact assessment text that measures it in "evidence".

4. CURRICULUM ALIGNMENT: For EACH objective (same ids as above), decide
   whether it is addressed by the CURRICULUM CONTENT below, using this
   STRICT rule: the curriculum content must name or clearly imply the same
   knowledge/skill as the objective (matching topic and intent). A generic
   or unrelated curriculum mention does NOT count. If unsure, mark
   is_addressed = false. For every objective you mark true, quote the exact
   curriculum text that supports it in "evidence".

STRICT rules:
- You must be able to quote real content as "evidence". A bare title/heading
  with no content under it is NOT sufficient -- still list the item, but with
  empty evidence.
- List each DISTINCT item once per list. Do not repeat the same item.

Return ONLY valid JSON in exactly this shape:
{{
  "objectives": [{{"id": 1, "text": "..."}}],
  "assessments": [
    {{"id": 1, "text": "short label", "assessment_type": "objective_test",
      "evidence": "exact assessment text"}}
  ],
  "alignment": [
    {{"objective_id": 1, "is_measured": true, "assessment_ids": [1],
      "evidence": "exact quote"}}
  ],
  "curriculum_alignment": [
    {{"objective_id": 1, "is_addressed": true, "evidence": "exact quote"}}
  ]
}}

SLM CONTENT:
{content}

CURRICULUM CONTENT:
{curriculum_text}
"""

BASKET_A2_PROMPT = """SLM ANALYSIS -- TASK FACTS

You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

The content below is the TASKS AND ASSESSMENTS section near the bottom of the
document.

List every TASK the student is asked to perform: any activity, exercise,
quiz, performance task, or prompt that requires the student to DO something.
For EACH task, provide ALL of the following:
- "bloom_level": classify what the student must actually DO into exactly one of
  the six canonical category names: "remember", "understand", "apply",
  "analyze", "evaluate", "create" (if unsure between two, pick the lower one).
  You MUST return the canonical category name, NOT the example action verb (for
  example, if the task is to "compare", return "analyze"; if to "explain", return
  "understand"; if to "justify", return "evaluate"; if to "list", return "remember").
- "directions": the exact instruction text telling the student what to do.
- "has_clear_directions": true ONLY IF the directions tell the student what
  to do well enough to actually perform the task; false for a bare title with
  no instructions, or vague/incomplete instructions. If unsure, false.
- "evidence": minimal evidence quote (the exact instruction or task sentence;
  same as "directions" is fine).

STRICT rules:
- You must quote minimal evidence in "directions"/"evidence". A bare
  title/heading with no content under it is NOT sufficient -- still list the
  task, but with empty directions/evidence.
- List each DISTINCT task once. Do not repeat the same task.

Return ONLY valid JSON in exactly this shape:
{{
  "tasks": [
    {{"id": 1, "text": "short label", "bloom_level": "apply",
      "directions": "exact instruction text", "has_clear_directions": true,
      "evidence": "exact task text"}}
  ]
}}

SLM CONTENT:
{content}
"""

BASKET_A3_PROMPT = """You are analyzing a Self-Paced Learning Module (SLM).

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
  exact same mechanism you already listed.
- If a mechanism does not clearly fit one of the four types, do not force it
  -- omit it rather than guessing.

For each mechanism found, put a short label in "text", one of the four types
in "monitoring_type", and the exact text as evidence.

Return ONLY valid JSON in exactly this shape:
{{
  "monitoring_mechanisms": [
    {{"id": 1, "text": "short label", "monitoring_type": "checkpoint",
      "evidence": "exact mechanism text"}}
  ]
}}

SLM CONTENT:
{content}
"""

BASKET_A4_PROMPT = """You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

List every ENHANCEMENT ACTIVITY: an OPTIONAL task, offered BEYOND the
required core lessons and assessments, that explicitly INSTRUCTS the student
to DO something extra to deepen learning (enrichment, extension, extra
practice, real-world application, independent / further exploration).

What COUNTS as an activity (all must be true):
- It is a direct INSTRUCTION to the student -- it uses a directive telling
  them to act (e.g. "Research...", "Create...", "Interview...", "Try...",
  "Watch...", "Explore...", "Answer...").
- The student has to DO or produce something.
- It is EXTRA / optional -- beyond the required lessons and graded
  assessments.

What does NOT count (this is the common mistake -- do NOT list these):
- Explanatory or informational CONTENT the student only READS (lesson text,
  definitions, worked examples, background, "did you know" facts, narrative).
- Statements ABOUT real-world relevance that ask the student to do nothing.
- Required core lesson tasks or graded assessments (those belong to other
  criteria).
- A bare heading like "Enrichment" with no instruction under it.

For each real activity put a short label in "text" and quote the exact
INSTRUCTION in "evidence". If the quote is not an instruction to the student,
do not list it. List each DISTINCT activity once.

Return ONLY valid JSON in exactly this shape:
{{
  "enhancement_activities": [
    {{"id": 1, "text": "short label", "evidence": "exact instruction to the student"}}
  ]
}}

SLM CONTENT:
{content}
"""

BASKET_B1_PROMPT = f"""You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

NOTE: the content below is SAMPLED from across the whole document -- the
marker "{GAP_MARKER.strip()}" marks a span that was OMITTED to fit the sample.
Do NOT treat a "{GAP_MARKER.strip()}" gap as evidence of a broken transition or
missing feedback -- only judge what you can actually read in full on both
sides of a boundary.

1. TOPICS & TRANSITIONS: Split the visible content into an ordered list of
   TOPIC BLOCKS (each a distinct subject/concept, in the order it appears).
   For each pair of CONSECUTIVE topic blocks you can directly compare, judge
   whether the transition is LOGICAL and COHERENT (builds on it / clearly
   sequenced / explicitly connected) or NOT (abrupt, unrelated, out of order).
   Skip any pair separated by a gap marker. Give a short reason for each.

2. FEEDBACK MECHANISMS: Identify every FEEDBACK or INTERVENTION mechanism the
   module provides, ANYWHERE in the visible content (it does not need to be
   attached to a specific assessment). Classify each into EXACTLY ONE of:
   - "answer_key"             -- model answers / an answer key for self-check
   - "rubric"                 -- a scoring rubric or evaluation descriptors
   - "remediation_referral"   -- explicit guidance on what to do if struggling
   - "positive_reinforcement" -- encouraging/motivational language about
                                 performance or effort
   If it does not clearly fit one of the four, omit it. Do NOT classify
   legal disclaimers, copyright notices, fair-use statements, reproduction/distribution
   prohibitions, administrative boilerplate, or institutional-policy notices
   as feedback mechanisms.

STRICT rules:
- You must quote a minimal evidence quote directly evidencing the feedback
  mechanism. A bare heading with no content is NOT sufficient -- still list it,
  with an empty evidence field.
- List each DISTINCT item once per list.

Return ONLY valid JSON in exactly this shape:
{{{{
  "topics": [{{{{"id": 1, "title": "short topic label"}}}}],
  "transitions": [
    {{{{"from_id": 1, "to_id": 2, "is_coherent": true, "reason": "short reason"}}}}
  ],
  "feedback_mechanisms": [
    {{{{"id": 1, "text": "short label", "feedback_type": "answer_key",
      "evidence": "exact mechanism text"}}}}
  ]
}}}}

SLM CONTENT (sampled):
{{content}}
"""

BASKET_B2_PROMPT = f"""You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

NOTE: the content below is SAMPLED from across the whole document -- the
marker "{GAP_MARKER.strip()}" marks a span that was OMITTED to fit the sample.
Do NOT treat a "{GAP_MARKER.strip()}" gap itself as a broken or incomplete
section -- only judge sections you can actually read in full.

Split the visible content into an ordered list of SECTIONS (each a distinct
paragraph or block of related paragraphs). For each section, judge whether it
is "clean" using this rule -- is_clean is true ONLY IF ALL of the following
hold:
- The writing is CLEAR and readable (not garbled, not incomplete).
- It does NOT contradict itself internally.
- It does NOT contradict another section you can see in this sample.
- It contains no BLATANT, SELF-EVIDENT error (e.g. a stated formula that does
  not compute, a claim directly contradicted a few sentences later).
Do NOT judge whether specialized subject-matter facts are correct against
your own outside knowledge -- you cannot verify that reliably. Only flag what
is verifiable FROM THE TEXT ITSELF.

If a section is not clean, quote the specific problematic text as "issue". If
clean, leave "issue" empty. Skip any section cut off by a gap marker on
either side.

Return ONLY valid JSON in exactly this shape:
{{{{
  "sections": [
    {{{{"id": 1, "title": "short section label", "is_clean": true, "issue": ""}}}}
  ]
}}}}

SLM CONTENT (sampled):
{{content}}
"""


def _find_section_start(text: str, *, after: int = 0) -> int | None:
    """Earliest SECTION_ANCHORS match at or after ``after``, or None."""
    lower = text.lower()
    start: int | None = None
    for anchor in SECTION_ANCHORS:
        idx = lower.find(anchor, after)
        if idx != -1 and (start is None or idx < start):
            start = idx
    return start


def slice_for_basket_a1(text: str, *, head: int = 4000, body: int = 7000) -> str:
    """Objectives head + the bottom Performance-Tasks section, for the
    assessment-centric call (objectives/assessments/alignment).
    """
    if len(text) <= head + body:
        return text
    head_part = text[:head]
    start = _find_section_start(text, after=head)
    body_part = text[-body:] if start is None else text[start : start + body]
    return head_part + "\n\n[...lecture body omitted...]\n\n" + body_part


def _slice_bottom_section(text: str, *, body: int = 9000) -> str:
    """The bottom Performance-Tasks section only, tail-anchored fallback.
    Shared by the task-centric and single-purpose bottom-section baskets.
    """
    start = _find_section_start(text)
    if start is None:
        return text[-body:] if len(text) > body else text
    return text[start : start + body]


def slice_for_basket_a2(text: str, *, body: int = 9000) -> str:
    """Bottom section only -- tasks (feeds A-01, OP-02, OP-03)."""
    return _slice_bottom_section(text, body=body)


def slice_for_basket_a3(text: str, *, body: int = 9000) -> str:
    """Bottom section only -- monitoring mechanisms (feeds A-03)."""
    return _slice_bottom_section(text, body=body)


def slice_for_basket_a4(text: str, *, body: int = 9000) -> str:
    """Bottom section only -- enhancement activities (feeds OP-05)."""
    return _slice_bottom_section(text, body=body)


def slice_for_basket_b1(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample evenly across the whole document (see slicing.downsample)."""
    return downsample(text, budget=budget, windows=windows)


def slice_for_basket_b2(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample evenly across the whole document (see slicing.downsample)."""
    return downsample(text, budget=budget, windows=windows)


_CURRICULUM_TEXT_CHAR_CAP = 3000


def extract_basket_a1(
    client: Any, text: str, *, curriculum_text: str | None = None
) -> dict[str, Any]:
    """One LLM call -> raw facts dict for A-02/A-05.

    When ``curriculum_text`` is given (Coordinator only, when a curriculum
    document is attached to the evaluation), the SAME call also returns
    curriculum-alignment judgments for A-05 -- this avoids a second LLM call
    for Coordinator's curriculum-aware A-05 (see ``coordinator.py``). SME
    never passes this, so its prompt and call are byte-for-byte unchanged.
    """
    content = slice_for_basket_a1(text)
    if curriculum_text and curriculum_text.strip():
        prompt = BASKET_A1_CURRICULUM_PROMPT.format(
            content=content,
            curriculum_text=curriculum_text[:_CURRICULUM_TEXT_CHAR_CAP],
        )
        max_tokens = 2200
    else:
        prompt = BASKET_A1_PROMPT.format(content=content)
        max_tokens = 1800
    raw = client.generate(
        prompt,
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=max_tokens,
    )
    data: dict[str, Any] = json.loads(raw)
    return data


def extract_basket_a2(client: Any, text: str) -> dict[str, Any]:
    """One LLM call -> raw facts dict for A-01/OP-02/OP-03."""
    content = slice_for_basket_a2(text)
    raw = client.generate(
        BASKET_A2_PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1800,
    )
    data: dict[str, Any] = json.loads(raw)
    return data


def extract_basket_a3(client: Any, text: str) -> dict[str, Any]:
    """One LLM call -> raw facts dict for A-03 (single-purpose)."""
    content = slice_for_basket_a3(text)
    raw = client.generate(
        BASKET_A3_PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1500,
    )
    data: dict[str, Any] = json.loads(raw)
    return data


def extract_basket_a4(client: Any, text: str) -> dict[str, Any]:
    """One LLM call -> raw facts dict for OP-05 (single-purpose)."""
    content = slice_for_basket_a4(text)
    raw = client.generate(
        BASKET_A4_PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1200,
    )
    data: dict[str, Any] = json.loads(raw)
    return data


def extract_basket_b1(client: Any, text: str) -> dict[str, Any]:
    """One LLM call -> raw facts dict for OP-01/A-04."""
    content = slice_for_basket_b1(text)
    raw = client.generate(
        BASKET_B1_PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=2000,
    )
    data: dict[str, Any] = json.loads(raw)
    return data


def extract_basket_b2(client: Any, text: str) -> dict[str, Any]:
    """One LLM call -> raw facts dict for OP-04 (single-purpose)."""
    content = slice_for_basket_b2(text)
    raw = client.generate(
        BASKET_B2_PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1800,
    )
    data: dict[str, Any] = json.loads(raw)
    return data


__all__ = [
    "SECTION_ANCHORS",
    "BASKET_A1_PROMPT",
    "BASKET_A2_PROMPT",
    "BASKET_A3_PROMPT",
    "BASKET_A4_PROMPT",
    "BASKET_B1_PROMPT",
    "BASKET_B2_PROMPT",
    "slice_for_basket_a1",
    "slice_for_basket_a2",
    "slice_for_basket_a3",
    "slice_for_basket_a4",
    "slice_for_basket_b1",
    "slice_for_basket_b2",
    "extract_basket_a1",
    "extract_basket_a2",
    "extract_basket_a3",
    "extract_basket_a4",
    "extract_basket_b1",
    "extract_basket_b2",
]
