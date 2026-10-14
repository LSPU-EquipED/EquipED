## Scope and ownership

- Own the actual pure SME, Coordinator, GAD and ITSO pipelines, prompts, scoring, semantic rubric contracts, result contracts and immutable snapshot hashing.
- Public execution is `evaluate(EvaluationRequest, client, ExecutionConfig)`. Require prepared inputs and explicit transport; no backend callbacks or default clients. Deep-freeze request mappings and reset execution scopes on success/failure; install scopes independently in worker threads.
- No server, ORM, retrieval, environment settings or implicit model-client imports.
- Backend retains admission, authorization, transport security and persistence.
- Preserve canonical snapshot bytes, hashes, prompts and manifest defaults.
- Verify installed-package imports and run `apps/server/.venv/bin/python -m pytest libs/evaluation-harness/tests` from repo root (or `pnpm harness:test`). Format/lint with server Ruff config. Preserve legacy regression assertions when relocating tests.
- Native build backend minimum is `uv_build>=0.11.25,<0.12`; server lock and Docker use the local package. Model-validation integration is imports only; do not expand workflow or API/schema policy.
