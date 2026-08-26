## Context

ITSO currently performs one normal agent call at a nonzero temperature. Repeated evaluation of the same SLM may therefore vary even when document chunks and rubric context are unchanged. Runtime changes such as model fallback, JSON-repair retry, and prompt-budget trimming are not recorded as a coherent ITSO evidence snapshot, making drift difficult to diagnose.

The baseline must improve reproducibility without claiming that a hosted LLM is mathematically deterministic. Human review remains authoritative. External citation verification, policy retrieval, plagiarism detection, and score decision tables are separate follow-on work.

## Goals / Non-Goals

**Goals:**
- Make ITSO calls use deterministic generation settings.
- Preserve enough non-sensitive provenance to explain a score and compare repeat runs.
- Provide local deterministic citation/reference prechecks as evidence signals, not legal or plagiarism conclusions.
- Make unsupported, unavailable, or insufficient evidence explicit in ITSO output.
- Establish an offline repeat-run benchmark and regression tests for fixed fixtures.

**Non-Goals:**
- Guarantee byte-identical output from a remote model provider.
- Call Crossref, OpenAlex, Exa, or any external service.
- Send SLM text, chunks, titles, filenames, or author data externally.
- Detect plagiarism, determine legal compliance, or replace human review.
- Change synthesis weights or introduce an institution-approved deterministic 1–4 score table.

## Decisions

### 1. Use an ITSO-specific zero-temperature setting

ITSO receives a dedicated validated setting with a default of `0.0`; its prompt version and normal agent contract remain intact. This is preferable to lowering global LLM temperature because other agents may retain intentionally different behavior. Provider-level variation can still occur, so zero temperature is a reduction in sampling variability, not a correctness guarantee.

### 2. Capture a bounded provenance snapshot in a new agent-result provenance column

The baseline adds a nullable JSON/JSONB `provenance` column to `agent_results` (one Alembic migration). One column, one schema version, durable audit record. It is ITSO-generated but the column is agent-agnostic for future use.

Provenance is assembled in two phases:

**Phase 1 — frozen before dispatch (supervisor precomputation):**
- ordered SLM chunk identifiers;
- prompt/rubric version identifier or hash;
- local precheck result version, compact output, and hash.

**Phase 2 — finalized after execution (agent callback):**
- requested model identifier and temperature;
- actual served model identifier (may differ from requested on fallback);
- fallback occurred flag;
- JSON repair occurred flag;
- context/prompt trim flags.

It excludes raw prompt text, raw SLM text, full chunk text, credentials, and external request payloads. Existing result ownership controls apply.

### 3. Create local deterministic prechecks before ITSO prompt assembly

A pure local utility consumes the already-authorized SLM evidence and returns stable signals: bibliography/reference-section presence, count of candidate references, count of in-text citation patterns, extracted DOI count, and simple reference-to-citation coverage. It does not score the rubric or label plagiarism. Stable ordering and versioned extraction rules ensure the same text gives the same precheck output.

### 4. Feed compact evidence status, not raw certainty, to ITSO

The ITSO prompt receives only the bounded precheck summary and must classify evidence as `VERIFIED`, `NOT_VERIFIED`, `INSUFFICIENT_EVIDENCE`, or `TOOL_UNAVAILABLE` where relevant. `NOT_VERIFIED` means local evidence did not confirm a condition; it never means misconduct or invalid citation.

### 5. Freeze an evaluation's evidence before dispatch

Supervisor precomputation produces the ITSO chunk-id ordering and local precheck once per evaluation. The immutable snapshot is passed to the agent call and persisted with its result. This prevents retry or later display code from silently rebuilding different evidence.

### 6. Benchmark consistency offline

The repository provides a fixture-driven harness that runs ITSO prompt assembly/prechecks repeatedly with a deterministic fake client and records normalized criterion-score deltas. Live-provider repeat runs remain an explicit manual benchmark because provider infrastructure can vary. A drift result is diagnostic and advisory; it does not alter an evaluation job automatically.

## Risks / Trade-offs

- **Remote provider output can vary at temperature zero** → Preserve actual model/fallback/repair provenance and benchmark real-provider behavior manually.
- **Metadata could expose sensitive content** → Persist IDs, counts, flags, versions, and hashes only; never raw SLM/reference text.
- **Citation regexes can misclassify styles** → Mark signals as local prechecks, retain versioning, and use `INSUFFICIENT_EVIDENCE` rather than infer a negative conclusion.
- **Prompt additions can increase token use** → Cap the compact precheck summary and reuse already retrieved evidence.
- **Fallback undermines direct comparison** → Record actual served model; benchmark comparisons group by model/provenance.

## Migration Plan

1. Deploy with the ITSO temperature default at zero and provenance capture enabled.
2. Existing results remain readable without provenance; UI/API consumers treat missing fields as unavailable historical data.
3. Run fixture and representative manual repeat benchmarks before treating consistency as improved in operational guidance.
4. Roll back by disabling the ITSO-specific setting/precheck injection; existing metadata remains inert and no schema rollback is needed.

## Open Questions

- What repeat-run tolerance should institutional reviewers accept for live provider benchmarks: exact criterion match, subtotal delta, or both?
- Which citation styles should the initial local precheck recognize beyond DOI and author-year/numeric patterns?
- Which ITSO evidence-status fields should be visible to faculty versus only to admins/reviewers?
