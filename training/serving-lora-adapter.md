# Serving a trained adapter on llama-server (GGUF LoRA)

For the person who runs the model server (Windows, llama.cpp CUDA build,
started by `start-gemma.bat`). This adds a trained adapter **on top of** the
model file you already serve. It never changes that file, and you can remove it
again at any time.

You will receive two files from the training side:

- `adapter-f16.gguf` (about 100-150 MB), the adapter converted for llama.cpp
- `adapter-f16.gguf.sha256`, its checksum

## 1. Put the file somewhere with space

Copy `adapter-f16.gguf` next to your models on the F: drive, for example
`F:\Dev\Models\gemma\adapters\sme-adapter-f16.gguf`. Do not put it on the full
C: drive, and never over the base model file.

Check the file arrived intact (compare with the value in the `.sha256` file):

```
certutil -hashfile F:\Dev\Models\gemma\adapters\sme-adapter-f16.gguf SHA256
```

## 2. Check your llama-server supports the flags

```
F:\Dev\Servers\llama.cpp\build-cuda\bin\Release\llama-server.exe --help | findstr /i lora
```

You should see `--lora` and `--lora-init-without-apply`. If
`--lora-init-without-apply` is missing, use
`--lora-scaled <file> 0.0` instead of the two flags in step 3.

## 3. Add two arguments to the launch command

In `start-gemma.bat`, add these to the `llama-server.exe` arguments (keep every
existing flag as is):

```
--lora F:\Dev\Models\gemma\adapters\sme-adapter-f16.gguf --lora-init-without-apply
```

`--lora-init-without-apply` loads the adapter but starts with it switched
**off**, so the server behaves exactly as it does today until a request asks
for the adapter.

Restart the server. Restarting is your call and briefly interrupts anything
using it.

## 4. Confirm it loaded

```powershell
Invoke-RestMethod http://127.0.0.1:8080/lora-adapters
```

Expected: one entry with `id` 0, the path to your file, and `scale` 0.

## 5. Turn it on for a request

Per request (no restart, other requests are unaffected):

```powershell
$body = @{
  model = "gemma-3-4b-it"
  messages = @(@{ role = "user"; content = "Say hello in one sentence." })
  max_tokens = 40
  lora = @(@{ id = 0; scale = 1.0 })
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri http://127.0.0.1:8080/v1/chat/completions -Method Post -ContentType "application/json" -Body $body
```

Use `scale = 0.0` (or leave `lora` out) for the plain model.

If the per-request field seems to be ignored, set the scale for the whole
server instead (this affects every request until you set it back):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8080/lora-adapters -Method Post -ContentType "application/json" -Body '[{"id":0,"scale":1.0}]'
```

## 6. Run the smoke test

From any machine that has this repo and Python:

```
python training/smoke_test_lora_serving.py training/sample_pairs.jsonl --base-url http://127.0.0.1:8080/v1 --limit 2
```

Through the tunnel, set `LLM_API_BASE` (and `LLM_API_KEY` if your endpoint
needs one) in the environment instead of passing them on the command line. Add
`--scale-mode global` if step 5's per-request field was ignored.

A global-mode run leaves the adapter switched on for every request. When it finishes, set the scale back to 0:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8080/lora-adapters -Method Post -ContentType "application/json" -Body '[{"id":0,"scale":0.0}]'
```

It sends the same real SME prompts with the adapter off and then on, and
checks every reply is valid SME JSON. `RESULT: PASS` means the adapter loads
and the server still behaves. It does **not** say the adapter is good: the
stored adapter was trained on only 25 synthetic pairs.

## 7. Roll back

Remove the two arguments from `start-gemma.bat` and restart. The base model
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
