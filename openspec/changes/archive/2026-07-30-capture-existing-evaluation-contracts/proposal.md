## Why

Curriculum extraction and SME engine scoring are implemented production behavior, but their durable rules live only in supporting design and progress notes. Future work on CCS-only reference ingestion and SME/Coordinator harnesses could regress those rules because OpenSpec has no canonical contract for them.

## What Changes

- Capture the existing CCS curriculum-reference extraction pipeline as a canonical contract, including its layout-specific fallback order, program-to-keyword mapping, and intentional Information Systems exclusion.
- Capture the existing SME engine-scoring contract: criterion measurement patterns, score bands, evidence rules, deterministic extraction, document slicing, and six-basket fact extraction.
- Link the Reference Library specification to the curriculum extraction contract.
- Preserve the existing implementation-history documents until the capture is validated; their deletion is explicitly outside this change.

## Capabilities

### New Capabilities
- `curriculum-reference-extraction`: Defines the established extraction behavior for multi-program CCS curriculum references.
- `sme-engine-scoring`: Defines the established deterministic scoring engine used by the Subject Matter Expert agent.

### Modified Capabilities
- `reference-library`: Clarifies that curriculum references use the documented curriculum extraction contract before embedding and retrieval.

## Impact

- Affected documentation: OpenSpec specifications and the existing supporting extraction and SME-scoring notes.
- Affected code behavior: none. This is a documentation capture of the current implementation.
- APIs, dependencies, data models, and migrations: unchanged.
