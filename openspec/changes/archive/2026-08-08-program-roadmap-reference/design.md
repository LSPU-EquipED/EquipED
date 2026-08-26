# Design: Program Roadmap Reference

## Context

Faculty SLM evaluations lost their program-level grounding when curriculum documents were retired (2026-08-02): every evaluation now runs `partial_without_curriculum=true` with the Coordinator skipped and weights renormalized (SME/GAD/ITSO). The institution is authoring per-program career roadmaps — BSCS Intelligent Systems and BSIT Web & Mobile Development — that contain the structured program facts evaluation currently lacks: course structure, year/semester placement, technology stacks, and competency stages. The roadmaps are long (10k+ words) and table-heavy, authored as Google Docs.

Two hard constraints shape the design:

1. **Agent prompt budget**: `agent_prompt_budget_chars=5000` (document chunks) and `agent_total_prompt_budget_chars=8000` (full prompt JSON). `BaseAgent._enforce_total_prompt_budget()` drops `reference_context` **first** under pressure, then trims rubric context, then truncates survivors to 400 chars. Anything routed through `reference_context` is expendable by design.
2. **Reference-library contract**: active document types are `syllabus` and `policy` only. Curriculum/rubric PDFs are retired types. SLMs are never embedded into ChromaDB.

## Goals / Non-Goals

**Goals:**
- Structured, versioned program roadmap data (`ProgramRoadmap` / `RoadmapYear` / `RoadmapCourse`) in `curriculum_map`, seeded from JSON like the curriculum map.
- Non-embedded roadmap PDF provenance files under `uploads/` for human reference.
- Read-only roadmap API endpoints.
- Evaluation-time resolution of the active roadmap from `confirmed_program` + `document.course_code`, delivered as compact structured context to the Coordinator only, as advisory enrichment that never displaces existing curriculum retrieval.

**Non-Goals:**
- Re-enabling the Coordinator as a full 4-agent evaluation participant (explicitly deferred product decision; this change keeps `partial_without_curriculum` semantics intact).
- Any client UI changes (roadmap admin surface and faculty-facing display are future changes).
- Adding roadmap documents to the reference library or ChromaDB — roadmap PDFs are provenance only.
- Roadmap consumption by SME/GAD/ITSO agents — SME scoring is contractually SLM-internal (`sme-engine-scoring` spec).
- Reusing roadmap data in the standalone `/alignment` or `/syllabus-alignment` features (future opportunity, not this change).

## Decisions

### D1: Structured relational data, not vector retrieval (reject document-as-reference)

The roadmap is table-structured (course matrices, tech-stack matrices). The embedding model (`paraphrase-multilingual-MiniLM-L12-v2`) encodes semantic meaning, not tabular structure — retrieval returns unparseable matrix fragments. Coordinator's current curriculum retrieval fetches only 3 chunks; roadmap chunks would additionally be the first thing dropped under budget pressure. Structured rows give exact, compact facts (~300–500 chars per course entry) that survive budget trimming without LLM re-extraction.

*Alternatives considered:* embedding the roadmap PDFs into the reference library (rejected: contract violation, retrieval quality, budget expendability), treating roadmaps as free-text syllabus substitutes (rejected: loses determinism).

### D2: Three tables in `curriculum_map`, first year/semester columns in the module

- `ProgramRoadmap`: `roadmap_id` PK, `program` (canonical code, e.g. `BSCS`, `BSInfoTech`), `specialization` (e.g. `Intelligent Systems`, nullable), `version_number`, `status` (`active`/`retired`), `source_document_path` (PDF path under `uploads/`), timestamps. Natural key: `(program, specialization, version_number)`.
- `RoadmapYear`: `year_id` PK, `roadmap_id` FK, `year_number` (1–4), `semester` (nullable — some entries are year-wide), `label` (e.g. "Computing Foundations"), `description` nullable.
- `RoadmapCourse`: `id` PK, `roadmap_id` FK, `year_id` FK, `course_code`, `course_title`, `course_id` **nullable FK → `courses.course_id`** (null for Proposed courses), `course_status` (`existing`/`proposed`), `tech_stack` (nullable text), `competency_stage` (nullable text), `learning_outcomes_summary` (nullable text), `portfolio_project_suggestion` (nullable), `relevant_certification` (nullable).

Program identity uses the canonical codes already used by `Course.program` and `confirmed_program` (`BSInfoTech` canonical, `BSIT` legacy alias). Specialization is a new dimension; the client's program selector remains program-level and untouched.

*Alternatives considered:* a separate `roadmaps` module (rejected — this is program-structure data, `curriculum_map` owns that domain); embedding roadmap rows into existing `Course` (rejected — `Course` has no year/semester and is outcome-mapping-oriented).

### D3: Proposed courses are first-class, flagged, never alignment targets

`course_status='proposed'` marks courses like "Intelligent Systems I" that don't officially exist yet. The Coordinator must treat them as informational and never score alignment against them. The flag is a required column with a check constraint — the distinction is inescapable in the data model.

### D4: Co-reference with `Course` by nullable FK, resolved by code

`courses.course_code` is UNIQUE. `RoadmapCourse.course_id` links when the course exists; when null, resolution falls back to `(course_code, program)`. This keeps existing courses linked (no duplicate definitions) while allowing Proposed entries.

### D5: No schema change to `EvaluationJob` — resolve at orchestration time

The orchestrator resolves the active roadmap from `job.confirmed_program` + `document.course_code` at context-build time. No `roadmap_id` is persisted on the job. This makes roadmap retirement trivially safe for historical truth: no FK to null out, evaluations are unaffected by later roadmap changes. Roadmap status (`active`/`retired`) governs whether resolution succeeds.

### D6: Roadmap context rides in a dedicated context key, Coordinator-only

The orchestrator context dict currently has one key: `reference_document_ids: {syllabus?, curriculum?}`. Roadmap facts are added as a separate compact key (`roadmap`), never inside `reference_document_ids` (which flows into the trimmable reference context path). Payload contains only the fields agents consume: `course_code`, `course_title`, `year`, `semester`, `tech_stack`, `competency_stage`, `course_status`. Coordinator reads it; SME/GAD/ITSO ignore it. When `document.course_code` is null or no active roadmap exists, the key is simply absent — evaluation proceeds exactly as today.

### D7: Coordinator consumption augments, never replaces

Coordinator's existing Chroma curriculum retrieval (`_prepare_curriculum_text`) stays. Roadmap facts enter as supplementary structured context alongside the A-05/basket-A1 path. Proposed entries inform, never anchor, alignment reasoning.

### D8: Seeding mirrors the proven pattern

`server/scripts/seed_roadmaps.py` + `server/data/roadmaps/bscs_intelligent_systems.json`, idempotent upsert by natural key `(program, specialization, version_number)`, invoked via `uv run --project server python -m server.scripts.seed_roadmaps`. BSCS-IS seeded first to validate the schema against real content; BSIT-WMD follows once validated. No startup seeding hooks (consistent with rubrics/curriculum map).

### D9: Read-only API surface

- `GET /curriculum-map/roadmaps` — list active (and optionally retired) roadmaps, auth-guarded
- `GET /curriculum-map/roadmaps/{id}` — roadmap detail
- `GET /curriculum-map/roadmaps/{id}/courses?year=&semester=` — course rows filtered by year/semester

Admin write surface (CRUD UI) is explicitly deferred; JSON re-seed is the update mechanism for now, matching rubrics.

## Risks / Trade-offs

- **[High] Proposed-course authority** — agents could treat speculative courses as real alignment targets → Mitigation: required `course_status` column with check constraint; Coordinator rule: Proposed entries never anchor alignment.
- **[Medium] Duplication with `Course`** — roadmap course rows vs existing course definitions drifting apart → Mitigation: nullable FK + code-based co-reference; seed script validates codes against `courses` where possible.
- **[Medium] Budget interplay** — even compact roadmap JSON consumes the 8,000-char total → Mitigation: payload restricted to the six consumed fields; description/portfolio/certification fields stay human-reference only and are excluded from agent payload.
- **[Medium] `course_code` null** — regex metadata detection is non-blocking and nullable → Mitigation: graceful no-op; roadmap enrichment is best-effort by design, never blocks or fails an evaluation.
- **[Low] Retirement lifecycle** — roadmap retirement must not corrupt historical truth → Mitigation: no FK from EvaluationJob (D5); retirement is a status flip; historical evaluations untouched.
- **[Low-Medium] Seed data transcription errors** — hand-transcribing the Google Doc into JSON → Mitigation: seed BSCS-IS first, validate against the source document before BSIT; read-only API enables inspection.

## Migration Plan

1. Alembic migration creating `program_roadmaps`, `roadmap_years`, `roadmap_courses` (with FK + check constraints).
2. `server/data/roadmaps/bscs_intelligent_systems.json` authored from the source document; `seed_roadmaps.py` run out-of-band (mirrors curriculum map workflow; no startup hook).
3. Read-only endpoints + tests (`server/tests/curriculum_map/`).
4. Orchestrator resolution + context key + Coordinator consumption + tests (`server/tests/evaluations/`, `server/tests/agents/`).
5. Rollback: migration downgrade drops tables; enrichment is inert (context key absent) without active roadmap data, so rolling back the coordinator wiring alone is safe.

## Open Questions

- Coordinator reactivation (roadmap as curriculum substitute for full 4-agent evaluations) — deliberately deferred; revisit after roadmap data is seeded and validated against real SLMs.
- Whether roadmap data should later feed the `/alignment` / `/syllabus-alignment` features — future change, not this one.
