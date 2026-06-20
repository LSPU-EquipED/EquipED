export const DOCUMENT_SOURCE_TYPES = [
  'slm',
  'syllabus',
  'rubric_sme',
  'rubric_coord',
  'rubric_gad',
  'rubric_itso',
  'curriculum',
] as const;

export type DocumentSourceType = (typeof DOCUMENT_SOURCE_TYPES)[number];
export type DocumentProcessingStatus = 'PENDING' | 'PROCESSED' | 'FAILED';

export type RawDocumentChunk = {
  chunk_id: string;
  document_id: string;
  source_type: DocumentSourceType;
  agent_domain: string;
  page_number: number;
  text: string;
  token_count: number;
  is_ocr: boolean;
};

export type ClientDocumentChunk = {
  chunkId: string;
  documentId: string;
  sourceType: DocumentSourceType;
  agentDomain: string;
  pageNumber: number;
  text: string;
  tokenCount: number;
  isOcr: boolean;
};

export type RawDocumentResponse = {
  document_id: string;
  title: string;
  course_title: string | null;
  lesson_title: string | null;
  source_type: DocumentSourceType;
  program: string | null;
  page_count: number | null;
  processing_status: DocumentProcessingStatus;
  has_ocr_pages: boolean;
  uploaded_at: string;
  structured_summary?: string | null;
  structured_outline?: Array<Record<string, unknown>> | null;
  section_summaries?: Array<Record<string, unknown>> | null;
  key_facts?: Record<string, unknown> | null;
  processing_warnings?: string[] | null;
  evaluation_readiness?: string | null;
  chunks?: RawDocumentChunk[] | null;
};

export type ClientDocument = {
  documentId: string;
  title: string;
  courseTitle: string | null;
  lessonTitle: string | null;
  sourceType: DocumentSourceType;
  program: string | null;
  pageCount: number | null;
  processingStatus: DocumentProcessingStatus;
  hasOcrPages: boolean;
  uploadedAt: string;
  structuredSummary?: string | null;
  structuredOutline?: Array<Record<string, unknown>> | null;
  sectionSummaries?: Array<Record<string, unknown>> | null;
  keyFacts?: Record<string, unknown> | null;
  processingWarnings?: string[] | null;
  evaluationReadiness?: string | null;
  chunks: ClientDocumentChunk[];
};

export type RawDocumentListResponse = {
  items: RawDocumentResponse[];
  total: number;
  page: number;
  page_size: number;
};

export type DocumentListResponse = {
  items: ClientDocument[];
  total: number;
  page: number;
  pageSize: number;
};

export type RawDocumentUploadResponse = {
  document_id: string;
  title: string;
  course_title: string | null;
  lesson_title: string | null;
  source_type: DocumentSourceType;
  processing_status: DocumentProcessingStatus;
  structured_summary?: string | null;
  evaluation_readiness?: string | null;
  error_message?: string | null;
};

export type DocumentUploadResponse = {
  documentId: string;
  title: string;
  courseTitle: string | null;
  lessonTitle: string | null;
  sourceType: DocumentSourceType;
  processingStatus: DocumentProcessingStatus;
  structuredSummary?: string | null;
  evaluationReadiness?: string | null;
  errorMessage?: string | null;
};

// --- Synthesis / Matrix shared types (used by admin + matrix features) ---

export type CriterionScoreItem = {
  criterion_id: string;
  criterion_text: string;
  score: number;
  justification: string;
  evidence: string | null;
  chunk_ids: string | null;
};

export type DomainScoreBlock = {
  criteria: CriterionScoreItem[];
  subtotal: number;
  max_score: number;
  status: string;
};

function mapDocumentChunk(chunk: RawDocumentChunk): ClientDocumentChunk {
  return {
    chunkId: chunk.chunk_id,
    documentId: chunk.document_id,
    sourceType: chunk.source_type,
    agentDomain: chunk.agent_domain,
    pageNumber: chunk.page_number,
    text: chunk.text,
    tokenCount: chunk.token_count,
    isOcr: chunk.is_ocr,
  };
}

export function mapDocumentResponse(document: RawDocumentResponse): ClientDocument {
  return {
    documentId: document.document_id,
    title: document.title,
    courseTitle: document.course_title,
    lessonTitle: document.lesson_title,
    sourceType: document.source_type,
    program: document.program,
    pageCount: document.page_count,
    processingStatus: document.processing_status,
    hasOcrPages: document.has_ocr_pages,
    uploadedAt: document.uploaded_at,
    structuredSummary: document.structured_summary,
    structuredOutline: document.structured_outline,
    sectionSummaries: document.section_summaries,
    keyFacts: document.key_facts,
    processingWarnings: document.processing_warnings,
    evaluationReadiness: document.evaluation_readiness,
    chunks: (document.chunks ?? []).map(mapDocumentChunk),
  };
}

export function mapDocumentListResponse(response: RawDocumentListResponse): DocumentListResponse {
  return {
    items: response.items.map(mapDocumentResponse),
    total: response.total,
    page: response.page,
    pageSize: response.page_size,
  };
}

export function mapDocumentUploadResponse(
  response: RawDocumentUploadResponse,
): DocumentUploadResponse {
  return {
    documentId: response.document_id,
    title: response.title,
    courseTitle: response.course_title,
    lessonTitle: response.lesson_title,
    sourceType: response.source_type,
    processingStatus: response.processing_status,
    structuredSummary: response.structured_summary,
    evaluationReadiness: response.evaluation_readiness,
    errorMessage: response.error_message,
  };
}
