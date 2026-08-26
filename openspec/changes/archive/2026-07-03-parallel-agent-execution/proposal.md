## Why

Phase 1 evaluation runs 4 agents (SME, Coordinator, GAD, ITSO) sequentially with pacing delays between calls to avoid Groq's per-model TPM rate limits. This results in ~2.2 minutes per 18-page SLM evaluation. Since Groq's free tier enforces TPM per-model (not globally), assigning each agent a different model creates 4 independent TPM pools — enabling true parallel execution without rate-limit contention and cutting runtime to ~35-40 seconds.

## What Changes

- Add per-agent LLM model configuration (`LLM_MODEL_SME`, `LLM_MODEL_COORD`, `LLM_MODEL_GAD`, `LLM_MODEL_ITSO`) with fallback to the global `LLM_MODEL_NAME`
- Replace the singleton `get_llm_client()` with per-agent client factory `get_llm_client_for_agent(agent_name)`
- Replace the sequential agent loop in `Supervisor.run_evaluation()` with `ThreadPoolExecutor`-based parallel execution (4 workers)
- Remove inter-agent pacing delays (`sleep_before`) — no longer needed with separate TPM pools
- Add model-failure fallback: if an agent's assigned model is unavailable (deprecation, rate limit, 429), retry with a different model before failing
- Preserve the existing precompute-then-execute-then-persist pipeline: precompute context stays sequential and shared, agent execution becomes parallel, persistence stays sequential after all agents complete
- Update `[EVAL_TIMING]` logs to reflect parallel execution (per-agent start/end, wall-clock total)

## Capabilities

### New Capabilities
- `per-agent-llm-config`: Per-agent LLM model assignment and client factory, allowing each evaluation agent to use a different model with independent rate-limit pools

### Modified Capabilities
- `evaluations`: The evaluation execution contract changes from sequential agent execution with pacing delays to parallel agent execution via thread pool, with per-agent model assignment and model-failure fallback

## Impact

- **`server/core/config.py`** — new per-agent model settings, per-agent API base/key overrides (optional)
- **`server/core/llm.py`** — `get_llm_client()` replaced by `get_llm_client_for_agent(agent_name)`, cached per agent
- **`server/modules/agents/base.py`** — `BaseAgent` receives its LLM client from the supervisor based on agent name, not from the global singleton
- **`server/modules/agents/supervisor.py`** — sequential loop replaced with `ThreadPoolExecutor`, pacing delays removed, per-agent client injection
- **`server/modules/agents/sme.py`, `coordinator.py`, `gad.py`, `itso.py`** — accept injected LLM client
- **`server/tests/agents/`** — tests updated for parallel execution, per-agent model config, fallback behavior
- **No database schema changes** — agent results persistence is unchanged
- **No API changes** — evaluation endpoints remain the same
- **No new dependencies** — `concurrent.futures` is stdlib
