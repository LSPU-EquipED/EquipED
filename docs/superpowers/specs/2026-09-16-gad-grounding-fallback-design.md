# GAD Evidence-Grounding Fallback — Design

## Problem

`apps/server/modules/agents/gad/registry.py`'s `llm_rubric_guidance` branch
(`score_from_combined`, added by the earlier GAD v2 conversion) grounds the
model's cited evidence by calling `ground_instances()` with a single-item
list containing only the model's claimed `chunk_id`. `ground_instances`
(`grounding.py`) requires an **exact substring match** against that one
chunk's text — no fallback. If the match fails (wrong chunk_id cited, or a
non-verbatim excerpt), `registry.py:154-159` raises `AgentExecutionError`,
which propagates up and fails the **entire** GAD evaluation (GAD scores all
5 criteria in one combined LLM call, so one criterion's grounding failure
takes down all five).

Confirmed in live testing (2026-09-16): after activating the v2 rubric in
the shared dev DB, GAD failed consistently — reference `cd4f661c9867681b`
decoded to `"GAD section 'gad-02' evidence is not grounded in any provided
document chunk"`.

## Root cause

This hard-fail design was copied from SME's validation pattern when GAD's
qualitative scoring was first built (on the abandoned branch this session
already found and worked from). SME has no chunking — it reads the whole
document as one continuous text — so a bad quote there just fails outright
with nothing more forgiving to fall back to, and that's fine. GAD and ITSO
both work over **chunked** documents, where the model citing the wrong
chunk_id for otherwise-correct text is a normal, expected failure mode.
ITSO already handles this (`itso/response.py::_normalize_evidence`): try
the cited chunk first, then search every other packed chunk before giving
up, and if it still can't ground the evidence, don't fail — mark that
criterion `advisory_only` and keep going. GAD's conversion copied the wrong
sibling.

Per project memory (`gad-dpo-conversion-todo`), this exact brittleness was
already suspected as the cause of a live failure during the abandoned
branch's own debugging (against `gemma-3-4b-it`), flagged then, and never
fixed because that branch was abandoned over a separate bug. What we hit
today is very likely the same latent issue.

## Design

Two changes, both scoped to `apps/server/modules/agents/gad/`. No changes
to `envelope.py`, `prompt.py`, `agent.py`, `manifests.py`, or any other
agent's code.

### 1. `grounding.py` — add a fallback-search function

`ground_instances()` stays exactly as-is (still used, unchanged, by the
`count_band` branch — v1's live behavior must not change). Add a new
function used only by the `llm_rubric_guidance` path:

```python
def ground_single_excerpt(
    excerpt: str,
    claimed_chunk_id: str,
    packed_chunks: list[dict[str, Any]],
) -> tuple[str, str] | None:
    """Ground one excerpt against packed chunks, trying the claimed chunk
    first, then searching every other chunk. Returns (excerpt, actual_chunk_id)
    on success, None if the excerpt is not found anywhere. Mirrors ITSO's
    itso/response.py::_normalize_evidence fallback search."""
```

Logic: build the same `chunk_map` as `ground_instances`. Try
`claimed_chunk_id` first (exact substring match, same rule as today). If
that fails, iterate every other chunk and check the same way; return the
first chunk where it matches. If nothing matches anywhere, return `None`.

### 2. `registry.py` — degrade instead of raise

In the `LlmRubricGuidanceConfig` branch, replace the raise-on-failure with:

- Call `ground_single_excerpt` instead of `ground_instances`.
- On success: unchanged behavior (build `CriterionScore` with the grounded
  excerpt/chunk_id, same as today) — except the chunk_id recorded is
  whichever chunk it was actually found in (not necessarily the model's
  claim).
- On failure (returns `None`): still build a `CriterionScore` using the
  model's own `score` (keep it — the model's judgment isn't discarded,
  it's just unverified), with `evidence=()` and `chunk_ids=()`, and append
  an `UngroundedCriterionAdvisory(criterion_id=crit.criterion_code, reason="model evidence could not be grounded in any provided document chunk")`
  to a list collected across the loop.
- `score_from_combined`'s return signature grows one item: the collected
  advisory list (empty list when nothing was ungrounded).

### 3. `pipeline.py` — thread advisories into the result

`_run_gad_scoring` receives the new 5th return value from
`score_from_combined`. If non-empty, build
`AdvisoryOutput(ungrounded_criteria=tuple(advisories))` and pass it as
`AgentEvaluationResult(..., advisory_outputs=...)` — the same field ITSO
already populates on the shared base contract, so no synthesis/monitoring-
matrix/frontend changes are needed for this to surface. (Worth a quick
visual check in the admin UI during testing that GAD's advisory flag
renders the same way ITSO's does, since this is the first time GAD uses
it — not expected to need code changes, but unverified until tested.)

## What does NOT change

- `count_band`/`ratio_band` branches and `ground_instances` — v1 behavior
  identical to today.
- `envelope.py`'s schema/validation (Task 2, already shipped) — unaffected,
  this only changes what happens after parsing succeeds.
- The `AgentExecutionError` still exists as a path — it's just no longer
  reachable via ungrounded evidence specifically. (Malformed JSON, unknown
  sections, etc. from `envelope.py` still fail the evaluation as before —
  only the specific "evidence didn't ground" case degrades instead of
  raising.)

## Testing

- `grounding.py`: new tests for `ground_single_excerpt` — found in claimed
  chunk (existing behavior), found in a *different* chunk than claimed
  (new fallback path), found nowhere (returns `None`).
- `registry.py`: update the existing Task 3 test
  `test_score_from_combined_rejects_ungrounded_evidence` — it currently
  asserts a raise; it now needs to assert an advisory-flagged
  `CriterionScore` with the model's score preserved and empty evidence,
  plus the new 5th return value containing the matching
  `UngroundedCriterionAdvisory`. Same treatment for
  `test_score_from_combined_rejects_unknown_chunk_id` — that scenario
  (wrong chunk_id, real text elsewhere) should now actually **succeed** via
  the fallback search rather than reject, since the point of this fix is
  exactly that case.
- `pipeline.py`/end-to-end: one new test driving `GAD.run()` with a mock
  LLM response containing an ungrounded citation, asserting the evaluation
  completes (`success=True`), the affected criterion still has a score, and
  `result.advisory_outputs` contains the expected
  `UngroundedCriterionAdvisory`.

## Out of scope

- Any change to ITSO or SME's own grounding code (same landmine exists in
  their unrelated `adapter_version` hardcoding per project memory, but
  that's separate follow-up work, not this fix).
- Wiring GAD into `agent_generations`/DPO training data (checklist section
  2, still a separate future plan).
- Re-activating v2 in the DB — it's already active; this fix ships onto
  the same activated rubric, no re-conversion or re-activation needed.
