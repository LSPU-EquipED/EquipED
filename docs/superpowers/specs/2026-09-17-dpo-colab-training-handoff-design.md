# DPO Colab Training Handoff — Design

Date: 2026-09-17
Status: approved, pending implementation plan

## Problem

All four agents (SME, Coordinator, GAD, ITSO) can now produce DPO pairs via
`export_dpo_package()` (`apps/server/modules/training_data/exporter.py`), but
the only way to actually get a package is a CLI script
(`apps/server/scripts/export_dpo_package.py`) run by someone with direct
server/DB access. There is no way for a CID admin to trigger an export from
the admin UI, and no path for a resulting trained LoRA adapter to come back
into the system as a tracked artifact.

Training itself will happen in Google Colab (the user's stated plan), not on
EquipED's own infrastructure. Colab has no public API for a third-party
server to remotely trigger a notebook run on the free/consumer tier — only
paid Vertex AI Workbench/Training exposes that, which is a different product.
So "integrate training into the system" cannot mean "the backend drives
Colab" — it means the backend should be the fastest, safest way to get a
clean dataset **into** a Colab notebook and to receive the trained adapter
**back out**, with the admin doing one manual "Run all" click in between.

## Goals

1. Admin UI button to export a DPO dataset for one agent, producing a URL a
   Colab notebook cell can fetch directly (no manual download/upload of the
   dataset).
2. A Colab notebook template with fetch and push-back cells pre-written.
3. An upload endpoint + storage so a trained adapter, once produced, becomes
   a tracked artifact (agent, version, uploader, timestamp, hash) visible in
   the admin UI.

## Non-goals (explicit)

- Writing the actual LoRA/PEFT training loop. Base model choice,
  hyperparameters, and HF/PEFT setup are a data-science decision left to the
  user, filled into the notebook template's middle section.
- An "active adapter" flag or wiring a trained adapter into live inference.
  Storage only, for now.
- Automating the Colab run itself. The admin still manually opens the
  notebook and clicks "Run all"; only the fetch/push legs are automated.
- Any change to `export_dpo_package()`'s DPO-shaping logic (capability
  registry, projectors, snapshot verification). This design only adds a
  transport layer around the existing, already-tested export function.

## Architecture

Two new backend pieces, one new frontend surface, one static template file.
The export-token and upload-token concepts from the first draft are merged
into a single **training job**: one admin action creates a job, freezes a
dataset snapshot against it, and issues both a download credential and an
upload credential scoped to that one job — so every stored adapter traces
back to the exact dataset that produced it, and retrying a failed run means
starting a new job rather than reusing or revoking a credential.

### 1. Start-job endpoint (admin-authenticated)

`POST /admin/training-data/{agent_id}/jobs`

- Requires normal admin session auth.
- Creates a `dpo_training_jobs` row: `job_id`, `agent_id`, `created_by`
  (user id), `created_at`, `status` (`pending` → `downloaded` → `completed`,
  or `expired`).
- **Freezes the dataset immediately**: calls `export_dpo_package()` at job
  creation time and persists its output (pairs/provenance/manifest content,
  or a reference to where it's stored) against the job, so the download leg
  always returns exactly what was frozen here — even if new corrections land
  later, or the notebook re-fetches it.
- Generates two opaque tokens, both scoped to this `job_id`, storing only
  their hashes (same discipline as any bearer credential):
  - **Download token** — single-use, short expiry (~24h).
  - **Upload token** — single-use, longer expiry (job-lifetime, e.g. 7 days,
    to survive a long or retried training run).
- Returns `{ job_id, download_url, upload_url, download_expires_at, upload_expires_at }`.

### 2. Token-authenticated download endpoint (no session required)

`GET /admin/training-data/jobs/{job_id}/download?token=<raw_token>`

- Called by the Colab notebook's first cell (`requests.get(url)`), which has
  no logged-in session.
- Looks up the token by hash; validates: exists, not expired, not already
  used, matches `job_id`. Any failure → `404` (not `403`, to avoid
  confirming whether a guessed token/job exists).
- On success: streams back the frozen zip (`pairs.jsonl` + `provenance.jsonl`
  + `manifest.json`) for this job, marks the download token used, job status
  → `downloaded`.
- Reuses existing snapshot-verification and capability-skip logic in
  `export_dpo_package()` unchanged (already applied at job-creation time).

### 3. Token-authenticated adapter upload endpoint (no session required)

`POST /admin/training-data/jobs/{job_id}/adapter?token=<raw_token>`

- Called by the Colab notebook's last cell after training completes.
- Looks up the upload token by hash; validates: exists, not expired, not
  already used, matches `job_id`. Any failure → `404`.
- Accepts a zip containing the adapter files (`.safetensors`/`.bin` +
  `adapter_config.json` allowlist), validates size cap and extensions,
  stores under a new `adapters/<agent_id>/<job_id>/` runtime directory
  (sibling to `uploads/`, same on-disk convention).
- Writes a `trained_adapters` row: `adapter_id`, `agent_id`, `job_id` (FK,
  giving full provenance back to the exact dataset snapshot), `version`
  (auto-incrementing per agent), `file_path`, `file_sha256`, `size_bytes`,
  `created_at`.
- Marks the upload token used, job status → `completed`.

### 4. Admin UI

Extends the existing `apps/admin/src/features/preference-log` feature (or a
new sibling feature if the existing one is scoped too narrowly to
preference-log review specifically — decide during planning) with:

- Per-agent "Start Training Job" action → calls the start-job endpoint,
  displays `download_url` and `upload_url` with copy-to-clipboard and their
  respective expiry countdowns.
- A jobs list/table per agent: `job_id`, status, created date, and — once
  `completed` — a link to the resulting adapter. No separate token
  management UI (no revoke-list): a job either completes or its tokens
  expire; retrying means starting a new job.
- Per-agent adapter list table (derived from `trained_adapters`, joined to
  its `job_id` for provenance): version, uploaded date, file size, hash
  (truncated, expandable), source job.

### 5. Colab notebook template

New file, e.g. `docs/colab/dpo_training_template.ipynb`, committed to the
repo (not generated dynamically). Contains:

- Cell 1: fetch — `requests.get(DOWNLOAD_URL)`, unzip, load `pairs.jsonl`.
- Cells 2..N: `# TODO: your LoRA/PEFT training loop here` — explicitly a
  placeholder, not implemented by this design.
- Last cell: push-back — zips the trained adapter output directory,
  `requests.post(UPLOAD_URL, headers={"Authorization": f"Bearer {UPLOAD_TOKEN}"}, files=...)`.
- A markdown cell at the top explaining where `DOWNLOAD_URL` and
  `UPLOAD_TOKEN` come from (pasted from the admin UI).

## Data flow

```
Admin UI (logged in)
  → POST /admin/training-data/{agent}/jobs
  → dataset frozen via export_dpo_package() and persisted against job_id
  → { job_id, download_url, upload_url, download_expires_at, upload_expires_at }
  → admin pastes download_url into notebook cell 1, upload_url into the last cell

Colab notebook (anonymous runtime, no login)
  → GET download_url             → frozen zip streamed back, download token
                                    marked used, job status → downloaded
  → [training happens — user's own code]
  → POST upload_url (multipart file) → adapter stored, trained_adapters row
                                        written with job_id, upload token
                                        marked used, job status → completed

Admin UI
  → GET /admin/training-data/{agent}/jobs → job list with status
  → GET /admin/training-data/{agent}/adapters → adapter list, each linked
    back to its source job_id
```

## Error handling / security

- Both tokens: single-use, hashed at rest, scoped to one `job_id` (and
  transitively one `agent_id`). Any validation failure (expired, used,
  wrong job, malformed) → `404`, not `403`, to avoid confirming whether a
  guessed token/job exists.
- Upload token grants only the adapter-upload capability for its one job —
  cannot read data, cannot act as the admin, cannot be reused for a
  different job or a retry (a failed run starts a fresh job instead).
- Adapter upload: file-size cap (exact limit TBD during planning — should
  comfortably fit a LoRA adapter, which is typically tens to low hundreds of
  MB, not full model weights), extension allowlist, content-hash recorded.
- Job rows for expired/abandoned jobs are harmless to leave around (no
  credential remains valid) — no active cleanup required for correctness,
  though a retention/cleanup job could be added later if the table grows.
- No change to how `export_dpo_package()` itself decides what's eligible for
  export (snapshot verification, capability skip reasons) — this design is
  purely a transport/auth layer around it, invoked once at job creation.

## Testing

- Backend: job creation (dataset frozen correctly, both tokens minted);
  download endpoint happy path + each failure case (expired/used/wrong-job
  token); upload endpoint happy path + each failure case, plus
  oversized/bad-extension rejection; job list and adapter list endpoints,
  including that an adapter row correctly links back to its `job_id`.
- Frontend: start-job action renders both URLs + expiry countdowns; job list
  reflects status transitions; adapter list renders stored rows with source
  job.
- No automated end-to-end Colab test — the notebook template is validated by
  hand once, not in CI (external dependency, out of reach of the test
  suite).

## Open questions for the implementation plan

- Whether to extend `apps/admin/src/features/preference-log` or add a new
  sibling admin feature — a planning-time call once the plan author looks at
  how large `preference-log`'s current scope already is.
- Exact file-size cap and expiry durations (defaults proposed above, not
  load-bearing decisions).
- Whether the download endpoint should stream from a temp directory or build
  the zip fully in memory — an implementation detail, not a design decision.
