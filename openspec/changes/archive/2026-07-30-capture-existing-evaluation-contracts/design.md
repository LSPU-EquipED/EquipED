## Context

EquipED already has two specialized evaluation paths that were designed and
validated outside the OpenSpec workflow:

- Curriculum references use layout-aware CMO extraction so multi-program CHED
  documents can be limited to the Computer Science and Information Technology
  sections relevant to the current CCS reference path.
- The SME agent uses a deterministic scoring engine rather than asking one LLM
  call to assign all final rubric scores. A six-basket fact-extraction pass is
  followed by code-owned criterion scoring.

The implementation and its rationale are presently split across three
supporting documents. Those documents are valuable, but they are not canonical
contracts and therefore do not reliably protect the behavior during later
reference-ingestion or SME/Coordinator harness work.

## Goals / Non-Goals

**Goals:**

- Preserve the established behavior, terminology, and known limitations in
  modular OpenSpec contracts.
- Make the CMO program filter and SME scoring rules discoverable before future
  changes are made.
- Preserve empirical constraints such as page-level CMO chunks and the
  six-basket extraction split.
- Link curriculum ingestion to the existing Reference Library capability.

**Non-Goals:**

- Changing application code, data models, APIs, prompts, score thresholds, or
  model routing.
- Enforcing the wider Phase 3 CCS-only program scope in code or replacing the
  existing metadata-detection program list.
- Resolving known SME quality gaps or redesigning the upcoming Program
  Coordinator harness.
- Deleting the source design and progress documents in this change.

## Decisions

### Capture settled behavior as new focused capabilities

`curriculum-reference-extraction` and `sme-engine-scoring` are separate
capabilities because they have different owners, failure modes, and future
change cadence. Combining them into `reference-library` or
`multi-agent-evaluation` would recreate the broad-document problem this change
is correcting.

### Preserve code-owned scoring rather than model-owned final scores

The SME contract records one shared structured extraction pass, criterion
evidence validation, and deterministic registry scoring. It does not prescribe
a new model or prompt format. This captures the architecture without freezing
incidental implementation classes or response fields.

### Record empirical limitations as constraints, not hidden implementation lore

The curriculum contract records that table OCR cannot reliably reconstruct
per-course rows in multi-program CMO layouts, so selected sections are kept as
page-level chunks. The SME contract records that three baskets must stay
single-purpose after grouped prompts produced empty facts. These are observable
constraints future work must respect unless it is deliberately revalidated.

### Keep known gaps visible but non-normative

The A-01 Bloom-label normalization and A-04 legal-boilerplate classification
issues are recorded as known limitations. They do not become acceptance rules
or silently change current scoring behavior.

### Reference Library owns lifecycle, extraction owns chunk semantics

The Reference Library delta only establishes that curriculum references are
processed through the curriculum extraction contract before their chunks are
embedded. Lifecycle, health, access, preview, and rebuild behavior remain in
the existing Reference Library specification.

## Risks / Trade-offs

- **Contract drifts from existing code** → Each requirement is sourced from the
  current implementation and supporting notes; capture validation includes
  targeted existing tests and a source-to-spec review.
- **Over-specification prevents later harness improvements** → The contracts
  define observable guarantees and empirical constraints, not internal class
  layout or prompt wording.
- **Known quality gaps are mistaken for accepted behavior** → Mark them as
  limitations and create future work explicitly when they are addressed.
- **Historical notes are deleted prematurely** → Keep all three source
  documents unchanged until the capture change is validated and accepted.
