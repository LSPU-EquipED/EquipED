import type {
  ITSOCriterionAssessment,
  MatrixCriterionScoreItem,
  MatrixDomainScoreBlock,
  MatrixListResponse,
  MatrixMetrics,
  MonitoringMatrixRow,
  CoordinatorAlignmentAdvisory,
} from "@equiped/types";

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

interface MasterSynthesisPillarBase {
  weight: number;
  subtotal: number | null;
  status: string;
  summary: string;
  evaluator: EvaluatorAttribution | null;
}

export interface LegacyMasterSynthesisPillar extends MasterSynthesisPillarBase {
  /** Legacy response omits contract; the discriminator is retained when present. */
  contract?: "legacy.v1";
  advisory_outputs?: CoordinatorAlignmentAdvisory | null;
  criteria: MatrixCriterionScoreItem[];
}

export interface ITSOMasterSynthesisPillar extends MasterSynthesisPillarBase {
  contract: "itso_evidence.v1";
  evaluation_id: string;
  criteria: ITSOCriterionAssessment[];
  max_score: 4;
  execution_status: "COMPLETED" | "FAILED";
  scoring_complete: boolean;
  scored_count: number;
  unscored_count: number;
  issue_count: number;
  uncertainty_count: number;
  adjectival_rating: null;
}

export type MasterSynthesisPillar =
  LegacyMasterSynthesisPillar | ITSOMasterSynthesisPillar;

export interface MasterSynthesisDetailResponse {
  document_id: string;
  document_title: string | null;
  course_code: string | null;
  course_title?: string | null;
  academic_year?: string | null;
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
