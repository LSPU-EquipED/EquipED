# Serving a trained adapter on llama-server (GGUF LoRA)

For the person who runs the model server (Windows, llama.cpp CUDA build,
started by `start-gemma.bat`). This adds a trained adapter **on top of** the
model file you already serve. It never changes that file, and you can remove it
again at any time.

You will receive two files from the training side:

- `adapter-f16.gguf` (about 60 MB), the adapter converted for llama.cpp
- `adapter-f16.gguf.sha256`, its checksum

**Verified 2026-09-19 on llama-server build 10430:** loading the adapter with
`--lora-scaled <file>:0.0` starts it switched **off** (scale 0.0), and a
request can switch it on. Loading it with `--lora <file>
--lora-init-without-apply` did **not** keep it off on that build: it showed
scale 1, meaning the adapter was live for every request. So step 3 recommends
`--lora-scaled`, and step 4 is a check you must not skip.

## 1. Put the file somewhere with space

Copy `adapter-f16.gguf` next to your models on the F: drive, for example
`F:\Dev\Models\gemma\adapters\adapter-f16.gguf`. Do not put it on the full C:
drive, and never over the base model file.

Check the file arrived intact (compare with the value in the `.sha256` file):

```
certutil -hashfile F:\Dev\Models\gemma\adapters\adapter-f16.gguf SHA256
```

## 2. Check your llama-server supports the flags

Run the same `llama-server.exe` that `start-gemma.bat` starts, with `--help`,
and search the output for `lora`:

```powershell
& "<the llama-server.exe path from your start-gemma.bat>" --help | findstr /i lora
```

You should see `--lora-scaled` (and `--lora`, `--lora-init-without-apply`).

## 3. Add one argument to the launch command

In `start-gemma.bat`, add this to the `llama-server.exe` arguments (keep every
existing flag as is):

```
--lora-scaled F:\Dev\Models\gemma\adapters\adapter-f16.gguf:0.0
```

The `:0.0` at the end is the starting scale: the adapter is loaded but **off**,
so the server behaves exactly as it does today until a request asks for it. Use
the full path. If your build rejects the colon form, use the space form
`--lora-scaled <file> 0.0` instead.

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

Expected: one entry with `id` 0, the path to your file, and `scale` 0 (or 0.0).

If `scale` is not 0, the adapter is being applied to every request right now.
Set it back with the POST command in step 6 (scale 0.0), then fix the launch
flags (use `--lora-scaled <file>:0.0` from step 3) and restart before
continuing.

## 5. Turn it on for a request

Per request (no restart, other requests are unaffected). This reuses `$headers`
from step 4, so stay in the same window:

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
server instead (this affects every request until you set it back; the command
to set it back is in step 6):

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
Python's default one. Add `--scale-mode global` if step 5's per-request field
was ignored.

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

## 7. Roll back

Remove the `--lora-scaled` argument (or the `--lora`/`--lora-init-without-apply`
arguments, if you used those) from `start-gemma.bat` and restart. The base model
file was never touched.

## Notes

- **GPU memory:** the current settings (`--ctx-size 24576 --parallel 3`, q8 KV
  cache) are estimated at about 5 of the 8 GiB. The adapter adds roughly
  0.1-0.2 GiB. Check with `nvidia-smi` before and after, and tell us the
  numbers. A second server running at the same time is not expected to fit.
- **Speed:** requests using different adapter settings may not be batched
  together across the 3 parallel slots. If throughput drops, that is why.
- **What this does not tell you:** whether the adapter improves answers. That
  needs a separate comparison on held-out reviewer data.
