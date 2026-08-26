## ADDED Requirements

### Requirement: Program roadmap identity and versioning
The system SHALL store program roadmaps as versioned records identified by the canonical program code (`program`), an optional specialization track (`specialization`), and a positive integer `version_number`. The combination of `program`, `specialization`, and `version_number` SHALL be unique. Each roadmap SHALL carry a `status` of `active` or `retired`. At most one roadmap version SHALL be `active` for a given `(program, specialization)` pair.

#### Scenario: Seed a first roadmap version
- **WHEN** a roadmap is seeded for program `BSCS` with specialization `Intelligent Systems` at version 1
- **THEN** the roadmap is stored with status `active` and is the active version for that pair

#### Scenario: Seed a second version
- **WHEN** a second roadmap version is seeded for the same `(program, specialization)` pair
- **THEN** the previous active version SHALL be set to `retired` and the new version SHALL become `active`

### Requirement: Roadmap year and course structure
Each roadmap SHALL contain one or more roadmap years (`RoadmapYear`), each with a `year_number`, an optional `semester`, and an optional label and description. Each roadmap year SHALL contain zero or more roadmap courses (`RoadmapCourse`), each with a `course_code`, `course_title`, optional `tech_stack`, optional `competency_stage`, optional `learning_outcomes_summary`, and a required `course_status` of `existing` or `proposed`. A roadmap course SHALL reference its owning roadmap and year. A roadmap course MAY reference the existing `courses` table via a nullable foreign key on `course_code`.

#### Scenario: Course rows carry roadmap metadata
- **WHEN** a roadmap course row is created for course code `ITEC 205` with a tech stack and competency stage
- **THEN** the row stores the code, title, tech stack, competency stage, and course status `existing`, and links to the owning year and roadmap

#### Scenario: Proposed course rows have no course table reference
- **WHEN** a roadmap course row is created for a course marked `proposed` (e.g. `Intelligent Systems I`)
- **THEN** the row stores `course_status = proposed` and leaves the reference to the `courses` table null

### Requirement: Roadmap lifecycle and historical truth preservation
Roadmaps SHALL be retired by flipping `status` from `active` to `retired`. Roadmap data SHALL NOT be referenced by foreign keys from evaluation jobs or evaluation results. Retiring or deleting a roadmap SHALL NOT alter any historical evaluation, synthesis, or monitoring matrix record.

#### Scenario: Retire an active roadmap
- **WHEN** an active roadmap is set to `retired`
- **THEN** it is no longer resolvable for new evaluations and no evaluation job or result row references it

#### Scenario: Historical evaluations remain intact after roadmap removal
- **WHEN** a roadmap is retired or deleted after evaluations have run
- **THEN** the stored evaluation results and monitoring matrix entries remain unchanged

### Requirement: Roadmap source document provenance
Each roadmap SHALL optionally store a `source_document_path` pointing to the original roadmap document (PDF) stored under the repository-root `uploads/` directory. Roadmap source documents SHALL NOT be embedded into the vector store, SHALL NOT be registered in the reference library, and SHALL NOT be retrievable as evaluation reference context.

#### Scenario: Roadmap PDF stored as provenance only
- **WHEN** a roadmap is seeded with a source document
- **THEN** the PDF exists under `uploads/`, the path is recorded on the roadmap, and no Chroma collection or reference-library listing contains it

### Requirement: Idempotent roadmap seeding
The system SHALL provide a seeding script that loads roadmap JSON from `server/data/roadmaps/` and upserts roadmap, year, and course rows idempotently by the natural key `(program, specialization, version_number)`. Re-running the seed SHALL NOT create duplicate rows.

#### Scenario: Re-seed updates in place
- **WHEN** the roadmap seed script is run twice with the same JSON payload
- **THEN** the second run updates existing rows in place and creates no duplicates

### Requirement: Read-only roadmap API
The system SHALL expose read-only endpoints under `/curriculum-map/roadmaps` listing roadmaps, returning roadmap detail, and listing roadmap courses filtered by year and semester. All roadmap endpoints SHALL require an authenticated user.

#### Scenario: List active roadmaps
- **WHEN** an authenticated user requests `GET /curriculum-map/roadmaps`
- **THEN** the response lists roadmaps with their program, specialization, version, and status

#### Scenario: Filter courses by year and semester
- **WHEN** an authenticated user requests `GET /curriculum-map/roadmaps/{id}/courses?year=2&semester=1`
- **THEN** the response returns only course rows belonging to year 2, semester 1 of that roadmap

#### Scenario: Unauthenticated request is rejected
- **WHEN** an unauthenticated request is made to any roadmap endpoint
- **THEN** the request is rejected with an authentication error
