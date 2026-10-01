# House-rule adapter validation: runbook

This runbook walks you through one experiment: teach an SME adapter an
invented, easy-to-measure rule, then check whether the adapter really learned
it. The script is `apps/server/scripts/seed_house_rule_edits.py`. The design is
in `docs/superpowers/specs/2026-09-26-adapter-validation-house-rule-design.md`.

All commands run from the `apps/` folder.

## 1. What this proves and what it does not

**What it proves.** The adapter learned the rule we taught it. The rule is:
for an "edited" criterion, the SME score goes up by 1 (never above 4). If the
adapter learned it, then on real SLMs its scores on those criteria move up,
the move also shows on SLMs it never saw in training (the held-out ones), and
the criteria we did not touch (the "controls") stay where they were.

**What it does not prove.** That the adapter is *better* at scoring. The rule
is made up, so being close to it says nothing about being close to a human
reviewer. A "better than base" claim needs human reference scores: enter the
human expected scores in Model Validation, train on corrections from some
benchmarked SLMs, test on others, and compare base and adapter error with a
paired sign test across at least 10 SLMs. That is a separate, later experiment.

## 2. Rules that must not be broken

- **Never publish the adapter trained on these corrections.** It teaches an
  invented rule. Publishing it would make real faculty SME scores follow that
  rule. It is a test artifact only. (If it is published by mistake: Unpublish
  is one click, and `adapter_resolution` on each evaluation records what was
  applied.)
- **Do not start any other SME training job between the write step and the
  cleanup.** The exporter reads ALL SME corrections, so any other job would
  also train on these. Run the cleanup as soon as validation is done.
- **Only the evaluations you list are touched.** The script never changes
  evaluations, generations, documents or snapshots. It only adds tagged
  correction rows, and cleanup removes exactly those.
- **Run every evaluation of the experiment under a test account**, so they are
  easy to find. Do not edit, accept or reject any score in the review UI for
  these evaluations. Any existing correction on a criterion makes the script
  skip that criterion (a real reviewer decision is never overridden).
- **Set `SME_TOTAL_PROMPT_BUDGET_CHARS=15000` in `.env` and restart the
  backend before running any evaluation of the experiment.** 15000 is the code
  default and the minimum allowed; the developer `.env` currently has 28000.
  Keep it at 15000 for the training-data runs AND for the validation
  benchmarks, then restore the old value afterwards.

Why 15000: at that budget every SLM, long or short, produces the same prompt of
about 14.4k characters (roughly 3,600 tokens). That size fits the training
limits and gave 8 of 8 clean answers on a long SLM. At 28000 the prompts are
about 27k characters and many answers come back repaired. Repaired and fallback
generations are not usable training pairs.

## 3. Phase 0: remove the old synthetic pairs

The database holds 25 old synthetic SME pairs, from run
`32f54b7b-1122-4d70-a869-e86eba03cb42`. They would be trained on together with
the new pairs, so remove them first:

```bash
uv run --project server python -m server.scripts.seed_synthetic_dpo_pairs \
    --cleanup --run-id 32f54b7b-1122-4d70-a869-e86eba03cb42 \
    --confirm CLEANUP --confirm-target <LOCAL or fingerprint>
```

For the shared Neon database, export the allowed fingerprint first (bash):

```bash
export SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS="<fingerprint>"
```

On PowerShell: `$env:SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS = "<fingerprint>"`.
The fingerprint is printed by the house-rule script's dry run (the last line
says `--confirm-target <value>`; that value is `LOCAL` for a local database, or
the fingerprint). Use the same value for `--confirm-target`.

Check it worked with the house-rule dry run (section 5, step 2) plus
`--verify-export`. The line "Existing exportable SME pairs already in the
database" must read **0**. If it is not 0, the report prints a WARNING.

## 4. Which SLMs to use

You have **10 SLMs**. Recommended split: **8 train, 2 held out**. You choose
which is which. Before you start, open each PDF and check that its text can be
selected (a real text layer).

- **Train SLMs** get their evaluations corrected, so the adapter learns from
  them.
- **Held-out SLMs** are never corrected and never trained on. They only show
  whether the rule carries over to SLMs the adapter has not seen. The script
  aborts if one document is in both lists.

Fill in this table as you go (one row per SLM; list every evaluation id you
will pass to the script):

| File name | TRAIN / HELD-OUT | Document id | Evaluation ids |
|---|---|---|---|
| | | | |
| | | | |
| | | | |
| | | | |
| | | | |
| | | | |
| | | | |
| | | | |
| | | | |
| | | | |

Facts to keep in mind:

- **Budget.** Keep `SME_TOTAL_PROMPT_BUDGET_CHARS=15000` (section 2). Long SLMs
  are fine at that budget, because the source is downsampled to the same prompt
  size.
- **Base model only.** The script refuses any evaluation that was scored with
  an adapter applied. Run these evaluations with no adapter (base model).
- **Scanned PDFs need OCR first.** A scanned PDF has no text layer and gives
  nothing to evaluate. Tesseract is not installed on the dev machine, so a
  scanned SLM cannot be used until it is OCR'd elsewhere.
- **Repeat runs, but not too many.** Running the same SLM again gives
  near-duplicate pairs, so 2-3 runs per SLM are enough. Each evaluation gives
  2 pairs (`envelope_0` = the OP criteria, `envelope_1` = the A criteria), so
  about 50 train evaluations give about 100 pairs. The pilot confirms the real
  yield.
- **Held-out SLMs** get 2-3 plain base runs each; those fix their base
  reference scores.
- **Tip: reuse existing generations.** If a faculty-uploaded SLM already has
  stored base-model `ok` SME generations (for example the six
  `BSIT_CMSC313_*` SLMs have some), those evaluations can be listed for free
  instead of running them again, as long as they were produced at the 15000
  budget and without an adapter.

## 5. The process

**Step 1: pilot.** Pick 3 SLMs and run each 2 times (about 6 evaluations) from
the faculty portal's SME workspace, under the test account, with no edits in
the review UI. Put the train evaluation ids in `train_ids.txt` and the
held-out ones in `heldout_ids.txt` (one id per line, or comma separated; `#`
starts a comment). For the pilot, treat one SLM as held out to see the report.

**Step 2: dry run.** This is the default; nothing is written:

```bash
uv run --project server python -m server.scripts.seed_house_rule_edits \
    --train-evaluations-file train_ids.txt \
    --reference-evaluations-file heldout_ids.txt \
    --verify-export --report-csv expected_scores.csv
```

(`--train-evaluations IDS` and `--reference-evaluations IDS` take comma
separated ids directly. `--edit-criteria` overrides the default edited set
`OP-01,OP-03,OP-05,A-01,A-03,A-05`; every other criterion is a control.)

Read the report. Check the pairs per evaluation, the skip reasons, the prompt
lengths and "Existing exportable SME pairs" (must be 0). `expected_scores.csv`
has, for each SLM and criterion, its role, the base score of each run, the
base reference (mean, rounded half up) and the expected score if the rule was
learned. You will type those into Model Validation later.

**Step 3: choose notebook values.** If more than about 20% of prompts are over
the 1536-token limit, the report prints suggested values. In the Colab notebook
`docs/colab/dpo_training_template.ipynb` (cell numbers are 0-based, as the
notebook counts them):

- Cell 6: change `MAX_SEQ_LENGTH = 2048` to the suggested value.
- Cell 7: change `max_prompt_length=1536` to the suggested value, and set
  `num_train_epochs=2` or `3` when you have fewer than 100 pairs (it is 1 by
  default). Cell 7 also uses `max_length=MAX_SEQ_LENGTH`, so it follows cell 6.

The values are estimates. Do a short T4 smoke run first and lower them if
memory runs out. Very long SLMs may be dropped if the limit cannot be raised
enough.

**Step 4: full data collection.** Run the remaining evaluations (8 train SLMs
about 4 runs each, 2 held-out SLMs 2-3 runs each) at budget 15000, add all ids
to the two files, and repeat the dry run with `--verify-export`.

**Step 5: write the corrections.** Both confirmations are required:

```bash
uv run --project server python -m server.scripts.seed_house_rule_edits \
    --train-evaluations-file train_ids.txt \
    --reference-evaluations-file heldout_ids.txt --verify-export \
    --confirm SEED --confirm-target <LOCAL or fingerprint>
```

For the shared Neon database, set `SYNTHETIC_SEEDER_ALLOWED_DB_FINGERPRINTS`
first (section 3). The script writes everything in one transaction, tags each
row `house-rule-seed:<run-id>`, and prints:

- `Wrote N correction(s) for run-id <UUID>`,
- an "Export check" line that must say `(OK)`,
- the cleanup command (section 8). **Copy the run id somewhere safe.**

A random run id is created unless you pass `--run-id <UUID>`. Held-out
evaluations are never written. If every edited criterion was skipped the script
writes nothing and says so.

**Step 6: train.** From the Training Data page start a training job, then run
the Colab notebook with Run all. It produces `sme-v<n>.gguf`. The host owner
loads it at scale 0.0 and the Training Data page should show it as Loaded.
**Do not publish it.**

**Step 7: validate** (section 6), then **step 8: clean up** (section 8).

## 6. Validation and acceptance

Do these four steps in order, after the adapter is loaded at scale 0.0:

1. The Training Data page shows the new version as **Loaded** (and
   `GET /lora-adapters` lists it at scale 0.0).
2. Run `training/smoke_test_lora_serving.py`: valid replies with the adapter
   off and on, and at least one differing answer.
3. Run `training/evaluate_adapter.py` on the adapter zip's held-out pairs. Note
   the verdict, wins/losses/ties and the valid-JSON rate. It needs at least 20
   decisive pairs (`--min-decisive`) to say anything but "inconclusive".
4. In Model Validation, set Target = SME. Run **Model = Base** first, then
   **Model = the new version** (for example v6), each 2-3 times, on a
   **training SLM** and on a **held-out SLM**. Enter the expected scores from
   `expected_scores.csv`. (This needs the per-agent adapter branch merged, or
   running it locally.) Remember: backend still at budget 15000.

**The experiment passes when all three hold** (starting thresholds, adjustable
after the pilot):

- On edited criteria, the adapter's mean score is at least 0.5 above the
  base's, on the training SLM **and** on a held-out SLM.
- On control criteria, the mean absolute change is at most 0.25.
- The adapter's valid-JSON rate is no lower than the base's.

## 7. Reading failures

- **No change at all.** Either the adapter was not applied (retry the smoke
  tool with `--scale-mode global`) or it is undertrained (more pairs or more
  epochs).
- **Invalid JSON or worse scores.** Overtrained. Use fewer epochs or a lower
  learning rate.
- **Controls shift too.** The adapter learned "score higher everywhere".
  Retrain with more control criteria (a smaller edited set).

## 8. Cleanup

When validation is done, remove this run's corrections. The write step prints
the exact command; it looks like this:

```bash
uv run --project server python -m server.scripts.seed_house_rule_edits \
    --cleanup --run-id <UUID> --confirm CLEANUP --confirm-target <LOCAL or fingerprint>
```

It deletes only rows whose note equals `house-rule-seed:<run-id>`, that belong
to the dedicated user `house-rule-seed@local.test`, and whose action is `EDIT`.
If any tagged row is not for the SME agent it stops and deletes nothing. It
prints `Removed N correction(s)`. Earlier real decisions become the effective
ones again, and the evaluations, generations and documents are untouched.

Afterwards: restore `SME_TOTAL_PROMPT_BUDGET_CHARS` in `.env` to its old value
and restart the backend. Exit codes of the script: 0 = ok, 2 = aborted (nothing
written), 3 = refused by a safety check (missing confirmation, unsafe database
target).
