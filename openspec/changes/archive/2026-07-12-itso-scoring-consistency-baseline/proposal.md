## Why

Repeated evaluations of the same SLM can produce materially different ITSO scores because the ITSO agent currently uses a sampled LLM call and evaluation provenance does not make model fallback, repair, prompt trimming, or evidence inputs easy to compare. Before adding citation or policy tools, EquipED needs a trustworthy consistency baseline so human reviewers can understand whether a result reflects document evidence or runtime variability.

## What Changes

- Set ITSO evaluation calls to deterministic generation settings and preserve the actual model that served each response, including any fallback.
- Capture an immutable, bounded ITSO evidence/provenance snapshot for each evaluation, covering prompt/rubric versions, retrieved chunk identifiers, prompt trimming, JSON repair, model fallback, and later tool-evidence identity.
- Add deterministic local prechecks for reference/citation presence and evidence quality; these checks inform ITSO review but do not make plagiarism or legal determinations.
- Require ITSO output to distinguish verified evidence, unavailable evidence, and insufficient evidence rather than inventing certainty.
- Add repeat-run consistency tests and an offline benchmark harness to measure score drift for fixed inputs.
- Keep external DOI verification, policy-document retrieval, and institution-approved deterministic score decision tables out of this baseline; they are follow-on changes.

## Capabilities

### New Capabilities
- `itso-scoring-consistency`: Deterministic ITSO execution, evidence/provenance capture, evidence-status honesty, and repeat-run consistency validation.

### Modified Capabilities
- `evaluations`: Evaluation results must expose the actual per-agent runtime provenance needed to explain ITSO score variation without exposing sensitive prompt or document content.

## Impact

- Affected backend: `server/core/config.py`, `server/core/llm.py`, `server/modules/agents/itso.py`, `server/modules/agents/base.py`, evaluation orchestration, synthesis result schemas/routes, and agent/evaluation tests.
- Adds local deterministic citation/reference precheck utilities and an offline benchmark fixture/harness.
- No new external service, package dependency, schema migration, or frontend workflow is required for the baseline; result payload additions may need lightweight frontend display in a follow-up only if exposed to users.
