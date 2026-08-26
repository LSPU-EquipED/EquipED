## 1. Per-agent model configuration

- [x] 1.1 Add per-agent model settings to `server/core/config.py`: `llm_model_sme`, `llm_model_coord`, `llm_model_gad`, `llm_model_itso` (all default to `None`, falling back to `llm_model_name`)
- [x] 1.2 Add `get_agent_model(agent_name)` helper method to `Settings` that returns the per-agent model or falls back to `llm_model_name`
- [x] 1.3 Add per-agent model env vars to `.env.example` with the RPD-optimized defaults: `LLM_MODEL_SME=llama-3.1-8b-instant`, `LLM_MODEL_COORD=allam-2-7b`, `LLM_MODEL_GAD=qwen/qwen3-32b`, `LLM_MODEL_ITSO=openai/gpt-oss-20b`
- [x] 1.4 Add tests for per-agent model config and fallback behavior in `server/tests/core/test_config.py`

## 2. Per-agent LLM client factory

- [x] 2.1 Add `get_llm_client_for_agent(agent_name)` to `server/core/llm.py` — cached per agent name, returns `LocalLLMClient` with the agent's assigned model
- [x] 2.2 Preserve existing `get_llm_client()` as the global fallback (used by non-agent callers and model-failure fallback)
- [x] 2.3 Add tests for client factory: per-agent caching, different models per agent, fallback to global client

## 3. Model-failure fallback

- [x] 3.1 Add fallback logic to `BaseAgent.run()` in `server/modules/agents/base.py`: if the LLM call fails with a persistent error (429 after retries, 404, 503), retry once with `get_llm_client()` (global fallback model)
- [x] 3.2 Log the fallback attempt with `[EVAL_MODEL_FALLBACK]` showing agent name, original model, fallback model, and outcome
- [x] 3.3 If fallback also fails, preserve existing failure behavior (AgentEvaluationResult with `success=False`)
- [x] 3.4 Add tests for model-failure fallback: assigned model fails + fallback succeeds, both fail, 404 deprecation triggers immediate fallback

## 4. Parallel agent execution in Supervisor

- [x] 4.1 Replace the sequential `for agent in agents` loop in `Supervisor.run_evaluation()` with `ThreadPoolExecutor(max_workers=4)` using `as_completed`
- [x] 4.2 Inject per-agent LLM clients: each agent receives its client via `get_llm_client_for_agent(agent_name)` before being submitted to the pool
- [x] 4.3 Remove inter-agent pacing delays (`sleep_before`, `_get_agent_delay` calls) — no longer needed with separate TPM pools
- [x] 4.4 Wrap each agent's `run()` in try/except inside the thread to produce `AgentEvaluationResult(success=False)` on failure (same as current sequential behavior)
- [x] 4.5 Update `[EVAL_TIMING]` logs: per-agent logs show `parallel=true`, add wall-clock total for the parallel section
- [x] 4.6 Ensure precomputed context dict is treated as read-only during parallel execution (no mutations inside `agent.run()`)

## 5. Orchestrator heartbeat adjustment

- [x] 5.1 Add heartbeat before dispatching parallel agents in the `EVALUATING` phase
- [x] 5.2 Add heartbeat after all agent futures complete (before synthesis)
- [x] 5.3 Verify the execution guard's stale timeout (60s) is longer than expected parallel runtime (~35s)

## 6. Agent class updates

- [x] 6.1 Update `BaseAgent` in `server/modules/agents/base.py` to accept an optional `llm_client` parameter in `run()` instead of always calling `get_llm_client()`
- [x] 6.2 Update `SMEAgent`, `ProgramCoordinator`, `GADAgent`, `ITSOAgent` to pass through the injected client
- [x] 6.3 Preserve backward compatibility: if no client is injected, fall back to `get_llm_client()` (existing behavior)

## 7. Test updates

- [x] 7.1 Update `server/tests/agents/test_supervisor.py` to test parallel execution: all agents complete, one agent fails while others succeed, precompute runs before parallel section
- [x] 7.2 Update `server/tests/agents/test_supervisor_delay.py` — pacing delays are removed for parallel mode; keep tests for fallback single-model mode
- [x] 7.3 Add integration test: full evaluation with parallel agents produces same result shape as sequential
- [x] 7.4 Add test: parallel execution with per-agent models uses correct model per agent
- [x] 7.5 Run full backend test suite and confirm all tests pass

## 8. Validation

- [x] 8.1 Run `pytest server/tests/agents/ -v` — all agent tests pass
- [x] 8.2 Run `pytest server/tests/core/ -v` — all core tests pass
- [x] 8.3 Run `pytest server/tests/evaluations/ -v` — all evaluation tests pass
- [x] 8.4 Run a real smoke test: submit an 18-page SLM evaluation and verify parallel execution + timing improvement
- [x] 8.5 Check `[EVAL_TIMING]` logs show parallel execution and no pacing delays
