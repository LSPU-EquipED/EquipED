export type EvaluationStatus = 
  | 'SUBMITTED'
  | 'PREPROCESSING'
  | 'EMBEDDING'
  | 'EVALUATING'
  | 'SYNTHESIZING'
  | 'COMPLETED'
  | 'FAILED';

export interface EvaluationResponse {
  evaluation_id: string;
  document_id: string;
  syllabus_id: string;
  curriculum_id: string;
  status: EvaluationStatus;
  error_message?: string;
  submitted_by?: string;
  submitted_at: string;
  completed_at?: string;
}

export interface EvaluationStatusResponse {
  evaluation_id: string;
  status: EvaluationStatus;
  error_message?: string;
  completed_at?: string;
}
