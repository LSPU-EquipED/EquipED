# Host sync setup

For the person who runs the model server (Windows, llama.cpp, started by
`start-gemma.bat`). Host sync is a small script that checks EquipED every few
minutes and brings new fine-tuned models onto this computer, so you no longer
copy files by hand.

## What the script does and does not do

It does:

- Ask EquipED which fine-tuned model files (`.gguf`) exist.
- Download new or changed files into your adapters folder, as
  `<agent>-v<number>.gguf` (for example `sme-v11.gguf`). A file is only kept
  if its checksum matches; a broken or partial download is thrown away and
  tried again on the next run.
- Write `lora-flags.txt` in the adapters folder: one `--lora-scaled
  "<full path>:0.0"` line per model file the server should load.
- Write what happened to `host_sync.log`, and show a desktop notification when
  a new model arrives.

It does not:

- Restart the model server. You do that yourself (see "After a training run").
- Delete old files. Old versions stay on disk.
- Publish anything. Publishing is still done in the admin page.

It loads only the newest 2 versions of each agent (change `keep_latest` to
alter this), plus the version that is published in EquipED.

## One-time setup

### 1. Check Python

You need Python 3.10 or newer on this computer. Open Command Prompt and type:

```
python --version
```

If it prints `Python 3.10` or higher, you are fine. If not, install Python
from python.org (tick "Add python.exe to PATH"). Nothing else needs installing.

### 2. Create the host key

1. In the EquipED admin page, open Model Training and find the **Host sync**
   panel.
2. Create a key. It is shown **once**; copy it right away.
3. If a key is ever lost or leaked, revoke it in the same panel and create a
   new one.

### 3. Put the script and settings on this computer

1. Make a folder, for example `F:\Dev\Models\gemma\host-sync`.
2. Copy `training/host_sync.py` into it.
3. Copy `training/host_sync.example.ini` into it and rename the copy to
   `host_sync.ini`.
4. Open `host_sync.ini` and fill it in:
   - `server_url`: the final https address of EquipED, with no slash at the
     end. It must be the real address, not one that redirects somewhere else:
     the script refuses redirects so your key is never sent to another place.
   - `key`: the key from step 2.
   - `adapters_dir`: the folder the model server loads adapters from.
   - `keep_latest`: how many newest versions per agent to load (default 2).
   - `notify`: `true` to show a notification when a new model arrives.

   **`host_sync.ini` contains your secret key.** Keep it private: do not email
   it, paste it in a chat, or commit it to git. If it is shared by mistake,
   revoke the key in the admin Host sync panel and create a new one.

   The log is written next to `host_sync.ini` as `host_sync.log` (you can set
   `log_file` to put it elsewhere).

Important about the adapters folder path:

- Use plain ASCII characters only (English letters, numbers, spaces and
  ordinary punctuation such as `\` `:` `.` `-` `_`). No accented or
  non-English characters: the flags file is saved as UTF-8 but `cmd` reads it
  in the older Windows codepage, so such characters get garbled.
- Do not use `!` or `%` anywhere in the path. The batch file below treats
  them specially and the path would break.

Try it once by hand:

```
python F:\Dev\Models\gemma\host-sync\host_sync.py --config F:\Dev\Models\gemma\host-sync\host_sync.ini
```

It prints nothing when there is nothing new. When it downloads a model it
prints `New model sme-v11 ready, restart the model server to load it`. On the
very first run it downloads every model version EquipED has (about 60 MB each),
even though only the newest 2 per agent plus the published one are loaded.

Errors found while syncing are printed and also written to `host_sync.log`.
Exit code 0 means all fine and 1 means something went wrong (see the log).
Exit code 2 means the settings file is missing or wrong; it prints
`Configuration error: ...` on screen only and is **not** written to the log. So
if a scheduled run does nothing and the log shows nothing new, run the command
above by hand from a Command Prompt window to see the message.

### 4. Make `start-gemma.bat` read the flags file

Open `start-gemma.bat` and add these lines before the `llama-server` command:

```bat
setlocal EnableDelayedExpansion
set "LORA_FLAGS="
if exist "F:\Dev\Models\gemma\adapters\lora-flags.txt" (
  for /f "usebackq delims=" %%L in ("F:\Dev\Models\gemma\adapters\lora-flags.txt") do set "LORA_FLAGS=!LORA_FLAGS! %%L"
)
```

Use your own adapters folder in both places. Then add `!LORA_FLAGS!` to the end
of your existing `llama-server` command line, after your other options:

```bat
llama-server.exe -m <your model file> <your other options> !LORA_FLAGS!
```

This was checked on Windows: the loop keeps the quotes and builds one single
line, for example:

```
 --lora-scaled "F:\Dev\Models\gemma\adapters\sme-v10.gguf:0.0" --lora-scaled "F:\Dev\Models\gemma\adapters\sme-v11.gguf:0.0"
```

The `:0.0` means the adapter is loaded but switched off by default; EquipED
turns the right one on per request.

### 5. Schedule it in Task Scheduler

1. Open Task Scheduler, choose Create Task.
2. General tab: choose **Run only when user is logged on**. This matters: the
   desktop notification can only appear in a logged-in desktop session. (The
   script still downloads files without it, but you would get no pop-up.)
3. Triggers: new trigger, repeat every 5 to 10 minutes, indefinitely.
4. Actions: Start a program. Program: `python`. Arguments:
   `F:\Dev\Models\gemma\host-sync\host_sync.py --config F:\Dev\Models\gemma\host-sync\host_sync.ini`
   Start in: `F:\Dev\Models\gemma\host-sync`
5. Save.

The admin page shows "Host last checked N min ago", so you can see that the
schedule is working.

## After a training run

1. Wait until the admin page shows the run as **Finished**. The model file is
   uploaded last, so earlier than that there is nothing to download yet.
2. Within a few minutes, a notification appears (or `host_sync.log` says)
   "New model ... ready, restart the model server to load it".
3. When no evaluation is running, restart the model server (run
   `start-gemma.bat` again).
4. In the admin page, the model's row in the Fine-tuned models table changes
   from **Not loaded** to **Loaded**.

A model keeps showing **Not loaded** until the server has been restarted.

## Troubleshooting

- **"EquipED rejected the host key"**: the key was revoked or copied wrong.
  Create a new key in the admin Host sync panel and paste it into
  `host_sync.ini`.
- **"checksum does not match; discarded"** or a failed download: nothing
  partial is kept. The next scheduled run tries again. If it keeps happening,
  check your internet connection.
- **"could not read the manifest from EquipED: ..."**: the script could not
  reach EquipED or could not understand the reply (internet down, wrong
  `server_url`, server down, or a damaged reply). Check the address in
  `host_sync.ini` and your connection; it retries on the next run. If it
  persists, send the log lines to the developer.
- **"EquipED returned HTTP N for the manifest"**: EquipED answered with an
  error (N is the number, for example 500 or 503). Usually the server is having
  trouble; try again later, and if it persists send the log lines to the
  developer.
- **"could not write the flags file: ..."**: the script could not save
  `lora-flags.txt` (folder missing rights, disk full, or the file is open in
  another program). Fix that and the next run rewrites it.
- **"ignored an unsafe or malformed entry"**: EquipED listed a model the script
  refuses (odd file name or size). It is skipped and nothing is written for it.
  Send the log line to the developer.
- **"larger than announced; discarded"**: a download was bigger than EquipED
  said. The partial file is thrown away and the next run tries again; if it
  repeats, send the log line to the developer.
- **"Configuration error: ..."**: shown on screen only, not in the log. Run
  the command by hand to see it, then fix `host_sync.ini`.
- **"answered with a redirect"**: `server_url` is not the final address. Use
  the final https address.
- **Model still shows Not loaded**: the server has not been restarted since the
  file arrived, or the file is older than the newest 2 versions (and not the
  published one).
- **No notification**: the task must be set to "Run only when user is logged
  on", and you must be logged in. The log still records the new model.
- **Old model files pile up**: the script never deletes. Delete old
  `.gguf` files yourself when you are sure you do not need them; remove them
  only while the server is stopped.
- **Where is the log?** `host_sync.log`, next to `host_sync.ini` (or wherever
  `log_file` points).
