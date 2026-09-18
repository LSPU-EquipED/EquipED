# Synthetic DPO dataset generator

**DEV/TEST/LOCAL ONLY.** Generates fake SME evaluations, agent generations, and
reviewer EDIT corrections so the DPO training pipeline (Colab handoff,
`export_dpo_package()`) can be exercised end-to-end before real faculty
correction volume exists.

Script: `seed_synthetic_dpo_pairs.py`

## Safety Guarantees

1. **Environment Restriction**:
   - Strictly permitted environments: `development`, `test`, `local`.
   - Always rejected: `production`, `prod`, or any unspecified/non-allowlisted environment.
2. **Database Target Guard & Fingerprint Allowlist**:
   - Refuses unsafe database targets based on actual configured `DATABASE_URL`, not `APP_ENV` alone.
   - Local/test targets (`sqlite`, `localhost`, `127.0.0.1`, loopback IPs, `.local`/`.test` hosts) are allowed automatically.
   - Non-local database targets (such as shared dev Neon) require explicit opt-in: the SHA256 fingerprint of the normalized target (`<host>:<port><path>`) must be present in `SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS` without embedding credentials or secrets.
   - Connection-routing query overrides are always refused before local classification or fingerprint confirmation. This includes URL-encoded, repeated, or case-variant `host`, `hostaddr`, `port`, `dbname`/`database`, `service`, `servicefile`, and multi-host routing keys. Benign Neon options such as `sslmode=require` remain allowed.
3. **Dual Acknowledgement**:
   - Requires explicit action confirmation: `--confirm SEED` for generation, or `--confirm CLEANUP` for deletion.
   - Requires explicit database target acknowledgement: `--confirm-target LOCAL` for local databases, or `--confirm-target <target_sha256_fingerprint>` for remote dev targets.
   - Rejects `--count <= 0` immediately before any user lookup or session mutation.
4. **Authentic Cryptographic Hashes**:
   - `prompt_sha256` and `response_sha256` are calculated directly from the exact UTF-8 stored prompt and response strings, strictly adhering to real generation invariants.
5. **Run-ID Tagging & Exact Run Cleanup**:
   - Every seed invocation is assigned a UUID `run-id` (or accepts a provided `--run-id`).
   - `Document.title` is tagged with `[SYNTHETIC-DPO-TEST] [run:<run_id>] ...`.
   - `PreferenceLog.notes` is tagged with `synthetic-dpo-seed:<run_id>`.
6. **Ownership Conjunction & Ambiguity Protection**:
   - Cleanup performs strict conjunction matching across:
     - Exact `run-id` matching in document titles and preference log notes
     - Dedicated synthetic user ownership (`synthetic-dpo-seed@local.test`)
     - SME agent ownership (`target_agent == "sme"`, `agent_name == "sme"`, `agent_id == "sme"`)
     - Model name verification (`synthetic-dpo-seed`)
   - Any ambiguity, mismatched count between documents and evaluation jobs, or orphaned/cross-linked rows causes an immediate fail-closed abort with a transaction rollback.
7. **Immutable Snapshot Limitations Preserved**:
   - Evaluated snapshot rows (`evaluation_form_snapshots`) remain immutable per database triggers (`trg_evaluation_form_snapshots_immutable`). Cleanup targets `PreferenceLog`, `AgentGeneration`, and `AgentResult`, rendering the synthetic evaluation inert for training exports while leaving audit trails intact.

## Where it runs

This connects to whatever `DATABASE_URL` your environment resolves to —
per this project's docs, that's normally the **shared Neon dev database**,
not something private to you. Every row it writes there is visible to
teammates using that same database until cleaned up.

To target a remote dev database like Neon:
1. Obtain the SHA-256 target fingerprint (the seeder outputs this if run without an allowlist).
2. Set `SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS=<fingerprint>` in your environment.
3. Pass `--confirm-target <fingerprint>` at CLI invocation.

For local databases (SQLite or local PostgreSQL), pass `--confirm-target LOCAL`.

## Usage

```bash
cd apps

# Generate 25 synthetic corrections against a local DB:
uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs \
  --count 25 --confirm SEED --confirm-target LOCAL --verify-export

# Or generate against an allowlisted shared Neon dev DB:
export SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS="<fingerprint>"
uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs \
  --count 25 --confirm SEED --confirm-target "<fingerprint>" --verify-export

# Or provide a custom run-id:
uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs \
  --count 25 --run-id 00000000-0000-0000-0000-000000000001 \
  --confirm SEED --confirm-target LOCAL

# Export them for real, exactly like a real DPO training job would:
uv run --project server python -m server.scripts.export_dpo_package \
  --agent sme --output /tmp/synthetic_dpo_package

# Clean up an exact run when you're done:
uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs \
  --cleanup --run-id <UUID> --confirm CLEANUP --confirm-target LOCAL
```

## Identifying synthetic records

Every row this script creates is tagged:

- `Document.title` is prefixed `"[SYNTHETIC-DPO-TEST] [run:<run-id>] "`
- `PreferenceLog.notes` is set to `"synthetic-dpo-seed:<run-id>"`
- The reviewer attributed to every correction is a dedicated synthetic user,
  `synthetic-dpo-seed@local.test` (created once, reused on later runs)
- Generations and results are associated with agent `sme` and model `synthetic-dpo-seed`

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
the `[SYNTHETIC-DPO-TEST]` title prefix and run-id, exactly as a real evaluation's
snapshot would remain forever. If those need to disappear from admin-facing
document/evaluation lists too, that's a DBA-level decision outside this
script's scope, not something to script around the immutability trigger for.

## Why SME

All 10 SME criteria are `llm_rubric_guidance` (score-shaped) in this
codebase, and `criterion_measurements.v1` is a fully supported DPO
contract. `tests/training_data/test_exporter.py::test_export_sme_score_edit`
is the existing, already-passing reference this script's approach is based
on.
