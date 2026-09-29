# Serving a trained adapter on llama-server (GGUF LoRA)

For the person who runs the model server (Windows, llama.cpp CUDA build,
started by `start-gemma.bat`). This adds a trained adapter **on top of** the
model file you already serve. It never changes that file, and you can remove it
again at any time.

You can serve one adapter per agent (SME, GAD, ITSO, Coordinator), and several
versions of each, side by side. The app picks which one each agent uses per
request; you only decide which files the server loads.

You will receive two files from the training side per adapter version:

- `adapter-f16.gguf` (about 60 MB), the adapter converted for llama.cpp
- `adapter-f16.gguf.sha256`, its checksum

**Rename the `.gguf` when you save it** (see the naming rule in step 1). The app
identifies an adapter by its file name, so `adapter-f16.gguf` is not recognized.

The training notebook (`docs/colab/dpo_training_template.ipynb`) now produces
both of these at the end of a run, plus an optional `adapter-f16.gguf.json`
that records which llama.cpp commit made the file and which uploaded adapter it
came from. You can ignore the JSON; it is a record for whoever trains. The
standalone conversion notebook (`docs/colab/adapter_to_gguf_template.ipynb`,
for re-converting an adapter that is already stored) produces only the first
two.

**Verified 2026-09-19 on llama-server build 10430:** loading the adapter with
`--lora-scaled <file>:0.0` starts it switched **off** (scale 0.0), and a
request can switch it on. Loading it with `--lora <file>
--lora-init-without-apply` did **not** keep it off on that build: it showed
scale 1, meaning the adapter was live for every request. So step 3 recommends
`--lora-scaled`, and step 4 is a check you must not skip.

## 1. Put the file somewhere with space, with the right name

Copy the adapter next to your models on the F: drive, for example
`F:\Dev\Models\gemma\adapters\sme-v3.gguf`. Do not put it on the full C:
drive, and never over the base model file.

**Naming rule: `<agent>-v<version>.gguf`**, all lowercase. `<agent>` is `sme`,
`gad`, `itso` or `coordinator`; `<version>` is the version number shown for the
adapter on the admin Training Data page. Examples: `sme-v3.gguf`,
`gad-v1.gguf`. The admin page shows the exact file name for each version.

The app matches loaded files to trained adapters by this name. A file the app
cannot match (wrong pattern, an unknown agent or version, or two files that
resolve to the same agent and version) is listed on the admin page as
"unrecognized" and is never used.

Check the file arrived intact (compare with the value in the `.sha256` file,
which still carries the original name):

```
certutil -hashfile F:\Dev\Models\gemma\adapters\sme-v3.gguf SHA256
```

## 2. Check your llama-server supports the flags

Run the same `llama-server.exe` that `start-gemma.bat` starts, with `--help`,
and search the output for `lora`:

```powershell
& "<the llama-server.exe path from your start-gemma.bat>" --help | findstr /i lora
```

You should see `--lora-scaled` (and `--lora`, `--lora-init-without-apply`).

## 3. Add one argument per adapter to the launch command

In `start-gemma.bat`, add one `--lora-scaled` argument for **each** adapter file
to the `llama-server.exe` arguments (keep every existing flag as is). For two
adapters:

```
--lora-scaled F:\Dev\Models\gemma\adapters\sme-v3.gguf:0.0 --lora-scaled F:\Dev\Models\gemma\adapters\gad-v1.gguf:0.0
```

The `:0.0` at the end is the starting scale: the adapter is loaded but **off**,
so the server behaves exactly as it does today until a request asks for it. Use
the full path. The colon form is required; do not drop the `:0.0`. If your build
rejects the colon form, use the space form `--lora-scaled <file> 0.0` instead.

Adapter ids follow the order you give the flags (first file is id 0, second is
id 1, and so on). The app looks up ids from `GET /lora-adapters` by file name,
so ordering never matters to the app. Only restart the server when no
evaluation or benchmark is running, and wait 30 seconds after the restart
before starting one: the app caches the server's adapter list for about 30
seconds and builds each evaluation's adapter plan once before scoring, so a
different load order mid-run can apply the wrong adapter or make llama.cpp
reject an id.

The admin Training Data page shows a `--lora-scaled <file>:0.0` line, with a
Copy button, for each version that is not loaded yet. It uses the bare file
name, so add the file's full path before pasting it into `start-gemma.bat`.

Avoid `--lora <file> --lora-init-without-apply`: on build 10430 it left the
adapter on.

If `start-gemma.bat` breaks the command over several lines with `^` at the line
ends, add the new argument in the same style, and make sure `^` is the very
last character on its line (no trailing space).

Restart the server. Restarting is your call and briefly interrupts anything
using it.

## 4. Confirm it loaded and is switched off

If your server was started with `--api-key`, every request needs the key. Open
a **new** PowerShell window and paste (it asks for the key; do not paste the key
into chats or screenshots):

```powershell
$key = Read-Host "API key"
$headers = @{ Authorization = "Bearer $key" }
Invoke-RestMethod http://127.0.0.1:8080/lora-adapters -Headers $headers
```

(Without `--api-key`, leave off `-Headers $headers`.)

Expected: one entry per file you loaded (ids 0, 1, ... in load order), each with
the path to its file and `scale` 0 (or 0.0).

If any `scale` is not 0, that adapter is being applied to every request right
now. Set it back with the POST command in step 6 (scale 0.0, one entry per
adapter id), then fix the launch
flags (use `--lora-scaled <file>:0.0` from step 3) and restart before
continuing.

## 5. Turn it on for a request

Per request (no restart, other requests are unaffected). This reuses `$headers`
from step 4, so stay in the same window. `id` is the adapter id from step 4; the
app does this itself, listing every loaded id with an explicit scale (1.0 for
the chosen adapter, 0.0 for the rest), so a stale global scale is always
overridden. For a manual test a single entry is enough, because llama.cpp
resets unlisted ids to 0:

```powershell
$body = @{
  model = "gemma-3-4b-it"
  messages = @(@{ role = "user"; content = "Say hello in one sentence." })
  max_tokens = 40
  lora = @(@{ id = 0; scale = 1.0 })
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri http://127.0.0.1:8080/v1/chat/completions -Method Post -ContentType "application/json" -Headers $headers -Body $body
```

Use `scale = 0.0` (or leave `lora` out) for the plain model.

If the per-request field seems to be ignored, set the scale for the whole
server instead. This is a manual diagnostic only: the app never does this, it
affects every request until you set it back. A single entry is enough for the
test, since llama.cpp resets unlisted ids to 0; to set everything back, send
scale 0.0 for each loaded id (the command is in step 6):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8080/lora-adapters -Method Post -ContentType "application/json" -Headers $headers -Body '[{"id":0,"scale":1.0}]'
```

## 6. Run the smoke test

From any machine that has this repo and Python 3.10 or newer:

```
python training/smoke_test_lora_serving.py training/sample_pairs.jsonl --base-url http://127.0.0.1:8080/v1 --limit 2
```

Through the tunnel, set `LLM_API_BASE` and `LLM_API_KEY` in the environment
instead of passing them on the command line (the script never prints the key).
The script sends its own `User-Agent`, because Cloudflare tunnels reject
Python's default one. The script tests **one** adapter: the first loaded by
default, or pick another with `--adapter-id <id>`. Add `--scale-mode global` if
step 5's per-request field was ignored (a diagnostic; see step 5).

It sends the same real SME prompts with the adapter off and then on, and
checks every reply is valid SME JSON. `RESULT: PASS` means the adapter loads
and the server still behaves. It does **not** say the adapter is good: the
stored adapter was trained on only 25 synthetic pairs.

On 2026-09-19 the test passed through the tunnel: every reply valid with the
adapter off and on, one of two prompts scored differently with it on, and the
adapter was still at scale 0.0 afterwards.

In global mode the script changes the server-wide scale, so it resets the scale
to 0.0 itself when it finishes or fails and prints a note saying so. If it
prints a warning that the reset failed, the adapter may still be on for every
request; run this yourself (on the server machine, or swap in the tunnel URL;
add `-Headers $headers` if your server needs the key):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8080/lora-adapters -Method Post -ContentType "application/json" -Headers $headers -Body '[{"id":0,"scale":0.0}]'
```

## 7. Use it from the admin pages

Once the server is restarted with the files loaded, everything else is done in
the admin app.

**Training Data page, per agent tab.** The adapter table lists every trained
version of that agent with a status:

- **Loaded**: the server has the file loaded and the app matched it.
- **Not loaded**: no matching file on the server. The row shows the copyable
  `--lora-scaled <file>:0.0` line to add to `start-gemma.bat` (step 3).
- **Unknown**: the app could not reach `GET /lora-adapters`. It does not mean
  the adapter is missing; scoring runs on the base model meanwhile.

**Publish / Unpublish** (with a confirmation) chooses which version of that
agent real evaluations use. Publishing is per agent, so SME can be on `v3`
while GAD stays on base. Files the server loaded that match no trained adapter
appear as "unrecognized".

**Model Validation benchmarks.** Pick **one** agent, then a Model: **Base**, the
agent's **Published** adapter, or a specific **version**. Only that agent's
adapter is applied to the run; other loaded adapters are sent at scale 0.0.

**If a published adapter is not loaded** (for example the file was removed, or
the server restarted without it): scoring does not stop. That agent continues on
the base model, the evaluation records what was requested and what was applied
(for example requested `gad-v1`, applied none, reason `not_loaded`), and the
Training Data adapter table shows a warning banner until the file is loaded again.

## Verifying a multi-adapter setup

A checklist for the host owner and an admin to run together after the first
multi-adapter restart (nothing here has been run yet; record the outcome in the
spec's open items):

1. Load two adapters, for example `sme-v1.gguf` and `gad-v1.gguf`, both with
   `:0.0`, and restart. Confirm step 4 shows both at scale 0.
2. On the Training Data page, confirm both versions show **Loaded**.
3. Publish each (SME tab, then GAD tab). Run a normal evaluation and confirm the
   status API's `adapter_resolution` shows the adapter as applied for both
   agents.
4. In Model Validation, benchmark SME with Model = Base, then Model = `v1`.
   Confirm scores differ on at least one criterion and that the GAD adapter is
   not applied to the SME run (its id is sent at scale 0.0).
5. Restart the server **without** `gad-v1.gguf`. Confirm the warning banner
   appears, an evaluation still completes on base, and `adapter_resolution` for
   GAD reads requested `gad-v1`, applied none, `not_loaded`.
6. Optional: compare the duration of a full evaluation with mixed adapters
   against base-only and note the numbers (see the Speed note below).

## 8. Roll back

Remove the `--lora-scaled` argument for that file (or the
`--lora`/`--lora-init-without-apply` arguments, if you used those) from
`start-gemma.bat` and restart. For one agent only, remove just its file: the app
falls back to base for that agent and shows the banner (Unpublish it on the
admin page to clear the banner). The base model file was never touched.

## Notes

- **GPU memory:** the current settings (`--ctx-size 24576 --parallel 3`, q8 KV
  cache) are estimated at about 5 of the 8 GiB. Each adapter adds roughly
  0.1-0.2 GiB, so four adapters is about 0.4-0.8 GiB. Check with `nvidia-smi` before and after, and tell us the
  numbers. A second server running at the same time is not expected to fit.
- **Speed:** requests using different adapter settings (for example SME on one
  adapter and GAD on another at the same time) may not be batched together
  across the 3 parallel slots. If throughput drops, that is why.
- **What this does not tell you:** whether the adapter improves answers. That
  needs a separate comparison on held-out reviewer data.
