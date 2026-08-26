## Context

EquipED is a single-process FastAPI modular monolith. Layer 3 dispatches agents in a supervisor-owned thread pool and Layer 4 writes the monitoring matrix. The current harness needs a local Gemma target, deterministic fake providers, transport capability and telemetry boundaries, global admission, and agent-local validation without weakening existing deterministic scoring or privacy contracts.

## Goals / Non-Goals

**Goals:**
- Freeze a provider-neutral completion interface with explicit structured-output capability, typed metadata, and process-wide pacing; each logical LLM request gets one absolute monotonic deadline.
- Guarantee one globally admitted job using database CAS/FIFO semantics, heartbeat-aware recovery, and one queue drainer.
- Prepare source/evidence once, then enforce strict, bounded, agent-local contracts and honest partial/full outcomes.
- Make local deterministic tests the plumbing gate and local Gemma the model-sensitive acceptance gate.

**Non-Goals:**
- No Groq dependency, external policy egress, Redis/Celery, scheduler table, generic scoring layer, fuzzy grounding, criterion-level GAD/ITSO repair, SME LLM repair, or curriculum reactivation.

## Decisions

1. **Local provider and fakes.** Default the local alias to `equiped-gemma3-4b-qat-q4`; use deterministic fake OpenAI-compatible providers for transport and harness tests. Provider configuration advertises JSON object or JSON Schema capability explicitly; no silent downgrade/retry.
2. **Transport boundary.** Return immutable content plus served model, usage, finish reason, timings, attempt count, and allowlisted rate data. Each logical LLM request has one absolute monotonic deadline covering provider-gate wait, attempts, backoff, and any explicitly configured distinct fallback. Evaluation lifecycle is governed separately by admission, heartbeat, and recovery. Implicit/global and same-target fallback are disabled; only explicit distinct endpoint/model/privacy-compatible fallback is allowed. A process-wide provider/endpoint/model gate enforces configurable in-flight/RPM/TPM limits; local quotas are disabled. Aliases may resolve to one model and do not create quota pools.
3. **Admission.** Add nullable `admission_slot=1` with uniqueness/check constraints and an Alembic revision. Atomic oldest-SUBMITTED claim, token/CAS transitions, terminal release, startup recovery, and submission share one queue drainer. Agent threads never share SQLAlchemy sessions; one worker drains FIFO.
4. **Immutable preparation.** Ingestion/OCR/boilerplate semantics prepare canonical clean source text once per evaluation; it is not persisted as a speculative duplicate. Supervisor freezes rubric, references, curriculum, evidence hashes/IDs, policy mode, and request deadlines before parallel dispatch.
5. **Agent ownership.** SME uses strict non-coercing schemas for six baskets, rejects `finish_reason=length`, never silently trims fixed slices/caps, preserves valid empty arrays, and uses existing deterministic scoring. ITSO uses an exact versioned criterion schema, status-only remote policy evidence, local-only policy delivery, one frozen-context regeneration, and normalized-only persistence; policy clauses require endpoint locality and explicit approval. GAD uses exact source/chunk matching, rejects duplicate frozen IDs, actual serialized-budget accounting, one compact whole-envelope repair, validation of all instances before cap ten, and an extraction-schema version bump without registry threshold changes. Coordinator consumes only authoritative precomputed curriculum, validates exact ten-criterion identity/uniqueness, scores all-false valid rows as 1, has no managed prompt attribution, deterministic summary, or independent fallback.
6. **Prompt attribution.** Persist a prompt ID only when exact managed text affects outbound input. SME gets a forward extraction-only managed preamble for grouped and criterion fallback calls; Coordinator remains non-consuming and has no prompt ID until a compatible fact-only contract exists. Historical migrations remain immutable.
7. **Lifecycle.** Preserve explicit no-curriculum partial completion (`COMPLETED` job / `COMPLETED_PARTIAL` matrix), while a requested full job missing curriculum or failing Coordinator terminates `FAILED` after synthesizing available outputs. Layer 4 deterministic synthesis is terminal and there is no Layer 5.

## Risks / Trade-offs

- [Risk] Local Gemma availability may block model-quality acceptance → deterministic fakes prove plumbing; report Windows host availability separately.
- [Risk] SQLite cannot prove cross-session concurrency → include PostgreSQL concurrency evidence in acceptance.
- [Risk] Provider pacing lowers parallel throughput → retain parallel futures and measure bounded gate wait.
- [Risk] Strict schemas reject usable malformed output → preserve only the specified bounded agent-local recovery paths and record failures honestly.

## Migration Plan

Add and verify the Alembic admission migration, deploy configuration with local alias/fake-provider test mode, run recovery/backfill checks, then enable the queue drainer. Rollback disables new harness behavior and reverses the migration only after terminal jobs and admission slots are safely drained.

## Open Questions

- Exact local Gemma endpoint health-check and Windows-host CI availability remain deployment concerns for the parent validation owner.
