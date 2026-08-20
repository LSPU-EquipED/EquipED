import type { ClientDocument } from '@/shared/types/documents';

export interface HomeEvaluationItem {
  evaluation_id: string;
  document_id: string;
  document_title?: string;
  syllabus_id: string;
  curriculum_id: string;
  status: string;
  error_message?: string;
  submitted_by?: string;
  submitted_at: string;
  completed_at?: string;
}

export interface HomeEvaluationsResponse {
  items: HomeEvaluationItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AttentionItem {
  id: string;
  type: 'document_failed' | 'evaluation_failed';
  title: string;
  detail: string;
  timestamp: string;
  targetUrl: string;
  actionLabel: string;
}

export interface FacultyHomeData {
  recentIssues: AttentionItem[];
  activeEvaluation: HomeEvaluationItem | null;
  latestReadyDocument: ClientDocument | null;
  hasEvaluations: boolean;
  recentSlms: ClientDocument[];
  recentEvaluations: HomeEvaluationItem[];
}
