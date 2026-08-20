export type EvaluationLifecycleStatus =
  | 'SUBMITTED'
  | 'PREPROCESSING'
  | 'EVALUATING'
  | 'SYNTHESIZING'
  | 'COMPLETED'
  | 'FAILED'
  | 'PENDING'
  | 'PROCESSING';

export interface LatestEvaluationItem {
  document_id: string;
  evaluation_id: string;
  status: string;
  submitted_at: string;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface LatestEvaluationsResponse {
  items: LatestEvaluationItem[];
}
