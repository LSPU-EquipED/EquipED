## Context

EquipED's Phase 1 evaluation pipeline runs 4 LLM agents (SME, Coordinator, GAD, ITSO) sequentially via FastAPI `BackgroundTasks`. Each agent calls the same Groq model (`llama-3.1-8b-instant`) through a singleton `LocalLLMClient`. Inter-agent pacing delays (5s, 10s, 20s) prevent TPM rate-limit violations since all 4 calls share a single 6,000 TPM budget.

Groq's free tier enforces TPM **per model**, not globally. Each model has its own independent TPM pool. By assigning each agent a different model, the 4 agents get 4 separate TPM budgets — eliminating contention and enabling parallel execution without rate-limit risk.

Current runtime: ~2.2 minutes for an 18-page SLM. Target: ~35-40 seconds.

## Goals / Non-Goals

**Goals:**
- Run all 4 evaluation agents in parallel using `ThreadPoolExecutor`
- Assign each agent a distinct Groq free-tier model with its own TPM pool
- Remove inter-agent pacing delays (no longer needed)
- Add model-failure fallback: retry with a different model before failing the agent
- Preserve the existing precompute → execute → persist pipeline shape
- Preserve execution guard, heartbeat, and idempotent resume behavior
- Keep the change within stdlib (`concurrent.futures`) — no new dependencies

**Non-Goals:**
- Celery/Redis integration (deferred to a separate change)
- asyncio rewrite of the LLM client (deferred — ThreadPoolExecutor is sufficient for I/O-bound parallelism)
- Local model support (deferred — per-agent config is designed to support it later but not implemented now)
- Changing the evaluation API surface or database schema
- Changing the synthesis/scoring logic

## Decisions

### D1: ThreadPoolExecutor over asyncio

**Choice:** `ThreadPoolExecutor(max_workers=4)`

**Rationale:** The current `LocalLLMClient` uses synchronous `urllib.request`. The work is I/O-bound (waiting for HTTP responses from Groq), so Python's GIL does not block parallelism. ThreadPoolExecutor requires no client rewrite and is simpler to debug.

**Alternatives considered:**
- `asyncio + aiohttp`: More "proper" for async I/O but requires rewriting `LocalLLMClient.generate()` to be async, propagating `async/await` through `BaseAgent.run()` and `Supervisor.run_evaluation()`. Larger change, more complexity, no measurable benefit for 4 concurrent I/O-bound tasks.
- `multiprocessing`: Unnecessary — the work is I/O-bound, not CPU-bound. Process spawn overhead would exceed any benefit.

### D2: Per-agent model assignment (RPD-optimized)

**Choice:**

| Agent | Model | TPM | RPD |
|---|---|---|---|
| SME | `llama-3.1-8b-instant` | 6,000 | 14,400 |
| Coordinator | `allam-2-7b` | 6,000 | 7,000 |
| GAD | `qwen/qwen3-32b` | 6,000 | 1,000 |
| ITSO | `openai/gpt-oss-20b` | 8,000 | 1,000 |

**Rationale:** RPD-optimized assignment maximizes daily evaluation capacity. Total 26K TPM is 13x more than each agent needs (~2K tokens per call). `gpt-oss-20b` for ITSO provides strict JSON schema enforcement — ideal for the structured IP/reference criteria. All models support JSON output.

**Alternatives considered:**
- TPM-optimized (llama-4-scout, llama-3.3-70b, gpt-oss-20b, qwen3-32b): Higher TPM (56K) but lower RPD (1K each = 250 evals/day). Overkill for current needs.
- All same model: Would reintroduce TPM contention and require pacing delays.

### D3: Per-agent LLM client factory

**Choice:** Replace `get_llm_client()` singleton with `get_llm_client_for_agent(agent_name)` that returns a cached `LocalLLMClient` configured with the agent's assigned model.

**Rationale:** Each agent needs its own `LocalLLMClient` instance with a different `model` parameter. The factory caches per agent name to avoid recreating clients on every evaluation. The global `get_llm_client()` is preserved as a fallback for non-agent callers.

**Implementation:**
```python
@lru_cache(maxsize=8)
def get_llm_client_for_agent(agent_name: str) -> LocalLLMClient:
    settings = get_settings()
    model = settings.get_agent_model(agent_name)  # falls back to llm_model_name
    return LocalLLMClient(
        provider=settings.llm_provider,
        model=model,
        api_base=settings.llm_api_base,
        api_key=settings.llm_api_key,
        request_timeout=float(settings.llm_request_timeout_seconds),
    )
```

### D4: Model-failure fallback (retry with different model)

**Choice:** If an agent's assigned model returns a persistent error (429 after retries, 404 deprecation, 503 extended outage), retry the LLM call with the global fallback model (`llm_model_name`) before marking the agent as failed.

**Rationale:** Model deprecations or temporary rate limits on one model should not fail an evaluation. The fallback is a single additional LLM call — cheap insurance.

**Flow:**
```
agent.run() with assigned model
  → if LLM call fails with persistent error:
    → retry with fallback model (get_llm_client())
    → if fallback also fails: mark agent as failed (existing behavior)
```

### D5: Precompute stays sequential, execution becomes parallel

**Choice:** The supervisor's `_build_precomputed_context()` and `_load_active_prompt_versions()` remain sequential (before parallel agents). Agent `run()` calls become parallel. `persist_agent_outputs()` remains sequential (after all agents complete).

**Rationale:** Precomputed context is read-only and shared across agents — no benefit to parallelizing it. Persistence must happen after all agents complete to maintain the existing idempotent resume contract. Only the LLM calls (the slow part) benefit from parallelism.

```
precompute_context()          ← sequential, shared, read-only
load_prompt_versions()        ← sequential, shared, read-only
                              ↓
ThreadPoolExecutor(4 workers) ← parallel
  sme.run(precomputed)
  coord.run(precomputed)
  gad.run(precomputed)
  itso.run(precomputed)
                              ↓
persist_agent_outputs()       ← sequential, after all complete
```

### D6: Thread safety

**Choice:** Precomputed context dict is read-only during parallel execution. Each agent receives its own LLM client instance. No DB access happens inside `agent.run()` — only the supervisor touches the DB, before and after the parallel section.

**Rationale:** The current `BaseAgent.run()` does not access the database. It receives all needed data (chunks, prompt, precomputed context) as parameters. This makes the parallel section naturally thread-safe without locks or session pooling.

## Risks / Trade-offs

- **[Model quality variance]** Different models may produce evaluation results of varying quality. → Mitigation: all chosen models are production-grade LLMs. The system already handles partial results and human review is authoritative. Quality can be tuned per-agent via prompt management.

- **[Model deprecation]** Groq may deprecate a model mid-development. → Mitigation: D4 fallback mechanism retries with the global model. Per-agent model config is environment-variable driven, so swapping a model is a config change, not a code change.

- **[Thread safety in logging]** Python's `logging` module is thread-safe by design. `[EVAL_TIMING]` logs from parallel agents may interleave but will not corrupt. → Mitigation: acceptable — logs include agent name for disambiguation.

- **[Error handling complexity]** `ThreadPoolExecutor` with `as_completed` requires careful exception handling. A single agent failure should not crash the pool. → Mitigation: each agent's `run()` is wrapped in try/except inside the thread, producing an `AgentEvaluationResult` with `success=False` on failure (same as current sequential behavior).

- **[Heartbeat gap]** The orchestrator heartbeats between phases. During parallel execution (~30s), no heartbeat fires. → Mitigation: add a single heartbeat before submitting to the pool and one after all futures complete. The execution guard's stale timeout (60s) is longer than the expected parallel runtime.

- **[Groq RPD limits]** At 1K RPD per model, sustained batch evaluation could hit daily caps. → Mitigation: acceptable for current development phase with no real users. RPD-optimized model assignment gives 250+ evaluations/day. Can revisit when moving to production.
