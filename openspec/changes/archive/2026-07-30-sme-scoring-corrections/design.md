## Context

The SME engine already separates factual extraction from code-owned scoring, but
two model-output edge cases currently cross that boundary without sufficient
normalization:

- A-01 extraction can return a Bloom verb such as `compare` instead of the
  requested canonical level `analyze`; strict prefix normalization then treats
  it as lower-order.
- A-04 extraction can classify legal or administrative boilerplate as positive
  reinforcement; the current scoring function accepts its evidence unchanged.

These are correctness defects in stable semantic code, not reasons to redesign
the six-basket harness. A-05's hierarchy between broad intended learning
outcomes and detailed targets remains a separate institutional scoring-policy
decision.

## Goals / Non-Goals

**Goals:**

- Normalize a bounded set of recognized Bloom verbs without using fuzzy or
  model-dependent inference.
- Prevent non-feedback legal and administrative boilerplate from qualifying as
  A-04 feedback evidence.
- Keep genuine, quotable learner feedback eligible for A-04.
- Produce unit and calibration evidence for every intended score change.

**Non-Goals:**

- Changing A-05 objective hierarchy, score bands, basket membership, model
  routing, or database/API contracts.
- Reworking the SME/Coordinator harness or broadening Bloom classification into
  a new NLP system.
- Treating all references to a law, section, or policy as boilerplate without
  high-confidence legal evidence.

## Decisions

### Preserve canonical-prefix compatibility and normalize four observed aliases

The normalizer will preserve the existing acceptance of normalized values that
begin with a canonical level (for example, legacy `apply-level` output). It
will then map only the four observed exact aliases:

| Canonical level | Accepted non-canonical values |
| --- | --- |
| `remember` | `list` |
| `understand` | `explain` |
| `analyze` | `compare` |
| `evaluate` | `justify` |

Alias lookup is exact after trimming and case-folding; it does not use fuzzy or
similarity matching. Unknown values retain current conservative treatment rather
than being silently promoted. Extraction prompts will explicitly require the
canonical category name rather than the example action verb.

### Combine A-04 prompt guidance with a narrow deterministic evidence guard

Both the per-criterion and grouped A-04 prompts will state that legal
disclaimers, copyright notices, fair-use statements, administrative boilerplate,
and institutional-policy notices are not feedback mechanisms. They will also
request a minimal quote directly evidencing feedback.

The compute path will first normalize the feedback type, then apply a guard only
to proposed `positive_reinforcement` evidence. It will reject only a
high-confidence boilerplate phrase: an all-rights-reserved notice, a copyright
ownership/year notice, a fair-use disclaimer, a reproduction/distribution
prohibition, or an `under/pursuant to Section ... RA/Republic Act` notice. An RA
citation alone is not boilerplate. Evidence containing a high-confidence notice
and an explicit learner-directed praise cue remains eligible; otherwise the
mechanism is rejected. Generic `section` and `policy` wording is never enough to
reject evidence.

### Preserve A-05 behavior explicitly

No text-similarity or hierarchy heuristic will be introduced for broad ILOs and
specific targets. The future policy decision must be made with CID/faculty
review and real SLM examples before changing the A-05 denominator.

### Validate changed scores instead of assuming parity

Frozen synthetic facts prove the deterministic rules. After code validation, a
manual local gate will use at least two de-identified SLMs with recorded
human-reviewed SME outcomes. It will record the local document identifiers,
configured model and prompt/version identifiers, code revision, intended A-01
and A-04 changes, and all unrelated score bands without committing source text.
Acceptance requires intended corrections to agree with review and no unreviewed
band change to `OP-01`, `OP-02`, or `OP-03`.

## Risks / Trade-offs

- **A valid verb is not in the map** → Unknown terms remain conservatively
  unpromoted; add an alias only after an observed, reviewed output and test.
- **Legal filter over-matches feedback** → Limit it to normalized
  `positive_reinforcement`, high-confidence complete phrases, and test mixed
  legal-plus-praise evidence plus legal-themed answer keys, rubrics, and
  remediation.
- **Prompt changes alter extraction beyond the target cases** → Cover both
  grouped and per-criterion paths, compare known examples, and retain the
  bounded code-side guards.
- **A-05 remains inaccurate for some documents** → Keep it visible in the spec
  and defer it until an institutional rule and calibration examples exist.

## Migration Plan

No data migration is required. Deploy with the updated prompts, normalization,
and evidence filter; future evaluations use the correction. If calibration
shows an unintended regression, revert the bounded map/filter and prompt text
as one change.
