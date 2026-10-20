# Remaining evaluation tasks

ITSO adapter 3 requires credential-free public search and available source-page retrieval for criteria 1 and 2 on every run, with ordinary five-criterion advisory scoring and the existing specialist UI. The owner approved lesson/topic-name search when no bibliography is detected, with missing citations reported rather than blocking otherwise queryable modules. Local search is enabled; no Brave key is required for current evaluations. SLM_4 completed through the real API and worker with a public-topic search, a retrieved source body passage and five scores, evaluation `5fc70913-6abe-4945-96a4-bac017741208`. This establishes live pipeline execution, not expert accuracy. Governance, attachment and manual fact-decision interfaces are retired; historical assessments and applied migrations remain intact. See `itso-evidence-first-release.md` for operation and browser verification limits.

Updated: 2026-10-19. This tracks the current SME work and outstanding experiment follow-ups. GAD package connection was verified on 2026-10-19; post-training steps remain pending. Other statuses reflect saved local reports, not a fresh database audit.

| Task | Status | Remaining work |
|---|---|---|
| SME rubric-guided source selection | **In progress** | Implementation and offline verification are complete. Restart the backend and run a new SME evaluation on the real ITST 302 SLM. Inspect the saved input, evidence, reasoning and scores. Then check additional SLM layouts and changed rubric wording before accepting the trial. |
| SME absence findings without fabricated quotations | Implemented; live validation pending | Confirm a new SME run can return an explicit absence finding with no quotation and a justified rubric score. Missing content in a selected excerpt must not be treated as proven whole-document absence. |
| GAD v3 synthetic experiment | Comparisons completed | Saved results: training-document MAE Base 0.78 vs v3 0.74; four held-out documents Base/v3 both MAE 0.50 and 12/20 exact matches. No overall held-out improvement was established. Preserve these results separately from the next experiment. |
| Focused GAD-02 experiment | Reviewed package connected; training pending | Restart the updated backend, confirm 12 GAD pairs in Admin Training Data, start a new run, and download its notebook. Only GAD-02 is edited; other criteria retain Base stability controls. After training, test fitting on the 12 training documents and compare Base, v3, and the new model on six fresh held-out SLMs. Keep held-out examples out of training. |
| SME OP-05 learning diagnosis | Pending follow-up | The saved Base/v13 comparison did not demonstrate the intended learning. Inspect training provenance, optimization steps and preference movement before deciding on a retrain. Keep this separate from the source-selection trial. |

## Focused GAD-02: next steps and post-training checklist

The reviewed source contains 12 full-response pairs. Only GAD-02 is edited;
the other four criterion sections retain genuine Base outputs as stability
controls, not independently verified expert scores. The six fresh held-out
SLMs remain unevaluated and outside training. Reference targets are 4 for
two women/two men, and 1 for either single-gender roster.

- [ ] Restart the updated backend, select GAD in Admin Training Data, confirm
      **12 pairs**, start a new training run, and download its new notebook.
- [ ] Complete Colab training and confirm that the fine-tuned model, training
      summary and required artifacts were saved and uploaded successfully.
- [ ] Inspect the saved training summary: source/job identity, exact pair
      counts, training/internal-held-out split, dropped pairs, optimizer
      updates and recorded training settings. Do not assume all 12 source
      pairs were actually used for optimization.
- [ ] Record the new GAD version and artifact hashes, and verify that its
      training job matches the approved GAD-02 package. Preserve GAD v3.
- [ ] When available, have the host load the new version and verify that
      Model Validation explicitly selects and actually applies that version.
- [ ] Re-run the 12 source SLMs with the new model, keeping original documents,
      rubric and fixed expected targets. Compare against their saved Base
      results; distinguish actual training examples from internal hold-outs
      and dropped examples using the saved split. Keep all runs in history.
- [ ] Evaluate the six fresh held-out SLMs with Base, GAD v3 and the new model.
      Use the same uploaded document, source packet, rubric and approved
      GAD-02 target per comparison. Do not change targets after seeing outputs.
- [ ] Compare GAD-02 MAE/exact matches, correct women/men counts in reasoning,
      exact roster evidence, other-criterion drift, and fallback/repair or
      grounding warnings. Keep captured reasoning distinct from stored
      fallback justifications. Do not count Base stability controls as
      independent expert accuracy labels or dilute the primary GAD-02 metric
      with the other four criteria.
- [ ] Save a final experiment report separating fitting results from fresh
      held-out results, including failures and unchanged/worse outcomes.
      Decide on another training experiment only after this analysis. Do not
      automatically publish the model for faculty use.

If the host is unavailable for operational reasons, retain the trained
version and defer the model-dependent evaluations; host availability alone
is not a reason to train another version. Keep the six external held-out
SLMs out of future training if they are to remain an untouched benchmark.

Current files: [experiment summary and dataset links](../.test-artifacts/gad02-focused-2026-10-19/SUMMARY.md),
[connection verification](../.test-artifacts/gad02-focused-2026-10-19/approved-training-package/connection-summary.json),
and [Admin training package workflow](reviewed-training-packages.md).

## Current SME trial acceptance checks

- Relevant objectives, tasks, expected outputs and rubrics reach the model when requested by the criteria; irrelevant cover text does not crowd them out.
- Renamed/reordered headings and revised rubric descriptions remain usable. Unfamiliar concepts can still require heuristic updates.
- Selected text remains verbatim and within the existing prompt budget, including the repair allowance.
- Evidence supports the criterion and explanation; a valid quotation alone does not establish a correct score.
- Scope remains SME only, with no schema changes, SLM embeddings or extra model calls.

The selector combines predefined section/task patterns with vocabulary derived from the criteria attached to each evaluation request. It is not semantic retrieval and cannot guarantee complete document coverage.

## Evidence and local review material

- SME trial: `.test-artifacts/sme-section-selection-preview/SUMMARY.md`. Recorded verification: 370 harness/SME tests passed, with lint, formatting and independent review passing. The preview did not run a new scoring inference.
- Historical GAD v3 experiment: `.test-artifacts/gad-synthetic-experiment-2026-10-16/realistic-v2/gad-v3-training-validation/summary.json` and `gad-v3-heldout-validation/REPORT.md`. These supersede the earlier candidate-review stage: training and held-out comparisons are complete. The four old held-out SLMs are separate from the six fresh GAD-02 test documents.
- Current GAD-02 experiment: `.test-artifacts/gad02-focused-2026-10-19/SUMMARY.md`, `approved-training-package/connection-summary.json`, and `approved-training-package/pairs.jsonl`. The user approved the edits and the exact 12-pair package is connected. Training and post-training evaluation remain pending.
- SME learning diagnosis: `.test-artifacts/sme-op05-focused-2026-10-16/synthetic-source-review-v1/adapter-rerun-analysis-v1/analysis.md`. Both Base and v13 had OP-05 MAE 1.3333 and 0/6 exact matches on the six training-document checks; this is not unseen-document validation.

Local artifacts are ignored by Git. Earlier source-selection and absence changes remain uncommitted. The old four-pair replacement plan preserved in the stash is explicitly superseded and is not a remaining execution task.
