# Training a fine-tuned model: before and after

Comparison of `main` and the branch `feat/plain-language-model-training`.
Written for the admin who starts training runs, the host owner who runs the
model server, and anyone reviewing the pull request.

**In one sentence:** on `main`, training meant copying links by hand, waiting
without any feedback, and passing a file to the host owner who set it up by
hand. On this branch, the admin downloads a ready notebook, watches the run's
progress in the admin page, and the host owner only restarts the model server.

Free Colab has no API, so someone still opens the notebook and presses
**Run all**. That step cannot be automated and is not.

---

## At a glance

| Step | On `main` | On this branch | What changed |
|---|---|---|---|
| Open the Training page | "Training Data": technical words (adapter, pairs, Prepare training run, SHA-256) | "Model Training": plain words (fine-tuned model, correction examples, Start a training run); technical details under "For IT staff" | Wording |
| Get the notebook ready | Copy two links, open `dpo_training_template.ipynb`, paste them into cell 1 by hand | Press **Download notebook**; the links are already filled in | **Automated** |
| Set training numbers | Fixed in the notebook (`MAX_SEQ_LENGTH = 2048`, 1 epoch). Too small for SME prompts, so people edited copies by hand | The notebook measures your pairs and sets lengths and epochs from the data | **Automated** |
| Start training | Open Colab, upload the notebook, pick the T4, Run all | Same | Manual (no Colab API) |
| Watch progress | None. The row says "Prepared / Downloaded / Adapter received". A crashed or disconnected run looks the same as a busy one | Row shows the stage ("Training · step 14 of 30 · updated 2 min ago"), refreshes by itself, and warns after 15 minutes of silence | **Automated** |
| Training safety | No safeguards in the template | Stops early if the chosen reward collapses; out-of-memory rescue cell; chat-format check before training | **Automated** |
| Get the model file out of Colab | Notebook uploads it to EquipED | Same, and reports "failed" if the upload did not happen | Already automated; now visible |
| Get the file to the model server | Admin downloads the GGUF (or copies a temporary link) and sends it to the host owner | A small script on the host downloads it by itself and checks it | **Automated** |
| Register the file with the server | Host copies it into the adapters folder with the exact name, then adds `--lora-scaled <full path>:0.0` to `start-gemma.bat` for every version, by hand | Script writes `lora-flags.txt`; `start-gemma.bat` reads it (edited once) | **Automated** |
| Load it | Host restarts the model server | Host restarts the model server | Manual (on purpose) |
| Use it | Admin presses **Publish** once it shows as Loaded | Same | Manual (on purpose) |

---

## The flow on `main`

1. **Admin:** open Training Data, check the counts, press *Prepare training run*.
2. **Admin:** copy the *Download URL* and *Upload URL* before leaving the page; they cannot be shown again.
3. **Admin:** open the Colab notebook and paste both links into cell 1.
4. **Admin:** if the prompts are long (SME), edit the length and training numbers by hand. Several hand-edited copies of the notebook exist for this.
5. **Admin:** choose the T4 GPU, press Run all, then wait with no feedback. Open the page now and then to see whether the status changed.
6. **Colab:** trains, uploads the adapter, converts it to GGUF and uploads that too.
7. **Admin:** open the model's details, press *Download* (or *Copy download link*) and send the file or link to the host owner.
8. **Host owner:** save the file into the adapters folder under the exact name `<agent>-v<n>.gguf`.
9. **Host owner:** edit `start-gemma.bat` to add a `--lora-scaled "<full path>:0.0"` flag for that file, and keep the list of flags up to date by hand as versions pile up.
10. **Host owner:** restart the model server and tell the admin.
11. **Admin:** check the model shows as *Loaded*, then press *Publish*.

Hand-offs between people: 3 (admin to Colab, admin to host owner, host owner back to admin).

## The flow on this branch

**One-time setup (once, not per run):**
- **Admin:** create a host key in the *Host sync* panel and send it privately.
- **Host owner:** put `host_sync.py` and `host_sync.ini` on the model-server computer, edit `start-gemma.bat` once so it reads `lora-flags.txt`, and schedule the script in Task Scheduler. Steps are in `docs/host-sync-setup.md`.

**Every run:**
1. **Admin:** open Model Training, press *Start a training run*.
2. **Admin:** press *Download notebook*. All links are inside; nothing to paste.
3. **Admin:** upload the file to Colab, choose the T4, press Run all.
4. **Automatic:** the notebook measures the pairs, sets lengths and epochs, trains with the safety checks, and reports each stage to the admin page.
5. **Admin:** watch the row go Starting, Training (step counter), Sending model, Converting file, Sending file, Finished. No refresh needed.
6. **Automatic:** the host script notices the new model within minutes, downloads it, checks the checksum, saves it with the right name, and updates `lora-flags.txt`. It writes a log line and shows a notification.
7. **Host owner:** restart the model server when it is idle.
8. **Admin:** check the model shows as *Loaded*, then press *Publish*.

Hand-offs between people: 1 (the host owner is told to restart; the notification does most of that).

---

## What is automated now

- **Notebook setup:** links filled in server-side, as a private file per run.
- **Training numbers:** lengths and epochs chosen from the data, not typed in.
- **Training safeguards:** early stop, chat-format check, out-of-memory rescue.
- **Progress reporting:** stage, step counter and "last heard from", with a disconnect warning.
- **Delivery to the host:** download, checksum verification, correct file name, and the list of models for the server to load. The host's list keeps only the newest 2 versions per agent plus the published one.
- **Wording:** the Training page uses plain language for non-technical admins.

## What is still manual, and why

| Still manual | Why |
|---|---|
| Opening Colab and pressing Run all | Free Colab has no API. Scripting its screen would be fragile and against Google's terms. |
| Restarting the model server | The server only reads its model list at startup. An automatic restart could kill a faculty evaluation in progress, so a person picks a quiet moment. |
| Pressing Publish | Choosing which model faculty use is a decision, not a chore. The button stays off until the model is Loaded. |
| One-time host setup | Needs a person on that computer. Done once. |

## What to know before relying on it

- **Not yet proven on real hardware.** Everything was tested offline against stand-ins. A real Colab run, a Docker build and the Windows host (batch file, Task Scheduler, real `llama-server`) are the first true checks.
- **Colab must reach your app.** Status reports only arrive if `PUBLIC_BASE_URL` is a public address (for example a tunnel).
- **Quiet stretches.** Installing packages and converting the file send no updates, so a slow session can show a false "may have disconnected" warning.
- **Two database migrations** (`20261010_0001`, `20261010_0002`) must be applied before using the new features.
- **A better model is not guaranteed.** Earlier versions (v7 to v9) showed no measured lift. This work makes training and delivery easier; it does not change whether a model scores better. That is still judged on the Model Validation page.

## Where things live

| Piece | Location |
|---|---|
| Notebook template | `docs/colab/dpo_training_template.ipynb` |
| Download-notebook builder | `apps/server/modules/training_data/notebook.py` |
| Run status (server) | `apps/server/modules/training_data/jobs.py`, `router.py` |
| Host key and host endpoints | `apps/server/modules/training_data/host_keys.py`, `router.py` |
| Host script | `training/host_sync.py`, `training/host_sync.example.ini` |
| Host setup guide | `docs/host-sync-setup.md` |
| Admin screens | `apps/admin/src/features/training-data/` |
| Design and plan | `docs/superpowers/specs/2026-10-10-semi-automatic-training-design.md`, `docs/superpowers/plans/2026-10-10-semi-automatic-training.md` |
