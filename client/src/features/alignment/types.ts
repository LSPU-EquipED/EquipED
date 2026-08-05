export type AlignmentProcessingStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
export type AlignmentLevel = 'MEETS' | 'PARTIALLY_MEETS' | 'DOES_NOT_MEET' | 'UNAVAILABLE';

export type TopicEvidence = {
  topic_id: string;
  topic: string;
  slm_chunk_id: string;
  slm_page_number?: number | null;
  slm_evidence: string;
  status: 'ALIGNED' | 'NOT_ALIGNED';
  rationale: string;
};

export type ContentMatch = TopicEvidence & {
  chunk_id: string;
  content_ref: string;
  content_text: string;
  page_number?: number | null;
};

export type AlignmentArtifact = {
  status: AlignmentLevel;
  statement: string;
  syllabus_document_id?: string | null;
  total_topics: number;
  aligned_topics: number;
  content_matches: ContentMatch[];
  unmatched_topics: TopicEvidence[];
  advisory_only: true;
};

export type AlignmentRun = {
  alignment_id: string;
  slm_document_id: string;
  slm_title?: string | null;
  syllabus_document_id: string;
  syllabus_title?: string | null;
  requested_by: string;
  status: AlignmentProcessingStatus;
  alignment_level?: AlignmentLevel | null;
  justification?: string | null;
  alignment_artifact?: AlignmentArtifact | null;
  model_name?: string | null;
  provenance?: Record<string, unknown> | null;
  error_message?: string | null;
  advisory_only: true;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at: string;
};

export type AlignmentSlmItem = {
  document_id: string;
  title: string;
  course_title?: string | null;
  lesson_title?: string | null;
  program?: string | null;
  course_code?: string | null;
  processing_status: string;
  uploaded_at: string;
  evaluation_available: boolean;
  current_result?: AlignmentRun | null;
};

export type AlignmentSlmListResponse = {
  items: AlignmentSlmItem[];
  total: number;
  page: number;
  page_size: number;
};

export type SyllabusReferenceOption = {
  document_id: string;
  title: string;
  program?: string | null;
  course_code?: string | null;
  academic_year?: string | null;
  content_count: number;
};

export type SyllabusReferenceOptionsResponse = {
  items: SyllabusReferenceOption[];
  total: number;
};
