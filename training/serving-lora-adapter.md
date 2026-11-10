# Serving a trained adapter

This guide covers loading an uploaded GGUF LoRA adapter in llama.cpp. The
adapter is an additional model artifact; it does not replace the base model.
Host sync can download files and generate launch flags; see
[host sync setup](../docs/host-sync-setup.md).

## Load the adapter

1. In Admin Training Data, download the adapter GGUF or copy its temporary
   download link to the host owner. Save the file with its displayed
   `<agent>-v<version>.gguf` name.
2. Add one `--lora-scaled` argument to the llama-server launch command for each
   adapter to load, using its full path and initial scale `0.0`. For example:

   ```text
   --lora-scaled "<adapter-directory>/sme-v1.gguf:0.0"
   ```

3. Restart llama-server when no evaluation is running. Confirm the adapter is
   listed by `GET /lora-adapters` at scale 0 and that Admin Training Data
   reports it as loaded.

The application selects an adapter per request. Publishing is a separate
administrator action. If a published adapter is not loaded, evaluations can
continue on the base model; inspect the recorded adapter resolution.

## Smoke check

With the server available, run:

```sh
python training/smoke_test_lora_serving.py training/sample_pairs.jsonl \
  --base-url http://<server>/v1 --limit 2
```

Set `LLM_API_KEY` in the environment when the server requires authentication.
The sample pairs are synthetic. A passing smoke check verifies response
format and adapter wiring only; it does not demonstrate output quality.

## Roll back

Remove the adapter's launch argument and restart the server. Unpublish the
version in Admin Training Data if it should no longer be selected for normal
evaluations. Keep old files only as long as needed and delete them only while
the server is stopped.
