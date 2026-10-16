export interface HomeEvaluationItem {
  evaluation_id: string;
  document_id: string;
  document_title?: string;
  syllabus_id: string;
  curriculum_id: string;
  status: string;
  target_agent?: string;
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

export interface FacultyHomeData {
  activeEvaluation: HomeEvaluationItem | null;
}

export interface FacultyWorkspaceAccess {
  evaluatorPermissions?: readonly string[] | null;
  userRole?: string;
}
