# Evaluating an adapter: is it better than the plain model?

`evaluate_adapter.py` answers one question: on cases a reviewer corrected, does
the served model with the adapter land closer to the reviewer's scores than the
same model without it? It prints a verdict (better, worse or inconclusive) and
can write a JSON report.

It needs a running llama-server with the adapter loaded at scale 0.0 (see
`training/serving-lora-adapter.md`). It uses only the Python standard library.

## What you need

1. **An adapter zip trained with the grouped-split notebook.** The training
   notebook (`docs/colab/dpo_training_template.ipynb`) holds out whole
   evaluations, prints how many, and saves them inside the zip as
   `heldout_pairs.jsonl`. An adapter trained with fewer than 20 pairs, or from a
   single evaluation, has no held-out set and cannot be evaluated.
2. **The adapter loaded on the server.** Convert the zip to a GGUF LoRA
   (`docs/colab/adapter_to_gguf_template.ipynb`) and ask the host owner to load
   it with `--lora-scaled <file>.gguf:0.0`. Every new adapter needs this step
   before it can be evaluated; the evaluation runs on the exact served
   artifact, not on the Colab copy.
3. **The server URL and API key**, in `LLM_API_BASE` and `LLM_API_KEY` (or
   `--base-url` / `--api-key`; the environment is safer, arguments end up in
   shell history). The key is never printed or written to the report.

## Run it

From the repo root, PowerShell:

```powershell
$env:LLM_API_BASE = "https://<host>/v1"
$env:LLM_API_KEY  = "<key>"
python training/evaluate_adapter.py --adapter-zip path\to\adapter.zip `
    --report-json report.json
```

Useful options:

| Option | Default | Meaning |
|---|---|---|
| `--limit N` | all | evaluate only the first N held-out pairs (each pair is 2 real requests on the host's GPU) |
| `--min-decisive N` | 20 | fewest decisive (win or loss) pairs before a verdict other than inconclusive is possible |
| `--alpha A` | 0.05 | significance level of the sign test |
| `--max-tokens N` | 2048 | reply length limit; too small a value cuts JSON off and counts as invalid |
| `--scale-mode global` | request | use if the server ignores the per-request scale; the script resets the scale to 0.0 afterwards |
| `--heldout FILE` | | evaluate a bare `heldout_pairs.jsonl` instead of a zip (the tool cannot verify it is disjoint from training data, so a `better` verdict assumes you passed only pairs the adapter was NOT trained on) |

## Read the result

For every held-out pair the script builds an answer key: the criteria whose
score the reviewer changed, with the reviewer's score. It sends the pair's
prompt with the adapter off and then on, and compares how far each reply's
scores are from the answer key.

- **win / loss / tie**: the adapter's reply was closer / further / equally far.
  An invalid reply counts as the worst possible error.
- **sign test p**: the chance of a split this lopsided if the adapter made no
  difference (ties are left out).
- **VERDICT**: `better` needs more wins than losses, p below `--alpha`, at least
  `--min-decisive` decisive pairs, and no more invalid JSON than the plain
  model. `worse` needs more losses than wins, p below `--alpha` and at least
  `--min-decisive` decisive pairs; invalid JSON does not block it. Anything else is `inconclusive`, and
  the reasons are printed.

Exit code: 0 better, 1 worse or inconclusive, 2 the run could not happen (or the JSON report could not be written after the verdict was printed).

## What a verdict does and does not mean

- The held-out pairs are only cases a reviewer **changed**. A `better` verdict
  means the adapter fixes known mistakes; it says nothing about harm to cases
  reviewers approved.
- With few pairs a verdict is weak evidence. Twenty decisive pairs is the floor
  for saying anything; real confidence needs many more.
- Output is advisory. A person decides whether an adapter goes into use.

## Common problems

| Message | Cause and fix |
|---|---|
| `this adapter has no held-out set` | The zip has no `heldout` block: too few pairs, one evaluation, or trained with the older notebook. Retrain, or pass `--heldout` with pairs the adapter was NOT trained on (the tool cannot check this, so a bare file gives no guarantee). |
| `no LoRA adapter is loaded on the server` | Ask the host to start llama-server with `--lora-scaled <file>.gguf:0.0`. |
| `WARNING: the adapter's replies are identical...` | The adapter is probably not being applied. Check `GET /lora-adapters` and retry with `--scale-mode global`. |
| adapter valid-JSON rate below the plain model's | The adapter damaged the output format; a `better` verdict is withheld. |
| HTTP 401/403 | Wrong or missing API key. |
