import type {
  MatrixCriterionScoreItem,
  MatrixDomainScoreBlock,
  MatrixListResponse,
  MatrixMetrics,
  MonitoringMatrixRow,
} from '@equiped/types';

export type {
  MatrixCriterionScoreItem,
  MatrixDomainScoreBlock,
  MatrixListResponse,
  MatrixMetrics,
  MonitoringMatrixRow,
};

export interface EvaluatorAttribution {
  user_id: string | null;
  name: string;
  email: string | null;
  department: string | null;
}

export interface EvaluationFlagItem {
  flag_id: string;
  evaluation_id: string;
  agent_id: string;
  criterion_id?: string | null;
  criterion_text?: string | null;
  score?: number | null;
  justification?: string | null;
  chunk_id?: string | null;
  flag_type?: string | null;
  severity?: string | null;
  message?: string | null;
}

export interface MasterSynthesisPillar {
  weight: number;
  subtotal: number | null;
  status: string;
  criteria: MatrixCriterionScoreItem[];
  summary: string;
  evaluator: EvaluatorAttribution | null;
}

export interface MasterSynthesisDetailResponse {
  document_id: string;
  document_title: string | null;
  course_code: string | null;
  program: string | null;
  author: EvaluatorAttribution;
  /** Weighted composite percentage (0–100); individual pillar subtotals use 0–4. */
  synthesized_score: number | null;
  adjectival_rating: string | null;
  evaluation_status: string;
  last_updated: string | null;
  pillars: Record<string, MasterSynthesisPillar>;
  flags: EvaluationFlagItem[];
  can_certify: boolean;
}
