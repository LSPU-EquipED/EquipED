export interface HistoryEvaluationItem {
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

export interface HistoryListResponse {
  items: HistoryEvaluationItem[];
  total: number;
  page: number;
  page_size: number;
}
