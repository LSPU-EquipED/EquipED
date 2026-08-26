## Why

The evaluation harness still carries provider-specific assumptions, unbounded concurrency, and agent paths that can turn malformed or weakly grounded output into misleading results. This change hardens the approved single-process architecture for local Gemma deployment and deterministic offline verification before implementation proceeds.

## What Changes

- Replace the development Groq dependency with the local `equiped-gemma3-4b-qat-q4` alias and deterministic fake OpenAI-compatible providers.
- Add provider-neutral JSON-object/JSON-Schema capability negotiation while keeping semantic schemas and validation authoritative inside each agent.
- Add one absolute monotonic deadline per logical LLM request, typed completion metadata, disabled implicit/same-target fallback, and a process-wide configurable provider gate; local quotas are disabled.
- Add database-backed FIFO single-job admission, CAS ownership transitions, queue draining, heartbeats, stale-job recovery, one worker, and the required Alembic migration.
- Prepare canonical clean source text once and pass immutable precomputed context to agents.
- Harden SME, ITSO, GAD, and dormant Coordinator paths with strict local contracts, bounded retries, deterministic scoring, exact grounding, privacy controls, and explicit partial behavior.
- Make deterministic Layer 4 synthesis the terminal output and add wave-based verification and council acceptance tasks.

## Capabilities

### New Capabilities
- `local-agent-harness`: Provider-neutral local runtime, admission, deadlines, completion metadata, and deterministic verification foundation.
- `coordinator-full-path-hardening`: Contract for the dormant curriculum-grounded Coordinator path and attribution-safe orchestration.

### Modified Capabilities
- `evaluations`: Change lifecycle, admission, recovery, source preparation, fallback, partial/full failure, and terminal synthesis requirements.
- `sme-engine-scoring`: Add strict non-coercing extraction contracts, canonical source use, and bounded call behavior.
- `itso-scoring-consistency`: Add exact criterion schema, local-only policy delivery, frozen tasks, safe regeneration, and raw-output privacy.
- `gad-grounded-scoring`: Require exact grounding, budget-aware prompts, compact repair, and validate-all-before-cap behavior.
- `per-agent-llm-config`: Clarify alias resolution, shared quota pools, and explicit fallback boundaries.
- `multi-agent-evaluation`: Replace the stale pre-Layer-4 stop with terminal deterministic synthesis.
- `evaluation-data-persistence`: Require terminal matrix persistence, ownership scope, and ITSO raw-output privacy.
- `agent-prompt-management`: Define exact prompt consumption/ID attribution and SME extraction prompt migration.
- `itso-evidence-tools`: Require endpoint locality plus explicit approval for policy clause delivery.

## Impact

The change affects core LLM/config/runtime transport, evaluation orchestration and persistence, agent modules, prompt attribution, configuration examples, and an Alembic migration. It preserves FastAPI BackgroundTasks, supervisor-managed ThreadPoolExecutor Layer 3 execution, local data residency, ownership scoping, and no Redis/Celery; no production code is included in this planning change.
