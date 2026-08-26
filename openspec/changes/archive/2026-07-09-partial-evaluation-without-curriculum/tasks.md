## 1. Backend submission contract

- [x] 1.1 Extend evaluation submission schema with explicit no-curriculum partial intent.
- [x] 1.2 Update evaluation creation validation so missing `curriculum_id` is accepted only with explicit partial intent.
- [x] 1.3 Persist enough partial/no-curriculum state for polling/results to explain the degraded mode.
- [x] 1.4 Add backend tests for full curriculum submission, missing curriculum rejection, and explicit partial acceptance.

## 2. Backend execution and synthesis

- [x] 2.1 Update orchestration/supervisor inputs so no-curriculum jobs do not run a misleading full Coordinator curriculum review.
- [x] 2.2 Persist a skipped/limited Coordinator outcome or otherwise ensure synthesis treats Coordinator as unavailable.
- [x] 2.3 Ensure synthesis normalizes weights across SME, GAD, and ITSO for no-curriculum partial evaluations.
- [x] 2.4 Expose partial/no-curriculum explanation in evaluation result or matrix payloads used by the frontend.
- [x] 2.5 Add backend tests for no-curriculum execution, synthesis partial flag, and matrix/result metadata.

## 3. Frontend setup flow

- [x] 3.1 Update evaluation setup so no ready curriculum shows Upload Curriculum, Change Program, and Continue Partial actions.
- [x] 3.2 Submit explicit no-curriculum partial intent when the user chooses Continue Partial.
- [x] 3.3 Preserve existing full-evaluation flow when a ready curriculum is selected.
- [x] 3.4 Add clear copy explaining that Coordinator/curriculum-grounded review is unavailable in partial mode.

## 4. Frontend result visibility

- [x] 4.1 Show partial/no-curriculum status in the evaluation header or setup summary after submission.
- [x] 4.2 Show partial/no-curriculum notice in the score dashboard/result experience.
- [x] 4.3 Ensure export/report actions do not imply a full curriculum-grounded evaluation when partial.

## 5. Verification

- [x] 5.1 Run focused backend evaluation/synthesis tests.
- [x] 5.2 Run frontend typecheck/build/lint as configured.
- [x] 5.3 Manually verify full curriculum evaluation still starts normally.
- [x] 5.4 Manually verify no-curriculum partial flow starts and produces honest partial messaging.
