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
  academic_year: string | null;
  course_code: string | null;
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
  academicYear: string | null;
  courseCode: string | null;
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
  program?: string | null;
  academic_year: string | null;
  course_code: string | null;
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
  program?: string | null;
  academicYear: string | null;
  courseCode: string | null;
  structuredSummary?: string | null;
  evaluationReadiness?: string | null;
  errorMessage?: string | null;
};

// --- Curriculum suggestion types (used by evaluation setup) ---

export type RawCurriculumSuggestionItem = {
  document_id: string;
  title: string;
  program: string | null;
  embedding_ready: boolean;
  match_reason: string;
};

export type CurriculumSuggestionItem = {
  documentId: string;
  title: string;
  program: string | null;
  embeddingReady: boolean;
  matchReason: string;
};

export type RawCurriculumSuggestionResponse = {
  document_id: string;
  detected_program: string | null;
  selected_program: string;
  detected_course_code: string | null;
  detected_academic_year: string | null;
  detected_lesson_title: string | null;
  preferred_suggestion: RawCurriculumSuggestionItem | null;
  curriculum_suggestions: RawCurriculumSuggestionItem[];
  unavailable_curricula: RawCurriculumSuggestionItem[];
};

export type CurriculumSuggestionResponse = {
  documentId: string;
  detectedProgram: string | null;
  selectedProgram: string;
  detectedCourseCode: string | null;
  detectedAcademicYear: string | null;
  detectedLessonTitle: string | null;
  preferredSuggestion: CurriculumSuggestionItem | null;
  curriculumSuggestions: CurriculumSuggestionItem[];
  unavailableCurricula: CurriculumSuggestionItem[];
};

function mapCurriculumSuggestionItem(
  item: RawCurriculumSuggestionItem,
): CurriculumSuggestionItem {
  return {
    documentId: item.document_id,
    title: item.title,
    program: item.program,
    embeddingReady: item.embedding_ready,
    matchReason: item.match_reason,
  };
}

export function mapCurriculumSuggestionResponse(
  response: RawCurriculumSuggestionResponse,
): CurriculumSuggestionResponse {
  return {
    documentId: response.document_id,
    detectedProgram: response.detected_program,
    selectedProgram: response.selected_program,
    detectedCourseCode: response.detected_course_code,
    detectedAcademicYear: response.detected_academic_year,
    detectedLessonTitle: response.detected_lesson_title,
    preferredSuggestion: response.preferred_suggestion
      ? mapCurriculumSuggestionItem(response.preferred_suggestion)
      : null,
    curriculumSuggestions: response.curriculum_suggestions.map(mapCurriculumSuggestionItem),
    unavailableCurricula: response.unavailable_curricula.map(mapCurriculumSuggestionItem),
  };
}

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
  adjectival_rating?: string;
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
    academicYear: document.academic_year,
    courseCode: document.course_code,
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
    program: response.program,
    academicYear: response.academic_year,
    courseCode: response.course_code,
    structuredSummary: response.structured_summary,
    evaluationReadiness: response.evaluation_readiness,
    errorMessage: response.error_message,
  };
}

// --- Reference library types (admin-only syllabus/curriculum management) ---

export const REFERENCE_SOURCE_TYPES = ['syllabus', 'curriculum'] as const;
export type ReferenceSourceType = (typeof REFERENCE_SOURCE_TYPES)[number];

export type RawReferenceLibraryItem = {
  document_id: string;
  title: string;
  source_type: ReferenceSourceType;
  program: string | null;
  course_code: string | null;
  academic_year: string | null;
  course_title: string | null;
  lesson_title: string | null;
  page_count: number | null;
  uploaded_at: string;
  uploaded_by: string | null;
  processing_status: DocumentProcessingStatus;
  file_exists: boolean;
  chunk_count: number;
  chroma_available: boolean;
  embedding_ready: boolean;
};

export type ReferenceLibraryItem = {
  documentId: string;
  title: string;
  sourceType: ReferenceSourceType;
  program: string | null;
  courseCode: string | null;
  academicYear: string | null;
  courseTitle: string | null;
  lessonTitle: string | null;
  pageCount: number | null;
  uploadedAt: string;
  uploadedBy: string | null;
  processingStatus: DocumentProcessingStatus;
  fileExists: boolean;
  chunkCount: number;
  chromaAvailable: boolean;
  embeddingReady: boolean;
};

export type RawReferenceLibraryResponse = {
  items: RawReferenceLibraryItem[];
  total: number;
};

export type ReferenceLibraryResponse = {
  items: ReferenceLibraryItem[];
  total: number;
};

export type RawReferenceDeleteResponse = {
  document_id: string;
  deleted: boolean;
  details: Record<string, unknown>;
};

export type RawReferenceRebuildResponse = {
  document_id: string;
  rebuilt: boolean;
  chunk_count: number;
  details: Record<string, unknown>;
};

export type ReferenceDeleteResponse = {
  documentId: string;
  deleted: boolean;
  details: Record<string, unknown>;
};

export type ReferenceRebuildResponse = {
  documentId: string;
  rebuilt: boolean;
  chunkCount: number;
  details: Record<string, unknown>;
};

export function mapReferenceLibraryItem(item: RawReferenceLibraryItem): ReferenceLibraryItem {
  return {
    documentId: item.document_id,
    title: item.title,
    sourceType: item.source_type,
    program: item.program,
    courseCode: item.course_code,
    academicYear: item.academic_year,
    courseTitle: item.course_title,
    lessonTitle: item.lesson_title,
    pageCount: item.page_count,
    uploadedAt: item.uploaded_at,
    uploadedBy: item.uploaded_by,
    processingStatus: item.processing_status,
    fileExists: item.file_exists,
    chunkCount: item.chunk_count,
    chromaAvailable: item.chroma_available,
    embeddingReady: item.embedding_ready,
  };
}

export function mapReferenceLibraryResponse(
  response: RawReferenceLibraryResponse,
): ReferenceLibraryResponse {
  return {
    items: response.items.map(mapReferenceLibraryItem),
    total: response.total,
  };
}

export function mapReferenceDeleteResponse(
  response: RawReferenceDeleteResponse,
): ReferenceDeleteResponse {
  return {
    documentId: response.document_id,
    deleted: response.deleted,
    details: response.details,
  };
}

export function mapReferenceRebuildResponse(
  response: RawReferenceRebuildResponse,
): ReferenceRebuildResponse {
  return {
    documentId: response.document_id,
    rebuilt: response.rebuilt,
    chunkCount: response.chunk_count,
    details: response.details,
  };
}
