## MODIFIED Requirements

### Requirement: ITSO output schema validation and bounded regeneration
ITSO SHALL validate a versioned criterion schema dynamically assembled from the pre-resolved ITSO form snapshot with no coercion, duplicates, unknown envelope keys, or missing criterion ids. Active ITSO managed prompts SHALL serve as criterion-agnostic framing only; fixed criterion identifiers in managed prompts SHALL fail closed, and per-criterion authority SHALL come exclusively from the bound form snapshot. Grounding chunk IDs and text SHALL come from the exact chunks actually packed into the request. Every nonempty evidence excerpt SHALL be an exact substring of a cited packed chunk; omitted or foreign chunk IDs and synthetic omission-marker evidence SHALL fail schema validation/repair. Every seeded or newly authored criterion code SHALL use its snapshot-bound `llm_rubric_guidance` configuration and ordered metadata; the criterion code SHALL NOT require a code-specific runtime plugin. ITSO SHALL permit at most one whole-task regeneration from identical frozen context using bounded validator categories/paths.

Shape tolerance for small models: `criterion_scores` MAY be accepted as a dict keyed by criterion id in addition to the canonical array form; criterion titles SHALL be derived from the form snapshot map rather than trusted from the model; missing justification/evidence/chunk_ids SHALL default to empty. A criterion scored without justification, evidence, or chunk grounding SHALL be recorded as ungrounded advisory output and surfaced as a review flag — it SHALL NOT be indistinguishable from a grounded score.

#### Scenario: Invalid judgment
- **WHEN** output fails the schema on an unrecoverable violation (unknown envelope key, unknown/duplicate/missing criterion id, foreign chunk id, non-substring evidence, synthetic omission marker, non-integer or out-of-range score, or oversized text relative to snapshot)
- **THEN** one safe regeneration occurs at most, then the result fails honestly without raw-output persistence

#### Scenario: Model emits shorthand or ungrounded scores
- **WHEN** output provides `criterion_scores` as a dict, alters a criterion title, or omits justification/evidence/chunk_ids
- **THEN** the harness SHALL normalize to the canonical ordered shape with titles derived from the snapshot and defaulted empty fields
- **AND** SHALL emit per-criterion ungrounded advisory flags so the score is marked for human review rather than presented as grounded

#### Scenario: ITSO snapshot adds or reorders criterion codes
- **WHEN** an ITSO snapshot adds, removes, or reorders criteria using `llm_rubric_guidance`
- **THEN** ITSO SHALL generate the prompt and strict response schema in snapshot order without a code deployment

### Requirement: ITSO evidence is frozen and provenance is bounded
ITSO SHALL prepare one frozen task containing exact criteria from the pre-resolved ITSO form snapshot, packed evidence IDs/hashes, precheck and policy mode. Remote requests SHALL receive status-only policy evidence; policy content SHALL be local-only and never fall back externally. Successful ITSO execution SHALL persist neither prompt text nor raw response, but only bounded identity, canonical hashes, typed provenance, and normalized output. The ITSO evaluator SHALL NOT execute worker-side database queries to fetch rubric definitions or fallback criteria.

#### Scenario: Policy locality
- **WHEN** policy evidence is disabled or a remote provider is selected
- **THEN** no policy clauses are delivered and local-only mode cannot fall back externally

#### Scenario: Criteria resolved from in-memory snapshot
- **WHEN** ITSO is dispatched for evaluation
- **THEN** it formats scoring prompts and output schema from the pre-resolved in-memory ITSO form snapshot without database lookups
