## MODIFIED Requirements

### Requirement: SLM documents are direct evaluation input
Student Learning Materials (SLMs) SHALL be treated as direct evaluation input and SHALL NOT be embedded into the vector store. Syllabus, curriculum, rubric, and policy documents MAY be embedded into source-appropriate local vector collections. Policy embeddings SHALL be used only for internal ITSO evidence retrieval and SHALL NOT make policies faculty-visible references.

#### Scenario: SLM document is uploaded
- **WHEN** a document with `source_type == "slm"` is uploaded
- **THEN** the system SHALL ingest and chunk the document but SHALL NOT embed it into ChromaDB

#### Scenario: Policy document is uploaded
- **WHEN** an authenticated admin uploads a policy document with a recognized policy area
- **THEN** the system SHALL chunk and embed it into the dedicated local policy collection
- **AND** SHALL NOT expose the policy as a faculty-selectable evaluation reference

### Requirement: chroma_stored validation is conditional on document type
The `chroma_stored` readiness gate SHALL apply to every document type that requires embedding, including syllabus, curriculum, rubric, and policy documents. SLM documents SHALL be exempt from the `chroma_stored` check during evaluation submission validation.

#### Scenario: Embedded document without chroma_stored is not ready
- **WHEN** a syllabus, curriculum, rubric, or policy document has `chroma_stored == False`
- **THEN** the system SHALL treat that document as unavailable for its source-appropriate retrieval path

#### Scenario: SLM document without chroma_stored is accepted
- **WHEN** an evaluation is submitted with an SLM document that has `chroma_stored == False`
- **THEN** the system SHALL accept the submission (SLMs do not require embedding)
