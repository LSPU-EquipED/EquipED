## 1. Wave 1 — Foundation parallel lanes

- [x] 1.1 Freeze local Gemma alias, deterministic fake-provider fixtures, provider-neutral JSON object/JSON-Schema capability, and typed completion metadata contract.
- [x] 1.2 Implement process-wide provider/endpoint/model gate with configurable in-flight/RPM/TPM limits, local quota disablement, rate-header handling, one absolute monotonic deadline per logical LLM request covering gate wait/attempts/backoff/explicit distinct fallback, and disabled implicit/same-target fallback.
- [x] 1.3 Add database-backed FIFO admission slot `1`, uniqueness/check constraints, CAS/token transitions, terminal release, required Alembic migration, and migration verification.
- [x] 1.4 Implement one-worker queue drainer shared by submission and startup recovery, with SQLAlchemy session isolation from agent threads.
- [x] 1.5 Add heartbeat freshness, periodic pending-future heartbeat, startup recovery, stale ownership protection, and bounded provenance aggregation.
- [x] 1.6 Add canonical clean source-text preparation once and immutable precomputed context wiring; remove direct agent PDF reopening.
- [x] 1.7 Update affected contracts, server rules, and `.env.example` to remove stale Llama/Groq examples generically without exposing secrets; add any required forward SME extraction-prompt seed migration.

## 2. Wave 1 — Integration and gate

- [x] 2.1 Integrate admission, drainer, recovery, heartbeat, deadline, gate, completion metadata, and source preparation through the supervisor/orchestrator.
- [x] 2.2 Verify one active job globally, FIFO advancement, CAS ownership, privacy, local capability behavior, and unchanged explicit partial/full selection semantics.
- [x] 2.3 Run Oracle gate 1 and resolve findings before agent lanes begin.

## 3. Wave 2 — Parallel agent lanes

- [x] 3.1 SME: implement strict grouped/fallback schemas, `finish_reason=length` basket failure, fixed-slice/cap enforcement without silent trim, valid empty arrays, extraction prompt attribution, canonical source consumption, bounded telemetry, and tests.
- [x] 3.2 ITSO: implement exact versioned criterion schema, frozen task/evidence, local-only policy enforcement, safe one-time regeneration, normalized-only persistence, and characterization tests.
- [x] 3.3 GAD: restore exact grounding, reject duplicate frozen chunk IDs, derive prompt/repair budgets from serialized content, bump extraction schema without changing registry thresholds, bound repair diagnostics, validate all before cap ten, and add tests.
- [x] 3.4 Coordinator: harden dormant full path around authoritative precomputed curriculum, exact ten-criterion merge identity/uniqueness, all-false valid rows scoring 1, no managed prompt ID, deterministic summary, no independent fallback/LLM summary, and attribution tests.

## 4. Wave 2 — Integration and gate

- [x] 4.1 Integrate shared dispatch attribution and Coordinator/orchestrator failure semantics under one owner; preserve ordinary explicit partial behavior.
- [x] 4.2 Verify strict output contracts, deterministic scores, evidence grounding, policy non-egress, prompt attribution, and call-count bounds.
- [x] 4.3 Run Oracle gate 2 and resolve findings before final acceptance. (Oracle APPROVE.)

## 5. Wave 3 — Acceptance and seal

- [x] 5.1 Run foundation concurrency/recovery/deadline/privacy suites and PostgreSQL admission evidence, not SQLite alone. (PostgreSQL FIFO test ran five rounds on disposable Neon.)
- [x] 5.2 Run SME, ITSO, GAD, Coordinator, evaluation/synthesis, migration, import/topology, and full server verification suites. (Full server: 1537 passed, 9 skipped; known Chroma-isolated suite green.)
- [ ] 5.3 Run synthetic/de-identified deterministic-provider characterization; run local Gemma acceptance and record host availability uncertainty explicitly. (Deterministic characterization is verified; local Gemma live-model acceptance was not performed and is deferred/not required for code closure per the proposal/design acceptance split.)
- [x] 5.4 Run Oracle gate 3, then the required bug/performance/security council over the complete diff. (Final council unanimous APPROVE; merged 828/9.)
