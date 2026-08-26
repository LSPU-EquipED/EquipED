## 1. Single-pass extraction contract

- [x] 1.1 Inventory the five current GAD criterion fact payloads and define versioned heterogeneous combined-envelope and registry-version constants.
- [x] 1.2 Add duplicate-safe ordered-list parsing and validate all five required heterogeneous criterion sections before any scorer runs; reject model-provided numeric score fields.
- [x] 1.3 Add bounded per-criterion evidence-entry limits, preserve score-band saturation thresholds, and validate GAD-01/03/04/05 excerpts and identifiers against the frozen ordered context.

## 2. GAD execution refactor

- [x] 2.1 Create a fact-only managed GAD prompt revision and build one combined GAD extraction prompt through a GAD-local pipeline that reuses BaseAgent packing, model-routing, fallback, and JSON-object transport helpers.
- [x] 2.2 Replace the normal-path five-call criterion loop with exactly one combined extraction invocation.
- [x] 2.3 Adapt accepted combined facts into the existing deterministic GAD registry, exclude syllabus/curriculum reference context from factual extraction, and preserve the standard AgentEvaluationResult and synthesis contract.
- [x] 2.4 Remove obsolete normal-path criterion-call orchestration and prevent nested criterion-level parallel or sequential LLM execution.

## 3. Honest failure and provenance behavior

- [x] 3.1 Implement one GAD-specific whole-envelope fact-only repair call for syntax, duplicate, missing, or field-invalid sections; do not repair grounding or registry failures.
- [x] 3.2 Record one failed GAD result with actual elapsed time and known runtime metadata when repair remains incomplete or invalid; do not issue criterion-level fallback calls.
- [x] 3.3 Add bounded extraction-schema, registry-version, and candidate/accepted/rejected evidence indicators to the provenance sanitizer allowlist; preserve actual model, repair, temperature, prompt-version, and trimming metadata.
- [x] 3.4 Add concise GAD timing instrumentation that distinguishes combined extraction, validation, and deterministic scoring duration.

## 4. Regression and consistency coverage

- [x] 4.1 Add fixed-response tests proving one normal-path LLM call yields all five criterion scores through the deterministic registry.
- [x] 4.2 Add tests for unknown, duplicate, malformed, and missing evidence references plus criterion-specific missing-evidence behavior.
- [x] 4.3 Add tests for repairable and unrecoverable combined responses, including no criterion-level fallback calls and honest partial synthesis behavior.
- [x] 4.4 Add repeatability tests proving identical accepted facts and registry version yield identical final GAD scores.
- [x] 4.5 Add a controlled comparison harness/report for current and single-pass GAD outputs: runtime, criterion coverage, grounded evidence quality, and deterministic scores.

## 5. Validation and rollout decision

- [x] 5.1 Run focused GAD, agent, evaluation, and synthesis test suites.
- [x] 5.2 Run the comparison on representative SLMs and obtain human review of criterion coverage and evidence quality before rollout.
- [x] 5.3 Run a real evaluation smoke test and verify GAD no longer dominates wall-clock runtime.
