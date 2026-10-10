# Semi-automatic training: ready-to-run notebook, live status, host delivery

Date: 2026-10-10. Status: draft for review. Classification: architectural (new endpoints, a
new table, notebook generation, a host-side script).

## Why

Training a fine-tuned model today needs several manual hand-offs:

1. Start a run in the admin page, copy two one-time links, paste them into cells of a
   17-cell Colab notebook.
2. No visibility while Colab trains. The admin page only knows Waiting / In progress /
   Finished, and a disconnected Colab looks the same as a busy one.
3. After the GGUF is uploaded, someone copies it into the model server's adapters folder,
   edits `start-gemma.bat` by hand, and restarts the server.

Goal: after a one-time setup, the only human actions are **Run all in Colab** (free Colab has
no API, so this stays manual) and **one server restart** by the host owner. Everything else is
done by the app, the notebook and a small host script.

## Decisions made in brainstorming (user, 2026-10-10)

| Question | Decision |
|---|---|
| Scope | All three steps, built in this order: notebook, status, host delivery |
| Notebook delivery | Admin page offers **Download notebook**: the server fills the links into the notebook and sends a private `.ipynb`. No shared/public notebook |
| Status detail | Stages **plus a step counter plus "last heard from"** time |
| Model server location | A **separate computer** run by someone else, so a pull script on the host |
| Restart | The script **never restarts** the model server. The host owner restarts when idle |
| Notebook base | The **main template**, after merging the improvements from `sme_retrain_gentle.ipynb`. No per-agent notebooks |
| Notebook numbers | Computed from the data by the approved plan in `2026-10-07-notebook-training-plan-design.md` |
| Models loaded on the host | **Latest 2 versions per agent plus the published one** |
| Host notification | Log file **and** a desktop notification |

## Delivery slices

Each slice is separately shippable and testable. Build in this order.

- **A. Notebook merge** (notebook content only).
- **B. Download notebook** (backend + admin button).
- **C. Live status** (backend + notebook + admin table).
- **D. Host sync** (backend + new script + admin panel).

B depends on A only for which notebook it serves, so B can ship before A against the current
template. C and D are independent of each other.

## Slice A. Notebook merge

Merge into `docs/colab/dpo_training_template.ipynb` the parts of `sme_retrain_gentle.ipynb`
that are not agent-specific, and implement the approved 2026-10-07 plan (measured lengths,
computed dose) in place of gentle's hand-typed numbers.

From gentle, bring over (all four agents are served by the same Gemma model through
`/chat/completions`, so none of these are SME-only):

- **Chat-format rows** (`_chat_row`) and the check that stops the run if the training prompt
  does not start with Gemma's `<start_of_turn>user`. This addresses the suspected
  raw-text-training vs chat-template-serving mismatch.
- **The out-of-memory rescue cell.** This adds one cell (index shift); the cell-index tests
  are updated deliberately, not by accident.
- **`StopIfChosenCollapses`** (stop when the chosen reward falls below -5). The -5 limit was
  calibrated from SME v7 and v8 only; it only stops training early, so it is low risk for
  other agents, but is recorded as unproven for them in the thresholds file.

Do **not** bring over gentle's hand-typed `MAX_SEQ_LENGTH 5888`, `max_prompt_length 4352`,
`num_train_epochs 3`, `gradient_accumulation_steps 4`. These come from the measured plan.
`LEARNING_RATE` stays a fixed named constant (`2e-5`, as approved on 2026-10-07); it is not
computed from the data. The "Gentler SME retrain copy" note in cell 0 is not carried over.

The experiment copies (`sme_retrain_gentle`, `sme_retrain_stronger`,
`latest_dpo_training_template`) stay untouched and remain outside the product path.

## Slice B. Download notebook

### Behaviour

After "Start a training run", the Colab panel shows **Download notebook** beside the existing
links (which stay as a fallback). The file is named `equiped-<agent>-run-<first 8 of job id>.ipynb`.
Open it in Colab, pick the T4, Run all.

### Server

- New module `training_data/notebook.py`, function `build_job_notebook(download_url,
  upload_url, status_url=None) -> str`.
  - Loads `docs/colab/dpo_training_template.ipynb` (repo-root anchored like
    `ADAPTER_ROOT`) as JSON, never as text, and replaces the placeholder assignments in cell 1.
    The existing `"PASTE_" in url` guard in cell 1 therefore passes for a filled notebook.
  - Fails loudly (an error, not a silently unfilled notebook) if a placeholder line is not
    found exactly once.
  - Returns the notebook as a JSON string. Nothing is written to disk and nothing contains a
    token after the response is sent.
- `POST /admin/training-data/{agent_id}/jobs` response gains two optional fields:
  `notebook` (the filled `.ipynb` text, about 65 KB) and `notebook_filename`. Tokens are only
  stored as hashes, so the notebook can only be built at creation time. This matches the
  existing rule that the links cannot be shown again after a reload.
- If the template cannot be loaded or filled, job creation still succeeds with the links and
  `notebook` is null (the panel hides the button). A notebook problem must not block training.

### Admin

`TrainingJobCredentials` gains a Download notebook button that turns the `notebook` string
into a Blob download. Held in the same React state as the links, so it disappears when the
links do.

## Slice C. Live status

### Behaviour

Each row in **Training runs** shows a plain stage, such as "Training · step 14 of 30", and
"updated 2 min ago". The stages are Waiting to start, Starting, Training, Sending model,
Converting file, Sending file, Finished, Failed. If a run is mid-way and nothing has been
heard for 15 minutes, the row says "No update for 15 minutes, Colab may have disconnected".
The page polls every 10 seconds, only while at least one run is in progress and the tab is
visible.

### Data (additive migration on `dpo_training_jobs`)

| Column | Type | Notes |
|---|---|---|
| `status_token_hash` | string(64), nullable | Same hashing as the other job tokens |
| `status_expires_at` | timestamptz, nullable | Same lifetime as the upload token (7 days) |
| `run_stage` | string(24), nullable | One of the stage keys below |
| `run_step` / `run_total` | integer, nullable | Training counter |
| `run_message` | text, nullable | Short failure reason, truncated to 500 chars |
| `run_reported_at` | timestamptz, nullable | Last report from the notebook or the server |

The existing `status` column (pending / downloaded / completed) and its check constraint are
unchanged. `run_stage` is shown on top of it; when `run_stage` is null the UI falls back to
the old status label (this covers all existing rows).

Stage keys: `starting`, `training`, `sending_model`, `converting`, `sending_file`,
`finished`, `failed`.

### API

- `POST /admin/training-data/jobs/{job_id}/status?token=…`, body
  `{stage, step?, total?, message?}`. The token must match `status_token_hash`, be unexpired,
  and belong to this job. Unknown stage, a negative or non-integer step, or `step > total`
  returns 422. Wrong or expired token returns 404 (same as the other token endpoints, so
  existence is not leaked). The token is reusable (not single-use) and can do nothing else.
- `TrainingJobListItem` gains `run_stage`, `run_step`, `run_total`, `run_message`,
  `run_reported_at` and `seconds_since_report` (computed by the server so a skewed browser
  clock cannot cause a false "no update" warning).
- **Server-observed stages.** The server sets the stage itself on events it already sees:
  adapter upload stored becomes `sending_model` done (stage moves to `converting` pending),
  and a GGUF stored for that adapter's job becomes `finished`. These do not depend on the
  notebook's posts, so the key milestones are right even if posts are lost. A server-set
  stage never moves backwards over a later notebook-reported one.

### Notebook

- Cell 1 gains a `STATUS_URL` line (filled by Slice B) and a `report(stage, step=None,
  total=None, message=None)` helper: one `requests.post` with a 5-second timeout inside a
  broad `try/except`. A failed or missing status post must never raise or slow training. An
  empty or placeholder `STATUS_URL` (an older job, or manual paste) makes `report` do nothing.
- A `TrainerCallback.on_log` in the training cell posts `training` with the step every N
  steps, at most once per 30 seconds.
- Existing `conversion_step` blocks post `converting` / `sending_file`, and any failure posts
  `failed` with a short message.

### Admin

`TrainingJobRow` renders the stage, counter and age. A small hook polls the existing jobs list
with `refetchInterval` set to 10 s only while some run is in an active stage and the document
is visible, and false otherwise.

## Slice D. Host sync

### Behaviour

On the model server's computer, `scripts/host_sync.py` (standard library only) runs every few
minutes or by hand. For every finished GGUF the app lists, it downloads missing or changed
files into the adapters folder as `<agent>-v<n>.gguf`, checks them, refreshes
`lora-flags.txt`, and reports what is new. It never restarts the model server, never deletes,
never publishes.

### Host sync key

- New table `host_sync_keys`: `key_id` (uuid), `key_hash` (string 64), `created_by`,
  `created_at`, `revoked_at` (nullable), `last_seen_at` (nullable). At most one active key;
  creating a new one revokes the old. The key is shown once at creation and stored hashed.
- Admin endpoints (admin auth): `POST /admin/training-data/host/key` (create, returns the raw
  key once), `DELETE /admin/training-data/host/key` (revoke), `GET /admin/training-data/host`
  (state: has active key, created_at, last_seen_at; never the key).
- Host endpoints, authenticated by the key in an `X-Host-Sync-Key` header (constant-time
  compare), read-only:
  - `GET /admin/training-data/host/manifest` returns, for every adapter with a stored GGUF:
    `adapter_id`, `agent_id`, `version`, `filename`, `sha256`, `size_bytes`, `published`.
    Each call updates `last_seen_at`.
  - `GET /admin/training-data/host/gguf/{adapter_id}` streams the file, reusing
    `open_gguf_stream`.
  Wrong, revoked or missing key returns 404.

### Script behaviour

1. Read config (`host_sync.ini` next to the script): `server_url`, `key`, `adapters_dir`,
   `flags_file` (default `<adapters_dir>\lora-flags.txt`), `keep_latest = 2`, `notify = true`.
2. Fetch the manifest. For each entry, skip when `<adapters_dir>\<filename>` exists with the
   same SHA-256 (size first as a cheap precheck).
3. Otherwise download to `<filename>.part`, compute SHA-256 while streaming, compare with the
   manifest. On mismatch delete the part file, log an error, and retry next run. On match,
   atomically rename into place.
4. Rewrite `lora-flags.txt` atomically with one `--lora-scaled "<full path>:0.0"` entry per
   file to load: the latest `keep_latest` versions per agent plus the published one. Older
   files stay on disk but are not listed. If the set of entries changed, say so.
5. For each newly downloaded file, append `New model sme-v11 ready, restart the model server
   to load it` to `host_sync.log`, print it, and (if `notify`) show a Windows desktop
   notification.

Properties: idempotent (running twice changes nothing), exits non-zero on config or network
errors with a clear message, a failure on one file does not stop the others, and the script
never writes outside `adapters_dir` and its own log/config.

**Notifications.** Standard library only, so a notification uses PowerShell's
`System.Windows.Forms.NotifyIcon` balloon tip, started best-effort in a subprocess; failure
to notify is logged and ignored. A notification only appears when the script runs in a
logged-in desktop session, so the Task Scheduler task must be created as "Run only when user
is logged on". The log file is the reliable record.

### One-time host setup (documented in `docs/host-sync-setup.md`)

1. Admin creates the key in the Host sync panel.
2. Host owner places `host_sync.py` and `host_sync.ini` and fills in the settings.
3. Host owner edits `start-gemma.bat` once so it loads the flags from `lora-flags.txt`
   instead of hard-coded `--lora-scaled` entries.
4. Host owner schedules the script in Task Scheduler (every 5-10 minutes, logged-on user).

### Admin

A **Host sync** panel in the Fine-tuned models section: create or revoke the key (shown
once, copy button), and "host last checked N min ago" from `last_seen_at`. The existing
Loaded / Not loaded badge continues to show whether the server has actually loaded a model.
The "Load on the model server" hint is reworded to point at the sync script and the restart
once the panel reports an active key.

## Security

- All new tokens and the host key are stored as SHA-256 hashes, shown once, and compared in
  constant time. The status token and host key are scoped (status can only post progress;
  the host key can only list and read GGUFs).
- The downloaded notebook contains live one-time tokens. It is only returned to an
  authenticated admin in the creation response and never stored, logged or cached. The docs
  and the panel tell the admin not to share it.
- Status posts and manifest calls are validated and size-limited (message 500 chars).
- No endpoint added here can publish, delete, restart, or train.

## Failure behaviour

- Notebook cannot be built: job still created, links still shown, no download button.
- Status post lost or Colab disconnected: stale-warning after 15 minutes; server-observed
  milestones still correct.
- Host script cannot reach the app or a download fails the checksum: logged, retried on the
  next run, nothing partial is ever left under the final file name.
- Host forgets to restart: nothing breaks. The published model (or base) keeps serving and
  the admin page shows the new model as Not loaded; Publish stays disabled until it loads.

## Testing

- **A:** notebook contract tests updated for the intentional cell shift; new tests for the
  chat-row builder, the early-stop callback, and the chat-format guard; the 2026-10-07
  planner tests.
- **B:** unit tests for `build_job_notebook` (fills both/three placeholders, fails on a
  missing or duplicated placeholder, output is valid notebook JSON, no `PASTE_` left);
  endpoint test that the creation response carries `notebook`; admin test for the button.
- **C:** migration test; endpoint tests (token ok / wrong / expired / other job's token,
  stage validation, step bounds); server-observed stage tests on adapter and GGUF upload; a
  never-moves-backwards test; list item serialization incl. `seconds_since_report`; notebook
  `report` helper test with a fake `requests` (timeouts and exceptions swallowed); admin row
  and polling-hook tests.
- **D:** migration test; key create / revoke / auth tests; manifest and stream endpoint tests;
  `host_sync.py` tested against a fake HTTP server (new file downloaded, checksum mismatch
  discarded, unchanged file skipped, `keep_latest` plus published selection, flags file
  atomic write, log lines, notification failure ignored); admin panel tests.
- Admin lint, typecheck for touched files, and backend `ruff` stay clean.

## Out of scope

- Any automatic restart of the model server, or the app pushing files to the host.
- Driving Colab's UI or any Colab API (none exists on the free tier).
- Live loss / margin while training, a cancel button, push (WebSocket) updates.
- More than one host, a Windows-service wrapper, a non-Windows notification path.
- Cleaning duplicate or disagreeing pairs (a separate later spec) and the benchmark badge or
  re-issuing lost links (separate ideas from the earlier UI review).

## Open items for review

- `keep_latest = 2` and the 15-minute stale threshold are proposed defaults.
- The host notification depends on the Task Scheduler "logged on" setting above.
- The `-5` early-stop limit is unproven outside SME.
