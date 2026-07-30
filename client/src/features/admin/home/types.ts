import type { DomainScoreBlock } from '@/shared/types/documents';

export interface SystemSummaryResponse {
  total_documents: number;
  total_faculty: number;
  active_evaluations: number;
  failed_evaluations: number;
}

export interface MonitoringMatrixRow {
  matrix_id: string;
  document_id: string;
  evaluation_id: string | null;
  faculty_name: string | null;
  program: string | null;
  document_title: string | null;
  evaluation_status: string;
  synthesized_score: number | null;
  domain_scores: Record<string, DomainScoreBlock> | null;
  flag_count: number;
  feedback_status: string;
  last_updated: string;
}

export interface MatrixListResponse {
  items: MonitoringMatrixRow[];
  total: number;
  page: number;
  page_size: number;
}
