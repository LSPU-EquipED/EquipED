# Coordinator Roadmap Enrichment Spec

## Purpose

Evaluation-time delivery of compact program-roadmap facts to the Coordinator agent as supplementary advisory context. Roadmap context enriches the Coordinator's curriculum-grounded review without changing the evaluation lifecycle, job status, or matrix status, and without affecting any other agent.

## Requirements

### Requirement: Evaluation-time roadmap resolution
When constructing agent context for an evaluation, the system SHALL attempt to resolve the active roadmap for the job's `confirmed_program` and the uploaded document's `course_code`. When an active roadmap exists, the `course_code` matches a roadmap course row, and the course is not marked `proposed`, the system SHALL include a compact roadmap context payload in the agent context. When no active roadmap exists, the course code is null, or no course row matches, the system SHALL omit the roadmap payload entirely and proceed with the evaluation unchanged.

#### Scenario: Roadmap context resolved from program and course code
- **WHEN** an evaluation has `confirmed_program = BSCS` and the document's `course_code` matches a course row in the active BSCS roadmap
- **THEN** the agent context includes a roadmap payload for that course

#### Scenario: Missing course code omits roadmap context
- **WHEN** an evaluation's document has a null `course_code`
- **THEN** no roadmap payload is included and the evaluation proceeds exactly as without roadmap support

#### Scenario: No active roadmap omits roadmap context
- **WHEN** no active roadmap exists for the job's `confirmed_program`
- **THEN** no roadmap payload is included and the evaluation proceeds exactly as without roadmap support

### Requirement: Compact roadmap context payload
The roadmap context payload SHALL contain only the fields agents consume: `course_code`, `course_title`, `year`, `semester`, `tech_stack`, `competency_stage`, and `course_status`. The payload SHALL be bounded to a compact size and SHALL NOT be placed in the trimmable reference-context path of the prompt budget.

#### Scenario: Payload excludes human-reference fields
- **WHEN** a roadmap context payload is constructed
- **THEN** it contains only the seven consumed fields and omits descriptions, portfolio suggestions, and certification details

### Requirement: Coordinator-only consumption
Only the Coordinator agent SHALL consume roadmap context. SME, GAD, and ITSO agents SHALL receive and behave identically whether or not roadmap context is present.

#### Scenario: Non-Coordinator agents ignore roadmap context
- **WHEN** roadmap context is present in the agent context
- **THEN** SME, GAD, and ITSO evaluation behavior is unchanged

### Requirement: Advisory augmentation of Coordinator review
The Coordinator SHALL treat roadmap context as supplementary advisory information that augments — and never replaces — its existing curriculum retrieval and rubric-based review. Roadmap facts SHALL NOT change the evaluation lifecycle, job status, or matrix status. When `partial_without_curriculum` is true, the Coordinator SHALL remain excluded from the agent list exactly as today.

#### Scenario: Coordinator receives roadmap facts alongside curriculum retrieval
- **WHEN** the Coordinator runs with both roadmap context and curriculum retrieval available
- **THEN** it grounds its review on curriculum retrieval and uses roadmap facts (year placement, tech stack, competency stage) as supplementary context

#### Scenario: Partial evaluation flow unchanged
- **WHEN** an evaluation is submitted with `partial_without_curriculum = true`
- **THEN** the Coordinator remains skipped and the job completes with matrix status `COMPLETED_PARTIAL` regardless of roadmap availability

### Requirement: Proposed courses are never alignment anchors
The Coordinator SHALL treat roadmap courses with `course_status = proposed` as informational only and SHALL NOT use them as alignment targets or scoring anchors. Roadmap context SHALL only be included for courses with `course_status = existing`.

#### Scenario: Proposed course excluded from roadmap context
- **WHEN** the document's `course_code` matches a roadmap course marked `proposed`
- **THEN** no roadmap context payload is included for that course
