# EquipEd Technical Design Document (TDD)
## A Multi-Agent SLM Evaluation System for Quality Assurance using NLP

**Institution:** Laguna State Polytechnic University – Santa Cruz Campus, College of Computer Studies  
**Proponents:** Alberto, Marc Justin G. · Aquino, Jose V. III · Garin, Jeremy M.  
**Version:** 0.2 | **Status:** `DRAFT — Pending Data Completion`  
**PRD Reference:** EquipEd PRD v0.3

---

## Table of Contents

1. [Document Purpose](#1-document-purpose)
2. [System Architecture](#2-system-architecture)
3. [Layer 1 — Document Ingestion & Preprocessing](#3-layer-1--document-ingestion--preprocessing)
4. [Layer 2 — Embedding & Vector Storage](#4-layer-2--embedding--vector-storage)
5. [Layer 3 — Multi-Agent Evaluation](#5-layer-3--multi-agent-evaluation)
6. [Layer 4 — Synthesis & Scoring](#6-layer-4--synthesis--scoring)
7. [Layer 5 — Preference Logging & Prompt Optimization](#7-layer-5--preference-logging--prompt-optimization)
8. [Database Schemas](#8-database-schemas)
9. [API Specification](#9-api-specification)
10. [Frontend Architecture](#10-frontend-architecture)
11. [Component Integration Map](#11-component-integration-map)
12. [Deferred Components](#12-deferred-components)
13. [Open Technical Items](#13-open-technical-items)

---

## 1. Document Purpose

This TDD is the implementation reference for EquipEd. It defines every architectural decision, data contract, module boundary, API shape, database schema, and pseudocode specification needed to build the system described in PRD v0.3.

This document is written for two audiences:

- **The development team** — as the authoritative source of implementation decisions, replacing ad-hoc design choices during development
- **An AI coding agent** — as architectural context so the agent understands the system it is operating within when generating, reviewing, or modifying code

This TDD intentionally excludes what-and-why framing (that belongs in the PRD). Every section here answers **how**.

### 1.1 PRD Traceability

All functional and non-functional requirements from PRD v0.3 are traceable to sections of this document:

| PRD Requirement Range | TDD Section |
|---|---|
| FR-01 to FR-05 (Document Submission) | Section 3 |
| FR-06 to FR-11 (Automated Evaluation) | Section 5 |
| FR-12 to FR-15 (Scoring & Reports) | Section 6 |
| FR-16 to FR-21 (Web Dashboard) | Section 10 |
| FR-22 to FR-25 (Preference Logging) | Section 7 |
| NFR-01 (Accuracy) | Section 5.4, Section 6 |
| NFR-02 (Language Support) | Section 4.1 |
| NFR-03, NFR-04 (Privacy & Residency) | Section 4.2, Section 8 |
| NFR-06 (Processing Time) | Section 3.3, Section 5.5 |
| NFR-07 (Maintainability) | Section 5.2, Section 7.3 |

---

## 2. System Architecture

### 2.1 Overview

EquipEd is a five-layer pipeline system with an asynchronous feedback loop. The layers execute sequentially per evaluation job. The feedback loop runs independently and does not block evaluation.

```
CLIENT (React + Vite + TanStack)
        │
        │ HTTPS / REST
        ▼
BACKEND API (FastAPI)
        │
        ├─── Layer 1: Document Ingestion & Preprocessing
        │         PyMuPDF → Conditional Tesseract OCR
        │         → LangChain SemanticChunker
        │         → TF-IDF Corpus Weighting
        │
        ├─── Layer 2: Embedding & Vector Storage
        │         SentenceTransformers (multilingual-MiniLM-L12-v2)
        │         → ChromaDB (local, metadata-filtered collections)
        │
        ├─── Layer 3: Multi-Agent Evaluation
        │         LangChain AgentExecutor
        │         Supervisor / Router Agent
        │           ├── SME Subagent
        │           ├── Program Coordinator Subagent
        │           ├── GAD Unit Subagent
        │           └── ITSO Subagent
        │         LLM Backbone: claude-haiku-4-5 (Anthropic API)
        │
        ├─── Layer 4: Synthesis & Scoring
        │         Score Aggregation Engine
        │         Report Generator
        │         Monitoring Matrix Updater
        │
        └─── Layer 5: Preference Logging & Prompt Optimization
                  PostgreSQL (preference_logs, prompt_versions)
                  Admin Prompt Review Interface
```

### 2.2 Technology Stack

| Layer | Component | Technology | Version |
|---|---|---|---|
| Frontend | Web dashboard | React + Vite + TanStack Router + TanStack Query | Latest stable |
| Backend | REST API | FastAPI (Python) | ≥ 0.111 |
| Task Queue | Async evaluation jobs | FastAPI BackgroundTasks (Phase 1) | — |
| PDF Parsing | Text extraction | PyMuPDF (fitz) | ≥ 1.23 |
| OCR | Scanned page extraction | Tesseract via pytesseract | ≥ 5.3 |
| Chunking | Semantic segmentation | LangChain SemanticChunker | ≥ 0.2 |
| Term Weighting | Key term analysis | scikit-learn TfidfVectorizer | ≥ 1.4 |
| Embedding | Text vectorization | SentenceTransformers `paraphrase-multilingual-MiniLM-L12-v2` | ≥ 3.0 |
| Vector Database | Embedding store & retrieval | ChromaDB | ≥ 0.5 |
| LLM | Agent reasoning | `claude-haiku-4-5` via Anthropic Python SDK | Latest |
| Agent Framework | Orchestration | LangChain AgentExecutor | ≥ 0.2 |
| Relational DB | Metadata, logs, schemas | PostgreSQL | ≥ 15 |
| ORM | Database access | SQLAlchemy + Alembic | ≥ 2.0 |
| File Storage | Uploaded PDFs | Local filesystem (institutional server) | — |

### 2.3 Evaluation Job Lifecycle

Every document submission triggers an **Evaluation Job**. The lifecycle is:

```
SUBMITTED → PREPROCESSING → EMBEDDING → EVALUATING → SYNTHESIZING → COMPLETED
                                                                    └── FAILED (any stage)
```

Job state is persisted in PostgreSQL (`evaluation_jobs` table). The frontend polls job status via TanStack Query until `COMPLETED` or `FAILED`.

### 2.4 Repository Structure

#### Structure Philosophy

**Server — Modular Monolith.** The backend is deployed and run as a single process, but its internal code is organized into self-contained modules. Each module owns its router, service logic, models, and schemas. Modules communicate through explicit service interfaces — never by importing each other's internals directly. The `core/` layer provides shared infrastructure (DB, LLM, ChromaDB clients) that any module may use. This structure supports clean boundaries today and simplifies a potential future split into services if ever needed, without the operational overhead of microservices now.

**Client — Feature-Driven Architecture.** The frontend is organized by feature, not by file type. Each feature folder is self-contained — it holds its own components, hooks, API calls, and types. Only genuinely shared code (layout, design system primitives, global auth state) lives outside feature folders. This prevents the common failure mode of a `components/` folder that becomes a dumping ground for everything.

---

```
equiped/
│
├── server/                          # Modular monolith (FastAPI)
│   │
│   ├── main.py                      # App entry point; mounts all module routers
│   │
│   ├── core/                        # Shared infrastructure — no business logic
│   │   ├── config.py                # Environment variables and settings (Pydantic BaseSettings)
│   │   ├── database.py              # SQLAlchemy engine, session factory
│   │   ├── chroma.py                # ChromaDB client singleton
│   │   ├── llm.py                   # Anthropic client singleton
│   │   ├── embedding.py             # SentenceTransformer model singleton
│   │   └── exceptions.py            # Shared exception base classes
│   │
│   ├── modules/
│   │   │
│   │   ├── documents/               # Module: document upload and ingestion
│   │   │   ├── router.py            # POST /documents/upload, GET /documents
│   │   │   ├── service.py           # Upload handling, ingestion orchestration
│   │   │   ├── ingestion.py         # PyMuPDF + Tesseract OCR + SemanticChunker (Layer 1)
│   │   │   ├── tfidf.py             # TF-IDF corpus computation
│   │   │   ├── models.py            # SQLAlchemy: Document, DocumentChunk
│   │   │   ├── schemas.py           # Pydantic: DocumentCreate, DocumentResponse
│   │   │   └── exceptions.py        # PasswordProtectedPDFError, ExtractionFailedError
│   │   │
│   │   ├── embeddings/              # Module: vector embedding and storage
│   │   │   ├── service.py           # Embedding orchestration; ChromaDB upsert (Layer 2)
│   │   │   ├── retrieval.py         # retrieve_context() — used by agents module
│   │   │   └── collections.py       # ChromaDB collection name constants
│   │   │
│   │   ├── evaluations/             # Module: evaluation job lifecycle
│   │   │   ├── router.py            # POST /evaluations, GET /evaluations, GET /evaluations/:id/status
│   │   │   ├── service.py           # Job creation, status management, background task dispatch
│   │   │   ├── models.py            # SQLAlchemy: EvaluationJob
│   │   │   ├── schemas.py           # Pydantic: EvaluationSubmit, EvaluationStatusResponse
│   │   │   └── exceptions.py        # EvaluationJobError
│   │   │
│   │   ├── agents/                  # Module: multi-agent evaluation (Layer 3)
│   │   │   ├── supervisor.py        # Evaluation orchestration; routes to subagents
│   │   │   ├── base.py              # BaseAgent: shared LLM call, parse, error handling
│   │   │   ├── sme.py               # SME subagent
│   │   │   ├── coordinator.py       # Program Coordinator subagent
│   │   │   ├── gad.py               # GAD Unit subagent
│   │   │   ├── itso.py              # ITSO subagent
│   │   │   ├── contracts.py         # AgentEvaluationResult, CriterionScore dataclasses
│   │   │   └── exceptions.py        # AgentParseError, AgentTimeoutError
│   │   │
│   │   ├── synthesis/               # Module: scoring and report generation (Layer 4)
│   │   │   ├── service.py           # Score aggregation, flag extraction, report assembly
│   │   │   ├── report.py            # Report builder; optional PDF export
│   │   │   ├── matrix.py            # Monitoring matrix upsert logic
│   │   │   ├── models.py            # SQLAlchemy: AgentResult, CriterionScore, EvaluationFlag,
│   │   │   │                        #             EvaluationReport, MonitoringMatrix
│   │   │   ├── schemas.py           # Pydantic: ScorecardResult, EvaluationFlag, ReportResponse
│   │   │   └── router.py            # GET /evaluations/:id/report, GET /matrix
│   │   │
│   │   ├── feedback/                # Module: preference logging (Layer 5)
│   │   │   ├── router.py            # POST /feedback
│   │   │   ├── service.py           # Preference record creation; matrix feedback status update
│   │   │   ├── models.py            # SQLAlchemy: PreferenceLog
│   │   │   └── schemas.py           # Pydantic: FeedbackSubmit, PreferenceResponse
│   │   │
│   │   └── admin/                   # Module: prompt management and preference review
│   │       ├── router.py            # GET|POST /admin/prompts/:agentId, GET /admin/preferences
│   │       ├── service.py           # Prompt version CRUD; revert logic; preference queries
│   │       ├── models.py            # SQLAlchemy: PromptVersion
│   │       └── schemas.py           # Pydantic: PromptVersionCreate, PromptVersionResponse
│   │
│   ├── db/
│   │   └── migrations/              # Alembic migration scripts (auto-generated)
│   │
│   └── tests/
│       ├── modules/                 # Mirror of modules/ — one test file per module service
│       └── conftest.py              # Shared fixtures (test DB, mock LLM client)
│
│
├── client/                          # Feature-driven SPA (React + Vite + TanStack)
│   │
│   ├── src/
│   │   │
│   │   ├── app/                     # App shell — routing tree, global providers, layout
│   │   │   ├── router.tsx           # TanStack Router root; all route definitions imported here
│   │   │   ├── providers.tsx        # QueryClientProvider, AuthProvider, ThemeProvider
│   │   │   └── layout/
│   │   │       ├── AppShell.tsx     # Persistent nav + page outlet
│   │   │       └── Sidebar.tsx
│   │   │
│   │   ├── features/
│   │   │   │
│   │   │   ├── auth/                # Login, session state, role access guard
│   │   │   │   ├── components/
│   │   │   │   │   └── LoginForm.tsx
│   │   │   │   ├── hooks/
│   │   │   │   │   └── useAuth.ts
│   │   │   │   ├── api/
│   │   │   │   │   └── auth.api.ts
│   │   │   │   ├── guards/
│   │   │   │   │   └── RoleGuard.tsx    # beforeLoad role check wrapper
│   │   │   │   └── types.ts
│   │   │   │
│   │   │   ├── upload/              # Document upload and evaluation submission
│   │   │   │   ├── components/
│   │   │   │   │   ├── UploadForm.tsx
│   │   │   │   │   ├── DocumentTypeSelector.tsx
│   │   │   │   │   └── ReferenceDocLinker.tsx   # Associates syllabus + curriculum
│   │   │   │   ├── hooks/
│   │   │   │   │   ├── useUploadDocument.ts
│   │   │   │   │   └── useSubmitEvaluation.ts
│   │   │   │   ├── api/
│   │   │   │   │   └── upload.api.ts
│   │   │   │   └── types.ts
│   │   │   │
│   │   │   ├── evaluation/          # Evaluation status, report display, feedback
│   │   │   │   ├── components/
│   │   │   │   │   ├── EvaluationStatusBanner.tsx   # Polling progress indicator
│   │   │   │   │   ├── Scorecard.tsx                # D-01: per-domain scores
│   │   │   │   │   ├── FlagList.tsx                 # D-02: contextual highlights
│   │   │   │   │   ├── ReportView.tsx               # D-03: full report layout
│   │   │   │   │   └── FeedbackPanel.tsx            # Accept / Reject / Edit controls
│   │   │   │   ├── hooks/
│   │   │   │   │   ├── useEvaluationStatus.ts       # Polling hook (3s interval)
│   │   │   │   │   ├── useEvaluationReport.ts
│   │   │   │   │   └── useSubmitFeedback.ts
│   │   │   │   ├── api/
│   │   │   │   │   └── evaluation.api.ts
│   │   │   │   └── types.ts
│   │   │   │
│   │   │   ├── history/             # Evaluation history list
│   │   │   │   ├── components/
│   │   │   │   │   ├── EvaluationHistoryTable.tsx
│   │   │   │   │   └── HistoryFilters.tsx
│   │   │   │   ├── hooks/
│   │   │   │   │   └── useEvaluationHistory.ts
│   │   │   │   ├── api/
│   │   │   │   │   └── history.api.ts
│   │   │   │   └── types.ts
│   │   │   │
│   │   │   ├── matrix/              # Instructional Materials Monitoring Matrix (D-04)
│   │   │   │   ├── components/
│   │   │   │   │   ├── MonitoringTable.tsx
│   │   │   │   │   └── MatrixFilters.tsx
│   │   │   │   ├── hooks/
│   │   │   │   │   └── useMonitoringMatrix.ts
│   │   │   │   ├── api/
│   │   │   │   │   └── matrix.api.ts
│   │   │   │   └── types.ts
│   │   │   │
│   │   │   └── admin/               # Prompt management and preference log review
│   │   │       ├── components/
│   │   │       │   ├── AgentPromptEditor.tsx        # Text editor + save + revert
│   │   │       │   ├── PromptVersionHistory.tsx
│   │   │       │   └── PreferenceLogTable.tsx
│   │   │       ├── hooks/
│   │   │       │   ├── usePromptVersions.ts
│   │   │       │   └── usePreferenceLogs.ts
│   │   │       ├── api/
│   │   │       │   └── admin.api.ts
│   │   │       └── types.ts
│   │   │
│   │   └── shared/                  # Genuinely shared — used by 2+ features
│   │       ├── components/          # Reusable UI primitives (Button, Badge, Table, Modal)
│   │       ├── hooks/               # Generic hooks (useDebounce, usePagination)
│   │       └── types/               # Global TypeScript types (User, ApiError, PaginatedResponse)
│   │
│   ├── index.html
│   └── vite.config.ts
│
├── chroma_data/                     # ChromaDB persistent storage (local, gitignored)
├── uploads/                         # Uploaded PDFs (local, gitignored)
├── docker-compose.yml
└── .env.example
```

#### Module Boundary Rules

The following rules apply across all server modules and must be respected throughout development:

1. **Modules never import from each other's `models.py` or `schemas.py` directly.** Cross-module data passing uses the contracts defined in `agents/contracts.py` or Pydantic response schemas. If module A needs data from module B, module B exposes a service function — not a model.

2. **All database access goes through the module's own `models.py`.** No module writes to another module's tables directly. The `synthesis` module owns the `monitoring_matrix` table; only `synthesis/matrix.py` writes to it.

3. **`core/` is read-only infrastructure.** No business logic lives in `core/`. Modules call `core/database.py` for sessions, `core/chroma.py` for the ChromaDB client, and `core/llm.py` for the Anthropic client — that is all.

4. **Features in `client/src/features/` do not import from each other.** If two features need the same data shape, that type belongs in `client/src/shared/types/`. If two features need the same UI element, that component belongs in `client/src/shared/components/`.

5. **`shared/` on the client is strictly policed.** Before adding to `shared/`, confirm the item is used by at least two features. Single-feature utilities stay inside their feature folder.

---

## 3. Layer 1 — Document Ingestion & Preprocessing

**PRD References:** FR-01 to FR-05  
**Module:** `server/modules/documents/ingestion.py`

### 3.1 Responsibilities

- Accept a PDF file path
- Extract all text content, handling both selectable text and scanned pages
- Segment extracted text into semantic chunks
- Tag each chunk with source metadata
- Return a list of `DocumentChunk` objects for Layer 2

### 3.2 DocumentChunk Contract

Every chunk produced by this layer must conform to this dataclass:

```python
@dataclass
class DocumentChunk:
    chunk_id: str          # UUID, generated at creation
    document_id: str       # FK to documents table
    source_type: str       # "slm" | "syllabus" | "rubric_sme" |
                           # "rubric_coord" | "rubric_gad" |
                           # "rubric_itso" | "curriculum"
    agent_domain: str      # "sme" | "coordinator" | "gad" |
                           # "itso" | "all"
    page_number: int       # Origin page in source PDF
    text: str              # Raw extracted text of the chunk
    token_count: int       # Approximate token count
    is_ocr: bool           # True if extracted via OCR
```

`agent_domain` drives ChromaDB metadata filtering in Layer 2. Rubric chunks carry the domain of the agent that owns them. SLM chunks and curriculum/syllabus chunks carry `"all"` because they are retrieved by multiple agents.

### 3.3 Ingestion Pseudocode

```python
def ingest_document(file_path: str, source_type: str, document_id: str) -> list[DocumentChunk]:

    raw_pages = pymupdf_extract_pages(file_path)
    # pymupdf_extract_pages returns list of {page_number, text, has_selectable_text}

    full_text_with_metadata = []

    for page in raw_pages:
        if page.has_selectable_text and len(page.text.strip()) > 20:
            # Page has sufficient selectable text — use directly
            full_text_with_metadata.append({
                "page_number": page.page_number,
                "text": page.text,
                "is_ocr": False
            })
        else:
            # Page is scanned or has minimal text — apply OCR
            ocr_text = tesseract_extract(file_path, page.page_number)
            full_text_with_metadata.append({
                "page_number": page.page_number,
                "text": ocr_text,
                "is_ocr": True
            })

    # Concatenate full document text for chunking
    # Preserve page boundaries as metadata markers
    full_text = join_pages_with_markers(full_text_with_metadata)

    # Semantic chunking via LangChain
    chunker = SemanticChunker(
        embeddings=get_embedding_model(),   # same model as Layer 2
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=95
    )
    raw_chunks = chunker.create_documents([full_text])

    # Map chunk positions back to page numbers
    chunks = []
    for i, raw_chunk in enumerate(raw_chunks):
        page_num = resolve_page_number(raw_chunk, full_text_with_metadata)
        agent_domain = resolve_agent_domain(source_type)

        chunks.append(DocumentChunk(
            chunk_id=generate_uuid(),
            document_id=document_id,
            source_type=source_type,
            agent_domain=agent_domain,
            page_number=page_num,
            text=raw_chunk.page_content,
            token_count=count_tokens(raw_chunk.page_content),
            is_ocr=page_is_ocr(page_num, full_text_with_metadata)
        ))

    return chunks


def resolve_agent_domain(source_type: str) -> str:
    domain_map = {
        "rubric_sme":   "sme",
        "rubric_coord": "coordinator",
        "rubric_gad":   "gad",
        "rubric_itso":  "itso",
        "slm":          "all",
        "syllabus":     "all",
        "curriculum":   "all"
    }
    return domain_map.get(source_type, "all")
```

### 3.4 TF-IDF Corpus Weighting

TF-IDF is computed across all SLM chunks in the corpus after chunking. It is not applied per-document in isolation — the corpus context is required for meaningful IDF values.

```python
def compute_tfidf_corpus(slm_chunks: list[DocumentChunk]) -> dict[str, float]:
    """
    Returns a term -> weight mapping for the SLM corpus.
    Used to flag significant deviations from expected instructional vocabulary.
    Stored in PostgreSQL tfidf_corpus table and refreshed when new SLMs are ingested.
    """
    corpus_texts = [chunk.text for chunk in slm_chunks]
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        stop_words=None   # Do not use English stop words — Filipino content present
    )
    vectorizer.fit(corpus_texts)
    return dict(zip(vectorizer.get_feature_names_out(),
                    vectorizer.idf_))
```

> **Note:** Stop words are intentionally disabled. The `english` stop word list in scikit-learn will incorrectly strip Filipino function words. A custom bilingual stop word list should be defined once the SLM corpus is collected. This is tracked as OTI-01.

### 3.5 Failure Handling

| Failure | Behavior |
|---|---|
| PDF is password-protected | Reject at upload; return HTTP 422 with reason |
| Page has no text and OCR returns empty string | Flag page as unprocessable; attach flag to document record; continue with remaining pages |
| Entire document produces zero chunks | Mark evaluation job as `FAILED`; record reason |
| Chunk exceeds 2000 tokens | Split at sentence boundary; log warning |

---

## 4. Layer 2 — Embedding & Vector Storage

**PRD References:** FR-06 (implied), NFR-02, NFR-03, NFR-04  
**Module:** `server/modules/embeddings/service.py`, `server/core/chroma.py`

### 4.1 Embedding Model

**Model:** `paraphrase-multilingual-MiniLM-L12-v2` (SentenceTransformers)

- Runs fully locally — no external API call
- 12-layer transformer; 118M parameters
- Supports 50+ languages including Filipino (Tagalog)
- Output dimension: 384
- Satisfies NFR-02 (bilingual) and NFR-04 (local data residency)

The model is loaded once at application startup as a singleton and shared across all ingestion jobs:

```python
# server/core/embedding.py

from sentence_transformers import SentenceTransformer
from functools import lru_cache

@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
```

### 4.2 ChromaDB Collection Structure

ChromaDB stores embeddings in named collections. EquipEd uses **one collection per domain** to enforce strict retrieval scoping per agent without relying solely on metadata filters (which add latency on large collections).

| Collection Name | Contents | Retrieved By |
|---|---|---|
| `col_slm` | All SLM chunks from all evaluated documents | All agents |
| `col_reference_all` | Syllabus and curriculum guide chunks | SME, Coordinator agents |
| `col_rubric_sme` | SME rubric criteria chunks | SME agent |
| `col_rubric_coordinator` | Program Coordinator rubric chunks | Coordinator agent |
| `col_rubric_gad` | GAD rubric criteria chunks | GAD agent |
| `col_rubric_itso` | ITSO rubric criteria chunks | ITSO agent |

Each document in a collection stores the following metadata alongside its embedding:

```python
{
    "chunk_id":    str,   # UUID
    "document_id": str,   # FK to documents table
    "source_type": str,   # as defined in DocumentChunk
    "page_number": int,
    "is_ocr":      bool,
    "token_count": int
}
```

### 4.3 Embedding Pseudocode

```python
def embed_and_store_chunks(chunks: list[DocumentChunk]) -> None:
    model = get_embedding_model()
    chroma_client = get_chroma_client()

    # Group chunks by their target collection
    collection_map = {
        "slm":          "col_slm",
        "syllabus":     "col_reference_all",
        "curriculum":   "col_reference_all",
        "rubric_sme":   "col_rubric_sme",
        "rubric_coord": "col_rubric_coordinator",
        "rubric_gad":   "col_rubric_gad",
        "rubric_itso":  "col_rubric_itso",
    }

    grouped = group_by(chunks, key=lambda c: collection_map[c.source_type])

    for collection_name, group_chunks in grouped.items():
        collection = chroma_client.get_or_create_collection(collection_name)

        texts = [c.text for c in group_chunks]
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False).tolist()
        ids = [c.chunk_id for c in group_chunks]
        metadatas = [
            {
                "document_id": c.document_id,
                "source_type": c.source_type,
                "page_number": c.page_number,
                "is_ocr":      c.is_ocr,
                "token_count": c.token_count
            }
            for c in group_chunks
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
```

### 4.4 Retrieval Interface

All agents call the same retrieval function. The collection name determines the scope:

```python
def retrieve_context(
    query_text: str,
    collection_name: str,
    n_results: int = 5,
    document_id_filter: str | None = None
) -> list[RetrievedChunk]:
    """
    Performs ANN search against the specified ChromaDB collection.

    Args:
        query_text:          The agent's query or the SLM chunk being evaluated
        collection_name:     One of the six collection constants
        n_results:           Number of top chunks to retrieve
        document_id_filter:  If provided, restricts results to a specific document
                             (used to scope SLM retrieval to the document under evaluation)

    Returns:
        List of RetrievedChunk with text, metadata, and distance score
    """
    model = get_embedding_model()
    query_embedding = model.encode([query_text]).tolist()[0]

    collection = get_chroma_client().get_collection(collection_name)

    where_filter = {}
    if document_id_filter:
        where_filter["document_id"] = {"$eq": document_id_filter}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where_filter if where_filter else None,
        include=["documents", "metadatas", "distances"]
    )

    return parse_chroma_results(results)
```

---

## 5. Layer 3 — Multi-Agent Evaluation

**PRD References:** FR-06 to FR-11, NFR-01  
**Modules:** `server/modules/agents/`

### 5.1 Agent Architecture Overview

All agents share the same LLM backbone (`claude-haiku-4-5`) accessed via the Anthropic Python SDK. They are differentiated by their system prompt, the ChromaDB collections they query, and the rubric criteria they evaluate against.

The **Supervisor Agent** orchestrates the evaluation workflow. It does not perform rubric evaluation itself — it routes SLM chunks to subagents and manages job state.

Each **Subagent** receives a batch of SLM chunks and for each chunk:
1. Retrieves relevant rubric context from its scoped collection
2. Retrieves relevant reference context (syllabus/curriculum) where applicable
3. Calls the LLM with the chunk text, retrieved context, and rubric criteria
4. Parses the structured response into an `AgentEvaluationResult`

### 5.2 System Prompt Architecture

Each subagent has a **versioned system prompt** stored in the `prompt_versions` table (see Section 8). At runtime the active prompt is loaded from the database, not hardcoded. This satisfies NFR-07 (maintainability) and FR-23 (prompt versioning).

System prompts follow a fixed structure. Each subagent prompt must define:

1. **Role declaration** — which institutional stakeholder the agent represents
2. **Evaluation domain** — which rubric domain(s) the agent covers
3. **Scoring instructions** — the 4-point scale definition and per-criterion scoring rules
4. **Output format contract** — the exact JSON structure the agent must return
5. **Grounding instruction** — the agent must base all justifications on retrieved context, not general knowledge
6. **Scope boundary** — what the agent must not evaluate (prevents domain overlap)

The output format contract is the most critical part. Every subagent must return a response that parses cleanly into `AgentEvaluationResult`. Prompts must specify the exact JSON schema.

### 5.3 AgentEvaluationResult Contract

```python
@dataclass
class CriterionScore:
    criterion_id:   str    # e.g., "OP-01", "A-03", "GAD-02", "ITSO-04"
    criterion_text: str    # Full criterion description from rubric
    score:          int    # 1 | 2 | 3 | 4
    justification:  str    # Retrieval-grounded explanation (max 200 words)
    flagged_chunks: list[str]  # chunk_ids of SLM passages that triggered this score


@dataclass
class AgentEvaluationResult:
    agent_id:        str              # "sme" | "coordinator" | "gad" | "itso"
    document_id:     str
    evaluation_id:   str
    prompt_version:  str              # Version ID of the system prompt used
    criteria_scores: list[CriterionScore]
    domain_subtotal: float            # Sum of criterion scores
    processing_time: float            # Seconds
    llm_tokens_used: int              # Total tokens (input + output)
    error:           str | None       # Non-null if agent failed
```

### 5.4 LLM Call Contract

All LLM calls follow this pattern. The structured output is enforced via prompt instruction — the model is instructed to return only valid JSON matching the schema.

```python
def call_llm_for_evaluation(
    system_prompt: str,
    slm_chunk_text: str,
    rubric_context: list[RetrievedChunk],
    reference_context: list[RetrievedChunk],
) -> str:
    """
    Returns raw LLM response string.
    Caller is responsible for JSON parsing and validation.
    """
    client = get_anthropic_client()

    rubric_block = format_retrieved_chunks(rubric_context, label="RUBRIC CRITERIA")
    reference_block = format_retrieved_chunks(reference_context, label="REFERENCE CONTEXT")

    user_message = f"""
## SLM CONTENT TO EVALUATE
{slm_chunk_text}

## RETRIEVED RUBRIC CRITERIA
{rubric_block}

## RETRIEVED REFERENCE CONTEXT
{reference_block}

Evaluate the SLM content above against the rubric criteria provided.
Return your evaluation as a JSON object matching the required schema.
Do not include any text outside the JSON object.
"""

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )

    return response.content[0].text


def parse_agent_response(raw_response: str) -> list[CriterionScore]:
    """
    Strips any accidental markdown fencing and parses JSON.
    Raises AgentParseError if response does not conform to schema.
    """
    clean = raw_response.strip().lstrip("```json").rstrip("```").strip()
    try:
        data = json.loads(clean)
        return [CriterionScore(**item) for item in data["criteria_scores"]]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise AgentParseError(f"Agent response parse failure: {e}\nRaw: {raw_response}")
```

### 5.5 Supervisor / Router Agent

The Supervisor does not call the LLM directly. It coordinates job execution and routes evaluation tasks:

```python
async def run_evaluation(evaluation_id: str, document_id: str) -> EvaluationJobResult:

    update_job_status(evaluation_id, "EVALUATING")

    # Load all SLM chunks for this document from ChromaDB col_slm
    slm_chunks = get_slm_chunks_for_document(document_id)

    # Run all four subagents — can be parallelized in Phase 2
    # Phase 1: sequential execution for simplicity and debuggability
    results = []

    for agent_fn in [run_sme_agent, run_coordinator_agent,
                     run_gad_agent, run_itso_agent]:
        try:
            result = await agent_fn(
                slm_chunks=slm_chunks,
                document_id=document_id,
                evaluation_id=evaluation_id
            )
            results.append(result)
        except AgentParseError as e:
            log_agent_error(evaluation_id, str(e))
            # Continue with remaining agents; mark this result as errored
            results.append(build_error_result(agent_fn, evaluation_id, str(e)))

    return EvaluationJobResult(
        evaluation_id=evaluation_id,
        document_id=document_id,
        agent_results=results
    )
```

> **Phase 1 note:** Agents run sequentially. Parallel execution (via `asyncio.gather`) is deferred to Phase 2 once agent behavior is validated individually.

### 5.6 Subagent Implementation Pattern

All subagents follow the same structure. The SME agent is shown as the reference implementation:

```python
async def run_sme_agent(
    slm_chunks: list[DocumentChunk],
    document_id: str,
    evaluation_id: str
) -> AgentEvaluationResult:

    system_prompt = load_active_prompt("sme")   # loads from prompt_versions table
    all_criteria_scores = []
    total_tokens = 0

    for chunk in slm_chunks:
        # Retrieve rubric context scoped to SME domain
        rubric_ctx = retrieve_context(
            query_text=chunk.text,
            collection_name="col_rubric_sme",
            n_results=5
        )

        # Retrieve syllabus/curriculum context scoped to this document
        reference_ctx = retrieve_context(
            query_text=chunk.text,
            collection_name="col_reference_all",
            n_results=3,
            document_id_filter=document_id
        )

        raw_response = call_llm_for_evaluation(
            system_prompt=system_prompt,
            slm_chunk_text=chunk.text,
            rubric_context=rubric_ctx,
            reference_context=reference_ctx
        )

        criterion_scores = parse_agent_response(raw_response)
        all_criteria_scores.extend(criterion_scores)
        total_tokens += get_token_count_from_response(raw_response)

    return AgentEvaluationResult(
        agent_id="sme",
        document_id=document_id,
        evaluation_id=evaluation_id,
        prompt_version=get_active_prompt_version_id("sme"),
        criteria_scores=deduplicate_and_aggregate_scores(all_criteria_scores),
        domain_subtotal=sum(s.score for s in all_criteria_scores),
        processing_time=elapsed_time(),
        llm_tokens_used=total_tokens,
        error=None
    )
```

The same pattern applies to `run_coordinator_agent`, `run_gad_agent`, and `run_itso_agent`, with the following differences:

| Agent | Rubric Collection | Reference Collection | Additional Context |
|---|---|---|---|
| `sme` | `col_rubric_sme` | `col_reference_all` | None |
| `coordinator` | `col_rubric_coordinator` | `col_reference_all` | Syllabus alignment query |
| `gad` | `col_rubric_gad` | None | No reference context needed |
| `itso` | `col_rubric_itso` | None | No reference context needed |

---

## 6. Layer 4 — Synthesis & Scoring

**PRD References:** FR-12 to FR-15, D-01, D-02, D-03, D-04  
**Module:** `server/modules/synthesis/service.py`

### 6.1 Score Aggregation

```python
def aggregate_scores(agent_results: list[AgentEvaluationResult]) -> ScorecardResult:
    """
    Aggregates per-criterion scores from all agents into a consolidated scorecard.
    """
    domain_scores = {}

    for result in agent_results:
        domain_scores[result.agent_id] = {
            "criteria": [
                {
                    "criterion_id":   s.criterion_id,
                    "criterion_text": s.criterion_text,
                    "score":          s.score,
                    "justification":  s.justification
                }
                for s in result.criteria_scores
            ],
            "subtotal":  result.domain_subtotal,
            "max_score": len(result.criteria_scores) * 4
        }

    # Aggregate total across all domains
    # Formula: sum of all criterion scores / (total criteria count * 4) * 100
    # Produces a percentage score 0–100
    # NOTE: Exact institutional formula to be confirmed against CID rubric documents (OTI-02)
    total_score_raw = sum(
        score
        for result in agent_results
        for score in [s.score for s in result.criteria_scores]
    )
    total_criteria_count = sum(
        len(result.criteria_scores)
        for result in agent_results
    )
    aggregate_percentage = (total_score_raw / (total_criteria_count * 4)) * 100

    return ScorecardResult(
        domain_scores=domain_scores,
        aggregate_raw=total_score_raw,
        aggregate_max=total_criteria_count * 4,
        aggregate_percentage=round(aggregate_percentage, 2)
    )
```

### 6.2 Flag Extraction

Flags are derived from low-scoring criteria and their associated `flagged_chunks`:

```python
def extract_flags(agent_results: list[AgentEvaluationResult]) -> list[EvaluationFlag]:
    """
    Extracts flags for all criteria scoring 1 or 2 (Needs Improvement or Poor).
    Each flag references the specific SLM chunk(s) that triggered it.
    """
    flags = []
    FLAG_THRESHOLD = 2  # Scores of 1 or 2 produce flags

    for result in agent_results:
        for criterion in result.criteria_scores:
            if criterion.score <= FLAG_THRESHOLD:
                for chunk_id in criterion.flagged_chunks:
                    flags.append(EvaluationFlag(
                        flag_id=generate_uuid(),
                        evaluation_id=result.evaluation_id,
                        agent_id=result.agent_id,
                        criterion_id=criterion.criterion_id,
                        criterion_text=criterion.criterion_text,
                        score=criterion.score,
                        justification=criterion.justification,
                        chunk_id=chunk_id
                    ))

    return flags
```

### 6.3 Report Generation

The final report (D-03) is assembled as a structured dictionary and persisted to PostgreSQL. It is served to the frontend as JSON and optionally rendered as a downloadable PDF.

```python
def generate_report(
    evaluation_id: str,
    document: DocumentRecord,
    scorecard: ScorecardResult,
    flags: list[EvaluationFlag]
) -> EvaluationReport:

    return EvaluationReport(
        report_id=generate_uuid(),
        evaluation_id=evaluation_id,
        document_id=document.document_id,
        document_title=document.title,
        program=document.program,
        evaluation_date=utcnow(),
        scorecard=scorecard,
        flags=flags,
        summary=build_summary_text(scorecard, flags),
        status="COMPLETED"
    )
```

### 6.4 Monitoring Matrix Update

After report generation, the monitoring matrix entry for the document is updated:

```python
def update_monitoring_matrix(
    document_id: str,
    evaluation_id: str,
    scorecard: ScorecardResult
) -> None:
    upsert_monitoring_record(
        document_id=document_id,
        evaluation_id=evaluation_id,
        evaluation_status="EVALUATED",
        aggregate_score=scorecard.aggregate_percentage,
        domain_scores={k: v["subtotal"] for k, v in scorecard.domain_scores.items()},
        feedback_status="NO_FEEDBACK"
    )
```

---

## 7. Layer 5 — Preference Logging & Prompt Optimization

**PRD References:** FR-22 to FR-25, D-06  
**Module:** `server/modules/feedback/service.py`

### 7.1 Preference Logging

Every evaluator interaction with a generated output is logged as a preference record:

```python
def log_preference(
    evaluation_id: str,
    agent_id: str,
    criterion_id: str,
    feedback_type: str,     # "ACCEPT" | "REJECT" | "EDIT"
    original_output: dict,  # The criterion score dict as shown to the user
    edited_output: dict | None,  # Non-null only for EDIT feedback type
    user_id: str,
    user_role: str
) -> PreferenceRecord:

    record = PreferenceRecord(
        preference_id=generate_uuid(),
        evaluation_id=evaluation_id,
        agent_id=agent_id,
        criterion_id=criterion_id,
        prompt_version_id=get_active_prompt_version_id(agent_id),
        feedback_type=feedback_type,
        original_output=json.dumps(original_output),
        edited_output=json.dumps(edited_output) if edited_output else None,
        user_id=user_id,
        user_role=user_role,
        created_at=utcnow()
    )

    db.save(record)
    return record
```

### 7.2 Prompt Version Management

```python
def create_prompt_version(
    agent_id: str,
    prompt_text: str,
    updated_by: str,
    motivation: str,         # Human-written summary of why this change was made
    preference_ids: list[str]  # IDs of preference records that motivated this change
) -> PromptVersion:

    # Deactivate all current active prompts for this agent
    deactivate_current_prompts(agent_id)

    version = PromptVersion(
        version_id=generate_uuid(),
        agent_id=agent_id,
        version_number=get_next_version_number(agent_id),
        prompt_text=prompt_text,
        is_active=True,
        updated_by=updated_by,
        motivation=motivation,
        preference_ids=json.dumps(preference_ids),
        created_at=utcnow()
    )

    db.save(version)
    return version


def load_active_prompt(agent_id: str) -> str:
    version = db.query(PromptVersion).filter_by(
        agent_id=agent_id,
        is_active=True
    ).one()
    return version.prompt_text
```

### 7.3 Prompt Revert

Admins can revert to any prior prompt version:

```python
def revert_prompt(agent_id: str, target_version_id: str, reverted_by: str) -> PromptVersion:
    target = db.query(PromptVersion).filter_by(version_id=target_version_id).one()

    # Create a new version entry that copies the target prompt text
    # (do not just flip is_active — preserve full history)
    return create_prompt_version(
        agent_id=agent_id,
        prompt_text=target.prompt_text,
        updated_by=reverted_by,
        motivation=f"Revert to version {target.version_number}",
        preference_ids=[]
    )
```

---

## 8. Database Schemas

**Technology:** PostgreSQL 15 + SQLAlchemy 2.0 ORM + Alembic migrations

### 8.1 `documents`

```sql
CREATE TABLE documents (
    document_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(500) NOT NULL,
    program         VARCHAR(300),
    source_type     VARCHAR(50) NOT NULL,
        -- "slm" | "syllabus" | "rubric_sme" | "rubric_coord"
        -- | "rubric_gad" | "rubric_itso" | "curriculum"
    file_path       TEXT NOT NULL,
    uploaded_by     UUID REFERENCES users(user_id),
    uploaded_at     TIMESTAMPTZ DEFAULT now(),
    page_count      INTEGER,
    has_ocr_pages   BOOLEAN DEFAULT FALSE,
    processing_status VARCHAR(50) DEFAULT 'PENDING'
        -- "PENDING" | "PROCESSED" | "FAILED"
);
```

### 8.2 `document_chunks`

```sql
CREATE TABLE document_chunks (
    chunk_id        UUID PRIMARY KEY,
    document_id     UUID NOT NULL REFERENCES documents(document_id),
    source_type     VARCHAR(50) NOT NULL,
    agent_domain    VARCHAR(50) NOT NULL,
    page_number     INTEGER,
    text            TEXT NOT NULL,
    token_count     INTEGER,
    is_ocr          BOOLEAN DEFAULT FALSE,
    chroma_stored   BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_agent_domain ON document_chunks(agent_domain);
```

### 8.3 `evaluation_jobs`

```sql
CREATE TABLE evaluation_jobs (
    evaluation_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(document_id),
    status          VARCHAR(50) NOT NULL DEFAULT 'SUBMITTED',
        -- "SUBMITTED" | "PREPROCESSING" | "EMBEDDING"
        -- | "EVALUATING" | "SYNTHESIZING" | "COMPLETED" | "FAILED"
    error_message   TEXT,
    submitted_by    UUID REFERENCES users(user_id),
    submitted_at    TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_jobs_document_id ON evaluation_jobs(document_id);
CREATE INDEX idx_jobs_status ON evaluation_jobs(status);
```

### 8.4 `agent_results`

```sql
CREATE TABLE agent_results (
    result_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id       UUID NOT NULL REFERENCES evaluation_jobs(evaluation_id),
    agent_id            VARCHAR(50) NOT NULL,
        -- "sme" | "coordinator" | "gad" | "itso"
    prompt_version_id   UUID REFERENCES prompt_versions(version_id),
    domain_subtotal     NUMERIC(6,2),
    processing_time_s   NUMERIC(8,3),
    llm_tokens_used     INTEGER,
    error               TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);
```

### 8.5 `criterion_scores`

```sql
CREATE TABLE criterion_scores (
    score_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id       UUID NOT NULL REFERENCES agent_results(result_id),
    evaluation_id   UUID NOT NULL REFERENCES evaluation_jobs(evaluation_id),
    criterion_id    VARCHAR(20) NOT NULL,   -- e.g., "OP-01", "A-03"
    criterion_text  TEXT NOT NULL,
    score           SMALLINT NOT NULL CHECK (score BETWEEN 1 AND 4),
    justification   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_scores_evaluation_id ON criterion_scores(evaluation_id);
```

### 8.6 `evaluation_flags`

```sql
CREATE TABLE evaluation_flags (
    flag_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id   UUID NOT NULL REFERENCES evaluation_jobs(evaluation_id),
    score_id        UUID REFERENCES criterion_scores(score_id),
    agent_id        VARCHAR(50) NOT NULL,
    criterion_id    VARCHAR(20) NOT NULL,
    criterion_text  TEXT NOT NULL,
    score           SMALLINT NOT NULL,
    justification   TEXT,
    chunk_id        UUID REFERENCES document_chunks(chunk_id),
    resolved        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_flags_evaluation_id ON evaluation_flags(evaluation_id);
```

### 8.7 `evaluation_reports`

```sql
CREATE TABLE evaluation_reports (
    report_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id       UUID NOT NULL UNIQUE REFERENCES evaluation_jobs(evaluation_id),
    document_id         UUID NOT NULL REFERENCES documents(document_id),
    aggregate_raw       INTEGER,
    aggregate_max       INTEGER,
    aggregate_pct       NUMERIC(5,2),
    domain_scores_json  JSONB,      -- full domain breakdown
    flags_count         INTEGER DEFAULT 0,
    summary_text        TEXT,
    generated_at        TIMESTAMPTZ DEFAULT now()
);
```

### 8.8 `monitoring_matrix`

```sql
CREATE TABLE monitoring_matrix (
    matrix_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL UNIQUE REFERENCES documents(document_id),
    evaluation_id       UUID REFERENCES evaluation_jobs(evaluation_id),
    evaluation_status   VARCHAR(50) DEFAULT 'PENDING',
        -- "PENDING" | "EVALUATED" | "REVIEWED" | "APPROVED"
    aggregate_score     NUMERIC(5,2),
    domain_scores_json  JSONB,
    feedback_status     VARCHAR(50) DEFAULT 'NO_FEEDBACK',
        -- "NO_FEEDBACK" | "PARTIALLY_REVIEWED" | "FULLY_REVIEWED"
    last_updated        TIMESTAMPTZ DEFAULT now()
);
```

### 8.9 `preference_logs`

```sql
CREATE TABLE preference_logs (
    preference_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id       UUID NOT NULL REFERENCES evaluation_jobs(evaluation_id),
    agent_id            VARCHAR(50) NOT NULL,
    criterion_id        VARCHAR(20) NOT NULL,
    prompt_version_id   UUID REFERENCES prompt_versions(version_id),
    feedback_type       VARCHAR(10) NOT NULL CHECK (feedback_type IN ('ACCEPT','REJECT','EDIT')),
    original_output     JSONB NOT NULL,
    edited_output       JSONB,          -- non-null only for EDIT
    user_id             UUID REFERENCES users(user_id),
    user_role           VARCHAR(50),
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_prefs_agent_id ON preference_logs(agent_id);
CREATE INDEX idx_prefs_feedback_type ON preference_logs(feedback_type);
```

### 8.10 `prompt_versions`

```sql
CREATE TABLE prompt_versions (
    version_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id            VARCHAR(50) NOT NULL,
    version_number      INTEGER NOT NULL,
    prompt_text         TEXT NOT NULL,
    is_active           BOOLEAN DEFAULT FALSE,
    updated_by          UUID REFERENCES users(user_id),
    motivation          TEXT,
    preference_ids      JSONB,          -- array of preference UUIDs
    created_at          TIMESTAMPTZ DEFAULT now(),

    UNIQUE (agent_id, version_number)
);

CREATE INDEX idx_prompts_agent_active ON prompt_versions(agent_id, is_active);
```

### 8.11 `users`

```sql
CREATE TABLE users (
    user_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(300) NOT NULL,
    email       VARCHAR(300) UNIQUE NOT NULL,
    role        VARCHAR(50) NOT NULL,
        -- "faculty" | "sme" | "coordinator" | "gad" | "itso" | "admin"
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

### 8.12 `tfidf_corpus`

```sql
CREATE TABLE tfidf_corpus (
    term        VARCHAR(200) PRIMARY KEY,
    idf_weight  NUMERIC(10,6) NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT now()
);
```

---

## 9. API Specification

**Base URL:** `/api/v1`  
**Format:** JSON  
**Auth:** `[TBD — session-based or JWT, to be decided]`

### 9.1 Documents

#### `POST /documents/upload`
Upload a document (SLM or reference document).

**Request:** `multipart/form-data`
```
file:        File (PDF)
source_type: string  -- "slm" | "syllabus" | "rubric_sme" | "rubric_coord"
                         | "rubric_gad" | "rubric_itso" | "curriculum"
title:       string
program:     string  (optional, required for SLMs)
```

**Response `201`:**
```json
{
  "document_id": "uuid",
  "title": "string",
  "source_type": "string",
  "processing_status": "PENDING"
}
```

**Errors:**
- `422` — Password-protected PDF or unsupported file type
- `413` — File too large `[TBD: size limit]`

---

#### `GET /documents/{document_id}`
Get document metadata and processing status.

**Response `200`:**
```json
{
  "document_id": "uuid",
  "title": "string",
  "source_type": "string",
  "program": "string",
  "page_count": 32,
  "processing_status": "PROCESSED",
  "has_ocr_pages": false,
  "uploaded_at": "ISO8601"
}
```

---

#### `GET /documents`
List all documents. Supports filtering by `source_type` and `program`.

**Query params:** `source_type`, `program`, `page`, `page_size`

**Response `200`:**
```json
{
  "items": [ /* array of document objects */ ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

### 9.2 Evaluations

#### `POST /evaluations`
Submit an SLM for evaluation.

**Request:**
```json
{
  "document_id": "uuid",
  "syllabus_id": "uuid",
  "curriculum_id": "uuid"
}
```

**Response `202`:**
```json
{
  "evaluation_id": "uuid",
  "document_id": "uuid",
  "status": "SUBMITTED",
  "submitted_at": "ISO8601"
}
```

---

#### `GET /evaluations/{evaluation_id}/status`
Poll evaluation job status. Used by TanStack Query for progress tracking.

**Response `200`:**
```json
{
  "evaluation_id": "uuid",
  "status": "EVALUATING",
  "submitted_at": "ISO8601",
  "completed_at": null,
  "error_message": null
}
```

---

#### `GET /evaluations/{evaluation_id}/report`
Retrieve the full evaluation report once status is `COMPLETED`.

**Response `200`:**
```json
{
  "report_id": "uuid",
  "evaluation_id": "uuid",
  "document_title": "string",
  "program": "string",
  "evaluation_date": "ISO8601",
  "aggregate_raw": 72,
  "aggregate_max": 80,
  "aggregate_pct": 90.0,
  "domain_scores": {
    "sme": {
      "subtotal": 36,
      "max_score": 40,
      "criteria": [ /* CriterionScore objects */ ]
    },
    "coordinator": { /* ... */ },
    "gad": { /* ... */ },
    "itso": { /* ... */ }
  },
  "flags": [ /* EvaluationFlag objects */ ],
  "summary": "string"
}
```

---

#### `GET /evaluations`
List evaluation history. Supports filtering by `status`, `program`, `document_id`.

**Query params:** `status`, `program`, `document_id`, `page`, `page_size`

---

### 9.3 Feedback

#### `POST /feedback`
Submit evaluator feedback on an evaluation output.

**Request:**
```json
{
  "evaluation_id": "uuid",
  "agent_id": "sme",
  "criterion_id": "OP-01",
  "feedback_type": "EDIT",
  "original_output": {
    "score": 2,
    "justification": "string"
  },
  "edited_output": {
    "score": 3,
    "justification": "Corrected justification text"
  }
}
```

**Response `201`:**
```json
{
  "preference_id": "uuid",
  "feedback_type": "EDIT",
  "created_at": "ISO8601"
}
```

---

### 9.4 Monitoring Matrix

#### `GET /matrix`
Retrieve the full monitoring matrix.

**Query params:** `evaluation_status`, `feedback_status`, `program`, `score_lt`, `score_gt`, `page`, `page_size`

**Response `200`:**
```json
{
  "items": [
    {
      "document_id": "uuid",
      "title": "string",
      "program": "string",
      "evaluation_status": "EVALUATED",
      "aggregate_score": 87.5,
      "domain_scores": { /* ... */ },
      "feedback_status": "PARTIALLY_REVIEWED",
      "last_updated": "ISO8601"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 20
}
```

---

### 9.5 Admin

#### `GET /admin/prompts/{agent_id}`
Get full prompt version history for an agent.

**Response `200`:**
```json
{
  "agent_id": "sme",
  "versions": [
    {
      "version_id": "uuid",
      "version_number": 3,
      "is_active": true,
      "motivation": "string",
      "preference_ids": ["uuid", "uuid"],
      "created_at": "ISO8601"
    }
  ]
}
```

---

#### `POST /admin/prompts/{agent_id}`
Create a new prompt version and activate it.

**Request:**
```json
{
  "prompt_text": "string",
  "motivation": "string",
  "preference_ids": ["uuid", "uuid"]
}
```

**Response `201`:**
```json
{
  "version_id": "uuid",
  "version_number": 4,
  "is_active": true,
  "created_at": "ISO8601"
}
```

---

#### `POST /admin/prompts/{agent_id}/revert/{version_id}`
Revert an agent to a prior prompt version.

**Response `200`:**
```json
{
  "version_id": "uuid",
  "version_number": 5,
  "is_active": true,
  "motivation": "Revert to version 2",
  "created_at": "ISO8601"
}
```

---

#### `GET /admin/preferences`
Query preference logs with filtering.

**Query params:** `agent_id`, `feedback_type`, `criterion_id`, `user_role`, `from_date`, `to_date`, `page`, `page_size`

---

## 10. Frontend Architecture

**Stack:** React 18 + Vite + TanStack Router + TanStack Query  
**Language:** TypeScript  
**Structure:** Feature-driven (see Section 2.4)

### 10.1 Route Structure

Routes are defined in `client/src/app/router.tsx` and import page-level components from their respective feature folders.

```
/                         → redirect to /dashboard
/login                    → client/src/features/auth — LoginForm
/dashboard                → client/src/app/layout — DashboardPage (overview, recent evaluations)
/upload                   → client/src/features/upload — UploadForm
/evaluations              → client/src/features/history — EvaluationHistoryTable
/evaluations/:id          → client/src/features/evaluation — Scorecard + FlagList + FeedbackPanel
/evaluations/:id/report   → client/src/features/evaluation — ReportView (full report, printable)
/matrix                   → client/src/features/matrix — MonitoringTable [coordinator + admin only]
/admin                    → client/src/features/admin — AdminLayout [admin only]
  /admin/prompts          → client/src/features/admin — AgentPromptEditor (list view)
  /admin/prompts/:agentId → client/src/features/admin — AgentPromptEditor (detail + version history)
  /admin/preferences      → client/src/features/admin — PreferenceLogTable
```

### 10.2 TanStack Query Hook Contracts

All hooks live inside their feature folder (`client/src/features/<name>/hooks/`). The contracts below are the source of truth for data fetching behavior:

```typescript
// client/src/features/evaluation/hooks/useEvaluationStatus.ts
// Polls job status every 3 seconds until COMPLETED or FAILED
export function useEvaluationStatus(evaluationId: string) {
  return useQuery({
    queryKey: ['evaluation', evaluationId, 'status'],
    queryFn: () => evaluationApi.getStatus(evaluationId),
    refetchInterval: (data) =>
      data?.status === 'COMPLETED' || data?.status === 'FAILED' ? false : 3000,
    staleTime: 0,
  })
}

// client/src/features/evaluation/hooks/useEvaluationReport.ts
// Only enabled once job status is COMPLETED
export function useEvaluationReport(evaluationId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['evaluation', evaluationId, 'report'],
    queryFn: () => evaluationApi.getReport(evaluationId),
    enabled,
    staleTime: 5 * 60 * 1000,   // 5 minutes — reports are immutable
  })
}

// client/src/features/evaluation/hooks/useSubmitFeedback.ts
export function useSubmitFeedback() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: FeedbackPayload) => evaluationApi.submitFeedback(payload),
    onSuccess: (_, variables) => {
      // Invalidate report so feedback status reflects immediately
      queryClient.invalidateQueries({
        queryKey: ['evaluation', variables.evaluation_id, 'report']
      })
      // Invalidate monitoring matrix — feedback_status column changes
      queryClient.invalidateQueries({ queryKey: ['matrix'] })
    }
  })
}

// client/src/features/matrix/hooks/useMonitoringMatrix.ts
export function useMonitoringMatrix(filters: MatrixFilters) {
  return useQuery({
    queryKey: ['matrix', filters],
    queryFn: () => matrixApi.getMatrix(filters),
    staleTime: 60 * 1000,   // 1 minute
  })
}
```

### 10.3 Key Component Responsibilities

| Component | Feature | Route | Responsibility |
|---|---|---|---|
| `UploadForm` | `upload` | `/upload` | PDF file input; source type selector; syllabus/curriculum association dropdowns; fires `useUploadDocument` then `useSubmitEvaluation` |
| `EvaluationStatusBanner` | `evaluation` | `/evaluations/:id` | Renders pipeline progress using `useEvaluationStatus`; disappears on `COMPLETED` |
| `Scorecard` | `evaluation` | `/evaluations/:id` | Renders per-domain scores and per-criterion breakdown from report (D-01) |
| `FlagList` | `evaluation` | `/evaluations/:id` | Renders contextual document highlights with criterion and justification (D-02) |
| `FeedbackPanel` | `evaluation` | `/evaluations/:id` | Accept / Reject / Edit controls per criterion; calls `useSubmitFeedback` |
| `ReportView` | `evaluation` | `/evaluations/:id/report` | Full printable report layout combining D-01, D-02, D-03 |
| `MonitoringTable` | `matrix` | `/matrix` | Filterable, paginated SLM tracking table (D-04); role-gated |
| `AgentPromptEditor` | `admin` | `/admin/prompts/:agentId` | Prompt text editor; version history list; save + revert actions |
| `PreferenceLogTable` | `admin` | `/admin/preferences` | Filterable preference log; links preference records to prompt versions |

### 10.4 Role-Based Access Control

Route-level access is enforced via a `RoleGuard` component (`client/src/features/auth/guards/RoleGuard.tsx`) used in TanStack Router's `beforeLoad`:

```typescript
// client/src/features/auth/guards/RoleGuard.tsx
// Used in router.tsx beforeLoad for protected routes
export function requireRole(allowedRoles: UserRole[]) {
  return ({ context }: { context: RouterContext }) => {
    const { user } = context.auth
    if (!user || !allowedRoles.includes(user.role)) {
      throw redirect({ to: '/dashboard' })
    }
  }
}

// client/src/app/router.tsx — usage example
const matrixRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/matrix',
  beforeLoad: requireRole(['coordinator', 'admin']),
  component: lazy(() => import('../features/matrix/components/MonitoringTable')),
})
```

| Route | faculty | sme | coordinator | gad | itso | admin |
|---|---|---|---|---|---|---|
| `/upload` | ✓ | — | ✓ | — | — | ✓ |
| `/evaluations/:id` | Own only | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/matrix` | — | — | ✓ | — | — | ✓ |
| `/admin/*` | — | — | — | — | — | ✓ |

---

## 11. Component Integration Map

This map shows data flow between all major components, tracing the full path of a single evaluation job:

```
1. Faculty uploads PDF
   POST /documents/upload
   → documents table (PostgreSQL)
   → file saved to /uploads/{document_id}.pdf

2. Faculty submits evaluation
   POST /evaluations
   → evaluation_jobs table: status = SUBMITTED
   → FastAPI BackgroundTask triggered

3. Layer 1 — Ingestion (background)
   ingestion.py ← /uploads/{document_id}.pdf
   → PyMuPDF extracts text
   → Tesseract OCR on image pages (conditional)
   → SemanticChunker produces DocumentChunk list
   → document_chunks table (PostgreSQL)
   → evaluation_jobs: status = PREPROCESSING → EMBEDDING

4. Layer 2 — Embedding (background)
   embedding.py ← document_chunks
   → multilingual-MiniLM encodes chunk texts
   → ChromaDB upsert into scoped collections
   → document_chunks: chroma_stored = TRUE
   → evaluation_jobs: status = EVALUATING

5. Layer 3 — Agents (background)
   supervisor.py orchestrates:
     sme.py → col_rubric_sme + col_reference_all → claude-haiku-4-5
     coordinator.py → col_rubric_coordinator + col_reference_all → claude-haiku-4-5
     gad.py → col_rubric_gad → claude-haiku-4-5
     itso.py → col_rubric_itso → claude-haiku-4-5
   → agent_results table (PostgreSQL)
   → criterion_scores table (PostgreSQL)

6. Layer 4 — Synthesis (background)
   synthesis.py ← agent_results + criterion_scores
   → Score aggregation
   → Flag extraction → evaluation_flags table
   → Report generation → evaluation_reports table
   → Monitoring matrix update → monitoring_matrix table
   → evaluation_jobs: status = COMPLETED

7. Frontend polls status
   GET /evaluations/{id}/status (TanStack Query, 3s interval)
   → Returns COMPLETED
   → useEvaluationReport enabled

8. Frontend fetches report
   GET /evaluations/{id}/report
   → EvaluationDetailPage renders scorecard + flags

9. Evaluator submits feedback
   POST /feedback
   → preference_logs table
   → monitoring_matrix feedback_status updated

10. Admin refines prompt
    GET /admin/preferences (filtered)
    → Reviews REJECT/EDIT patterns
    POST /admin/prompts/{agentId}
    → prompt_versions table (new version, is_active = TRUE)
    → Prior version is_active = FALSE
```

---

## 12. Deferred Components

### 12.1 RNN-AES Module (Phase 2)

**Status:** Deferred  
**Condition for inclusion:** Phase 1 validation shows that LLM-based coherence evaluation (FR-11, via SME subagent prompt) produces insufficient agreement with human evaluators on sequential flow and organizational quality criteria.  
**Planned approach:** Taghipour & Ng (2016) RNN-AES model adapted for SLM text. Would run as a pre-processing step before agent evaluation, providing a coherence score that is injected into the SME agent's context.  
**Integration point:** Between Layer 2 and Layer 3. Output: a `coherence_score` (0.0–1.0) attached to each SLM document, passed to the SME agent as additional context.

### 12.2 Parallel Agent Execution (Phase 2)

**Status:** Deferred  
**Current:** Agents execute sequentially in Phase 1  
**Planned:** Replace sequential loop in `supervisor.py` with `asyncio.gather` for concurrent agent execution  
**Condition:** Implement after individual agent behavior is validated and evaluation latency is benchmarked as unacceptably high

### 12.3 Task Queue (Phase 2)

**Status:** Deferred  
**Current:** FastAPI `BackgroundTasks` for evaluation job execution  
**Planned:** Celery + Redis for distributed task queue if concurrent evaluation jobs create resource contention  
**Condition:** Implement if Phase 1 load testing shows BackgroundTasks insufficient for expected concurrent submission volume at LSPU SCC

---

## 13. Open Technical Items

| ID | Item | Blocked Section | Owner | Status |
|---|---|---|---|---|
| OTI-01 | Custom bilingual (EN + Filipino) stop word list for TF-IDF | Section 3.4 | Research team | Pending corpus collection |
| OTI-02 | Exact institutional score aggregation formula from CID rubric documents | Section 6.1 | Research team | Pending CID document release |
| OTI-03 | Criterion ID naming convention (`OP-01`, `A-01`, etc.) — must match rubric document structure exactly | Sections 5.3, 8.5 | Research team | Pending rubric finalization |
| OTI-04 | Authentication strategy (session-based vs JWT) | Section 9, Section 10.4 | Development team | Pending decision |
| OTI-05 | File size upload limit | Section 9.1 | Development team | Pending benchmarking |
| OTI-06 | API data handling policy confirmation for Anthropic API calls (RA 10173 compliance) | Section 2.2 | LSPU SCC IT | Pending institutional review |
| OTI-07 | Minimum preference log volume threshold before prompt update is actionable | Section 7.1 | Research team + advisor | Pending advisor input |
| OTI-08 | Exact SemanticChunker breakpoint threshold value — 95th percentile is initial default, may need tuning per corpus | Section 3.3 | Development team | Pending corpus testing |
| OTI-09 | PDF report generation for D-03 download — library selection (WeasyPrint vs ReportLab) | Section 6.3 | Development team | Pending decision |

---

*EquipEd TDD v0.1 — For Development Team and AI Agent Reference*  
*LSPU SCC, College of Computer Studies*
