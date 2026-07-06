import type { DomainScoreBlock, ReferenceSourceType } from '../../shared/types/documents';

export interface PromptVersionItem {
  version_id: string;
  version_number: number;
  prompt_text: string;
  is_active: boolean;
  updated_by: string | null;
  motivation: string | null;
  created_at: string;
}

export interface PromptVersionListResponse {
  agent_id: string;
  versions: PromptVersionItem[];
  total: number;
}

export interface PromptCreateBody {
  prompt_text: string;
  motivation?: string;
}

export interface PreferenceLogItem {
  log_id: string;
  evaluation_id: string;
  user_id: string;
  action: string;
  edited_json: Record<string, unknown> | null;
  notes: string | null;
  created_at: string;
}

export interface PreferenceLogListResponse {
  items: PreferenceLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUserResponse {
  user_id: string;
  name: string;
  email: string;
  role: 'admin' | 'faculty';
  is_active: boolean;
  created_at: string;
}

export interface AdminUserListResponse {
  items: AdminUserResponse[];
  total: number;
}

export interface AdminUserCreateBody {
  name: string;
  email: string;
  password: string;
  role: 'admin' | 'faculty';
}

export interface AdminUserUpdateBody {
  name?: string;
  email?: string;
  is_active?: boolean;
}

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

export interface AdminUploadInput {
  file: File;
  sourceType: ReferenceSourceType;
  title: string;
}
