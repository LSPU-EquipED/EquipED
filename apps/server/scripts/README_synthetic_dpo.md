# Synthetic DPO dataset generator

**DEV/TEST ONLY.** Generates fake SME evaluations, agent generations, and
reviewer EDIT corrections so the DPO training pipeline (Colab handoff,
`export_dpo_package()`) can be exercised end-to-end before real faculty
correction volume exists.

Script: `seed_synthetic_dpo_pairs.py`

## What it does

For each synthetic pair, it creates (through the same real ORM models and
functions the production evaluation pipeline uses — nothing hand-crafted or
faked at the integrity-check level):

- A `Document` and `EvaluationJob`
- A genuinely hash-signed `EvaluationFormSnapshot`, via
  `resolve_or_reuse_evaluation_snapshots()` (the real snapshot function —
  it snapshots whatever SME rubric is actually active in this database; it
  does **not** seed or modify any rubric)
- An `AgentResult` and `AgentGeneration` with a varied SME
  `criterion_measurements.v1` response, targeting a real, currently-active
  SME `llm_rubric_guidance` criterion
- A `PreferenceLog` EDIT correction with a different score/justification
  than the original, so `export_dpo_package()`'s projector produces a real,
  non-trivial `DpoPair`

It does **not** modify `export_dpo_package()`, the projectors, or the
capability registry, and it does not introduce a second DPO/pairs format —
every row it writes is read by the exporter completely unmodified, in
exactly the shape a real reviewer correction would take.

## Where it runs

This connects to whatever `DATABASE_URL` your environment resolves to —
per this project's docs, that's normally the **shared Neon dev database**,
not something private to you. Every row it writes there is visible to
teammates using that same database until cleaned up.

## Usage

```bash
cd apps

# Generate 25 synthetic corrections (default), and immediately sanity-check
# that they're exportable:
uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs \
  --count 25 --verify-export

# Export them for real, exactly like a real DPO training job would:
uv run --project server python -m server.scripts.export_dpo_package \
  --agent sme --output /tmp/synthetic_dpo_package

# Clean up when you're done:
uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs --cleanup
```

## Identifying synthetic records

Every row this script creates is tagged two ways:

- `Document.title` is prefixed `"[SYNTHETIC-DPO-TEST] "`
- `PreferenceLog.notes` is set to `"synthetic-dpo-seed"`
- The reviewer attributed to every correction is a dedicated synthetic user,
  `synthetic-dpo-seed@local.test` (created once, reused on later runs)

## About `--cleanup` — a real limitation, not a bug

This database enforces a permanent, unconditional DB-level trigger
(`trg_evaluation_form_snapshots_immutable`, added in migration
`20260829_0004`) that blocks **UPDATE or DELETE on
`evaluation_form_snapshots` for any evaluation, real or synthetic.** That's
a deliberate audit guarantee — once an evaluation's exact rubric snapshot
exists, it can never be altered or erased — and this script does not work
around it.

Because `EvaluationJob`/`Document` are referenced by that immutable
snapshot row's foreign key, they can't be deleted either.

So `--cleanup` deletes what it actually can — `PreferenceLog`,
`AgentGeneration`, `AgentResult` — which is enough to make every synthetic
evaluation permanently inert (no generation, no correction, so it can never
again produce a DPO pair or show up in an export). It leaves behind
`Document`/`EvaluationJob`/`EvaluationFormSnapshot` rows, still tagged with
the `[SYNTHETIC-DPO-TEST]` title prefix, exactly as a real evaluation's
snapshot would remain forever. If those need to disappear from admin-facing
document/evaluation lists too, that's a DBA-level decision outside this
script's scope, not something to script around the immutability trigger for.

## Why SME

All 10 SME criteria are `llm_rubric_guidance` (score-shaped) in this
codebase, and `criterion_measurements.v1` is a fully supported DPO
contract. `tests/training_data/test_exporter.py::test_export_sme_score_edit`
is the existing, already-passing reference this script's approach is based
on.
