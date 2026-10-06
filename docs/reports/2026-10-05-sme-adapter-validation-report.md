# SME adapter validation report (adapter v7)

Date: 2026-10-05. Scope: SME agent only. Status: v7 result final; a stronger retrain (v8) was in progress when this was written.

## 1. Question

Does the DPO training pipeline change how the SME model scores when it is trained on reviewer corrections? To test that without needing real reviewers, we taught the model an invented rule and checked whether its scores moved the way the rule says. The test is about **behavior change**, not about the adapter being better.

**The rule:** raise the score by 1 (maximum 4) on the odd criteria OP-01, OP-03, OP-05, A-01, A-03 and A-05. The other criteria (OP-02, OP-04, A-02, A-04) are controls and should not change.

## 2. Method

| Step | What was done |
|---|---|
| Documents | 10 SLMs: 8 for training, 2 held out (`ITST-302-Module-1_-SLM-3_heldout`, `...-SLM-4_heldout`) |
| Base answers | SME evaluations on the base model with the prompt budget at 15,000 characters. Only generations that were valid on the first try (`ok`) become training pairs. Result: **32 usable pairs** |
| Corrections | A script (`seed_house_rule_edits.py`) wrote **94 score corrections** under run id `dab64dac-2ed5-408d-b05b-29b89ca7090f`. It needs two confirmations, refuses evaluations that used an adapter, writes in one transaction, and can be undone by run id |
| Training | Colab T4, Gemma 3 4B (4-bit), LoRA r=16, DPO beta 0.1, learning rate 5e-6, 3 epochs, 12 steps, effective batch 8. 25 pairs trained, 7 held back by the notebook. About 35 minutes |
| Serving | The adapter file `sme-v7.gguf` was loaded on the model server at scale 0.0 (off by default) and switched on per request |
| Benchmark | Model Validation, SME only. Each SLM was scored once with Base and once with v7. The system records the requested and applied adapter for every run. All three v7 runs record `applied: sme-v7` |

## 3. Results

Held-out SLMs only have a clean base answer for one group of criteria each (SLM-4: OP, SLM-3: A), so only those criteria are compared for them.

| SLM | Edited criteria that went up | Mean change on edited criteria (hoped: +0.5 or more) | Control criteria that changed (hoped: none) |
|---|---|---|---|
| Capstone SLM 4 (training) | 1 of 6 | +0.17 | 1 of 4 |
| ITST-302 SLM-4 (held out, OP criteria) | 1 of 3 | +0.33 | 0 of 2 |
| ITST-302 SLM-3 (held out, A criteria) | 0 of 3 | +0.00 | 0 of 2 |
| **All together** | **2 of 12** | **+0.17** | **1 of 8** |

- **No criterion scored a 4 with v7 in any run.** The rule asks for 3 to become 4.
- The three criteria that changed all went from 2 to 3 (A-05 and OP-05, which are edited, and A-04, a control). That looks like ordinary run-to-run variation, not the rule.
- **Valid answers:** both Base and v7 had 4 of 6 answer groups valid on the first try and 2 of 6 repaired. v7 did not make the output format worse.

### Per-criterion scores (Base to v7)

| Criterion | Role | Capstone SLM 4 | SLM-4 (held out) | SLM-3 (held out) |
|---|---|---|---|---|
| A-01 | edited | 3 to 3 | - | 3 to 3 |
| A-02 | control | 3 to 3 | - | 3 to 3 |
| A-03 | edited | 3 to 3 | - | 3 to 3 |
| A-04 | control | 2 to 3 | - | 3 to 3 |
| A-05 | edited | 2 to 3 | - | 3 to 3 |
| OP-01 | edited | 3 to 3 | 3 to 3 | - |
| OP-02 | control | 3 to 3 | 3 to 3 | - |
| OP-03 | edited | 3 to 3 | 3 to 3 | - |
| OP-04 | control | 3 to 3 | 3 to 3 | - |
| OP-05 | edited | 3 to 3 | 2 to 3 | - |

## 4. Interpretation

The pipeline works end to end, and the adapter was applied, but **the effect did not meet the target** (mean change +0.17 against a target of +0.5, with no score of 4). The most likely cause is that the training was too gentle: 12 weight updates at a learning rate of 5e-6 barely move the model. The corrections differ from the original answers only in a few score digits, so the training signal is small. This points to undertraining, not to a broken pipeline.

## 5. What was verified

- Per-agent adapter versions can be published, selected and benchmarked. Requested and applied adapters are recorded for every run.
- The model server loaded two adapters at once (SME v7 and GAD v2) and selected them per request.
- The Colab notebook runs end to end on a T4, uploads a validated adapter and converts it to GGUF.
- No adapter was published, so scoring for faculty stayed on the base model throughout.

## 6. Limits of this result

- One run per condition: Base and v7 were each scored once per SLM, so ordinary run-to-run variation is not measured.
- Only three SLMs, and the held-out SLMs cover half of the criteria each.
- The expected scores are the invented rule's values, not human scores. "Closer to the expected scores" means "followed the rule". It does not mean closer to a human reviewer.
- The preference margin from the v7 training run was **not captured**: the notebook deleted the training log before it could be read. This is what the training summary feature (PR #377) was added to fix, so later runs record margin, accuracy and loss with each adapter.
- Some expected scores were typed by hand, and one pair had two criteria swapped. The Compare tab now only compares criteria whose expected scores match in both runs.

## 7. Next steps

1. **Stronger retrain (v8)** on the same 32 pairs: learning rate 5e-5 (was 5e-6), gradient accumulation 2 (was 8, about 4 times more updates), 4 epochs. It was running on Colab when this report was written.
2. Benchmark v8 with the new Re-run button and compare it to Base in the new Compare tab.
3. If v8 changes the edited criteria without moving the controls, the pipeline is confirmed. If it breaks the output or moves the controls, lower the learning rate (2e-5).
4. Run the cleanup of the 94 corrections (`--cleanup --run-id dab64dac-2ed5-408d-b05b-29b89ca7090f`), then restore the local settings (prompt budget 28,000; OCR language `eng+fil`).
5. Never publish the experiment adapters. They teach an invented rule.

## 8. Tools added during this work

- **Training summary** for adapter versions (merged, PR #377): margin, accuracy and loss saved with each adapter and shown in the admin page.
- **House-rule script** and runbook (merged, PR #377).
- **SME JSON fix** for raw line breaks in model output (merged, PR #377).
- **Re-run** button on Model Validation history: preloads the agent, stored SLM and expected scores, and creates a new entry without changing the original.
- **Compare** tab: pick a Base run and an adapter run and see mean error against the expected scores, exact matches, closer/same/farther counts and a "Better" highlight.
