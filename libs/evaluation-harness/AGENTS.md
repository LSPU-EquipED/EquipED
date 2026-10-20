## Scope and ownership

- Own SME, Coordinator, GAD and ITSO pipelines, prompts, scoring, semantic rubric contracts, result contracts, immutable snapshot hashing and specialist tool workflows.
- Public execution is `evaluate(EvaluationRequest, client, ExecutionConfig)` with explicit optional tool dependencies. Require authorized prepared inputs and explicit configuration/transport; no database callbacks, environment lookup or default model clients. Deep-freeze request mappings and reset execution scopes on success/failure; install scopes independently in worker threads.
- No server, ORM, FastAPI, Chroma or environment-settings imports. Network operations are restricted to explicit tool modules; preserve pinned HTTPS, safe public-query selection and bounded execution.
- Backend retains admission, authorization, local storage/retrieval infrastructure, model resolution, durable job ownership and persistence. It supplies authorized institutional reference data; the harness owns specialist evidence interpretation and public-reference execution.
- Shared contracts/runtime must not load specialist pipelines. Agents must not import sibling agents. Capability metadata may be loaded without executable pipelines.
- Preserve canonical snapshot bytes, hashes, prompts and manifest defaults.
- Verify installed-package imports and run `apps/server/.venv/bin/python -m pytest libs/evaluation-harness/tests` from repo root (or `pnpm harness:test`). Format/lint with server Ruff config. Preserve legacy regression assertions when relocating tests.
- Native build backend minimum is `uv_build>=0.11.25,<0.12`; server lock and Docker use the local package. Model-validation integration is imports only; do not expand workflow or API/schema policy.
