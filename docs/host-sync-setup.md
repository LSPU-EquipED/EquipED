# Host sync setup

Host sync runs on the computer that runs llama.cpp. It requests the adapter
manifest using a dedicated host key, downloads missing or changed GGUF files,
checks their SHA-256 hashes, and writes `--lora-scaled` launch arguments to a
flags file. By default, it includes the newest two versions per agent and any
published version. It does not restart llama-server, delete files, or publish
adapters.

## Configure

1. In Admin Training Data, create a host sync key and copy it when shown. The
   key can be revoked and replaced from the same panel.
2. Copy `training/host_sync.py` and `training/host_sync.example.ini` to the
   model host. Rename the copied INI to `host_sync.ini`.
3. Set `server_url` to the final EquipED HTTPS address, `key` to the host key,
   and `adapters_dir` to the directory llama.cpp loads adapters from. Keep
   `keep_latest` and `notify` as needed. The INI contains a secret; keep it out
   of source control and shared messages.
4. Run `python host_sync.py --config host_sync.ini` with Python 3.10 or later.
   Schedule the same command at a suitable interval if automatic downloads
   are needed. The log is `host_sync.log` beside the INI by default.
5. Configure the llama-server launch command to read the generated
   `lora-flags.txt` and append its lines as arguments. Each line loads one
   adapter with scale `0.0`, so it is available but inactive by default.

The example INI uses a placeholder URL, key, and adapter path; replace them
with values for the host. Do not paste real keys into documentation.

## After an adapter upload

Wait until the training job is finished and the uploaded GGUF appears in
EquipED. The next sync downloads it and updates the flags file. Restart
llama-server when no evaluation is running, then confirm the adapter is listed
as loaded in Admin Training Data. A download alone does not load the file into
the running server.

## Troubleshooting

- **Key rejected:** check that it was copied correctly and has not been
  revoked; replace it in Admin and update `host_sync.ini`.
- **Checksum mismatch or failed download:** the incomplete file is discarded;
  the next sync retries it.
- **Redirect response:** set `server_url` to the final HTTPS address. The
  script refuses redirects to avoid sending the key elsewhere.
- **Adapter still not loaded:** confirm the file and flags path, then restart
  llama-server. Sync never restarts the process.
- **No notification:** Windows notifications require a logged-in desktop.
  Check `host_sync.log` for sync results.
- **Old files accumulate:** sync does not delete old GGUF files. Remove files
  only when they are no longer needed and the server is stopped.
