# Evaluation harness extraction — implementation progress

This note records the completed source extraction/review; it does not replace or
modify the user-staged `evaluation-harness-extraction.md` plan.

## Implemented boundary

- `libs/evaluation-harness/equiped_harness` (flattened package layout: root-level module, direct `sme`, `coordinator`, `gad`, `itso`, and `runtime` domains). Historical extraction references below describe the original source layout. owns the actual SME, Coordinator,
  GAD and ITSO pipelines, pure runtime/prompt/scoring logic, rubric contracts,
  semantic manifests/calculators, snapshots and shared result contracts.
- Public execution: `evaluate(EvaluationRequest, client, ExecutionConfig)`.
  Request mappings are deeply copied/frozen. Explicit immutable controls are
  scoped with ContextVar tokens, reset on failure/success and isolated across
  threads. Global temperature/packing controls do not impose new upper bounds
  on legitimate backend Settings values.
- `apps/server/modules/evaluations/harness/` retains supervision, prepared context, residency-gated ITSO
  evidence retrieval and transport/config adapters. Production dispatch invokes
  the public harness seam; custom agents retain `.run`. Core response-contract
  validation, security, deadline handling and retries remain core-owned.
  `HarnessModelClient` translates contracts and returns the same shared
  completion result without extra retries.
- Feedback, synthesis and scripts use supported harness helpers. Coordinator
  coverage validation preserves the existing derivation and backend storage
  guards. The offline ITSO benchmark calls the public evaluator with explicit
  configuration. Admin model-validation changes are imports only.
- Native `uv_build>=0.11.25,<0.12`, the local server dependency/lock, package
  test/lint scripts, Docker copy order and development source mount are wired.
  No repository CI workflow existed to update.

No API/schema changes, rubric activation, official C-01 export, synthetic SME/GAD
semantic fixes, standalone alignment changes, live services, staging or commits
were performed. Historical migration comments remain historical.

## Actual verification

Independent final verification evidence: `/tmp/equiped-harness-independent-verification.log`.
The affected crosscuts suite completed with **2061 passed, 2 failed, 2 skipped**
in 536.62 seconds. Both failures are the independently reproduced baseline
failures listed below; no new regressions were found.

- Initial requested scoped run: 539 passed, one new GAD test expectation failed.
  Corrected the expectation to preserve GAD's existing fixed-zero temperature.
- Affected package/agents/core LLM/worker-isolation/persistence/feedback/rubrics/
  converter/synthesis run: 1007 passed, 1 skipped; two failures were a remaining
  ITSO test's obsolete settings patch (fixed) and the stale migration-head test.
- Final evaluation/scripts/DPO/public API/package run: 585 passed, 1 skipped,
  one preexisting faculty allowlist failure. The attempted deselection did not
  match pytest's normalized node ID; the test ran and exposed the same baseline
  failure, not a new regression.
- Settled package/public API/transport adapter/generation regression run:
  **182 passed**. Includes all four actual specialists, repair, nested request
  immutability, snapshot UUID binding, scope reset/thread isolation, installed
  import boundary, and the frozen canonical snapshot hash
  `52fa13d885eb0aa8d2779264067c223831e68444aa588f100e492bbb48c09de3`.
- Scoped Ruff check and format check: passed (165 Python files).
- Offline native sdist/wheel build, clean wheel installation and isolated actual
  four-pipeline imports: passed with UV 0.11.25. Offline lock check/frozen sync
  and a fresh copied Docker-layout dependency installation: passed. No Docker
  image build or live provider/service test was attempted.
- Offline ITSO benchmark CLI: stable precheck hashes and zero agent drift.
- Independent verification: Ruff across 165 Python files, isolated wheel checks
  for all four specialists, and frozen lock checks passed. The original staged
  plan was not modified. Runtime Docker, browser, and real-model verification
  remain unverified.

## Independently established preexisting failures

A temporary `git archive a6ec5a59 apps/server` checkout, using the existing venv,
reproduced both failures without the extraction:

1. `test_faculty_results_returns_allowlisted_presentation_and_no_private_keys`:
   stale allowlist reports `advisory_outputs` as private.
2. `test_single_alembic_head_and_down_revision`: expects `20260929_0001`, actual
   head is `20261010_0002`.

Neither unrelated test nor API/migrations was changed to hide these failures.
The final affected crosscuts verification completed with the results recorded
above. These two baseline failures are not new regressions.

## Extraction-boundary cleanup

Backend integration now lives directly in `modules/evaluations/harness/`
(context, dispatch, result, supervisor, evidence, transport and envelope map),
without an extra supervision package or an agents compatibility facade.
Its public service exports `Supervisor`, `get_envelope_criteria_map` and
`get_criterion_envelope_key`; synthesis imports the pure envelope helper directly
from `equiped_harness`. Rubrics retain backend ORM/lifecycle exports only;
actual pure consumers import harness contracts/snapshots directly. The unused
backend strategy-calculator reexport package was removed after tracing imports.
Integration-owned tests moved to `tests/evaluations/harness`; specialist backend
regressions remain in place. Durable FIFO/CAS execution documentation is corrected;
admission, recovery, heartbeats, persistence and synthesis behavior are unchanged.

Cleanup verification: 273 targeted backend tests passed, followed by 121 tests
covering library boundary/evaluation smoke, remaining migrated callers and public
ownership assertions. Scoped Ruff import sorting, lint and format checks and
`git diff --check` passed. Guarded in-process HTTP smoke returned health/OpenAPI
200 and unauthenticated evaluations 401 without lifespan, network or live services.
Exact commands/exits: `/tmp/equiped-harness-boundary-cleanup.log`.
The staged original plan/index checksum was preserved. Historical plan, ADR and
migration references remain unchanged. Independent final verification is separate.
