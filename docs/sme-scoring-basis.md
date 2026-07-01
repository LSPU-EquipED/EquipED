# SME Scoring Basis — Design Summary

> **Status:** Proposal / experimental. No code written yet. This document
> explains *what* we want to change and *why*, in plain terms, so reviewers and
> teammates can follow the idea before any implementation begins.
> **Scope:** SME agent only (Program Coordinator may follow later).

---

## 1. The problem in one paragraph

Right now the SME agent reads an SLM and assigns each criterion a score of 1–4,
but it has **no concrete rule for how to arrive at that score**. The criteria are
just short descriptions (e.g. *"Material is interactive in each lesson"*). Because
there's no defined method, two issues appear:

- **Inconsistency** — the same SLM can get different scores on different runs.
- **Incompleteness** — when all the scoring guidance is stuffed into one big
  prompt, the model tends to skip or rush some criteria.

## 2. What we want instead

Give **every criterion a concrete, repeatable scoring basis**: a defined unit to
count, a formula, and fixed score bands. The guiding principles:

1. **The LLM judges; code does the math.** The model only does what it's good at —
   reading and making per-item yes/no judgments ("does this task have clear
   directions?"). All counting, ratios, and band lookups happen in **code**, so the
   same inputs always produce the same score.
2. **Only measure units that always exist.** SLMs don't always label "Lesson 1/2,"
   so we never divide by "number of lessons." We divide by things that are always
   present: objectives, tasks, assessments, sections.
3. **Everything is auditable.** The result can show the item-by-item evidence
   (e.g. "Task 3: missing expected output"), which matches the system's
   **advisory-only** role — human CID reviewers make the final call.

## 3. Background: what an SLM looks like

SLMs follow a fixed **template** (content varies, structure doesn't):

1. Course metadata / header
2. **Learning Objectives** — a numbered list of targets *(always present)*
3. **Student Learning Strategies** — online + offline activities *(where most
   interactive tasks live)*
4. **Main Content** — introduction + topic blocks (sometimes labeled "Lesson 1…N",
   sometimes just straight content)
5. **Assessments & Performance Tasks** — the graded/reflective tasks *(always
   present)*
6. Appendices — references, disclaimer

Two facts from real SLMs drove the design:

- **Activities are centralized**, not spread one-per-lesson. They sit in sections 3
  and 5, and a module may share one activity set for the whole thing.
- **Lessons aren't always labeled.** Some SLMs jump straight into content.

This is why we **don't** measure "per lesson" anything.

## 4. The three kinds of measurement

Every criterion uses one of three patterns:

| Pattern | What it does | Example |
|---|---|---|
| **A. Coverage ratio** | count units that pass a check ÷ total units → % → band | Objective alignment = aligned objectives ÷ total objectives |
| **B. Checklist count** | count how many expected *types* are present (fixed small list) → band | Interactivity = how many of 7 interaction types appear |
| **C. Per-unit mean** | score each unit 1–4, then average | Clear directions = average of per-task scores |

The **denominator** (what we divide by, or the checklist we tick off) is always
something the template guarantees exists.

## 5. The full SME scoring basis (all 10 criteria)

### Domain A — Organization & Presentation

| Code | Criterion | How it's measured | Score bands (4 / 3 / 2 / 1) |
|---|---|---|---|
| **OP-01** | Topic Coherence | **Coverage ratio.** Split content into ordered topic blocks; the LLM judges each transition as logical or not. Coherence = coherent transitions ÷ total transitions. | 80–100% / 50–79% / 20–49% / <20% |
| **OP-02** | Interactivity | **Checklist count** of 7 interaction types present (practice, reflection, problem-solving, application, discussion, learning checks, real-world). | 5–7 / 3–4 / 1–2 / 0 types |
| **OP-03** | Clear Directions | **Per-unit mean.** Score each task on its element checklist (instructions, materials, expected output, steps, submission, criteria), then average and round. | per task: all elements / 1 missing / 2–3 missing / unusable |
| **OP-04** | Accurate Sections | **Coverage ratio.** Clarity/internal-consistency only (no external references). Clean sections ÷ total sections. | 80–100% / 50–79% / 20–49% / <20% |
| **OP-05** | Enhancement Activities | **Checklist count** of 5 enhancement types (enrichment, additional exercises, extension, independent learning, real-world application). | 4–5 / 2–3 / 1 / 0 types |

### Domain B — Assessment

| Code | Criterion | How it's measured | Score bands (4 / 3 / 2 / 1) |
|---|---|---|---|
| **A-01** | Learner Transformation | **Coverage ratio.** Classify each task by Bloom level; higher-order tasks (apply/analyze/evaluate/create) ÷ total tasks. | 80–100% / 50–79% / 20–49% / <20% |
| **A-02** | Varied Assessment Tools | **Checklist count** of distinct assessment types used (quiz, reflection, project, performance task, etc.). | ≥5 / 3–4 / 2 / ≤1 types |
| **A-03** | Progress Monitoring | **Checklist count** of 4 monitoring types (checkpoints, self-assessment, reflection, cumulative tasks). | 3–4 / 2 / 1 / 0 types |
| **A-04** | Prescriptive Feedback | **Coverage ratio.** Assessments with feedback/remediation ÷ total assessments. | 80–100% / 50–79% / 20–49% / <20% |
| **A-05** | Objective Gauging | **Coverage ratio.** Objectives that have a matching assessment ÷ total objectives. | 80–100% / 50–79% / 20–49% / <20% |

> **Note on the bands:** we use a single **moderate** percentage scale (80/50/20)
> across all ratio criteria. This is intentionally a bit forgiving — appropriate
> for an experimental, advisory system where over-flagging is worse than
> under-flagging. Thresholds can be tightened later once we see real score
> distributions.

## 6. Edge-case rules

- **No units to measure?** If a criterion's denominator is 0 (e.g. an SLM with no
  objectives, or no assessments), the criterion scores **1** — absence is a real
  deficiency, not something to skip.
- **Very short documents (OP-01).** If there are fewer than 4 topic transitions,
  the percentage swings too wildly (one bad transition = 50%). In that case OP-01
  falls back to a simple **issue count**: 0 issues = 4, 1 = 3, 2 = 2, 3+ = 1.
- **Assessments referenced but not contained (A-04, A-05).** Many SLMs only *name*
  an assessment (e.g. "Final QUIZ 1") without including the actual questions. An
  objective counts as "measured" / an assessment counts as having "feedback" **only
  if real assessment content can be quoted** — a bare title is not enough evidence.
  When the instruments are absent, alignment/feedback simply can't be demonstrated,
  so the criterion scores **low**. That is the correct verdict, not a failure: the
  module genuinely doesn't show that its objectives are assessed.

## 7. How content gets split into "blocks/sections" (OP-01 & OP-04)

These two criteria need the document divided into pieces. Because some SLMs have
clear headings and some don't, we use a **hybrid** approach:

- If the SLM has clear headings → use them (deterministic).
- If it's "straight content" with few headings → the LLM splits it into ordered
  topic blocks instead.

This happens **once**, as part of reading the document, and both criteria reuse the
same split — OP-01 at the coarse (topic) level, OP-04 at the finer (section) level.

## 8. What changes vs. what stays the same

**Changes (planned):**
- Each criterion gains a **scoring basis** (the method + bands above), stored as
  structured configuration alongside the rubric.
- The agent's flow shifts from "LLM picks a score" to "LLM reports measurements →
  code computes the score."
- The score's explanation will include the computed evidence (counts, ratio,
  examples).

**Stays the same:**
- The 1–4 score scale and the overall result format.
- The system remains **advisory only** — humans hold final authority.
- Other agents (Coordinator, GAD, ITSO) are untouched for now.

## 9. Validation findings (A-05 spike, 2026-06-30)

We prototyped one criterion (A-05) end-to-end against a real SLM (CMSC 313) to
de-risk the approach before building. What we learned:

- **The loop works.** "LLM enumerates + judges → code computes the band" runs
  end-to-end and produces a sensible score.
- **Enumeration is reliable; subjective judgment is not (by default).** Counting
  objectives was stable (11 every run), but "is this objective measured?" swung
  wildly (scores 4 / 2 / 2) until we constrained it.
- **Two fixes made it fully stable** (identical score every run): run evaluation
  calls at **temperature 0**, and give each judgment a **strict, rule-based
  definition plus a required real-content evidence quote.** Implication: each
  criterion's `scoring_config` must carry a precise judgment rule, not just a label.
- **Stability ≠ correctness.** The first stable score was built on a *fabricated*
  alignment, because the SLM contained **no actual assessment instruments** — only
  a quiz title. This produced the "referenced but not contained" rule in §6.
- **Rate limits are a hard constraint.** The LLM tier caps at ~6,000 tokens/min; a
  full SLM (~9.5k tokens) doesn't fit in one call. The design must **slice** each
  criterion's input to only what it needs (the spike sliced 33.8k → 8.2k chars and
  still scored fine) and **budget calls per minute**.

## 10. Current architecture (reference — what exists today)

Anchor any plan to the real pipeline. As of this writing, an evaluation runs like
this (see `server/modules/evaluations/orchestrator.py`,
`server/modules/agents/supervisor.py`, `server/modules/agents/base.py`):

```
run_evaluation_job (orchestrator, FastAPI background task)
  ├─ loads the SLM document, gets its chunks from the DB
  ├─ slm_text = ALL chunks joined            ← FULL document text exists here
  └─ Supervisor.run_evaluation(chunks, query_text=slm_text)
        ├─ builds chunk_infos + precomputes rubric/reference context (Chroma)
        └─ LOOP over 4 agents in order: SME → Coordinator → GAD → ITSO
              ├─ sleeps BEFORE each agent  (rate-limit pacing already exists,
              │                             via llm_agent_delay_seconds / per-agent)
              └─ agent.run(chunk_infos, context_text=slm_text, ...)
                     ├─ _pack_chunks   → trims to ~12 excerpts
                     ├─ _build_prompt  → ONE big prompt (all criteria)
                     ├─ _call_llm      → ONE LLM call
                     └─ parse → criterion_scores + subtotal (mean)
        collects one AgentEvaluationResult per agent
  ├─ persist_agent_outputs
  └─ synthesis → monitoring matrix → done
```

**Three facts that make integration easier than it looks:**

1. **Full SLM text is already passed to every agent** as `context_text=slm_text`.
   The agent only trims it by choice (`_pack_chunks`). Our engine can read
   `context_text` directly and skip trimming — **integration invariant #1 (full
   text) needs no new plumbing.**
2. **Pacing already exists, but only *between* agents** (Supervisor sleeps before
   each). Our engine adds several calls *inside* SME, which that sleep does not
   cover — so the only new pacing work is **intra-SME**.
3. **Clean seam: `AgentEvaluationResult` + `CriterionScore`.** Everything
   downstream (`persist_agent_outputs`, synthesis, matrix) only needs SME to
   return an `AgentEvaluationResult` with a `criterion_scores` tuple + `subtotal`.
   Match that shape and nothing downstream changes.

**Plug-in point: override `run()` in the SME agent only** (`server/modules/
agents/sme.py`, currently a thin `BaseAgent` subclass). SME's `run()` would:
take `context_text` (full SLM) → run the scoring engine (skeleton + grouped,
paced) → build `criterion_scores` + `subtotal` in the same shape → return
`AgentEvaluationResult`. Supervisor, orchestrator, synthesis, and the other three
agents stay untouched — which matches the "only modify SME" scope.

## 11. Integration & call budget (how this runs inside the agent)

The scoring engine (`server/modules/agents/scoring/`) is **permanent production
code**; the CLI (`server/scripts/score_criterion.py`) is only a manual test
harness that calls the same engine. Integration means letting the SME **agent**
call the engine too — nothing gets rewritten.

**Modified agent flow (vs. today):**

| | Today | After integration |
|---|---|---|
| Input | SLM trimmed to ~12 chunks | **Full document text** (engine counts denominators, so it must see the whole doc) |
| Prompt | one big prompt, all criteria | driven **per criterion** from code |
| Score | LLM picks each 1–4 | LLM only **measures**; `bands.py` computes the 1–4; evidence goes in `justification` |
| Calls | 1 | several (see budget rule below) |

Everything downstream is unchanged: 1–4 scale, `CriterionScore` shape,
subtotal = mean, result format, UI.

**Integration invariants** (hold these constant or scores drift from the CLI):
1. feed the engine **full text**, not the agent's trimmed chunks;
2. same model + **temperature 0**;
3. **pace** calls under the provider token/min limit.

A **shared registry** `{criterion_code -> evaluator}` is the single source of
truth. Both the CLI and the agent read it. Migrate criteria **incrementally**:
if a criterion is in the registry → use the engine; else → fall back to the old
"LLM picks a score" path. This lets a half-migrated agent still produce all
scores, and lets you A/B the same SLM through the app and the CLI.

### Call-budget rule: batch by shared input, NOT one call per criterion

Do **not** design toward "1 LLM call per criterion." At the ~6k tokens/min tier
that is ~2 calls/min, so 30 criteria ≈ 30 calls ≈ ~15 min/SLM — too slow, and it
scales badly.

**Remember the budget is shared across ALL agents.** A full evaluation runs
**SME + Coordinator + GAD + ITSO**, and they all draw on the same ~6k tokens/min
limit. So call counts are **additive across agents** — SME's calls are only a
slice of the real per-evaluation load. Budgeting for SME alone will understate it;
always multiply by the agent count.

Instead, **group calls by the part of the document they read**, because many
criteria share the same input:

- **One "skeleton" extraction call** enumerates the structure once (objectives,
  tasks, assessments, sections, topic blocks). Many criteria are then computed by
  **code alone, zero extra calls** (e.g. A-02 distinct assessment types, total
  objectives/sections denominators).
- **Batch the remaining judgment calls by shared slice.** All assessment-based
  criteria (A-01 Bloom level, A-04 feedback, A-05 alignment) read the same
  assessment section → one call judges them together; code splits the result into
  each band. Same for activity-based and content-based groups.

Net effect: ~30 naive calls collapse to **~3–5 calls per SLM** regardless of how
many criteria exist — same accuracy, same "code does the math." This is the
purpose of the Phase-3 skeleton pass (§7): keep the call count **flat** as
criteria grow. A paid tier (higher tokens/min) is the fallback if calls still
exceed budget, but batching should make that unnecessary.

## 12. Open / still experimental

- **OP-01 (coherence)** and **A-02 (variety)** are the least settled — coherence is
  inherently subjective and may need refinement on what "coherent transition" means.
- Exact **checklist counts** (e.g. "5–7 of 7 = top score") are starting points and
  may be tuned against real SLMs.
- **Per-criterion slicing strategy** — how to reliably feed each criterion only its
  relevant section(s) under the token budget (the spike used a crude head+keyword
  slice; production needs the structured "skeleton" pass from §7).
- **Objective granularity** — SLMs list both broad *Intended Learning Outcomes* and
  specific *Targets*; whether A-05 counts both (risking double-counting) or only the
  specific targets is undecided.
- Whether the Program Coordinator agent reuses this same machinery later.
