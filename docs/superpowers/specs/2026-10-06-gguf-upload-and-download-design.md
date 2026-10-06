# GGUF upload from the notebook and download from the admin page - design

Date: 2026-10-06. Status: draft for review.

## Why

After training, the Colab notebook converts the adapter into a GGUF file, which
is the file the model server actually loads. Today that file is only downloaded
to the trainer's computer from Colab. Someone has to rename it, carry it to the
host owner, and the Colab copy is gone when the session ends. The app only keeps
the adapter zip.

Goal: the notebook sends the GGUF to the app by itself, the app stores it, and
an admin (or the host owner, through a time-limited link) can download the
correctly named `<agent>-v<version>.gguf` from the Training Data page. Nobody
renames or carries files.

## Decisions already agreed with the user

- Backend and model server run on different machines, so the host downloads from
  the app.
- The file lives in **object storage** through the app's existing storage layer
  (`core/storage.py`; Cloudflare R2 when configured, local disk otherwise). It is
  **not** stored in the database; the database only holds a small record.
- A manual **Upload GGUF** button in the admin page covers adapters trained
  before this feature (v7, v8, GAD v2).
- Scale: one backend, one model server, about 5-10 adapters. Several backends or
  several model servers are out of scope.

## Scope

In: notebook upload step; GGUF upload endpoint with validation; storage and
metadata; download link; admin UI (status, Download, Copy link, Upload, Remove);
a retention action. Out: the host launcher script, automatic pull-sync on the
host, moving the existing adapter zip into object storage, automatic retention,
publishing changes.

## 1. Data

Four nullable columns on `trained_adapters` (one additive migration, existing rows
stay empty):

| Column | Purpose |
|---|---|
| `gguf_storage_key` (String 512) | key in the storage layer, built by the server |
| `gguf_sha256` (String 64) | checksum of the stored file |
| `gguf_size_bytes` (Integer) | size |
| `gguf_uploaded_at` (DateTime tz) | when it arrived |

Plus the permission for the notebook upload, stored on the same row so no new
table is needed: `gguf_upload_token_hash` (String 64), `gguf_upload_expires_at`
(DateTime tz). The token is set when the adapter zip is uploaded and cleared after
a successful GGUF upload.

Storage key: `adapters/<agent_id>/<adapter_id>/<agent_id>-v<version>.gguf`, always
built from database values, never from user input.

## 2. Notebook

The zip upload response (`TrainedAdapterResponse`, used only by that call) gains
one field, `gguf_upload_url`: the full URL (built from `PUBLIC_BASE_URL`, same as
the job links) with a fresh single-purpose token that expires in 24 hours. The user
pastes nothing new.

The existing GGUF conversion cells keep their order. A new
`conversion_step("upload the GGUF to EquipED")` block is added **inside an existing
cell** (before the "download the files" step), because existing tests address
cells by index. It streams the verified `<agent>-v<version>.gguf` to
`gguf_upload_url` with a long timeout and up to 3 retries, prints the result, and
**never fails the run**: if the upload fails, the existing local download still
happens and the message says how to use the Upload button later. If the upload
response had no `gguf_upload_url` (older backend), the step is skipped with a note.

## 3. Backend

New module code in `modules/training_data` (service plus router; business rules in
the module, not `core/`).

**Notebook upload** - `POST /admin/training-data/adapters/{adapter_id}/gguf?token=...`
(multipart file, no login; authorised by the token like the zip upload):
- Token: hash match, not expired, row has no GGUF yet. Any failure returns 404 with
  no detail (same behavior as the existing upload tokens).
- Validate while streaming: extension `.gguf`; size at most 500 MB (reuse
  `MAX_ADAPTER_UPLOAD_BYTES`); first 4 bytes are `GGUF`; the claimed filename must
  equal `<agent>-v<version>.gguf` or is ignored (the server names it itself).
- Compute SHA-256, store through the storage layer, then in one transaction set the
  four metadata columns and clear the token. The token is consumed only on success,
  so a failed attempt can be retried until it expires.
- Returns the adapter record.

**Manual upload** - `POST /admin/training-data/{agent_id}/adapters/{adapter_id}/gguf`
(admin login required): the same validation and storage path, without a token.
Replaces an existing file only if the admin passes `replace=true`.

**Download link** - `POST /admin/training-data/{agent_id}/adapters/{adapter_id}/gguf/download-link`
(admin login required): returns `{url, filename, sha256, size_bytes, expires_at}`.
With R2 the URL is a presigned link (24 hours by default, adjustable by the admin
up to 7 days). With local storage the URL points to an admin-only streaming
endpoint (`GET .../gguf/file`), so the host needs a login in that setup.

**Remove file** - `DELETE /admin/training-data/{agent_id}/adapters/{adapter_id}/gguf`
(admin login required): deletes the stored file and clears the four columns. Refused
for the currently published adapter.

**List** - `TrainedAdapterListItem` gains `gguf`: `null` or
`{size_bytes, sha256, uploaded_at}`.

## 4. Admin UI (Training Data adapter row, Details)

- A "GGUF file" line: "Not uploaded", or size, SHA-256 (copyable) and upload time.
- When present: **Download**, **Copy download link** (with the expiry shown), and
  **Remove file**. When absent: **Upload GGUF** (file picker, progress, errors).
- The existing "Load on the model server" hint stays and gains one line pointing to
  the download. The file name shown is always `<agent>-v<version>.gguf`.
- Remove is disabled for the published adapter.

## 5. Safety

- Upload tokens: random, stored hashed, single purpose, 24-hour expiry, consumed only
  on success.
- The server builds every storage key; user input never becomes a path.
- GGUF magic-byte check and size limit before anything is stored; files that fail are
  not kept.
- Download links grant access to anyone holding them until they expire, so they are
  generated on request, show their expiry, and default to 24 hours.
- No file content is logged. A missing or failed GGUF never blocks training,
  publishing or benchmarks.

## 6. Testing

- Backend: valid upload stores the file and metadata; wrong magic bytes, wrong
  extension, oversize, expired, reused and bad tokens are refused with nothing stored;
  a failed attempt can be retried; manual upload and `replace`; download-link for R2
  (fake storage) and local fallback; delete refuses the published adapter; list shows
  `gguf`; migration is additive.
- Notebook: the upload step posts the file, retries on failure, never raises, and is
  skipped without `gguf_upload_url`; existing cell-index tests still pass.
- Frontend: states "Not uploaded" and "Uploaded", Download, Copy link with expiry,
  Upload with error display, Remove disabled when published.

## 7. Rollout

1. Merge code. 2. Apply the additive migration to the shared database (after the
user confirms). 3. Upload GGUFs for v7 and v8 with the manual button. 4. New training
runs upload their GGUF automatically.

## Open choices for review

- Presigned link default lifetime (proposed 24 hours, up to 7 days).
- Whether "Remove file" should also be offered automatically (retention rule); this
  spec keeps retention manual.
- Maximum file size (proposed 500 MB, same as the zip).

## Adjustment found while planning (2026-10-06)

The existing document storage methods cannot hold these files as the spec first
assumed: they force every key under `documents/` and flatten directories, and their
presigned links cannot set a download file name (the host needs the exact name
`<agent>-v<version>.gguf`). The plan therefore adds a small **additive artifact API**
to `core/storage.py` (verbatim keys, presigned links with a download file name) and
leaves the document methods untouched. Nothing else in the design changes.
