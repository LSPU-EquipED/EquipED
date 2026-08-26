## 1. Roadmap Data Model

- [x] 1.1 Add `ProgramRoadmap`, `RoadmapYear`, `RoadmapCourse` SQLAlchemy models to `server/modules/curriculum_map/models.py` (program + specialization + version natural key, status active/retired, source_document_path; year_number/semester/label; course_code/course_title/tech_stack/competency_stage/learning_outcomes_summary/course_status with check constraint, nullable FK to courses.course_id)
- [x] 1.2 Register the new models in `server/db/metadata.py` model imports
- [x] 1.3 Create Alembic migration for `program_roadmaps`, `roadmap_years`, `roadmap_courses` tables with FKs and check constraints (use `sa.false()`/`sa.true()` for boolean defaults)

## 2. Seed Data and Script

- [x] 2.1 Author `server/data/roadmaps/bscs_intelligent_systems.json` from the BSCS Intelligent Systems roadmap source document (program=BSCS, specialization=Intelligent Systems, version 1; all years, semesters, courses with tech stacks, competency stages, course_status, and Proposed flags for Intelligent Systems I / Machine Learning / Computer Vision / NLP)
- [x] 2.2 Implement `server/scripts/seed_roadmaps.py` mirroring `seed_curriculum_map.py` (idempotent upsert by program+specialization+version, retire superseded versions, validate course codes against `courses` table where possible)
- [x] 2.3 Run the seed script against the dev DB and verify rows via a quick query

## 3. Read-Only Roadmap API

- [x] 3.1 Add roadmap schemas to `server/modules/curriculum_map/schemas.py` (roadmap summary, roadmap detail with years, course row)
- [x] 3.2 Add `GET /curriculum-map/roadmaps`, `GET /curriculum-map/roadmaps/{roadmap_id}`, `GET /curriculum-map/roadmaps/{roadmap_id}/courses?year=&semester=` endpoints to `server/modules/curriculum_map/router.py` guarded by `require_authenticated_user`

## 4. Evaluation-Time Resolution and Coordinator Enrichment

- [x] 4.1 Add roadmap resolution helper in `server/modules/curriculum_map/service.py` (resolve active roadmap by program, find course row by course_code, enforce existing-only and active-only)
- [x] 4.2 Extend orchestrator context construction in `server/modules/evaluations/orchestrator.py` to include a compact `roadmap` context key when resolution succeeds (fields: course_code, course_title, year, semester, tech_stack, competency_stage, course_status); omit the key entirely when resolution fails
- [x] 4.3 Update `server/modules/agents/coordinator.py` to read the `roadmap` context key and use it as supplementary advisory context alongside existing curriculum retrieval (never replacing it; Proposed courses never anchor alignment)
- [x] 4.4 Confirm SME/GAD/ITSO agents ignore the new context key (no behavior change)

## 5. Tests and Verification

- [x] 5.1 Unit tests for roadmap models (natural key uniqueness, status lifecycle, check constraints) in `server/tests/curriculum_map/`
- [x] 5.2 Tests for read-only roadmap endpoints (list, detail, year/semester filter, auth rejection) in `server/tests/curriculum_map/`
- [x] 5.3 Tests for orchestrator roadmap resolution (resolved, null course_code, no active roadmap, proposed course excluded) in `server/tests/evaluations/`
- [x] 5.4 Tests for Coordinator enrichment (roadmap facts present/absent, partial flow unchanged, budget payload compactness) in `server/tests/agents/`
- [x] 5.5 Migration test in `server/tests/migrations/` covering upgrade/downgrade of the roadmap tables
- [x] 5.6 Run full backend suite (`uv run --project server pytest server/tests`) and `uv run --project server ruff check server`
## 6. Council Hardening (post-review, 2026-08-08)

- [x] 6.1 Replace `one_or_none()` with deterministic `.first()` in `resolve_roadmap_course_context` and use `.order_by(...).limit(1).first()` for the active-roadmap lookup (no duplicate-course_code crash; no `.all()[0]`)
- [x] 6.2 Enforce `(roadmap_id, course_code)` uniqueness: add `UniqueConstraint` to `RoadmapCourse` model, add migration `20260808_0002` (drop plain `idx_roadmap_courses_roadmap_code`, create unique `uq_roadmap_courses_roadmap_code`), update `CHAIN_HEAD_REV` in `test_curriculum_map_migration.py`
- [x] 6.3 Case-insensitive program matching: `func.lower` comparison in resolution query + normalize case in `_normalize_program` and seed `_resolve_course_id`
- [x] 6.4 Replace `.ilike()` with exact `func.lower()` equality in resolution course-code match
- [x] 6.5 Add `isinstance(roadmap_context, dict)` guard to `_format_roadmap_note`
- [x] 6.6 Remove `source_document_path` from `RoadmapSummaryResponse` (info leak; detail already omits it)
- [x] 6.7 Add `le=10` upper bound to `year` query param in router; fix stale "Revises:" docstring in `20260808_0001` migration
- [x] 6.8 Regression tests: duplicate course_code resolution, case-insensitive program match, summary omits `source_document_path`, non-dict roadmap_context; run targeted suites + ruff
