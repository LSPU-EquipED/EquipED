## 1. Deterministic ITSO Runtime Configuration

- [x] 1.1 Add a validated ITSO-specific temperature setting with a default of `0.0`, without changing other agents' configured defaults.
- [x] 1.2 Route the ITSO agent through the ITSO-specific setting and preserve the requested model/temperature in runtime metadata.
- [x] 1.3 Ensure model fallback returns and persists the actual served model rather than only the originally requested model.
- [x] 1.4 Add configuration and agent tests for the ITSO temperature and requested-versus-served model behavior.

## 2. Deterministic Local Evidence Prechecks

- [x] 2.1 Create a versioned local ITSO precheck module for bibliography presence, in-text citation patterns, DOI candidates, and compact reference/citation coverage signals.
- [x] 2.2 Make precheck ordering, normalization, limits, and output hashing deterministic for fixed source evidence.
- [x] 2.3 Integrate one frozen precheck snapshot into supervisor ITSO context preparation without rebuilding it inside agent retries.
- [x] 2.4 Add fixture tests for bibliography/citation/DOI signals, missing evidence, stable ordering, and bounded output.

## 3. ITSO Prompt and Result Honesty

- [x] 3.1 Update the ITSO prompt contract to consume local precheck evidence as advisory signals and distinguish verified, not-verified, insufficient, and unavailable evidence states.
- [x] 3.2 Ensure prompt/output guidance prohibits plagiarism, invalid-citation, or legal-noncompliance conclusions based solely on absent local signals.
- [x] 3.3 Add structured validation for ITSO evidence-status fields while preserving existing score/result compatibility.
- [x] 3.4 Add ITSO prompt/result tests for sufficient evidence, insufficient evidence, and unavailable precheck evidence.

## 4. Bounded Provenance Persistence and Results Contract

- [x] 4.1 Define a bounded ITSO provenance payload in existing agent-result metadata with requested/served model, temperature, retry/repair/trim indicators, evidence version, identifiers, and hashes.
- [x] 4.2 Persist immutable ITSO provenance with agent results without storing raw prompts, raw SLM/reference text, credentials, or external payloads.
- [x] 4.3 Expose authorized result consumers to safe runtime provenance while preserving compatibility for historical evaluations that have none.
- [x] 4.4 Add persistence and route tests for provenance, fallback attribution, redaction, and historical-result compatibility.

## 5. Consistency Benchmark and Validation

- [x] 5.1 Add fixture-driven repeat-run tests proving deterministic prechecks, prompt assembly, provenance, and normalized criterion outputs for fixed fake-client inputs.
- [x] 5.2 Add an offline benchmark harness that reports ITSO criterion/subtotal deltas and provenance without mutating jobs or production scores.
- [x] 5.3 Document the manual live-provider repeat benchmark procedure and its advisory-only interpretation.
- [x] 5.4 Run targeted agent/evaluation/synthesis tests plus lint and format checks.
- [x] 5.5 Run post-implementation review and record any limits that must remain for the later citation/policy verification change.
