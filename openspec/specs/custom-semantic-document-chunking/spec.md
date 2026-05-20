# custom-semantic-document-chunking Specification

## Purpose
Define the deterministic, local, page-bounded semantic chunking contract for newly uploaded documents.

## Requirements

### Requirement: New uploads use deterministic semantic chunking
The system SHALL chunk newly uploaded PDF pages with a local deterministic, structure-aware chunker that prefers headings, paragraphs, and lists before falling back to sentence and word splitting.

#### Scenario: Structured page is chunked by document structure
- **WHEN** a newly uploaded PDF page contains recognizable headings, paragraphs, or list blocks
- **THEN** the system SHALL form chunks from those structural units before considering sentence-only splitting

#### Scenario: Weak structure falls back safely
- **WHEN** a page contains little or unreliable structure
- **THEN** the system SHALL fall back to sentence splitting and, if necessary, word-tail splitting instead of failing the upload

### Requirement: Semantic chunks remain page-bounded
The system SHALL keep every generated chunk within the bounds of a single source page.

#### Scenario: Logical content crosses a page break
- **WHEN** a logical section continues onto the next page
- **THEN** the system SHALL split the content at the page boundary and SHALL not create a cross-page chunk

### Requirement: Chunk sizing uses fixed deterministic thresholds
The system SHALL use deterministic sizing targets for new chunks, including a target of roughly 450 tokens, overlap of roughly 60 tokens, a hard maximum of 2000 tokens, and a minimum merge threshold that prevents tiny adjacent fragments when a safe merge is possible.

#### Scenario: Chunk is near the target size
- **WHEN** the current page content can be represented within the target size
- **THEN** the system SHALL emit a chunk near the target threshold instead of fragmenting the page unnecessarily

#### Scenario: Chunk exceeds the hard maximum
- **WHEN** a single structural unit or sentence run exceeds the hard maximum
- **THEN** the system SHALL split it deterministically by words so that emitted chunks stay within the maximum limit

#### Scenario: Tiny fragments can be merged
- **WHEN** a page would emit a fragment smaller than the minimum merge threshold and a safe adjacent merge exists on the same page
- **THEN** the system SHALL merge the fragment rather than emit an isolated tiny chunk

### Requirement: Overlap remains structure-aware with deterministic fallback
The system SHALL create overlap from a trailing structural or sentence boundary when available and SHALL fall back to a word-tail overlap when no cleaner boundary exists.

#### Scenario: Clean overlap boundary exists
- **WHEN** a chunk is followed by another chunk on the same page and the trailing content has a clear structural or sentence boundary
- **THEN** the system SHALL reuse that trailing unit for overlap

#### Scenario: No clean overlap boundary exists
- **WHEN** no structural or sentence boundary is suitable for overlap
- **THEN** the system SHALL use a deterministic word-tail fallback

### Requirement: Chunking preserves existing persistence and ingestion contracts
The system SHALL continue to emit the existing `DocumentChunkData` shape and SHALL keep the current `DocumentChunk` persistence contract unchanged.

#### Scenario: Ingested document is persisted without schema changes
- **WHEN** a newly uploaded PDF is ingested
- **THEN** the system SHALL persist chunks using the current document and chunk fields without requiring new database columns

### Requirement: Existing documents are not automatically reprocessed
The system SHALL apply the new chunking behavior only to newly uploaded documents and SHALL not automatically rechunk or reindex existing stored documents.

#### Scenario: Previously uploaded document remains unchanged
- **WHEN** the system deploys with this change
- **THEN** already stored documents SHALL keep their existing chunks until they are manually re-uploaded or otherwise explicitly reprocessed by a later change

### Requirement: SLM documents skip embedding after chunking
Student Learning Materials (SLMs) SHALL be chunked and persisted normally but SHALL NOT be embedded into ChromaDB. The embedding step SHALL be skipped entirely for documents with `source_type == "slm"`.

#### Scenario: SLM document upload completes without embedding
- **WHEN** an SLM document is uploaded and chunked
- **THEN** the system SHALL persist the chunks but SHALL NOT call the embedding service

#### Scenario: Reference document upload triggers embedding
- **WHEN** a reference document (syllabus or curriculum) is uploaded and chunked
- **THEN** the system SHALL persist the chunks AND embed them into ChromaDB
