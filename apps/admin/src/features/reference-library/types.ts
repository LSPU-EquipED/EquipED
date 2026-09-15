import type {
  DocumentProcessingStatus,
  PolicySourceType,
  ReferenceSourceType,
} from '@/shared/types/documents';

export type RawPolicyLibraryItem = {
  document_id: string;
  title: string;
  source_type: string;
  policy_area: string | null;
  program: string | null;
  course_code: string | null;
  academic_year: string | null;
  page_count: number | null;
  uploaded_at: string;
  uploaded_by: string | null;
  processing_status: DocumentProcessingStatus;
  file_exists: boolean;
  chunk_count: number;
  chroma_available: boolean;
  embedding_ready: boolean;
};

export type PolicyLibraryItem = {
  documentId: string;
  title: string;
  sourceType: PolicySourceType;
  policyArea: string | null;
  program: string | null;
  courseCode: string | null;
  academicYear: string | null;
  pageCount: number | null;
  uploadedAt: string;
  uploadedBy: string | null;
  processingStatus: DocumentProcessingStatus;
  fileExists: boolean;
  chunkCount: number;
  chromaAvailable: boolean;
  embeddingReady: boolean;
};

export type RawPolicyLibraryResponse = {
  items: RawPolicyLibraryItem[];
  total: number;
};

export type PolicyLibraryResponse = {
  items: PolicyLibraryItem[];
  total: number;
};

export type RawPolicyDeleteResponse = {
  document_id: string;
  deleted: boolean;
  details: Record<string, unknown>;
};

export type RawPolicyRebuildResponse = {
  document_id: string;
  rebuilt: boolean;
  chunk_count: number;
  details: Record<string, unknown>;
};

export type PolicyDeleteResponse = {
  documentId: string;
  deleted: boolean;
  details: Record<string, unknown>;
};

export type PolicyRebuildResponse = {
  documentId: string;
  rebuilt: boolean;
  chunkCount: number;
  details: Record<string, unknown>;
};

export function mapPolicyLibraryItem(item: RawPolicyLibraryItem): PolicyLibraryItem {
  return {
    documentId: item.document_id,
    title: item.title,
    sourceType: 'policy',
    policyArea: item.policy_area,
    program: item.program,
    courseCode: item.course_code,
    academicYear: item.academic_year,
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

export function mapPolicyLibraryResponse(
  response: RawPolicyLibraryResponse,
): PolicyLibraryResponse {
  return {
    items: response.items.map(mapPolicyLibraryItem),
    total: response.total,
  };
}

export function mapPolicyDeleteResponse(response: RawPolicyDeleteResponse): PolicyDeleteResponse {
  return {
    documentId: response.document_id,
    deleted: response.deleted,
    details: response.details,
  };
}

export function mapPolicyRebuildResponse(
  response: RawPolicyRebuildResponse,
): PolicyRebuildResponse {
  return {
    documentId: response.document_id,
    rebuilt: response.rebuilt,
    chunkCount: response.chunk_count,
    details: response.details,
  };
}

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
