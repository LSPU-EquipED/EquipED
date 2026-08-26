## Why

Faculty cannot proceed when the system fails to detect a program or when no ready curriculum reference exists for the selected program. This blocks otherwise useful SME, GAD, and ITSO review even though the missing curriculum only limits Coordinator/curriculum-grounded evaluation.

## What Changes

- Add an honest partial-evaluation path when no curriculum reference is available.
- Keep the full evaluation path curriculum-grounded when an embedding-ready curriculum exists.
- Replace “detected reference required” UX with a confirmed curriculum decision:
  - detected program → suggest curriculum → faculty confirms;
  - missing program → faculty selects program;
  - missing/unready curriculum → faculty can upload/rebuild/change program or continue as partial.
- Allow evaluation submission without `curriculum_id` only when the request explicitly chooses partial/no-curriculum mode.
- Skip or mark Coordinator as limited when curriculum is missing; do not pretend curriculum-grounded scoring occurred.
- Surface partial status/copy in the evaluation UI and result summary.

## Capabilities

### New Capabilities
- `partial-evaluation-without-curriculum`: Defines the explicit partial evaluation mode used when no ready curriculum reference is available.

### Modified Capabilities
- `evaluations`: Evaluation submission and synthesis must allow explicit partial/no-curriculum jobs while preserving full curriculum-grounded jobs.
- `program-confirmed-curriculum-selection`: Setup flow must offer clear alternatives when curriculum suggestion cannot provide a ready curriculum.

## Impact

- Backend evaluation submission schema/service will need an explicit partial mode flag or equivalent intent field.
- Evaluation orchestration/supervisor must avoid running a misleading full Coordinator curriculum evaluation when no curriculum is attached.
- Synthesis and matrix output must mark the result partial/limited and normalize weights over available successful domains.
- Frontend evaluation setup must offer Upload Curriculum, Change Program, and Continue Partial actions when no ready curriculum exists.
- No new external dependencies are expected.
