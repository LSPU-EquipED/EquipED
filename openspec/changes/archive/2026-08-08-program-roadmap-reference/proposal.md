# Program Roadmap Reference

## Why

Faculty SLM evaluations currently run without program-level reference context: the curriculum retirement (2026-08-02) removed curriculum documents, so every evaluation is a Coordinator-skipped partial run grounded only in the SLM itself. The institution is authoring per-program career roadmaps (BSCS Intelligent Systems, BSIT Web & Mobile Development) that prescribe course structure, year/semester placement, technology stacks, and competency stages. These roadmaps are long, table-heavy documents — unfit for vector retrieval — yet they contain exactly the structured program facts agents need to reason about an SLM's fit within its program.

## What Changes

- Introduce structured program roadmap data in `curriculum_map`: `ProgramRoadmap` (program + specialization identity, versioned, `active`/`retired` lifecycle), `RoadmapYear` (year, semester), `RoadmapCourse` (code, title, tech stack, competency stage, learning outcomes summary, `course_status` Existing/Proposed). Year/semester columns are introduced for the first time in this module.
- Add a JSON seed script mirroring the existing `seed_curriculum_map.py` pattern; seed the BSCS Intelligent Systems roadmap first. Roadmap source PDFs are stored as non-embedded provenance files under `uploads/` (never embedded into ChromaDB, never added to the reference library).
- Add read-only roadmap API endpoints (`GET /curriculum-map/roadmaps`, roadmap detail, courses by year/semester).
- Evaluation orchestration resolves the active roadmap from `confirmed_program` + `document.course_code` (graceful no-op when the course code is null) and passes a compact structured roadmap payload to the Coordinator only.
- Coordinator consumes roadmap facts as advisory context: it augments — never replaces — its existing Chroma curriculum retrieval, and ignores `course_status="Proposed"` entries as alignment targets.
- Explicitly **out of scope**: re-enabling the Coordinator as a full evaluation participant (deferred decision), client UI changes, reference-library document category changes, and roadmap consumption by SME/GAD/ITSO agents.

## Capabilities

### New Capabilities

- `program-roadmap`: Structured program roadmap data — models, versioning, active/retired lifecycle, JSON seeding, non-embedded PDF provenance, and read-only API surface in `curriculum_map`.
- `coordinator-roadmap-enrichment`: Evaluation-time roadmap resolution (program + course code) and Coordinator-only advisory consumption of compact roadmap context, respecting the partial-evaluation flow.

### Modified Capabilities

<!-- No existing spec requirements change: roadmap PDFs stay out of the reference library, the evaluation lifecycle and weights are untouched, and Coordinator-skipped partial runs behave exactly as today. -->

## Impact

- **Server code**: `server/modules/curriculum_map/` (models.py, router.py, service.py, new schemas), new Alembic migration, `server/scripts/seed_roadmaps.py` + `server/data/roadmaps/bscs_intelligent_systems.json`, `server/modules/evaluations/orchestrator.py` (context construction), `server/modules/agents/coordinator.py` (roadmap context consumption).
- **Tests**: new unit/integration tests in `server/tests/curriculum_map/` and `server/tests/agents/` (Coordinator enrichment), migration test.
- **Data**: new roadmap tables; `uploads/` gains roadmap PDF provenance files (non-embedded).
- **No client changes** in this change; no changes to `reference-library`, `evaluations`, or `sme-engine-scoring` contracts.
