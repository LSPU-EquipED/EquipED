## Why

GAD currently performs five serialized criterion-level LLM calls inside one supervisor-dispatched agent. This recreates nested orchestration, produces independently drifting model interpretations, bypasses the managed GAD prompt/rubric context, and has made GAD the evaluation wall-clock bottleneck (about 104–148 seconds in recent runs).

## What Changes

- Replace normal-path per-criterion GAD LLM extraction with one grounded, structured extraction call that returns facts for all five GAD criteria.
- Preserve deterministic, criterion-specific GAD score-band mapping and chunk-evidence validation after extraction; the model SHALL not assign final numeric scores.
- Replace the conflicting managed GAD scoring prompt with a fact-only prompt version and use a GAD-local execution/repair pipeline that reuses BaseAgent transport helpers without inheriting its score-shaped contract.
- Preserve the existing GAD result and synthesis contract while making one-call execution, bounded repair, and honest failure behavior explicit.
- Add repeatability, grounding, single-call, malformed-response, and runtime regression coverage.
- Add a controlled benchmark plan to compare the current and single-pass designs on representative SLMs before rollout.

## Capabilities

### New Capabilities
- `gad-grounded-scoring`: Single-pass, grounded GAD fact extraction with deterministic five-criterion scoring and repeatability safeguards.

### Modified Capabilities
- None.

## Impact

- Affected code: `server/modules/agents/gad.py`, `server/modules/agents/gad_scoring/`, agent prompt/context assembly, and GAD tests.
- APIs and persisted `AgentEvaluationResult`/synthesis shapes remain compatible.
- No new dependencies, migrations, or client changes.
- Reduces GAD LLM requests from five sequential calls to one normal-path call without adding nested parallelism.
